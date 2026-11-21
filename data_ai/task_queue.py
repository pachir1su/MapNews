"""A crash-safe, derived work queue for optional Gemini analysis.

The crawler archive remains canonical. The queue carries only one article
revision (id + content_hash) per row, is rebuilt from the archive on each
run, and never treats its own 'completed' flag as a durable AI result.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile

QUEUE_VERSION = 1
MAX_QUEUE_BYTES = 32 * 1024 * 1024
MAX_ARTICLES = 10000
MAX_ATTEMPTS = 5
MAX_BACKOFF_SECONDS = 3600
STATUSES = frozenset({"pending", "retry_wait", "failed", "completed"})


def now_utc():
    return datetime.now(timezone.utc)


def _parse_time(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def read_queue(path):
    """Reject a corrupt queue rather than deleting retry history."""
    path = Path(path)
    if not path.exists():
        return []
    with path.open("rb") as stream:
        raw = stream.read(MAX_QUEUE_BYTES + 1)
    if len(raw) > MAX_QUEUE_BYTES:
        raise ValueError("Gemini 대기열 JSON이 32 MiB를 초과했습니다.")
    payload = json.loads(raw.decode("utf-8-sig"))
    if (not isinstance(payload, dict)
            or payload.get("version") != QUEUE_VERSION
            or not isinstance(payload.get("articles"), list)
            or len(payload["articles"]) > MAX_ARTICLES):
        raise ValueError("Gemini 대기열 스키마/버전/건수가 올바르지 않습니다.")
    unique = set()
    checked = []
    for row in payload["articles"]:
        if not isinstance(row, dict):
            raise ValueError("Gemini 대기열에 JSON 객체가 아닌 행이 있습니다.")
        key = (row.get("id"), row.get("content_hash"))
        if (not all(isinstance(x, str) and 0 < len(x) <= 256 for x in key)
                or key in unique or row.get("status") not in STATUSES
                or type(row.get("attempts")) is not int
                or not 0 <= row["attempts"] <= MAX_ATTEMPTS):
            raise ValueError("Gemini 대기열 중복/ID/상태/시도 횟수 오류")
        retry_at = row.get("retry_at")
        if retry_at and _parse_time(retry_at) is None:
            raise ValueError("Gemini 대기열 재시도 날짜가 올바르지 않습니다.")
        unique.add(key)
        checked.append(row)
    return checked


def rebuild_queue(articles, results, previous=()):
    """Synchronize the queue with current source revisions and valid results."""
    completed = {
        (str(r.get("id")), r.get("content_hash"))
        for r in results if isinstance(r, dict)
        and r.get("id") is not None and isinstance(r.get("content_hash"), str)
    }
    old = {
        (r["id"], r["content_hash"]): r
        for r in previous if isinstance(r, dict)
        and isinstance(r.get("id"), str)
        and isinstance(r.get("content_hash"), str)
    }
    if len(articles) > MAX_ARTICLES:
        raise ValueError("Gemini 대기열은 최대 10,000건까지 지원합니다.")
    rows = []
    seen = set()
    for article in articles:
        key = (str(article["id"]), str(article["content_hash"]))
        if key in seen:
            continue
        seen.add(key)
        prev = old.get(key, {})
        attempts = min(MAX_ATTEMPTS, max(0, int(prev.get("attempts", 0))))
        if key in completed:
            status, attempts, retry_at = "completed", 0, None
        elif attempts >= MAX_ATTEMPTS:
            status, retry_at = "failed", None
        elif prev.get("retry_at"):
            status, retry_at = "retry_wait", prev["retry_at"]
        else:
            status, retry_at = "pending", None
        rows.append({
            "id": key[0], "content_hash": key[1],
            "title": str(article.get("title") or "")[:1000],
            "url": str(article.get("url") or "")[:4096],
            "datetime": str(article.get("datetime") or "")[:80],
            "source": str(article.get("source") or "real")[:80],
            "body": str(article.get("body") or "")[:1500],
            "status": status, "attempts": attempts, "retry_at": retry_at,
            "last_error": str(prev.get("last_error") or "")[:120] if key not in completed else "",
        })
    rows.sort(key=lambda r: (r["datetime"], r["id"]), reverse=True)
    return rows


def select_ready(queue, limit, *, now=None):
    """Deterministic, newest-first, bounded selection; delayed jobs do not block."""
    if not isinstance(limit, int) or not 0 <= limit <= MAX_ARTICLES:
        raise ValueError("Gemini 처리 기사 수가 유효하지 않습니다.")
    now = now or now_utc()
    ready = [
        row for row in queue if row["status"] in {"pending", "retry_wait"}
        and (_parse_time(row.get("retry_at")) is None
             or _parse_time(row["retry_at"]) <= now)
    ]
    return ready[:limit]


def mark_batch(queue, *, completed=(), failed=(), reason="", now=None):
    now = now or now_utc()
    done_ids, failed_ids = set(completed), set(failed)
    for row in queue:
        if row["id"] in done_ids:
            row.update(status="completed", attempts=0,
                       retry_at=None, last_error="")
        elif row["id"] in failed_ids:
            attempts = min(MAX_ATTEMPTS, row["attempts"] + 1)
            cooldown = min(60 * (2 ** (attempts - 1)), MAX_BACKOFF_SECONDS)
            row.update(
                status="failed" if attempts == MAX_ATTEMPTS else "retry_wait",
                attempts=attempts,
                retry_at=None if attempts == MAX_ATTEMPTS
                else (now + timedelta(seconds=cooldown)).isoformat(),
                last_error=str(reason or "API 응답 누락/오류")[:120],
            )
    return queue


def write_queue(path, queue):
    """Atomic JSON update, fsync, unique temp file and cleanup on failure."""
    path = Path(path)
    if len(queue) > MAX_ARTICLES:
        raise ValueError("Gemini 대기열이 최대 건수를 초과했습니다.")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": QUEUE_VERSION,
        "updated_at": now_utc().isoformat(),
        "articles": queue,
    }
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                         indent=2).encode("utf-8")
    if len(encoded) > MAX_QUEUE_BYTES:
        raise ValueError("Gemini 대기열 기록이 32 MiB를 초과했습니다.")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=".mapnews-ai-",
            suffix=".tmp", delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()
