"""Offline integration and failure-recovery regression checks."""
import json

import pytest

import search
import run_pipeline
from data_ai.rule_analysis import classify, enrich, extract_location
from map_visualization import map_visualization as maps
from frontend.models import parse_news


def sample(url="https://example.org/a?utm_source=test", title="충남 천안시 교통사고",
           summary="천안시에서 차량이 추돌했다.", published="2026-11-18 10:00"):
    return {"url": url, "title": title, "summary": summary, "datetime": published}


def test_url_identity_removes_tracking_but_keeps_essential_parameters():
    url1 = "https://EXAMPLE.ORG/story?article=11&utm_source=a#fragment"
    url2 = "https://example.org/story?utm_source=b&article=11"
    assert search.canonical_url(url1) == search.canonical_url(url2)
    assert search.make_article_id(search.canonical_url(url1)) == search.make_article_id(
        search.canonical_url(url2))
    assert search.canonical_url("file:///etc/passwd") == ""


def test_same_headline_distinct_articles_and_modified_revision():
    old = [sample("https://example.org/1", title="동일 제목", summary="초기")]
    new = [sample("https://example.org/2", title="동일 제목", summary="다른 사건")]
    merged, stats = search.merge_archive(old, new)
    assert len(merged) == 2 and stats["new"] == 1
    update = [sample("https://example.org/1", title="동일 제목", summary="수정된 사실")]
    merged2, stats2 = search.merge_archive(merged, update)
    assert len(merged2) == 2 and stats2["updated"] == 1


def test_unchanged_recollection_keeps_archive():
    old = [sample(url="https://example.org/a", summary="기존")]
    merged, stats = search.merge_archive(old, old)
    assert len(merged) == 1 and stats == {"new": 0, "updated": 0, "unchanged": 1}


def test_archive_legacy_numeric_id_is_migrated(tmp_path):
    path = tmp_path / "archive.json"
    path.write_text(json.dumps([dict(sample(url="https://example.org/legacy"), id=1)]),
                    encoding="utf-8")
    entries = search.load_archive(path)
    assert entries[0]["id"].startswith("news-")
    assert entries[0]["source"] == "real"


def test_zero_rss_preserves_existing_archive(monkeypatch, tmp_path):
    path = tmp_path / "archive.json"
    original = b'[{"id":1,"title":"old","url":"https://example.org/old"}]'
    path.write_bytes(original)
    monkeypatch.setattr(search, "RSS_FEEDS", {"broken": "https://rss.example.org"})
    monkeypatch.setattr(search, "fetch_url", lambda url: b"<rss><channel></channel></rss>")
    with pytest.raises(RuntimeError):
        search.main(["--output", str(path)])
    assert path.read_bytes() == original


def test_corrupt_rss_dtd_is_rejected():
    with pytest.raises(ValueError):
        search.parse_rss(b'<!DOCTYPE rss><rss><channel></channel></rss>')


def test_save_fails_without_destroying_previous(monkeypatch, tmp_path):
    path = tmp_path / "news.json"
    path.write_text("old", encoding="utf-8")
    monkeypatch.setattr(search.os, "replace",
                        lambda source, destination: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        search.save_json([search.normalize_article(sample())], path)
    assert path.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.glob(".mapnews-*")) == []


def test_rule_analysis_is_api_free_and_conservative():
    assert classify("대전 아파트 화재") == "화재"
    assert extract_location("충남 천안시 서북구 도로 사고") == "충남 천안시 서북구"
    assert extract_location("시험 관리 부실") == ""
    result = enrich([sample(url="https://example.com/test/1",
                            title="시험 관리 부실", summary="[서울=뉴시스] 기자 보도")])
    assert result[0]["location"] == ""
    assert result[0]["source"] == "demo"


def test_changed_article_recomputes_rule_result():
    old = enrich([sample(url="https://example.org/1", title="부산 축제 개최")])
    new = enrich([sample(url="https://example.org/1", title="부산 아파트 화재")], old)
    assert new[0]["category"] == "화재"
    assert new[0]["analysis_status"] == "rule-based"


def test_map_write_failure_preserves_prior_file(monkeypatch, tmp_path):
    path = tmp_path / "map.json"
    path.write_text("old", encoding="utf-8")
    monkeypatch.setattr(maps.os, "replace",
                        lambda source, destination: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        maps.atomic_write_json(path, [{"id": "1"}])
    assert path.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.glob(".mapnews-*")) == []


