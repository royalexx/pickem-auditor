# Phase 7 research-only execution

Read REPORT.md, RUNBOOK.md, PROTOCOL.md and INTEGRITY_AMENDMENT.md first. Real source-qualified F remains blocked; P1/P2 are unfitted. New game-day pilot captures and settlements have not happened. No scheduler is provided.

Requirements: Python, NumPy/SciPy (original scientific byte replay uses NumPy 2.3.5 / SciPy 1.17.0) and `pdftotext`/Poppler for official PDFs. The current Cloud runtime has it; the tested Deepnote Basic image does not. Public ESPN/NBA acquisition needs no key. This runner does not acquire new PropLine offers.

Reproduce in a clean checkout with the warehouse pin and preserved original sources:

```bash
git fetch --depth 1 origin 97a8bb566826afe5a3e5a7b8c632043d8a1dca24
OPENBLAS_NUM_THREADS=1 python -B -m research.nba_joint_v01.reproduce --output work/phase6_baseline
OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase6.run --output work/phase7_phase6_replay_new
OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase6.validate --results work/phase7_phase6_replay_new --output work/phase7_ws4_validation_new.json
OPENBLAS_NUM_THREADS=1 python -B -m unittest discover -s tests/nba_phase7 -v
OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase7.smoke --output work/phase7_fixture_new
```

Use new exclusive paths. Compare scientific hashes/score bytes; runtime/head metadata may differ. The Phase 6 runner deliberately requires a PASSED `work/phase6_baseline/reproduction_check.json` first. Original artifacts are never overwritten.

For an actual registered slot, use the precise date/time and command in RUNBOOK.md, or `bash research/nba_phase7/manual_capture.sh 1` for slot 1 at its acquisition window. The wrapper refuses early/late invocation, identity/schedule changes and duplicate captures. It preserves first source/ledger versions even when forecasting abstains. Do not substitute another game. A failed persistent acquisition claim is retained for inspection before any separately versioned recovery; no silent automatic retry/replacement exists.

The only declared numeric participation assumptions are fixture probabilities. Real Available/starter/membership never becomes probability one. P0 verified-Out exclusions remain separate from eligibility and calibrated positive participation; P1/P2 and real F stay blocked. The underlying J2 engine, M0 and event model are unchanged.

`settlement` independently fetches a matching canonical ESPN NBA FINAL source after an original captured game; it never converts absent players to DNP, voids to pushes, or DNPs to losing Unders. Unsupported periods, missing original terms, wrong identities and schedule changes block. League-native parity and external review remain separate gates.

`initial_team_label_audit/` preserves superseded metadata with an erroneous narrative team name. Use `source_identity_audit/` for final source conclusions. Both fixture directories are explicitly synthetic; the final validation receipt is fixture_validation_final/receipt.json. Never mix them with pilot game-day evidence.

Rollback: close the separate stacked draft and stop Phase 7 calls; if ever merged as research, revert its isolated modules and optional WS1 capture parameters to pinned parent 4f509d4b9817a130ab78e2d24a03321459cb452d while preserving original evidence. No deployment or schedule reversal is required.
