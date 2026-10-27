# Unified free-source collection

Run from repository root with the interpreter containing requirements.txt dependencies:

```bash
python3 scripts/collect_workflow.py --date 2026-10-26
```

Use the actual Toronto slate date. Optional `--data-dir` selects the persistent data root.
The workflow retains nflreadpy for NFL, nhl-api-py plus NHL REST for NHL, and ESPN for NBA. Existing configured odds access remains separate; no new paid provider is required. Python wrappers do not imply a different underlying data provider.

Each invocation creates a unique directory under `data/collection_runs/` and records collection, preparation and scan exit codes. It stops on a failed stage, preserves its logs and partial artifacts, and never falls back silently to yesterday's slate. After scanning it runs structured-source research resolution and an ID-reconciled audit, saving `research_queue.json`. Inspect the research stage separately: successful collection cannot hide a blocked research audit. The output manifest provides the actual paths. Usage histories remain within the same run directory as the slate, and downstream stages use that directory as their data root. Research packets emitted by the collector remain within the run directory.

`research_required` means the commands completed, not that coverage or research passed. Inspect per-sport coverage, context status, source notes, unmatched markets, freshness and scan exclusions. Complete the research blueprint and packet audit using this run's paths. Missing sources and zero priced histories must be disclosed. Never translate a successful HTTP request or process exit into an approved pick.

Do not replace working NFL/NHL sources solely to reduce provider count. Use alternate sources only when their player/game identities, stat definitions and timestamps reconcile. Missing first-read, forced-checkdown or coverage charting stays unknown. Preserve source provenance, zero observations and correction history; never apply the same contextual event twice.

This command orchestrates existing collectors; it does not add new advanced-stat coverage, change engine mathematics, fit calibration, or settle forecasts. Scheduled shadow collection continues through scripts/jobs.py. Continue to archive its persistent history after each run. An isolated run directory is not itself durable storage.
