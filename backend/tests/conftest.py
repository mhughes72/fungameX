import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="xpg-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["JOBS_MODE_OVERRIDE"] = "sync"
os.environ["APP_PASSWORD"] = "test-pass"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["REDIS_URL"] = ""
os.environ["OPENAI_API_KEY"] = "sk-test-not-real"

import feedparser  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import ingest, llm, pipeline  # noqa: E402

ARTICLE = (
    "Riverton city council voted 7-4 on Tuesday to raise the standard bus fare from $2.00 to $2.50. "
    "Officials said the increase is meant to close a $40 million transit budget gap. "
    "The council also expanded the low-income discount program to 15,000 additional riders. "
    "Council member Dana Ortiz said the vote was \"a hard but necessary step.\" "
    "The new fare takes effect on March 1. " * 2
)

FEED_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Riverton News</title>
<item><title>Council raises Riverton bus fare to $2.50</title><link>https://news.example.com/fare?utm_source=x</link>
<description>Council voted 7-4.</description><pubDate>Tue, 06 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>Library hours extended for winter season</title><link>https://news.example.com/library</link>
<description>Libraries open later.</description></item>
</channel></rss>"""


def fake_fetch_feed(url, etag=None, modified=None):
    return feedparser.parse(FEED_XML), "etag-1", None


def fake_extract_article(url):
    if "library" in url:
        return ("The city library will stay open until 9 pm on weekdays during winter, the library board "
                "announced, citing demand from students and shift workers. " * 3), None, None
    return ARTICLE, None, None


class Calls:
    def __init__(self):
        self.steps = []


@pytest.fixture
def calls(monkeypatch):
    c = Calls()

    def fake_call_structured(role, system, user, schema, step):
        c.steps.append(step)
        if schema is llm.ExtractResult:
            return llm.ExtractResult(
                summary="Riverton raised its bus fare to $2.50 to close a $40M gap and expanded discounts.",
                claims=[
                    llm.Claim(id="c1", text="Council voted 7-4 to raise the fare from $2.00 to $2.50.",
                              quote="voted 7-4 on Tuesday to raise the standard bus fare from $2.00 to $2.50"),
                    llm.Claim(id="c2", text="The increase aims to close a $40 million gap.",
                              quote="close a $40 million transit budget gap"),
                    llm.Claim(id="c3", text="Discounts expanded to 15,000 riders.",
                              quote="expanded the low-income discount program to 15,000 additional riders"),
                    llm.Claim(id="c4", text="Fabricated claim.", quote="this text is not in the article"),
                ],
                topic_tags=["transit"],
            ), 0.01, "fake-fast"
        if schema is llm.GenerateResult:
            n = 1 if '"candidates_requested": 1' in user else 3
            texts = [
                "Riverton's 7-4 vote makes the bus 25% pricier. Riders didn't create the $40M gap.",
                "A $40M transit hole and the fix is $2.50 fares? 15,000 more get discounts, but still.",
                "Fare hike passed 7-4. Fully 99% of riders oppose it.",  # planted unsupported fact
            ][:n]
            return llm.GenerateResult(candidates=[
                llm.Candidate(text=t, claim_ids=["c1", "c2", "zz"], framing_note="test") for t in texts
            ]), 0.05, "fake-writer"
        if schema is llm.VerifyResult:
            if "99%" in user:
                return llm.VerifyResult(supported=False, issues=[
                    llm.Issue(span="Fully 99% of riders oppose it", problem="unsupported",
                              explanation="No claim mentions rider opinion.")]), 0.001, "fake-fast"
            return llm.VerifyResult(supported=True, issues=[]), 0.001, "fake-fast"
        raise AssertionError(schema)

    monkeypatch.setattr(pipeline, "call_structured", fake_call_structured)
    monkeypatch.setattr(pipeline, "moderate", lambda text: (False, []))
    monkeypatch.setattr(ingest, "fetch_feed", fake_fetch_feed)
    monkeypatch.setattr(ingest, "extract_article", fake_extract_article)
    return c


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def authed(client):
    r = client.post("/api/auth/login", json={"password": "test-pass"})
    assert r.status_code == 200
    return client
