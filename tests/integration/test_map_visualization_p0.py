
"""PR #16: 파일 보호, 오프라인 캐시, 메타데이터 회귀 검사."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from map_visualization import map_visualization as maps


def article(url="https://news.kr/1", **overrides):
    data = {
        "id": url,
        "url": url,
        "title": "테스트 기사",
        "location": "서울",
        "summary": "요약",
        "category": "사회",
        "datetime": "2026-11-20T12:00:00",
    }
    data.update(overrides)
    return data


def save(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False),
        encoding="utf-8"
    )


# 1~3. 같은 파일 또는 심볼릭 링크에 덮어쓰기 방지
@pytest.mark.parametrize("kind", ["same", "relative", "symlink"])
def test_input_output_same_file(tmp_path, monkeypatch, kind):
    source = tmp_path / "source.json"
    save(source, [article()])
    before = source.read_bytes()

    output = source

    if kind == "relative":
        monkeypatch.chdir(tmp_path)
        output = Path("source.json")

    elif kind == "symlink":
        output = tmp_path / "alias.json"
        try:
            output.symlink_to(source)
        except (OSError, NotImplementedError):
            pytest.skip("심볼릭 링크 권한 없음")

    with pytest.raises(SystemExit):
        maps.main([
            str(source), str(output), "--skip-geocode"
        ])

    assert source.read_bytes() == before


# 4~6. 기사 0건 또는 잘못된 결과로 기존 JSON 덮어쓰기 방지
@pytest.mark.parametrize(
    "kind", ["empty_input", "empty_result", "blank_news"]
)
def test_zero_news_keeps_existing_output(
    tmp_path, monkeypatch, kind
):
    source = tmp_path / "source.json"
    output = tmp_path / "map_results.json"

    save(output, [article("https://news.kr/old")])
    before = output.read_bytes()

    if kind == "empty_input":
        save(source, [])
    elif kind == "blank_news":
        save(source, [{}])
    else:
        save(source, [article()])

    monkeypatch.setattr(
        maps, "CACHE_FILE", tmp_path / "cache.json"
    )

    if kind == "empty_result":
        monkeypatch.setattr(
            maps,
            "prepare_news_for_frontend",
            lambda *a, **kw: []
        )

    with pytest.raises(ValueError, match="0건"):
        maps.main([
            str(source), str(output), "--skip-geocode"
        ])

    assert output.read_bytes() == before


# 7~8. 저장 도중 오류 발생 시 원본 파일과 임시 파일 검사
@pytest.mark.parametrize("kind", ["replace", "serialize"])
def test_atomic_write_failure_keeps_original(
    tmp_path, monkeypatch, kind
):
    target = tmp_path / "map_results.json"

    save(target, [article("https://news.kr/old")])
    before = target.read_bytes()

    if kind == "replace":
        def fail_replace(*args):
            raise OSError("disk full")

        monkeypatch.setattr(
            maps.os, "replace", fail_replace
        )

        with pytest.raises(OSError):
            maps.atomic_write_json(
                target, [article("https://news.kr/new")]
            )
    else:
        with pytest.raises(TypeError):
            maps.atomic_write_json(
                target, [{"cannot_serialize": object()}]
            )

    assert target.read_bytes() == before
    assert not list(
        tmp_path.glob(".map_results.json.*.tmp")
    )


# 9. CLI 실행 중 저장 실패 시 원본 보존
def test_cli_write_failure_keeps_original(
    tmp_path, monkeypatch
):
    source = tmp_path / "input.json"
    output = tmp_path / "map_results.json"

    news = [article(latitude=37.5, longitude=127.0)]

    save(source, news)
    save(output, news)
    before = output.read_bytes()

    monkeypatch.setattr(
        maps, "CACHE_FILE", tmp_path / "cache.json"
    )

    def fail_replace(*args):
        raise OSError("disk full")

    monkeypatch.setattr(
        maps.os, "replace", fail_replace
    )

    with pytest.raises(OSError):
        maps.main([
            str(source), str(output), "--skip-geocode"
        ])

    assert output.read_bytes() == before
    assert not list(
        tmp_path.glob(".map_results.json.*.tmp")
    )


# 10. --skip-geocode 사용 시 캐시 사용 및 인터넷 차단
def test_skip_geocode_reuses_cache_without_network(
    tmp_path, monkeypatch
):
    source = tmp_path / "input.json"
    output = tmp_path / "map_results.json"
    cache = tmp_path / "cache.json"

    save(cache, {"서울": [37.5665, 126.978]})
    save(source, [
        article("https://news.kr/1"),
        article(
            "https://news.kr/2",
            location="미확인지역"
        ),
    ])

    monkeypatch.setattr(maps, "CACHE_FILE", cache)

    with patch.object(
        maps,
        "_geocode",
        side_effect=AssertionError("네트워크 호출 금지")
    ) as network:
        assert maps.main([
            str(source), str(output), "--skip-geocode"
        ]) == 0

        network.assert_not_called()

    rows = json.loads(output.read_text(encoding="utf-8"))

    assert rows[0]["latitude"] == pytest.approx(37.5665)
    assert rows[0]["coordinate_source"] == "region_cache"
    assert rows[0]["coordinate_precision"] == "region"

    assert rows[1]["latitude"] is None
    assert rows[1]["longitude"] is None


# 11. 환경변수로 오프라인 설정 시 캐시 재사용
def test_offline_env_uses_cache(tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"

    save(cache, {"서울": [37.5, 127.0]})
    monkeypatch.setattr(maps, "CACHE_FILE", cache)
    monkeypatch.setenv("MAPNEWS_OFFLINE", "1")

    with patch.object(
        maps,
        "_geocode",
        side_effect=AssertionError("네트워크 호출 금지")
    ) as network:
        rows = maps.prepare_news_for_frontend([
            article(),
            article(
                "https://news.kr/2",
                location="미확인지역"
            ),
        ])

        network.assert_not_called()

    assert rows[0]["coordinate_source"] == "region_cache"
    assert rows[1]["latitude"] is None


# 12. 기본 입력 및 출력 경로 확인
def test_default_paths(tmp_path, monkeypatch):
    base = tmp_path / "map_visualization"
    base.mkdir()

    data_dir = tmp_path / "data_ai"
    data_dir.mkdir()

    save(
        data_dir / "results_sample.json",
        [article(latitude=37.5, longitude=127.0)]
    )

    monkeypatch.setattr(maps, "BASE_DIR", base)
    monkeypatch.setattr(
        maps, "CACHE_FILE", tmp_path / "cache.json"
    )

    assert maps.main(["--skip-geocode"]) == 0
    assert (base / "map_results.json").exists()


# 13. 출처 및 좌표 정보가 JSON과 지도에 보존되는지 확인
def test_source_and_precision_survive_json_and_folium(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        maps, "CACHE_FILE", tmp_path / "cache.json"
    )

    raw = [
        article(
            "https://example.com/demo",
            source="real",
            publisher="시연",
            latitude=37.5,
            longitude=127.0,
            coordinate_precision="region",
            coordinate_note="실제 사건 위치 아님",
        ),
        article(
            "https://news.kr/real",
            source="real",
            publisher="실제언론사",
            latitude=36.5,
            longitude=127.5,
            coordinate_precision="region",
            coordinate_note="지역 대표 좌표",
        ),
    ]

    rows = maps.prepare_news_for_frontend(
        raw, geocode_missing=False
    )

    output = tmp_path / "result.json"
    html = tmp_path / "news_map.html"

    maps.atomic_write_json(output, rows)

    news_map = maps.create_news_map(
        rows,
        output_file=html,
        geocode_missing=False
    )

    stored = json.loads(
        output.read_text(encoding="utf-8")
    )

    assert [row["source"] for row in stored] == [
    "demo", "real"
]

    assert all(
        row["coordinate_precision"] == "region"
        for row in stored
    )

    assert maps.count_folium_markers(news_map) == 2

    rendered = html.read_text(encoding="utf-8")

    for word in (
        "테스트 기사",
        "수집 기사",
        "시연",
        "실제언론사",
        "실제 사건",
    ):
        assert word in rendered
