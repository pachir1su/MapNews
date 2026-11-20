# MapNews release-readiness and location integrity audit (2026-11-21)

## Decision: v0.1.0 release NOT YET approved

Evidence: connected GitHub code and data on main after PR #15, PR #16 and PR #17 diffs, 339 archived news articles, 120 cached regional geocodes, and Linux/Windows GitHub Actions.

| Measure (same 339 stored articles) | main | PR #17 after false-positive filtering |
| --- | ---: | ---: |
| Archive rows | 339 | 339 |
| Region found in title / restricted lead | 82 | 64 |
| Exact regional cache-key matches | 17 | 46 |
| Unpinned articles | 322 | 293 |

New evidence categories: 63 explicit headline, 1 restricted lead, 2 ambiguous, 273 no evidence. A cache hit means a regional centre, not verified event coordinates; no ground-truth location labels exist to measure real precision/recall.

## Root causes and changes in PR #17

- Main rule regex matches ordinary strings such as 반드시, 대학입시, 혁신도시 and misses real shorthand names such as 하남, 안산, 강남, 태안. PR #17 introduces curated Korean administrative names, conservative boundaries, ambiguity handling and regression tests.
- Main mapper skips even existing cache if geocode_missing=False; PR #17 pipeline loads validated cache coordinates offline and marks them as approximate. Team member PR #16 independently fixes mapper caching.
- String variants 서울/서울특별시 and 충남/충청남도 prevent exact cache hits; PR #17 normalizes names.
- Main optional Gemini runner can feed legacy numeric IDs directly to AI but then join against URL-hash IDs. PR #17 normalizes the full original article before sending to AI.
- Previous map locations were reused without geographic evidence. PR #17 only reuses historical coordinates where current location evidence and existing title/URL/region support reuse.
- Frontend export discards source/content_hash/analysis_status/coordinate_note; PR #17 preserves the provenance and coordinate metadata.
- Old saved map_results.json has 341 articles and 209 pins, NOT the same source run as current 339-article archive. Do not compare these map counts as if they were one pipeline.
- Old data_ai/results_sample.json contains 3 example.com test stories incorrectly marked real. PR #16 standardizes demo source on new conversion, while historical published fixtures need separate cleanup.

## Verified tests and independent reporting

- Each new CI uses Ubuntu/Python 3.11 and Windows/Python 3.12, integration regressions, Qt native tests and WebEngine tests.
- tools/audit_location_coverage.py emits an inspectable CSV row for every stored article and JSON summary; never calls Gemini or Nominatim.
- CI generates a separate Qt screenshot from the current 339-story pipeline result at test-artifacts/latest-real-screenshots. Earlier real-screenshots are from the old 341-story map.
- Live RSS probe is advisory and a single successful request does not certify multi-day uptime.

## Unresolved release blockers and important risks

1. No verified article-to-incident-location ground truth; province/district centre is not an actual incident address. Human-reviewed location labels and error acceptance threshold needed.
2. PR #16 (mapper safety) and PR #17 are independent changes. After both merges, re-run all tests and the same-input Qt GUI, including source and coordinate metadata.
3. Multi-stage pipeline writes map JSON and analysis JSON separately. Atomic per file does not guarantee a consistent transaction/snapshot across both files.
4. GUI provider has an 8 MiB input limit vs crawler archives up to 32 MiB / 10000 news. UI filters process all items and do not implement explicit pagination; load tests and capacity strategy needed.
5. Actual Windows GPU/HiDPI GUI, network-loss recovery, online map tile policy, multi-day RSS/Nominatim and Gemini 429/503 usage all require explicit validation.
6. The public archive includes long newspaper article text (median summary roughly 865 characters and some above 8900). Review provider reuse/redistribution permissions before public packaging.
7. AI queue as a separate derived ai_queue.json, rate-limit retry state and publication metadata are still not finished.

## Release policy

Hold v0.1.0 until the above release blockers are closed with evidence. Passing CI alone does not establish correct incident places or production uptime.