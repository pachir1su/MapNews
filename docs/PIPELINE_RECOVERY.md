# MapNews pipeline output recovery

Run `python run_pipeline.py --skip-fetch` or the normal fetch command as before.

The pipeline now publishes its analysis and map JSON as one **recoverable pair**.
A small checksum manifest is written as the commit marker after both JSON files
are updated:

- `<map-output>.manifest.json`: run ID, timestamp, article count, both SHA-256 hashes.
- `.<map-output>.pending-transaction.json`: short-lived journal for interrupted writes.
- `.<map-output>.lock`: operating-system file lock; multiple pipeline runs cannot overwrite the same map simultaneously.
- Hidden `.mapnews-tx-*.tmp` files: staged payloads/backups, normally deleted immediately.

On startup, a pending transaction is recovered before old analysis/map files
are read. If the last manifest and both hashes confirm completion, journal
cleanup finishes; otherwise both files are reverted to backups. A failure
during ordinary publication also restores both previous output files.

**Important limitation:** Operating systems do not replace two separate files
atomically as a single operation. An unrelated consumer that reads only a
single mutable JSON file while publishing is in progress could see a newer
version. Consumers comparing analysis and map data must validate the shared
manifest using `pipeline_transaction.verify_pair(analysis, mapped)`, and
restart their read if it changes. Neither the timestamp nor one file alone
establishes a consistent pair.

`JsonNewsProvider` and the optional frontend export now accept JSON inputs up
to **32 MiB** (matching the crawler archive boundary). GUI rendering of
10,000 simultaneous news items has not been performance-certified; this size
limit change alone is not pagination or streaming.
