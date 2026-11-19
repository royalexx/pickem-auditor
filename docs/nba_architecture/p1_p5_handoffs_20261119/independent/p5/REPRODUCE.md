# Reproduction

Run from repository root at exact commit `7643a100153b3dd3084e03887eb43f1f8a60be9e`, plus the review evidence files. No source network access is needed. Use fresh output directories; the CLI is create-only.

```sh
PYTHONPATH=. python docs/nba_architecture/p1_p5_handoffs_20261119/independent/p5/probe.py
PYTHONPATH=. python scripts/nba_subset_pipeline.py --capture docs/nba_architecture/p1_subset_acceptance_20261119/initial_tonight_capture --cohort docs/nba_architecture/p1_p5_handoffs_20261119/PROSPECTIVE_COHORT.json --history docs/nba_architecture/p1_p5_handoffs_20261119/prospective_inputs --through p5 --forecast-at 2026-11-19T23:18:04.957103+00:00 --output /tmp/fresh-nba-p5-replay
sha256sum -c docs/nba_architecture/p1_p5_handoffs_20261119/independent/p5/SHA256SUMS
```

The stored actual forward command was identical to the second command except it omitted `--forecast-at` and used `docs/nba_architecture/p1_p5_handoffs_20261119/independent/p5/actual_forward` as output. Its command, implementation SHA, operation label, actual clocks and complete counts are retained in `actual_forward/receipt.json`; stdout/stderr are `forward.stdout`/`forward.stderr`. Replaying the recorded clock later reproduces the wire/manifest, not a new pregame observation. Current-clock execution after event start must fail the pregame invariant and must not be claimed as forward evidence.

`public.stdout`/`public.stderr` retain the four-method public probe and raw test outcomes. `actual_manifest.json`/`actual_receipt.json` refer to the probe's earlier genuine saved P3 forecast, separately from the new current-clock CLI artifact. The complete 99-object fresh forward archive is retained under `actual_forward/archive/subset_research_audit`; its own SHA256SUMS includes all output and object files. Exact raw byte domains and hashes are recorded in each manifest. Record IDs hash canonical UTF-8 JSON with terminal LF; model hashes refer to original saved file bytes, source hashes to captured HTTP response bodies, and wire hashes to exact serialized handoff bytes.

The probe writes its small actual receipt files; copy the independent directory before rerunning if retaining those earlier operation receipts. Existing captured evidence is immutable historical evidence. Do not overwrite the published actual_forward directory.