def test_map_without_geocoder_keeps_unlocated_articles(monkeypatch, tmp_path):
    monkeypatch.setattr(maps, "CACHE_FILE", tmp_path / "coords.json")
    rows = enrich([sample("https://example.org/no-location",
                          title="시험 관리 부실")])
    mapped = maps.prepare_news_for_frontend(rows, geocode_missing=False)
    assert len(mapped) == 1
    assert mapped[0]["latitude"] is None and mapped[0]["longitude"] is None
    # example.org는 시연용 주소이므로 실제 기사로 분류하지 않는다.
    assert mapped[0]["source"] == "sample"


def test_frontend_prevents_demo_open_link_and_keeps_source():
    row = enrich([sample("https://example.com/test/1")])[0]
    row.update({"latitude": 36.8, "longitude": 127.1})
    item = parse_news([row]).items[0]
    assert item.is_mock and item.source == "demo"


def test_pipeline_offline_smoke(tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "CACHE_FILE", tmp_path / "coords.json")
    archive = tmp_path / "archive.json"
    archive.write_text(json.dumps([sample("https://example.org/one",
                                          title="충남 천안시 교통사고")]), encoding="utf-8")
    analyzed, mapped = tmp_path / "analysis.json", tmp_path / "map.json"
    assert run_pipeline.main([
        "--skip-fetch", "--archive", str(archive),
        "--analysis-output", str(analyzed), "--map-output", str(mapped),
    ]) == 0
    ai_rows = json.loads(analyzed.read_text(encoding="utf-8"))
    map_rows = json.loads(mapped.read_text(encoding="utf-8"))
    assert len(ai_rows) == len(map_rows) == 1
    assert ai_rows[0]["id"] == map_rows[0]["id"]
    assert map_rows[0]["latitude"] is None
    assert map_rows[0]["analysis_status"] == "rule-based"


def test_pipeline_rejects_missing_input_without_clobber(tmp_path):
    output = tmp_path / "previous.json"
    output.write_text("old", encoding="utf-8")
    with pytest.raises(ValueError):
        run_pipeline.main(["--skip-fetch", "--archive", str(tmp_path / "absent.json"),
                           "--map-output", str(output)])
    assert output.read_text(encoding="utf-8") == "old"


def test_gemini_not_called_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    baseline = enrich([sample("https://example.org/a")])
    assert run_pipeline.apply_optional_ai(baseline, tmp_path / "a", tmp_path / "b", 30) == baseline


def test_max_archive_and_stable_newest_order():
    entries = [sample("https://example.org/" + str(n), title="기사 " + str(n),
                      published=f"2026-11-{n + 1:02d} 00:00") for n in range(4)]
    output, _ = search.merge_archive([], entries, maximum=2)
    assert len(output) == 2
    assert output[0]["datetime"] == "2026-11-04 00:00"



def test_existing_same_headline_pin_is_reused_but_not_claimed_exact():
    news = enrich([sample("https://example.org/one",
                          title="충남 천안시 교통사고")])
    old = [{
        "url": "https://example.org/one", "title": news[0]["title"],
        "latitude": 36.8, "longitude": 127.1, "source": "real"
    }]
    result = run_pipeline.retain_prior_coordinates(news, old)
    assert result[0]["latitude"] == 36.8
    assert "실제 발생 주소는 확인되지" in result[0]["coordinate_note"]


def test_prior_coordinate_not_reused_for_changed_title_or_demo():
    rows = enrich([sample("https://example.org/one", title="새 기사")])
    old = [{"url": "https://example.org/one", "title": "이전 기사",
            "latitude": 36.8, "longitude": 127.1}]
    assert "latitude" not in run_pipeline.retain_prior_coordinates(rows, old)[0]
    demo = enrich([sample("https://example.com/test/1", title="가상 기사")])
    old_demo = [{"url": demo[0]["url"], "title": demo[0]["title"],
                 "latitude": 36.8, "longitude": 127.1, "source": "demo"}]
    assert "latitude" not in run_pipeline.retain_prior_coordinates(demo, old_demo)[0]



def test_pipeline_rejects_aliased_output_without_mutation(tmp_path):
    archive = tmp_path / "archive.json"
    archive.write_text(json.dumps([sample("https://example.org/one")]), encoding="utf-8")
    old = archive.read_bytes()
    with pytest.raises(ValueError, match="입력·출력"):
        run_pipeline.main(["--skip-fetch", "--archive", str(archive),
                           "--map-output", str(archive)])
    assert archive.read_bytes() == old


def test_frontend_export_rejects_overwriting_source(tmp_path):
    from frontend.tools.export_team_news import export_news
    source = tmp_path / "source.json"
    source.write_text(json.dumps([sample("https://example.org/one")]), encoding="utf-8")
    before = source.read_bytes()
    with pytest.raises(ValueError, match="서로 다른"):
        export_news(source, source, lambda rows: rows)
    assert source.read_bytes() == before
