"""The team-data export adapter must work offline without touching other modules."""
import json
from threading import Event

from frontend.providers import JsonNewsProvider

import pytest

from frontend.tools.export_team_news import export_news, prepare_with_cache, main


def test_export_team_news_preserves_rows_and_coordinates(tmp_path):
    source = tmp_path / "source.json"
    target = tmp_path / "out" / "frontend.json"
    source.write_text(json.dumps([
        {
            "id": 1, "title": "천안 뉴스", "category": "교통",
            "location": "충남 천안시", "summary": "교통 안내", "url": "",
            "datetime": "2026-11-04 10:23"
        },
        {
            "id": 2, "title": "위치 미상 뉴스", "category": "사회",
            "location": "지역 미제공", "summary": "요약", "url": "",
            "datetime": None
        }
    ], ensure_ascii=False), encoding="utf-8")

    def prepare(rows):
        result = [dict(row) for row in rows]
        result[0].update(latitude=36.81, longitude=127.15)
        result[1].update(latitude=None, longitude=None)
        return result

    total, with_coordinates = export_news(source, target, prepare)
    assert (total, with_coordinates) == (2, 1)
    exported = json.loads(target.read_text(encoding="utf-8"))
    assert [row["id"] for row in exported] == ["1", "2"]
    assert exported[0]["latitude"] == 36.81
    assert exported[1]["latitude"] is None
    assert exported[0]["datetime"].endswith("+09:00")


def test_export_does_not_replace_valid_output_on_failure(tmp_path):
    source = tmp_path / "source.json"
    target = tmp_path / "news.json"
    target.write_text('[{"stable":true}]', encoding="utf-8")
    source.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="배열"):
        export_news(source, target, lambda rows: rows)
    assert target.read_text(encoding="utf-8") == '[{"stable":true}]'


def test_cache_connects_crawler_shape_to_map_markers(tmp_path, window):
    """Cached geocodes are passed to the real Qt offline map without new estimates."""
    source = tmp_path / "news_results.json"
    target = tmp_path / "frontend-news.json"
    cache = tmp_path / "cache.json"
    source.write_text(json.dumps([
        {"id": "news-k1", "title": "기사 1", "location": "충남 천안시",
         "category": "사회", "summary": "실제 수집 결과 형식", "url": "https://example.org/a",
         "datetime": "2026-11-17 10:00"},
        {"id": "news-k2", "title": "기사 2", "location": "지역 미상",
         "category": "사회", "summary": "위치 미제공", "url": "https://example.org/b",
         "datetime": "2026-11-17 10:05"}
    ], ensure_ascii=False), encoding="utf-8")
    cache.write_text(json.dumps({"충남 천안시": [36.81, 127.15]}), encoding="utf-8")

    total, mapped = export_news(source, target,
                                lambda rows: prepare_with_cache(rows, cache),
                                require_pins=True)
    assert (total, mapped) == (2, 1)
    batch = JsonNewsProvider(target).load(Event())
    assert len(batch.items) == 2
    assert batch.items[0].has_coordinates
    assert batch.items[1].latitude is None
    window._loaded(batch)
    assert window.news_count.text() == "2건"
    assert len(window.map.offline.markers) == 1


def test_no_pin_export_preserves_previous_result(tmp_path):
    source = tmp_path / "news_results.json"
    target = tmp_path / "frontend-news.json"
    source.write_text('[{"id": "1", "title":"기사", "location":"미상"}]', encoding="utf-8")
    target.write_text('[{"stable":true}]', encoding="utf-8")
    with pytest.raises(ValueError, match="좌표가 있는 기사가 0건"):
        export_news(source, target, lambda rows: rows, require_pins=True)
    assert target.read_text(encoding="utf-8") == '[{"stable":true}]'


def test_cached_coordinates_are_validated(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text('{"A":[91,127],"B":[36.5,127],"C":[0,false]}', encoding="utf-8")
    rows = [
        {"id": 1, "location": "A"},
        {"id": 2, "location": "B"},
        {"id": 3, "location": "C"},
        {"id": 4, "location": "B", "latitude": 36.8, "longitude": 127.2},
    ]
    result = prepare_with_cache(rows, cache)
    assert result[0]["latitude"] is None
    assert result[1]["latitude"] == 36.5
    assert result[2]["longitude"] is None
    assert result[3]["latitude"] == 36.8
    assert rows[1].get("latitude") is None


def test_cache_cli_runs_without_backend_import(tmp_path, monkeypatch, capsys):
    source = tmp_path / "news_results.json"
    target = tmp_path / "frontend-news.json"
    cache = tmp_path / "cache.json"
    source.write_text('[{"id": 1, "title": "기사", "location": "천안"}]', encoding="utf-8")
    cache.write_text('{"천안": [36.81, 127.15]}', encoding="utf-8")
    monkeypatch.setattr("sys.argv", [
        "export_team_news", "--input", str(source), "--output", str(target),
        "--coordinate-cache", str(cache)
    ])
    assert main() == 0
    assert "지도에 표시할 기사 1건" in capsys.readouterr().out
    assert json.loads(target.read_text(encoding="utf-8"))[0]["latitude"] == 36.81
