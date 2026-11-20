
"""MapNews P1 회귀 테스트."""

import json

import pytest

from map_visualization import map_visualization as maps


def article(number, **extra):
    """테스트용 가상 뉴스 생성."""
    result = {
        "id": str(number),
        "url": f"https://news.kr/{number}",
        "title": f"뉴스 {number}",
        "location": "서울",
        "summary": "테스트 요약",
        "source": "real",
    }
    result.update(extra)
    return result


def save(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False),
        encoding="utf-8",
    )


# P1-A: 교체 옵션이 없으면 기사 수 감소 차단
def test_shrink_without_flag_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(
        maps, "CACHE_FILE", tmp_path / "cache.json"
    )

    source = tmp_path / "input.json"
    output = tmp_path / "map_results.json"

    save(output, [article(1), article(2), article(3)])
    save(source, [article(1), article(2)])

    before = output.read_bytes()

    with pytest.raises(ValueError, match="기사 수"):
        maps.main([
            str(source), str(output), "--skip-geocode"
        ])

    assert output.read_bytes() == before


# P1-A: 교체 옵션으로 기사 수 감소 허용 및 백업 확인
def test_shrink_with_flag_creates_backup(tmp_path, monkeypatch):
    monkeypatch.setattr(
        maps, "CACHE_FILE", tmp_path / "cache.json"
    )

    source = tmp_path / "input.json"
    output = tmp_path / "map_results.json"

    save(output, [article(1), article(2), article(3)])
    save(source, [article(1), article(2)])

    before = output.read_bytes()

    assert maps.main([
        str(source),
        str(output),
        "--skip-geocode",
        "--replace-dataset",
    ]) == 0

    new_data = json.loads(
        output.read_text(encoding="utf-8")
    )

    assert len(new_data) == 2

    backups = list(
        (tmp_path / ".mapnews_backups")
        .glob("map_results.json.*.bak")
    )

    assert len(backups) == 1
    assert backups[0].read_bytes() == before


# 기존 P0 보호: 교체 옵션을 사용해도 빈 뉴스는 차단
def test_replace_cannot_write_empty_news(tmp_path, monkeypatch):
    monkeypatch.setattr(
        maps, "CACHE_FILE", tmp_path / "cache.json"
    )

    source = tmp_path / "input.json"
    output = tmp_path / "map_results.json"

    save(output, [article(1)])
    save(source, [])

    before = output.read_bytes()

    with pytest.raises(ValueError, match="0건"):
        maps.main([
            str(source),
            str(output),
            "--skip-geocode",
            "--replace-dataset",
        ])

    assert output.read_bytes() == before


# 기존 P0 보호: 교체하더라도 정상 좌표 손실 차단
def test_replace_protects_existing_coordinates(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        maps, "CACHE_FILE", tmp_path / "cache.json"
    )

    source = tmp_path / "input.json"
    output = tmp_path / "map_results.json"

    save(output, [
        article(1, latitude=37.5, longitude=127.0),
        article(2),
    ])

    save(source, [article(1)])
    before = output.read_bytes()

    with pytest.raises(ValueError, match="정상 좌표"):
        maps.main([
            str(source),
            str(output),
            "--skip-geocode",
            "--replace-dataset",
        ])

    assert output.read_bytes() == before


# P1-B: 시연 기사를 프론트엔드 규격 demo로 변환
@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/test",
        "https://example.org/test",
        "https://example.net/test",
    ],
)
def test_sample_source_becomes_demo(tmp_path, monkeypatch, url):
    monkeypatch.setattr(
        maps, "CACHE_FILE", tmp_path / "cache.json"
    )

    news = article(1, url=url, source="real")

    mapped = maps.prepare_news_for_frontend(
        [news], geocode_missing=False
    )

    assert mapped[0]["source"] == "demo"


# P1-C: 분석 및 좌표 메타데이터 유지
def test_metadata_fields_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(
        maps, "CACHE_FILE", tmp_path / "cache.json"
    )

    original = article(
        1,
        content_hash="hash-123",
        analysis_status="rule-based",
        coordinate_source="upstream",
        latitude=37.5,
        longitude=127.0,
    )

    mapped = maps.prepare_news_for_frontend(
        [original], geocode_missing=False
    )

    result = mapped[0]

    assert result["content_hash"] == "hash-123"
    assert result["analysis_status"] == "rule-based"
    assert result["source"] == "real"
    assert result["coordinate_source"] == "upstream"
