# NBA Phase 6 — opt-in opportunity diagnostics

Read REPORT.md, PROTOCOL.md and INTEGRITY_AMENDMENT.md first. Final results are only results/. The partial oracle outputs in quarantined_incomplete_oracle/ are unsafe and superseded; never pool them into final C metrics. No certified pregame forecast or model adoption is delivered.

From the repository root, restore the exact parent/warehouse source manifests and reproduce the frozen baseline before scoring:

```bash
git fetch --depth 1 origin 97a8bb566826afe5a3e5a7b8c632043d8a1dca24
OPENBLAS_NUM_THREADS=1 python -B -m research.nba_joint_v01.reproduce --output work/phase6_baseline
OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase6.run --output work/phase6_reproduction_new
OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase6.validate --results work/phase6_reproduction_new --output work/phase6_validation_new.json
OPENBLAS_NUM_THREADS=1 python -B -m unittest discover -s tests/nba_phase6 -v
OPENBLAS_NUM_THREADS=1 python -B -m unittest discover -s tests -p 'test_nba_joint*.py' -v
```

Use fresh exclusive output paths. The original baseline path work/phase6_baseline is a deliberate run precondition; the Phase 6 runner refuses a missing/failed reproduction receipt. No model is refitted during the Phase 6 arm experiment. All original model bytes and original raw M0 arrays remain fixed. Timing and executed-head metadata can differ; compare scientific scenario and score hashes. NumPy 2.3.5 and SciPy 1.17.0 are required for the original local float-hash replay.

`roster.build_roster_contract(folder, model)` reads an existing WS1 capture folder and replays its exact raw bytes. It cannot infer unknown participation probabilities or turn a season roster into legal game eligibility. `require_forecast_ready` remains blocked while complete eligibility and a validated participation method are absent.

The optional `simulate(..., research_minutes=...)` keyword accepts only historical/synthetic conditional M0/J2 diagnostic injections. It rejects prospective use, wrong parent hashes, invalid arrays, inactive exposure and infeasible oracle witnesses. D skips automatic full-rotation acceptance explicitly; the unchanged public rotation audit still rejects D. Both C and D are refused by normal forecast export. Existing default behavior has exact unchanged baseline hashes.

Original future schedule registration and current-source probes are preserved evidence. Do not rerun them to replace original receipts. The existing WS1 manual capture remains the sole capture path for a legitimate future game-day attempt; there is no new automation. The pilot has ten future slots but no completed future observations. Never backfill.

Rollback: close the separate stacked draft and stop invoking the isolated package; if later merged as research, revert Phase 6 commits only. Preserve all original and quarantined artifacts. No production migration exists.
