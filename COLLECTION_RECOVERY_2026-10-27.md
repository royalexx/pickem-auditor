# Morning collection rerun and reliability fixes — 2026-10-27

## Reproduction
- An immediate run was requested for the recurring 06:00 America/Toronto history task. Its recorded result was `no_update`, without a collection summary or updated archive.
- The restored canonical history archive's `data/handoff-summary.json` still has `collected_at=2026-10-26T21:30:16.501304+00:00`; `data/archive_manifest.json` has `slate_date=2026-10-26`.
- Running `python scripts/fetch_slate.py --preflight` in the local execution runtime failed: missing `nflreadpy`, `polars`, `nhlpy`, `nba_api`, plus DNS/HTTPS reachability failure to the NHL, ESPN, NFLverse, NBA and Odds API hosts. A credential was detectable but never printed.
- Running `python scripts/jobs.py settle --as-of 2026-10-27 --snapshots data/prop_snapshots.jsonl` initially crashed with uncaught `urllib.error.URLError` while requesting historical NBA data. No settlement updates were written.
- After the fix, that command exits 1 with a structured `SETTLEMENT_SOURCE_UNAVAILABLE` JSON error, and writes zero rows. No new 2026-10-27 source data or settlement was verified or saved.

## Fixes
1. `scripts/fetch_slate.py` now adds `feeds_ready` and `operational` to strict preflight diagnostics: NHL REST's stdlib fallback works without nhlpy; ESPN's API access does not require nba_api or stats.nba.com. The snapshot workflow can proceed when at least one sports feed and the odds feed are viable. The original strict `ok` result is unchanged for compatibility.
2. `scripts/jobs.py` now rejects a fully unavailable preflight with a specific failed-feed list instead of an opaque `preflight failed` string. It records partial preflight state in successful snapshot summaries.
3. Historical settlement now turns network/import failures into a structured `SETTLEMENT_SOURCE_UNAVAILABLE` job error, preserving existing snapshots. No outcomes are fabricated, and the job cannot return a successful zero-rows result on this exception.
4. Regression tests in `tests/test_morning_preflight_recovery.py` cover fallback viability, a total outage, missing odds, independent sport availability and settlement atomicity on a source failure.

## Still not solved by code
- This execution environment has no DNS/network access to the upstream feeds and lacks optional feed libraries. No HTTP request can be made here, so the existing history cannot be refreshed here. Do not replace the canonical history archive with an old archive bearing a new date.
- A scheduled task's `no_update` state is not proof of collection success; verify latest run logs, source counts, the actual archive timestamp and version before declaring success.

## Offline validation
- 5 new recovery regression tests pass.
- Existing collection, jobs, fetch, settlement, and history tests pass when run in focused groups.
- Complete full repository test suite did not complete within the available runtime; do not describe it as passing.
