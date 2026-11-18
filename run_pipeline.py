"""MapNews integrated runner: RSS/archive -> rule/optional AI -> coordinates -> GUI.

The default path requires no Gemini account and does not contact a geocoder.
Use --geocode explicitly to permit Nominatim network requests.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from search import load_archive, main as crawl_main, save_json
from data_ai.rule_analysis import enrich


def load_optional(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open("rb") as stream:
        data = stream.read(32 * 1024 * 1024 + 1)
    if len(data) > 32 * 1024 * 1024:
        raise ValueError(f"파일이 32 MiB를 초과했습니다: {path}")
    rows = json.loads(data.decode("utf-8-sig"))
    if not isinstance(rows, list):
        raise ValueError(f"JSON 배열이 아닙니다: {path}")
    return rows


def apply_optional_ai(baseline, input_path, ai_path, limit):
    if not os.getenv("GEMINI_API_KEY"):
        print("GEMINI_API_KEY 없음: Gemini 호출 없이 규칙 기반 분석을 사용합니다.")
        return baseline
    env = dict(os.environ, MAPNEWS_MAX_AI_ARTICLES=str(limit))
    completed = subprocess.run(
        [sys.executable, "data_ai/analyze_news.py", str(input_path), str(ai_path)],
        env=env, check=False,
    )
    if completed.returncode:
        print("Gemini 일부/전체 실패: 규칙 기반 결과를 유지하고 다음 실행에서 재시도할 수 있습니다.")
    ai_items = {}
    for row in load_optional(ai_path):
        if isinstance(row, dict) and row.get("content_hash"):
            ai_items[(row.get("id"), row.get("content_hash"))] = row
    merged = []
    for row in baseline:
        ai = ai_items.get((row["id"], row["content_hash"]))
        if ai and ai.get("category") in {"사고", "화재", "교통", "행사", "사회"}:
            updated = dict(row)
            updated.update({key: ai[key] for key in ("category", "location", "summary") if key in ai})
            updated["analysis_status"] = "gemini"
            merged.append(updated)
        else:
            merged.append(row)
    return merged




def retain_prior_coordinates(rows, prior_map):
    """Reuse only same URL+headline coordinates already present in a prior map.

    They remain approximate regional pins; never claim incident-location accuracy.
    """
    from frontend.models import coordinate
    lookup = {}
    for old in prior_map:
        if not isinstance(old, dict) or old.get("source") in {"demo", "mock"}:
            continue
        if str(old.get("url") or "").startswith("https://example.com/"):
            continue
        lat = coordinate(old.get("latitude"), 90)
        lon = coordinate(old.get("longitude"), 180)
        if lat is not None and lon is not None:
            lookup[(old.get("url"), old.get("title"))] = (lat, lon)
    merged = []
    for raw in rows:
        row = dict(raw)
        old_coordinate = lookup.get((row.get("url"), row.get("title")))
        if old_coordinate and row.get("source") == "real":
            row["latitude"], row["longitude"] = old_coordinate
            row["coordinate_note"] = (
                "이전 지도 데이터의 지역 대표 좌표 재사용. 실제 발생 주소는 확인되지 않았습니다."
            )
        merged.append(row)
    return merged

def main(argv=None):
    parser = argparse.ArgumentParser(description="MapNews 전체 데이터 파이프라인")
    parser.add_argument("--skip-fetch", action="store_true",
                        help="기존 기사 파일로만 실행(RSS 네트워크 요청 생략)")
    parser.add_argument("--archive", type=Path, default=Path("news_results.json"))
    parser.add_argument("--with-ai", action="store_true", help="Gemini를 선택적으로 사용")
    parser.add_argument("--max-ai-articles", type=int, default=30)
    parser.add_argument("--geocode", action="store_true",
                        help="좌표 캐시에 없는 지역만 Nominatim으로 조회")
    parser.add_argument("--gui", action="store_true", help="완료 후 PySide6 앱 실행")
    parser.add_argument("--offline-map", action="store_true",
                        help="GUI를 인터넷 타일 없이 실행")
    parser.add_argument("--analysis-output", type=Path,
                        default=Path("data_ai/results_real.json"))
    parser.add_argument("--map-output", type=Path,
                        default=Path("map_visualization/map_results.json"))
    args = parser.parse_args(argv)
    if args.max_ai_articles < 0 or args.max_ai_articles > 1000:
        parser.error("--max-ai-articles는 0~1000 범위여야 합니다.")
    if not args.skip_fetch:
        if crawl_main(["--output", str(args.archive)]):
            return 1
    archive = load_archive(args.archive)
    if not archive:
        raise ValueError("기사 0건: 이전 분석·지도 결과를 보호하고 중단합니다.")

    previous = load_optional(args.analysis_output)
    baseline = enrich(archive, previous)
    # Only commit the analysis result after the full preparation succeeds.
    if args.with_ai and args.max_ai_articles:
        baseline = apply_optional_ai(
            baseline, args.archive, Path("data_ai/results_ai.json"), args.max_ai_articles
        )
    from map_visualization.map_visualization import prepare_news_for_frontend, atomic_write_json
    previous_map = load_optional(args.map_output)
    baseline_for_map = retain_prior_coordinates(baseline, previous_map)
    mapped = prepare_news_for_frontend(baseline_for_map, geocode_missing=args.geocode)
    if not mapped:
        raise ValueError("유효한 뉴스가 없어 기존 지도 결과를 보존합니다.")
    # The map output is written first; a crash never destroys either old valid file.
    atomic_write_json(args.map_output, mapped)
    save_json(baseline, args.analysis_output)
    pins = sum(row.get("latitude") is not None and row.get("longitude") is not None
               for row in mapped)
    print(f"수집 보관 {len(archive)}건 / 분석 {len(baseline)}건 / 지도 좌표 {pins}건 "
          f"/ 좌표 미확인 {len(mapped)-pins}건")
    print(f"실제 뉴스 파일: {args.map_output}")
    if args.gui:
        command = [sys.executable, "-m", "frontend", "--json", str(args.map_output)]
        if args.offline_map:
            command.append("--offline")
        return subprocess.run(command, check=False).returncode
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(errors="backslashreplace")
            except (OSError, ValueError):
                pass
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"MapNews 통합 실행 실패: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
