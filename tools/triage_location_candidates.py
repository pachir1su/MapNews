"""Evidence-first review of all automatically flagged location candidates.

Every stored news row is inspected. Flagged rows are triaged; only curated
ground-truth cases have human-checked expected locations. Never assume that
the remaining flagged rows have been personally read or confirmed.
"""
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from search import load_archive
from data_ai.rule_analysis import locate, RULE_VERSION
from data_ai.location_gold import GOLD
from tools.audit_location_coverage import audit


def review(rows, cache):
    summary, records = audit(rows, cache)
    flagged = [r for r in records if r["review_flags"]]
    golden = []
    for substring, expected, rationale in GOLD:
        matches = [row for row in rows if substring in row["title"]]
        if len(matches) != 1:
            golden.append({
                "substring": substring, "expected": expected,
                "actual": None, "status": "missing-or-ambiguous-headline",
                "matches": len(matches), "reason": rationale,
            })
            continue
        article = matches[0]
        got, evidence = locate(article["title"], article.get("summary", ""))
        golden.append({
            "substring": substring, "title": article["title"], "id": article["id"],
            "expected": expected, "actual": got, "evidence": evidence,
            "status": "pass" if got == expected else "mismatch",
            "reason": rationale,
        })
    summary.update({
        "triage_flagged_rows": len(flagged),
        "triage_unflagged_rows": len(records) - len(flagged),
        "human_labeled_examples": len(golden),
        "human_labeled_pass": sum(x["status"] == "pass" for x in golden),
        "human_labeled_mismatch": sum(x["status"] != "pass" for x in golden),
        "caution": (
            "The curated examples were manually compared to archived article leads. "
            "The flagged CSV includes unverified items; it is not a true "
            "accuracy/precision/recall estimate of the remaining archive."
        ),
    })
    return summary, records, flagged, golden


def save_csv(path, rows, fallback_fields):
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        fields = list(rows[0]) if rows else fallback_fields
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=ROOT / "news_results.json")
    parser.add_argument("--cache", type=Path,
                        default=ROOT / "map_visualization/.geocode_cache.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "test-artifacts/location-review")
    opts = parser.parse_args(argv)
    rows = load_archive(opts.archive)
    if not rows:
        raise ValueError("원본 뉴스가 없어서 분석을 중단합니다.")
    cache = json.loads(opts.cache.read_text(encoding="utf-8-sig")) if opts.cache.exists() else {}
    if not isinstance(cache, dict):
        raise ValueError("좌표 캐시는 JSON 객체여야 합니다.")
    summary, all_rows, flagged, golden = review(rows, cache)
    opts.output.mkdir(parents=True, exist_ok=True)
    for name, data in (("all_articles.csv", all_rows),
                       ("flagged_candidates.csv", flagged)):
        save_csv(opts.output / name, data, list(all_rows[0]))
    for name, data in (("summary.json", summary), ("curated_gold.json", golden)):
        (opts.output / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False),
            encoding="utf-8",
        )
    print(f"전수 조사 {len(all_rows)}건 / 추가 검토 후보 {len(flagged)}건 / "
          f"검증 사례 {summary['human_labeled_pass']}/{len(golden)}건")
    if summary["human_labeled_mismatch"]:
        raise ValueError("수동 검증 사례가 회귀되었습니다. 세부 결과를 확인하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
