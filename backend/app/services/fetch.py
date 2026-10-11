import time
import urllib.robotparser
from urllib.parse import urlsplit

import httpx

from ..config import get_settings

_robots_cache: dict[str, tuple[float, urllib.robotparser.RobotFileParser | None]] = {}
_ROBOTS_TTL_S = 3600


class FetchError(Exception):
    pass


def client() -> httpx.Client:
    s = get_settings()
    return httpx.Client(
        headers={"User-Agent": s.user_agent, "Accept-Language": "en"},
        timeout=s.fetch_timeout_s,
        follow_redirects=True,
    )


def robots_allows(url: str) -> bool:
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    now = time.time()
    cached = _robots_cache.get(origin)
    if cached is None or now - cached[0] > _ROBOTS_TTL_S:
        parser: urllib.robotparser.RobotFileParser | None = None
        try:
            with client() as c:
                r = c.get(origin + "/robots.txt")
            if r.status_code == 200:
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(r.text.splitlines())
        except httpx.HTTPError:
            parser = None  # unreachable robots.txt: treat as allowed
        _robots_cache[origin] = (now, parser)
        cached = _robots_cache[origin]
    parser = cached[1]
    return True if parser is None else parser.can_fetch(get_settings().user_agent, url)


def fetch_page(url: str) -> str:
    if not robots_allows(url):
        raise FetchError("blocked by robots.txt")
    try:
        with client() as c:
            r = c.get(url)
    except httpx.HTTPError as e:
        raise FetchError(f"fetch failed: {e.__class__.__name__}") from e
    if r.status_code in (401, 402, 403):
        raise FetchError(f"access denied (HTTP {r.status_code}), possibly a paywall")
    if r.status_code >= 400:
        raise FetchError(f"HTTP {r.status_code}")
    ctype = r.headers.get("content-type", "")
    if "html" not in ctype and "xml" not in ctype and ctype:
        raise FetchError(f"not an HTML page ({ctype.split(';')[0]})")
    return r.text
