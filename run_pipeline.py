"""MapNews integrated runner: RSS/archive -> rule/optional AI -> coordinates -> GUI.

The default path requires no Gemini account and does not contact a geocoder.
Use --geocode explicitly to permit Nominatim network requests.
"""
import argparse
import json
import os
import subprocess
import tempfile
import sys
from pathlib import Path

from search import load_archive, main as crawl_main
from data_ai.rule_analysis import enrich
from pipeline_transaction import output_lock, recover_pair, publish_pair, verify_pair


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
    normalized = load_archive(input_path)
    if not normalized:
        return baseline
    # Legacy numeric IDs must be replaced with canonical URL IDs before Gemini.
    # Keep the full original article body, not the shortened rule summary.
    with tempfile.TemporaryDirectory(prefix="mapnews-ai-input-") as directory:
        canonical_input = Path(directory) / "articles.json"
        canonical_input.write_text(
            json.dumps(normalized, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent /
                                   "data_ai" / "analyze_news.py"),
             str(canonical_input), str(ai_path)],
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
            lookup[(old.get("url"), old.get("title"))] = (
                lat, lon, str(old.get("location") or "").strip()
            )
    merged = []
    for raw in rows:
        row = dict(raw)
        old_coordinate = lookup.get((row.get("url"), row.get("title")))
        region = str(row.get("location") or "").strip()
        if old_coordinate and row.get("source") == "real" and region:
            lat, lon, prior_region = old_coordinate
            same_region = (
                not prior_region
                or region == prior_region
                or region.startswith(prior_region + " ")
                or prior_region.startswith(region + " ")
            )
            if same_region:
                row["latitude"], row["longitude"] = lat, lon
                row["coordinate_source"] = "previous_map"
                row["coordinate_precision"] = "region"
                row["coordinate_note"] = (
                    "이전 지도 데이터의 지역 대표 좌표 재사용. "
                    "실제 발생 주소는 확인되지 않았습니다."
                )
        merged.append(row)
    return merged


def attach_cached_regional_coordinates(rows):
    """Read already-known regional centres without network geocoding.

    Compatible with both main's mapper and PR #16's offline cache behaviour.
    """
    from map_visualization import map_visualization as maps
    cache = maps.load_coordinate_cache()
    output = []
    for raw in rows:
        row = dict(raw)
        region = str(row.get("location") or "").strip()
        if (region and row.get("latitude") is None
                and row.get("longitude") is None):
            candidate = cache.get(region)
            if isinstance(candidate, (list, tuple)) and len(candidate) == 2:
                coords = maps.parse_coordinates(candidate[0], candidate[1])
                if coords is not None:
                    row["latitude"], row["longitude"] = coords
                    row["coordinate_source"] = "region_cache"
                    row["coordinate_precision"] = "region"
                    row["coordinate_note"] = (
                        "지역명과 일치하는 행정구역 대표 좌표입니다. "
                        "실제 사건 발생 위치가 아닐 수 있습니다."
                    )
        output.append(row)
    return output


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
    io_paths = [args.archive, args.analysis_output, args.map_output]
    if args.with_ai:
        io_paths.append(Path("data_ai/results_ai.json"))
    if len({str(path.resolve()) for path in io_paths}) != len(io_paths):
        raise ValueError("입력·출력 파일 경로가 같거나 심볼릭 링크로 겹칩니다.")
    if args.max_ai_articles < 0 or args.max_ai_articles > 1000:
        parser.error("--max-ai-articles는 0~1000 범위여야 합니다.")
    with output_lock(args.map_output):
        restored = recover_pair(args.analysis_output, args.map_output)
        if restored:
            print("중단된 이전 실행의 분석·지도 파일을 함께 복구했습니다.")
        exit_code = _execute_pipeline(args)
        if exit_code:
            return exit_code
    if args.gui:
        if not verify_pair(args.analysis_output, args.map_output):
            raise RuntimeError("분석·지도 파일의 동일 실행 스냅샷 검증에 실패했습니다.")
        command = [sys.executable, "-m", "frontend", "--json", str(args.map_output)]
        if args.offline_map:
            command.append("--offline")
        return subprocess.run(command, check=False).returncode
    return 0


def _execute_pipeline(args):
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
    from map_visualization.map_visualization import prepare_news_for_frontend
    previous_map = load_optional(args.map_output)
    baseline_for_map = retain_prior_coordinates(baseline, previous_map)
    baseline_for_map = attach_cached_regional_coordinates(baseline_for_map)
    mapped = prepare_news_for_frontend(baseline_for_map, geocode_missing=args.geocode)
    if not mapped:
        raise ValueError("유효한 뉴스가 없어 기존 지도 결과를 보존합니다.")
    # Commit the analysis + map as one recoverable transaction.
    # An atomic manifest records their shared run and file checksums.
    publish_pair(args.analysis_output, baseline, args.map_output, mapped)
    if not verify_pair(args.analysis_output, args.map_output):
        raise RuntimeError("분석·지도 파일의 체크섬이 일치하지 않습니다.")
    pins = sum(row.get("latitude") is not None and row.get("longitude") is not None
               for row in mapped)
    print(f"수집 보관 {len(archive)}건 / 분석 {len(baseline)}건 / 지도 좌표 {pins}건 "
          f"/ 좌표 미확인 {len(mapped)-pins}건")
    print(f"실제 뉴스 파일: {args.map_output}")
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
