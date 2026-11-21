"""Failure injection and version-consistency checks for multi-file publishing."""
import json
import os

import pytest

from pipeline_transaction import (output_lock, publish_pair, recover_pair,
                                  verify_pair, _journal_path, _manifest_path)
import pipeline_transaction as tx
from frontend.providers import JsonNewsProvider
from threading import Event


def rows(tag="new"):
    record = {"id": tag, "title": "테스트", "category": "사회"}
    return [record], [{**record, "latitude": None, "longitude": None}]


def test_publish_outputs_share_manifest_and_checksums(tmp_path):
    analysis, mapped = tmp_path / "analysis.json", tmp_path / "map.json"
    x, y = rows()
    with output_lock(mapped):
        manifest = publish_pair(analysis, x, mapped, y)
        assert verify_pair(analysis, mapped)
    assert manifest["article_count"] == 1
    assert json.loads(_manifest_path(mapped).read_text())["run_id"] == manifest["run_id"]
    assert not _journal_path(mapped).exists()
    assert list(tmp_path.glob(".mapnews-tx-*.tmp")) == []


def test_analysis_replace_failure_rolls_back_map_too(tmp_path, monkeypatch):
    analysis, mapped = tmp_path / "analysis.json", tmp_path / "map.json"
    old_x, old_y = rows("old")
    publish_pair(analysis, old_x, mapped, old_y)
    originals = (analysis.read_bytes(), mapped.read_bytes())
    real_replace = os.replace
    error_once = {"failed": False}

    def fails_second(source, target):
        if (str(target) == str(analysis) and not error_once["failed"]):
            error_once["failed"] = True
            raise OSError("simulated disk interruption")
        return real_replace(source, target)

    monkeypatch.setattr(tx.os, "replace", fails_second)
    with pytest.raises(OSError, match="simulated"):
        publish_pair(analysis, rows("new")[0], mapped, rows("new")[1])
    assert error_once["failed"]
    assert (analysis.read_bytes(), mapped.read_bytes()) == originals
    assert verify_pair(analysis, mapped)
    assert not _journal_path(mapped).exists()


def test_crash_recovery_restores_last_consistent_pair(tmp_path, monkeypatch):
    analysis, mapped = tmp_path / "analysis.json", tmp_path / "map.json"
    old_x, old_y = rows("old")
    publish_pair(analysis, old_x, mapped, old_y)
    saved = (analysis.read_bytes(), mapped.read_bytes())
    original_replace = os.replace
    real_recover = tx.recover_pair

    def interrupted(source, target):
        if str(target) == str(analysis):
            raise KeyboardInterrupt("simulated process death")
        return original_replace(source, target)

    monkeypatch.setattr(tx.os, "replace", interrupted)
    monkeypatch.setattr(tx, "recover_pair", lambda *args: None)
    with pytest.raises(KeyboardInterrupt):
        publish_pair(analysis, rows("new")[0], mapped, rows("new")[1])
    assert _journal_path(mapped).is_file()
    assert mapped.read_bytes() != saved[1]
    monkeypatch.setattr(tx.os, "replace", original_replace)
    monkeypatch.setattr(tx, "recover_pair", real_recover)
    assert recover_pair(analysis, mapped)
    assert (analysis.read_bytes(), mapped.read_bytes()) == saved
    assert verify_pair(analysis, mapped)


def test_mismatched_article_id_is_rejected_before_any_output(tmp_path):
    analysis, mapped = tmp_path / "analysis.json", tmp_path / "map.json"
    with pytest.raises(ValueError, match="ID"):
        publish_pair(analysis, [{"id": "a"}], mapped, [{"id": "b"}])
    assert not analysis.exists() and not mapped.exists()


def test_manifest_detects_external_modification(tmp_path):
    analysis, mapped = tmp_path / "analysis.json", tmp_path / "map.json"
    publish_pair(analysis, rows()[0], mapped, rows()[1])
    mapped.write_text('[]', encoding="utf-8")
    assert not verify_pair(analysis, mapped)


def test_interprocess_lock_prevents_overlapping_writes(tmp_path):
    mapped = tmp_path / "map.json"
    with output_lock(mapped):
        with pytest.raises(RuntimeError, match="다른 MapNews"):
            with output_lock(mapped):
                pass


def test_32mib_json_boundary_preserves_prior_limit_contract(tmp_path):
    mapped = tmp_path / "map.json"
    payload = [{"id": "big", "summary": "x" * (9 * 1024 * 1024)}]
    mapped.write_text(json.dumps(payload), encoding="utf-8")
    batch = JsonNewsProvider(mapped).load(Event())
    assert len(batch.items) == 1
    with mapped.open("wb") as out:
        out.write(b"[]")
        out.write(b" " * (32 * 1024 * 1024))
    with pytest.raises(ValueError, match="32 MiB"):
        JsonNewsProvider(mapped).load(Event())


def test_pipeline_offline_writes_consistent_manifest(tmp_path, monkeypatch):
    import run_pipeline
    from map_visualization import map_visualization as maps
    monkeypatch.setattr(maps, "CACHE_FILE", tmp_path / "cached.json")
    source = tmp_path / "archive.json"
    source.write_text(json.dumps([{
        "url": "https://news.example.org/article",
        "title": "천안시 도로 공사",
        "summary": "천안시에서 도로 공사가 진행된다",
    }], ensure_ascii=False), encoding="utf-8")
    analysis, mapped = tmp_path / "analysis.json", tmp_path / "map.json"
    assert run_pipeline.main([
        "--skip-fetch", "--archive", str(source),
        "--analysis-output", str(analysis), "--map-output", str(mapped),
    ]) == 0
    assert verify_pair(analysis, mapped)
    assert len(json.loads(analysis.read_text(encoding="utf-8"))) == len(
        json.loads(mapped.read_text(encoding="utf-8"))) == 1
