import calendar
import hashlib
import html
import logging
import re
from datetime import datetime, timedelta, timezone

import feedparser
import httpx
import trafilatura

from ..config import get_settings
from ..db import SessionLocal
from ..models import Item, Source
from .fetch import FetchError, client, fetch_page, robots_allows
from .urls import canonicalize

log = logging.getLogger("app.ingest")

MIN_ARTICLE_CHARS = 300
DUP_WINDOW = timedelta(hours=72)
DUP_TITLE_JACCARD = 0.75

_TAG_RE = re.compile(r"<[^>]+>")
_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "at", "by", "with", "as"}


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub(" ", text))).strip()


def content_hash(text: str) -> str:
    norm = re.sub(r"\s+", " ", text.lower()).strip()
    return hashlib.sha256(norm.encode()).hexdigest()


def title_tokens(title: str) -> set[str]:
    return {w for w in _WORD_RE.findall(title.lower()) if w not in _STOPWORDS}


def titles_similar(a: str, b: str) -> bool:
    ta, tb = title_tokens(a), title_tokens(b)
    if len(ta) < 4 or len(tb) < 4:
        return False
    return len(ta & tb) / len(ta | tb) >= DUP_TITLE_JACCARD


def _entry_datetime(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc)
    return None


# ---------------------------------------------------------------- feeds


def fetch_feed(url: str, etag: str | None = None, modified: str | None = None):
    """Return (parsed_feed | None if unchanged, etag, last_modified)."""
    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    if modified:
        headers["If-Modified-Since"] = modified
    if not robots_allows(url):
        raise FetchError("blocked by robots.txt")
    try:
        with client() as c:
            r = c.get(url, headers=headers)
    except httpx.HTTPError as e:
        raise FetchError(f"fetch failed: {e.__class__.__name__}") from e
    if r.status_code == 304:
        return None, etag, modified
    if r.status_code >= 400:
        raise FetchError(f"HTTP {r.status_code}")
    parsed = feedparser.parse(r.content)
    if not parsed.entries and not parsed.feed.get("title"):
        raise FetchError("not a valid RSS or Atom feed")
    return parsed, r.headers.get("etag"), r.headers.get("last-modified")


def preview_feed(url: str) -> dict:
    parsed, _, _ = fetch_feed(url)
    return {
        "title": strip_html(parsed.feed.get("title")) or url,
        "entries": [
            {
                "title": strip_html(e.get("title")) or "(untitled)",
                "url": e.get("link"),
                "published_at": (_entry_datetime(e).isoformat() if _entry_datetime(e) else None),
            }
            for e in parsed.entries[:3]
        ],
    }


def poll_source(source_id: int) -> int:
    """Fetch a feed and create items for new entries. Returns number of new items."""
    from ..jobs import enqueue

    new_ids: list[int] = []
    with SessionLocal() as db:
        source = db.get(Source, source_id)
        if source is None or source.type != "rss":
            return 0
        try:
            parsed, etag, modified = fetch_feed(source.url, source.etag, source.last_modified)
        except FetchError as e:
            source.last_error = str(e)
            source.last_polled_at = datetime.now(timezone.utc)
            db.commit()
            log.warning("poll failed", extra={"source_id": source_id, "error": str(e)})
            return 0

        source.last_polled_at = datetime.now(timezone.utc)
        source.last_error = None
        if parsed is None:
            db.commit()
            return 0
        source.etag, source.last_modified = etag, modified
        if not source.title:
            source.title = strip_html(parsed.feed.get("title")) or source.url

        for entry in parsed.entries:
            link = entry.get("link")
            if not link:
                continue
            canon = canonicalize(link)
            if db.query(Item.id).filter(Item.canonical_url == canon).first():
                continue
            summary = entry.get("summary") or ""
            if entry.get("content"):
                summary = max((c.get("value", "") for c in entry.content), key=len) or summary
            item = Item(
                source_id=source.id,
                canonical_url=canon,
                title=strip_html(entry.get("title")) or "(untitled)",
                author=entry.get("author"),
                published_at=_entry_datetime(entry),
                feed_summary=strip_html(summary)[:20000] or None,
                status="new",
            )
            db.add(item)
            db.flush()
            new_ids.append(item.id)
        db.commit()

    for item_id in new_ids:
        enqueue(process_item, item_id)
    log.info("polled", extra={"source_id": source_id, "new_items": len(new_ids)})
    return len(new_ids)


def create_url_item(db, source: Source) -> Item:
    item = Item(source_id=source.id, canonical_url=canonicalize(source.url), title=source.title or source.url,
                status="new")
    db.add(item)
    db.flush()
    return item


# ---------------------------------------------------------------- items


def _find_duplicate(db, item: Item) -> int | None:
    if item.content_hash:
        hit = (
            db.query(Item.id)
            .filter(Item.content_hash == item.content_hash, Item.id != item.id, Item.duplicate_of.is_(None))
            .order_by(Item.id)
            .first()
        )
        if hit:
            return hit[0]
    since = datetime.now(timezone.utc) - DUP_WINDOW
    recent = (
        db.query(Item.id, Item.title)
        .filter(Item.id != item.id, Item.source_id != item.source_id, Item.duplicate_of.is_(None),
                Item.created_at >= since)
        .order_by(Item.id)
        .all()
    )
    for other_id, other_title in recent:
        if titles_similar(item.title, other_title or ""):
            return other_id
    return None


def extract_article(url: str) -> tuple[str | None, str | None, str | None]:
    """Return (text, title, error)."""
    try:
        page = fetch_page(url)
    except FetchError as e:
        return None, None, str(e)
    text = trafilatura.extract(page, include_comments=False, include_tables=False, favor_precision=True)
    meta = trafilatura.extract_metadata(page)
    title = meta.title if meta and meta.title else None
    return text, title, None


def process_item(item_id: int) -> None:
    """Fetch full text, deduplicate, then run fact extraction."""
    from .pipeline import extract_facts_for_item

    s = get_settings()
    with SessionLocal() as db:
        item = db.get(Item, item_id)
        if item is None:
            return
        text, title, fetch_err = extract_article(item.canonical_url)
        if title and (not item.title or item.title in ("(untitled)", item.source.url)):
            item.title = title.strip()
        if not text or len(text) < MIN_ARTICLE_CHARS:
            text = item.feed_summary if item.feed_summary and len(item.feed_summary) > len(text or "") else text
        if not text:
            item.status = "extract_failed"
            item.error = fetch_err or "no article text found"
            db.commit()
            return
        item.raw_text = text[: s.article_max_chars]
        item.content_hash = content_hash(item.raw_text)
        dup = _find_duplicate(db, item)
        if dup:
            item.duplicate_of = dup
            db.commit()
            log.info("duplicate item", extra={"item_id": item.id, "duplicate_of": dup})
            return
        db.commit()

    extract_facts_for_item(item_id)
