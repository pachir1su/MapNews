"""Regression tests: derived Gemini queue, budget, cooldown, file safety."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import os

import pytest

from data_ai import analyze_news as ai
from data_ai import task_queue as q


def article(n, version="a"):
    return dict(id=f"news-{n}", content_hash=f"h-{version}-{n}",
                title=f"기사 {n}", datetime=f"2026-11-{n+1:02d} 09:00",
                url=f"https://news.test/{n}", source="real", body="본문")


def test_build_queue_skips_completed_hash_and_requeues_changed_version():
    rows = [article(0), article(1), article(2)]
    results = [dict(rows[1], category="사회", location="", summary="내용")]
    queue = q.rebuild_queue(rows, results)
    assert len(queue) == 3
    assert queue[1]["status"] == "completed"
    assert [x["id"] for x in q.select_ready(queue, 30)] == ["news-2", "news-0"]
    changed = [article(0), article(1, "changed"), article(2)]
    newer = q.rebuild_queue(changed, results, queue)
    assert next(x for x in newer if x["id"] == "news-1")["status"] == "pending"


def test_retry_cooldown_does_not_starve_other_new_articles():
    now = datetime(2026, 11, 21, tzinfo=timezone.utc)
    queue = q.rebuild_queue([article(0), article(1), article(2)], [])
    q.mark_batch(queue, failed=["news-2"], now=now, reason="429")
    assert q.select_ready(queue, 10, now=now)[0]["id"] == "news-1"
    delayed = next(x for x in queue if x["id"] == "news-2")
    assert delayed["status"] == "retry_wait" and delayed["attempts"] == 1
    assert q.select_ready(queue, 10, now=now + timedelta(seconds=61))[0]["id"] == "news-2"
    for attempt in range(4):
        q.mark_batch(queue, failed=["news-2"], now=now + timedelta(days=attempt+1))
    assert delayed["status"] == "failed"
    assert delayed["retry_at"] is None
    assert all(x["id"] != "news-2" for x in q.select_ready(queue, 10, now=now + timedelta(days=10)))


def test_atomic_queue_write_failure_keeps_previous_file(tmp_path, monkeypatch):
    dest = tmp_path / "ai_queue.json"
    q.write_queue(dest, q.rebuild_queue([article(0)], []))
    old = dest.read_bytes()
    def fail_replace(*a):
        raise OSError("disk full")
    monkeypatch.setattr(q.os, "replace", fail_replace)
    with pytest.raises(OSError, match="disk full"):
        q.write_queue(dest, q.rebuild_queue([article(1)], []))
    assert dest.read_bytes() == old
    assert not list(tmp_path.glob(".mapnews-ai-*.tmp"))


def test_queue_schema_corruption_fails_closed(tmp_path):
    f = tmp_path / "queue.json"
    f.write_text('{"version":1,"articles":[{"id":"a"}]}', encoding="utf-8")
    with pytest.raises(ValueError, match="대기열"):
        q.read_queue(f)
    f.write_text("truncated{", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        q.read_queue(f)
    with pytest.raises(ValueError, match="정수"):
        q.select_ready([], -1)


def test_completed_in_queue_without_real_result_is_pending():
    rows = [article(0)]
    stale = q.rebuild_queue(rows, [dict(rows[0], category="사회")])
    assert stale[0]["status"] == "completed"
    repaired = q.rebuild_queue(rows, [], stale)
    assert repaired[0]["status"] == "pending"


def test_429_rate_limit_never_falls_back_to_more_models(monkeypatch):
    calls = []
    class Quota(Exception):
        code = 429
    def fail(**kwargs):
        calls.append(kwargs["model"])
        raise Quota("rate-limited")
    monkeypatch.setattr(ai, "_api_attempts", 0)
    monkeypatch.setattr(ai, "get_client", lambda: SimpleNamespace(
        models=SimpleNamespace(generate_content=fail)))
    assert ai.ask_gemini("test") is None
    assert len(calls) == 1 and ai._api_attempts == 1


def test_503_retries_respect_budget_without_sleeping_in_tests(monkeypatch):
    calls = []
    class Unavailable(Exception):
        status_code = 503
    def fail(**kwargs):
        calls.append(kwargs["model"])
        raise Unavailable()
    monkeypatch.setattr(ai, "_api_attempts", 0)
    monkeypatch.setattr(ai, "MAX_AI_REQUESTS_PER_RUN", 2)
    monkeypatch.setattr(ai, "get_client", lambda: SimpleNamespace(
        models=SimpleNamespace(generate_content=fail)))
    monkeypatch.setattr(ai.time, "sleep", lambda *a: None)
    assert ai.ask_gemini("test") is None
    assert len(calls) == 2


def test_ai_results_atomic_write_failure_preserves_original(tmp_path, monkeypatch):
    destination = tmp_path / "result.json"
    destination.write_bytes(b"old")
    monkeypatch.setattr(ai.os, "replace",
                        lambda *a: (_ for _ in ()).throw(OSError("failure")))
    with pytest.raises(OSError):
        ai.save_json_safely(destination, [{"id":"new"}])
    assert destination.read_bytes() == b"old"
    assert not list(tmp_path.glob(".mapnews-ai-*.tmp"))


def test_analyzer_rejects_corrupt_queue_before_calls(tmp_path, monkeypatch):
    archive = tmp_path / "input.json"
    archive.write_text(json.dumps([article(0)]), encoding="utf-8")
    queue_path = tmp_path / "queue.json"
    queue_path.write_text("broken", encoding="utf-8")
    output = tmp_path / "result.json"
    output.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(ai, "analyze_batch",
                        lambda *a: (_ for _ in ()).throw(AssertionError("unexpected API")))
    with pytest.raises(json.JSONDecodeError):
        ai._run_analysis(archive, output, queue_path, "real")
    assert output.read_text(encoding="utf-8") == "[]"


def test_analyzer_recovery_after_failed_batch(tmp_path, monkeypatch):
    archive = tmp_path / "input.json"
    archive.write_text(json.dumps([article(0), article(1)]), encoding="utf-8")
    out, queue = tmp_path / "result.json", tmp_path / "queue.json"
    monkeypatch.setattr(ai, "analyze_batch", lambda *a: None)
    with pytest.raises(SystemExit) as exit_value:
        ai._run_analysis(archive, out, queue, "real")
    assert exit_value.value.code == 3
    stored = q.read_queue(queue)
    assert len(stored) == 2
    assert all(x["attempts"] == 1 and x["status"] == "retry_wait" for x in stored)
    monkeypatch.setattr(ai, "analyze_batch", lambda *a: (_ for _ in ()).throw(
        AssertionError("should wait")))
    # A consecutive execution is quarantined by retry_at, not immediately retried.
    ai._run_analysis(archive, out, queue, "real")
    assert q.read_queue(queue)[0]["attempts"] == 1


def test_analyzer_limits_input_count_and_type(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"not":"an array"}', encoding="utf-8")
    with pytest.raises(ValueError, match="배열"):
        ai._read_input(path)
    path.write_text("[] " + " " * (32*1024*1024), encoding="utf-8")
    with pytest.raises(ValueError, match="32 MiB"):
        ai._read_input(path)


def test_corrupt_existing_ai_output_is_not_automatically_replaced(tmp_path):
    output = tmp_path / "ai_results.json"
    original = [{"id":"ok", "title":"뉴스", "category":"사회",
                 "location":"", "summary":"정상"},
                {"id":"broken"}]
    output.write_text(json.dumps(original), encoding="utf-8")
    before = output.read_bytes()
    with pytest.raises(ValueError, match="불완전"):
        ai.load_existing(output, "real")
    assert output.read_bytes() == before


def test_ai_result_duplicate_id_fails_closed(tmp_path):
    output = tmp_path / "ai_results.json"
    row = {"id":"news-1", "title":"뉴스", "category":"사회",
           "location":"", "summary":"정상"}
    output.write_text(json.dumps([row,row]), encoding="utf-8")
    with pytest.raises(ValueError, match="중복 ID"):
        ai.load_existing(output, "real")


def test_queue_does_not_requeue_previous_result_after_crash(tmp_path, monkeypatch):
    articles = [article(0)]
    input_file, output, queue_path = (
        tmp_path/"input.json", tmp_path/"result.json", tmp_path/"queue.json")
    input_file.write_text(json.dumps(articles), encoding="utf-8")
    record = dict(articles[0], category="사회", location="",
                  summary="Gemini 완료", analysis_status="gemini")
    output.write_text(json.dumps([record]), encoding="utf-8")
    q.write_queue(queue_path, q.rebuild_queue(articles, []))
    monkeypatch.setattr(ai, "analyze_batch",
                        lambda *a: (_ for _ in ()).throw(AssertionError("duplicate call")))
    ai._run_analysis(input_file, output, queue_path, "real")
    assert q.read_queue(queue_path)[0]["status"] == "completed"
