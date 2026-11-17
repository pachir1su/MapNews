"""The team-data export adapter must work offline without touching other modules."""
import json

import pytest

from frontend.tools.export_team_news import export_news


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
