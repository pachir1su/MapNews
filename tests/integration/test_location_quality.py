"""Contract tests for evidence-backed regions, mapped cache points and AI IDs."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import run_pipeline
from search import load_archive
from data_ai.rule_analysis import RULE_VERSION, enrich, extract_location, locate
from map_visualization import map_visualization as maps
from frontend.tools.export_team_news import export_news


@pytest.mark.parametrize("headline,expected", [
    ("하남 미사지구 헌옷수거함에서 신생아 시신 발견", "경기도 하남시"),
    ("안산 주점 성폭행 사건", "경기도 안산시"),
    ("강남 학원장 성폭행 혐의", "서울특별시 강남구"),
    ("'성북 10대 살인' 피의자", "서울특별시 성북구"),
    ("태안 해광호 실종자 수색", "충청남도 태안군"),
    ("충남 서산 마트서 외국인 근로자 추락사", "충청남도 서산시"),
    ("충남 천안시 서북구 도로 사고", "충청남도 천안시 서북구"),
    ("세종시 전의면 사찰서 화재", "세종특별자치시"),
    ("서울 강남구 행사", "서울특별시 강남구"),
    ("부산 동구청 지역 행사", "부산광역시"),
    ("경기남부경찰 수사 대책", ""),
    ("서울대 입시 면접", ""),
    ("서울고법 판결", ""),
    ("반드시 지킬 것", ""),
    ("AI 커닝 따른 대학입시 혼란", ""),
    ("전국 혁신도시 지자체", ""),
    ("청주 특례시 입법", "충청북도 청주시"),
    ("광주시의 행사", ""),
    ("영덕군청 소속 공무원 적발", ""),
    ("서울과 부산 특별 교류 사업", ""),
])
def test_headline_only_uses_bounded_gazetteer(headline, expected):
    assert extract_location(headline) == expected


def test_dateline_does_not_become_incident_location():
    title = "감독관 실수에 응시자 결시 처리…시험 관리 부실"
    summary = "[서울=뉴시스] 강지은 기자 = 전국에서 문제가 제기됐다."
    assert locate(title, summary) == ("", "none")


def test_rule_upgrade_invalidates_stale_cached_location():
    raw = {"title": "서울대 수시 면접", "url": "https://news.example.kr/1",
           "summary": "입시 공정성 관련 보도"}
    first = enrich([raw])[0]
    assert first["location"] == ""
    assert first["rule_version"] == RULE_VERSION
    older = dict(first, location="서울", rule_version="regional-headline-v1")
    improved = enrich([raw], [older])[0]
    assert improved["location"] == ""


def test_ambiguous_city_is_not_fabricated():
    location, evidence = locate("서울과 부산 사이 교통 사업")
    assert not location and evidence == "ambiguous"


def test_verified_cache_can_be_reused_without_network(tmp_path, monkeypatch):
    path = tmp_path / "cache.json"
    path.write_text(json.dumps({"서울특별시": [37.5665, 126.978]}), encoding="utf-8")
    monkeypatch.setattr(maps, "CACHE_FILE", path)
    rows = [{"id":"x", "title":"서울 시내 사고", "location":"서울특별시",
             "source":"real", "url":"https://news.kr/a"}]
    result = run_pipeline.attach_cached_regional_coordinates(rows)
    assert result[0]["latitude"] == pytest.approx(37.5665)
    assert result[0]["coordinate_source"] == "region_cache"
    assert result[0]["coordinate_precision"] == "region"
    assert "실제 사건 발생 위치" in result[0]["coordinate_note"]


def test_old_map_coordinates_not_reused_without_location_evidence():
    rows = [{"url":"https://news.kr/a", "title":"전국 정책 발표",
             "location":"", "source":"real"}]
    old = [{"url":"https://news.kr/a", "title":"전국 정책 발표",
            "location":"서울특별시", "latitude":37.5, "longitude":127.0}]
    result = run_pipeline.retain_prior_coordinates(rows, old)
    assert "latitude" not in result[0]


def test_legacy_numeric_ids_align_with_gemini_input(tmp_path, monkeypatch):
    raw = [{"id": 7, "title": "강남 행사", "url": "https://news.kr/a",
            "datetime":"2026-11-18 10:00", "summary":"서울 강남구에서 행사 진행"}]
    archive = tmp_path / "news.json"
    archive.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    baseline = enrich(load_archive(archive))
    ai_file = tmp_path / "ai.json"
    monkeypatch.setenv("GEMINI_API_KEY", "fake-only")
    calls = []

    def fake_run(command, env, check):
        rows = json.loads(Path(command[-2]).read_text(encoding="utf-8"))
        calls.append(rows)
        assert rows[0]["id"] == baseline[0]["id"]
        assert rows[0]["content_hash"] == baseline[0]["content_hash"]
        ai_file.write_text(json.dumps([dict(baseline[0], category="행사",
                                           summary="Gemini mock summary")]),
                           encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_pipeline.subprocess, "run", fake_run)
    output = run_pipeline.apply_optional_ai(baseline, archive, ai_file, limit=1)
    assert len(calls) == 1
    assert output[0]["analysis_status"] == "gemini"


def test_frontend_export_keeps_demo_status_and_source_contract(tmp_path):
    source = tmp_path / "input.json"
    output = tmp_path / "output.json"
    article = {
        "id":"article-1", "title":"가상 시연 기사", "url":"https://example.com/test/1",
        "source":"demo", "category":"사회", "location":"서울특별시",
        "datetime":"2026-11-18T10:00:00", "summary":"테스트",
        "latitude":37.56, "longitude":126.97, "content_hash":"hash1",
        "analysis_status":"rule-based", "coordinate_source":"region_cache",
        "coordinate_precision":"region", "coordinate_note":"지역 대표 좌표",
    }
    source.write_text(json.dumps([article], ensure_ascii=False), encoding="utf-8")
    count, pins = export_news(source, output, lambda rows: rows)
    assert (count, pins) == (1, 1)
    row = json.loads(output.read_text(encoding="utf-8"))[0]
    assert row["source"] == "demo"
    assert row["content_hash"] == "hash1"
    assert row["analysis_status"] == "rule-based"
    assert row["coordinate_source"] == "region_cache"
    assert row["coordinate_note"] == "지역 대표 좌표"


def test_inventory_rules_do_not_invent_false_place_tokens():
    inventory = Path("news_results.json")
    if not inventory.is_file():
        pytest.skip("Sample archive unavailable")
    news = load_archive(inventory)
    assert news
    results = enrich(news)
    assert len(results) == len(news)
    for row in results:
        assert row["location"] not in {"반드시", "대학입시", "통합시", "혁신도시", "특례시"}
        assert row["location_source"] in {"headline", "lead-event", "none", "ambiguous"}
