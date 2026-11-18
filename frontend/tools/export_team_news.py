"""Export team news to the existing frontend JSON format.

This adapter does not modify crawler, AI, or map-visualization source files.
"""
import argparse
import json
import os
import tempfile
from pathlib import Path

from frontend.models import coordinate, parse_news


def prepare_with_cache(rows: list[dict], cache_path: Path) -> list[dict]:
    """Attach only previously verified coordinates from the team's region cache."""
    if not cache_path.is_file():
        raise FileNotFoundError(cache_path)
    with cache_path.open("rb") as stream:
        raw = stream.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("좌표 캐시 JSON이 8 MiB를 초과했습니다.")
    cache = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(cache, dict):
        raise ValueError("좌표 캐시는 지역명을 키로 사용하는 JSON 객체여야 합니다.")

    result = []
    for row in rows:
        if not isinstance(row, dict):
            result.append(row)
            continue
        updated = dict(row)
        lat = coordinate(row.get("latitude"), 90)
        lon = coordinate(row.get("longitude"), 180)
        location = row.get("location")
        if (lat is None or lon is None) and isinstance(location, str):
            cached = cache.get(location.strip())
            if isinstance(cached, list) and len(cached) == 2:
                lat, lon = coordinate(cached[0], 90), coordinate(cached[1], 180)
        if lat is not None and lon is not None:
            updated["latitude"] = lat
            updated["longitude"] = lon
        else:
            updated["latitude"] = None
            updated["longitude"] = None
        result.append(updated)
    return result


def export_news(input_file: Path, output_file: Path, prepare, *,
                require_pins: bool = False) -> tuple[int, int]:
    """Prepare rows, validate their frontend shape, and atomically export JSON."""
    if input_file.resolve() == output_file.resolve():
        raise ValueError("입력 JSON과 출력 JSON은 서로 다른 경로여야 합니다.")
    if not input_file.is_file():
        raise FileNotFoundError(input_file)
    if input_file.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("입력 JSON이 8 MiB를 초과했습니다.")

    rows = json.loads(input_file.read_text(encoding="utf-8-sig"))
    if not isinstance(rows, list):
        raise ValueError("입력 JSON은 뉴스 객체 배열이어야 합니다.")
    if len(rows) > 10000:
        raise ValueError("뉴스는 최대 10,000건까지 지원합니다.")

    prepared = prepare(rows)
    batch = parse_news(prepared, source=str(input_file))
    if not batch.items:
        raise ValueError("사용할 수 있는 뉴스가 없습니다.")
    count = sum(item.has_coordinates for item in batch.items)
    if require_pins and not count:
        raise ValueError("좌표가 있는 기사가 0건입니다. 결과를 덮어쓰지 않습니다.")

    output = [{
        "id": item.id,
        "title": item.title,
        "category": item.category,
        "location": item.location,
        "summary": item.summary,
        "url": item.url,
        "datetime": item.published_at.isoformat() if item.published_at else None,
        "latitude": item.latitude,
        "longitude": item.longitude,
    } for item in batch.items]

    output_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", prefix=".mapnews-", suffix=".json",
            dir=output_file.parent, delete=False
        ) as tmp:
            tmp_name = tmp.name
            json.dump(output, tmp, ensure_ascii=False, indent=2)
        os.replace(tmp_name, output_file)
    finally:
        if tmp_name is not None and os.path.exists(tmp_name):
            os.unlink(tmp_name)

    return len(output), count


def main() -> int:
    parser = argparse.ArgumentParser(description="MapNews 분석 결과를 지도 입력 JSON으로 변환")
    parser.add_argument("--input", type=Path, default=Path("data_ai/results.json"))
    parser.add_argument("--output", type=Path, default=Path("test-artifacts/team-news.json"))
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--coordinate-cache", type=Path,
                       help="팀 좌표 캐시 JSON을 이용해 지역별 좌표를 추가 (네트워크 요청 없음)")
    modes.add_argument("--existing-coordinates", action="store_true",
                       help="입력 JSON에 이미 존재하는 좌표만 사용")
    parser.add_argument("--allow-no-pins", action="store_true",
                        help="마커가 0개여도 뉴스 목록만 내보내기")
    args = parser.parse_args()

    if args.coordinate_cache:
        def prepare(rows):
            return prepare_with_cache(rows, args.coordinate_cache)
    elif args.existing_coordinates:
        def prepare(rows):
            return rows
    else:
        try:
            from map_visualization.map_visualization import prepare_news_for_frontend
        except ImportError as exc:
            parser.error(
                "좌표 변환 모듈이 없습니다. 팀 지도 코드를 통합하거나 "
                "--coordinate-cache/--existing-coordinates 옵션을 사용하세요. "
                f"원인: {exc}"
            )
        prepare = prepare_news_for_frontend

    try:
        total, mapped = export_news(
            args.input, args.output, prepare, require_pins=not args.allow_no_pins
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(f"뉴스 {total}건 저장 / 지도에 표시할 기사 {mapped}건 / 파일 {args.output}")
    if mapped < total:
        print(f"좌표 없는 기사 {total - mapped}건은 목록에만 표시됩니다.")
    print("시연용 가상 데이터를 쓰는 경우 프론트엔드 실행 시 --mock-json을 붙이세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
