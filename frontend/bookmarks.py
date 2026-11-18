"""Local bookmark identities only; article content stays with the provider."""
import hashlib
import json
import re
from .models import NewsItem, safe_url

MAX_BOOKMARKS = 1000


def bookmark_key(item: NewsItem) -> str:
    # Real canonical links survive title edits; mock/URL-less rows need content
    # as well as ID, since different imports can reuse the same numeric IDs.
    identity = (["url", item.url] if not item.is_mock and safe_url(item.url)
                else ["row", item.is_mock, item.id, item.title, item.location])
    payload = json.dumps(identity, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_bookmarks(value: object) -> set[str]:
    if not isinstance(value, str) or len(value) > 100_000:
        return set()
    try:
        entries = json.loads(value)
    except (ValueError, TypeError):
        return set()
    if not isinstance(entries, list):
        return set()
    return {entry for entry in entries[:MAX_BOOKMARKS]
            if isinstance(entry, str) and re.fullmatch(r"[a-f0-9]{64}", entry)}


def write_bookmarks(keys: set[str]) -> str:
    return json.dumps(sorted(keys), separators=(",", ":"))
