"""Export team news to the existing frontend JSON format.

This adapter does not modify crawler, AI, or map-visualization source files.
"""
import argparse
import json
import os
import tempfile
from pathlib import Path

from frontend.models import parse_news


def export_news(input_file: Path, output_file: Path, prepare) -> tuple[int, int]:
    """Prepare rows, validate their frontend shape, and atomically export JSON."""
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

    count = sum(item.has_coordinates for item in batch.items)
    return len(output), count


def main() -> int:
    parser = argparse.ArgumentParser(description="MapNews 분석 결과를 지도 입력 JSON으로 변환")
    parser.add_argument("--input", type=Path, default=Path("data_ai/results.json"))
    parser.add_argument("--output", type=Path, default=Path("test-artifacts/team-news.json"))
    args = parser.parse_args()

    try:
        from map_visualization.map_visualization import prepare_news_for_frontend
    except ImportError as exc:
        parser.error(
            "팀 지도 시각화 모듈과 geopy, folium 설치가 필요합니다. "
            "팀 코드를 병합한 작업 디렉터리에서 실행하세요. "
            f"원인: {exc}"
        )

    total, mapped = export_news(args.input, args.output, prepare_news_for_frontend)
    print(f"뉴스 {total}건 저장 / 좌표 확인 {mapped}건 / 파일 {args.output}")
    print("시연용 가상 데이터를 쓰는 경우 실행할 때 --mock-json을 붙이세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
