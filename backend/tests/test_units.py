from app.services.charcount import count_hashtags, weighted_length
from app.services.ingest import titles_similar
from app.services.pipeline import angle_rubric_text, load_prompt, validate_claims
from app.services.urls import canonicalize


def test_plain_text_counts_one_per_char():
    assert weighted_length("hello world") == 11


def test_urls_count_as_23():
    assert weighted_length("see https://example.com/a/very/long/path?with=query") == 4 + 23
    assert weighted_length("a http://x.co b") == 2 + 23 + 2


def test_emoji_and_cjk_count_double():
    assert weighted_length("\U0001F600") == 2
    assert weighted_length("日本") == 4


def test_hashtags_ignore_urls():
    assert count_hashtags("#one two #three https://x.com/#frag") == 2


def test_canonicalize_strips_tracking_and_fragment():
    assert canonicalize("https://WWW.Example.com/story/?utm_source=x&id=5&at_medium=RSS#top") == "https://example.com/story?id=5"


def test_validate_claims_keeps_only_verbatim_quotes():
    article = "The council voted “7–4”   on Tuesday."
    claims = [{"id": "c1", "text": "t", "quote": 'voted "7-4" on Tuesday'},
              {"id": "c2", "text": "t", "quote": "voted unanimously"}]
    assert [c["id"] for c in validate_claims(claims, article)] == ["c1"]


def test_titles_similar():
    assert titles_similar("Council raises Riverton bus fare to $2.50", "Riverton council raises bus fare to $2.50")
    assert not titles_similar("Council raises Riverton bus fare", "Library hours extended for winter season")


def test_prompts_and_rubrics_load():
    for name in ("extract", "generate", "verify"):
        assert load_prompt(name).version.startswith(name)
    for angle in ("left", "center", "right"):
        assert "Angle:" in angle_rubric_text(angle)
