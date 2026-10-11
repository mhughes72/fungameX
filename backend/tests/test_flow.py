from app.services.charcount import weighted_length


def test_requires_login(client):
    assert client.get("/api/items").status_code == 401
    assert client.post("/api/auth/login", json={"password": "nope"}).status_code == 401


def test_end_to_end(authed, calls):
    c = authed

    # Add a feed: polling and extraction run inline in sync mode.
    r = c.post("/api/sources", json={"type": "rss", "url": "https://news.example.com/feed.xml"})
    assert r.status_code == 201, r.text
    source = r.json()
    assert source["title"] == "Riverton News"
    assert c.post("/api/sources", json={"type": "rss", "url": "https://news.example.com/feed.xml"}).status_code == 409

    items = c.get("/api/items").json()
    assert len(items) == 2
    fare = next(i for i in items if "fare" in i["title"])
    assert fare["status"] == "extracted"
    assert fare["canonical_url"] == "https://news.example.com/fare"

    detail = c.get(f"/api/items/{fare['id']}").json()
    # c4's quote isn't in the article, so it was dropped.
    assert [cl["id"] for cl in detail["facts"]["claims"]] == ["c1", "c2", "c3"]

    # Polling again doesn't create duplicates.
    c.post(f"/api/sources/{source['id']}/refresh")
    assert len(c.get("/api/items").json()) == 2

    # Generate.
    r = c.post(f"/api/items/{fare['id']}/generate", json={"angle": "left", "tone": "punchy"})
    assert r.status_code == 200, r.text
    gen = r.json()
    assert gen["angle"] == "left" and len(gen["posts"]) == 3
    for p in gen["posts"]:
        assert p["text"].endswith("https://news.example.com/fare")
        assert p["char_count"] == weighted_length(p["text"]) <= 280
        assert "zz" not in p["claim_ids"]
    statuses = [p["verification"]["status"] for p in gen["posts"]]
    assert statuses == ["pass", "pass", "fail"]  # the planted 99% claim is flagged
    assert gen["posts"][2]["verification"]["issues"][0]["problem"] == "unsupported"

    # Edit, re-verify, use.
    post = gen["posts"][0]
    r = c.patch(f"/api/posts/{post['id']}", json={"text": "Edited text https://news.example.com/fare"})
    assert r.json()["status"] == "edited" and r.json()["verification"]["stale"] is True
    r = c.post(f"/api/posts/{post['id']}/verify")
    assert r.json()["verification"]["status"] == "pass"
    r = c.post(f"/api/posts/{post['id']}/use")
    assert r.json()["status"] == "used" and r.json()["used_at"]

    # Regenerate one candidate.
    r = c.post(f"/api/posts/{gen['posts'][2]['id']}/regenerate", json={"instruction": "mention the vote"})
    assert r.status_code == 200, r.text
    assert r.json()["generation_id"] == gen["id"]

    # History.
    hist = c.get("/api/posts", params={"angle": "left", "status": "used"}).json()
    assert [h["id"] for h in hist] == [post["id"]]
    assert c.get("/api/posts", params={"angle": "right"}).json() == []


def test_duplicate_from_second_source(authed, calls):
    c = authed
    c.post("/api/sources", json={"type": "rss", "url": "https://news.example.com/feed.xml"})
    before = len(c.get("/api/items").json())
    # Same article text arriving as a one-off URL from another source is attached as a duplicate.
    r = c.post("/api/sources", json={"type": "url", "url": "https://other.example.org/riverton-fares"})
    assert r.status_code == 201, r.text
    assert len(c.get("/api/items").json()) == before


def test_budget_cap_blocks_generation(authed, calls):
    c = authed
    c.post("/api/sources", json={"type": "rss", "url": "https://news.example.com/feed.xml"})
    item = c.get("/api/items", params={"status": "extracted"}).json()[0]
    c.put("/api/settings", json={"monthly_budget_usd": 0.001})
    r = c.post(f"/api/items/{item['id']}/generate", json={})
    assert r.status_code == 429
    c.put("/api/settings", json={"monthly_budget_usd": 0})


def test_settings_defaults_and_update(authed):
    s = authed.get("/api/settings").json()
    assert s["max_chars"] == 280 and s["include_link"] is True
    s = authed.put("/api/settings", json={"angle": "right", "hashtags": 1}).json()
    assert s["angle"] == "right" and s["hashtags"] == 1
    authed.put("/api/settings", json={"angle": "center", "hashtags": 0})
