"""X (Twitter) weighted character counting.

Follows the twitter-text v3 rules closely enough for drafting: every URL counts
as 23, code points in the common Latin/punctuation ranges count 1, everything
else (CJK, emoji, ...) counts 2. Keep in sync with frontend/lib/charcount.ts.
"""
import re
import unicodedata

URL_WEIGHT = 23
MAX_WEIGHT = 280

URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
HASHTAG_RE = re.compile(r"(?<![\w#])#\w+", re.UNICODE)

_LIGHT_RANGES = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))


def _weight(ch: str) -> int:
    cp = ord(ch)
    for lo, hi in _LIGHT_RANGES:
        if lo <= cp <= hi:
            return 1
    return 2


def weighted_length(text: str) -> int:
    text = unicodedata.normalize("NFC", text)
    total = 0
    pos = 0
    for m in URL_RE.finditer(text):
        total += sum(_weight(c) for c in text[pos:m.start()])
        total += URL_WEIGHT
        pos = m.end()
    total += sum(_weight(c) for c in text[pos:])
    return total


def count_hashtags(text: str) -> int:
    return len(HASHTAG_RE.findall(URL_RE.sub(" ", text)))
