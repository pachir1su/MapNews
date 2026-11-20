"""Audit every archived headline against evidence-based location rules.

No network, Gemini or Nominatim calls are performed. The output is an
inspectable article-by-article CSV and JSON summary. Cache hits are regional
centres, not independently verified incident positions.
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from search import load_archive
from data_ai.rule_analysis import RULE_VERSION, enrich, locate

# Historical baseline is diagnostics-only; it is not used to decide locations.
OLD_REGIONS = (
    "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시",
    "대전광역시", "울산광역시", "세종특별자치시", "경기도",
    "강원특별자치도", "충청남도", "충청북도", "전북특별자치도",
    "전라남도", "경상남도", "경상북도", "제주특별자치도",
    "서울", "부산", "대구", "인천", "광주", "대전", "울산",
    "세종", "경기", "강원", "충남", "충북", "전북", "전남",
    "경남", "경북", "제주",
)
OLD_REGION_RX = re.compile(
    r"(?<![가-힣])(" + "|".join(map(re.escape, OLD_REGIONS))
    + r")(?:\s+([가-힣]{1,12}(?:시|군|구)))?"
    + r"(?:\s+([가-힣]{1,12}(?:구|군)))?"
)
OLD_CITY_RX = re.compile(
    r"(?<![가-힣])([가-힣]{2,9}(?:시|군))(?=\s|[·,에서의]|$)"
)


def old_location(title):
    match = OLD_REGION_RX.search(title)
    if match:
        return " ".join(x for x in match.groups() if x)
    match = OLD_CITY_RX.search(title)
    return match.group(1) if match else ""


def audit(archive, cache):
    """Audit all rows independently; no side effects or external lookups."""
    results = enrich(archive, [])
    records = []
    kinds = Counter()
    old_positives = old_hits = new_hits = 0
    for source, article in zip(archive, results):
        title = str(article.get("title") or "")
        region, evidence = locate(title, source.get("summary") or "")
        old = old_location(title)
        old_positives += bool(old)
        old_hits += bool(old and old in cache)
        new_hits += bool(region and region in cache)
        kinds[evidence] += 1
        records.append({
            "id": article["id"], "title": title, "url": article.get("url") or "",
            "location": region, "evidence": evidence,
            "cache_hit": bool(region and region in cache),
            "previous_location": old, "previous_cache_hit": bool(old and old in cache),
            "category": article.get("category") or "",
        })
    summary = {
        "rule_version": RULE_VERSION,
        "article_count": len(results),
        "legacy_title_matched": old_positives,
        "legacy_exact_cache_hits": old_hits,
        "new_title_or_lead_matched": sum(bool(x["location"]) for x in records),
        "new_exact_cache_hits": new_hits,
        "cache_keys": len(cache),
        "evidence_counts": dict(kinds),
        "quality_note": (
            "A cache hit is a coarse regional centre; it is NOT a verified "
            "incident coordinate or an accuracy/precision measurement."
        ),
        "limitations": [
            "Headline/explicit lead rules intentionally leave unclear stories unpinned",
            "No new Nominatim call was made",
            "Cached coordinates may be approximate or stale",
            "Archived news_results.json and old map_results.json need not share an input run",
            "Cached analysis outputs are refreshed by rule_version in the application",
        ],
    }
    return summary, records


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "news_results.json")
    parser.add_argument("--cache", type=Path,
                        default=ROOT / "map_visualization/.geocode_cache.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "test-artifacts/location-audit")
    args = parser.parse_args(argv)
    archive = load_archive(args.input)
    if not archive:
        raise ValueError("유효한 저장 기사가 0건입니다.")
    if args.cache.exists():
        with args.cache.open("r", encoding="utf-8-sig") as stream:
            cache = json.load(stream)
        if not isinstance(cache, dict):
            raise ValueError("좌표 캐시는 JSON 객체여야 합니다.")
    else:
        cache = {}
    cache = {
        name: value for name, value in cache.items()
        if isinstance(name, str)
        and isinstance(value, (list, tuple)) and len(value) == 2
        and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                for x in value)
    }
    summary, records = audit(archive, cache)
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "summary.json").open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
    with (args.output / "articles.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    print(
        f"전수조사: {summary['article_count']}건 / "
        f"기존 규칙 지역 {summary['legacy_title_matched']}건 "
        f"(캐시 {summary['legacy_exact_cache_hits']}) / "
        f"수정 규칙 지역 {summary['new_title_or_lead_matched']}건 "
        f"(캐시 {summary['new_exact_cache_hits']})"
    )
    print(f"증거 유형: {summary['evidence_counts']}")
    print(f"기사별 CSV 및 보고서: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
