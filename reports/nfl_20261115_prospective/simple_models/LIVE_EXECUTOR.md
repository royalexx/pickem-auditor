# Sunday WS2 prospective activation

Authority: PA-V25-MASTER-2026-11-09 / v1.1 and explicit WS2 Sunday execution instruction. Research only. Existing model configurations and production policy unchanged.

`scripts/nfl_ws2_live.py` consumes the corrected native HANDOFF_PIN (required source file SHA-256 `5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71`). It makes no provider requests. Every candidate, including rejected sources, remains in the population. An unavailable feature packet yields a real-source abstention ledger, never a numerical forecast. No historical research result is relabeled prospective.

Command (source-root is the shared original report directory):

```
python scripts/nfl_ws2_live.py --source-root /datasets/_deepnote_work/reports/nfl_20261115_prospective --out-root /datasets/_deepnote_work/reports/nfl_20261115_prospective/simple_models/live
```

Each invocation creates an exclusive timestamped directory; INDEX.json is the final commit marker. Forecast rows and index are never overwritten. Index reports per-model, per-market and per-kickoff coverage, failures, input and output SHA-256, real creation and freeze times, code commit and module hashes. Original candidate dictionaries retain individual provider/book/stat/line/quote timestamps. Runs after kickoff abstain for that game, preserving later games. Freezing every remaining kickoff window now is permitted; later runs append without editing earlier ones.

## Supported normalized feature interface (awaiting WS1 real table verification)

The consumer accepts `source_control/FORECAST_FEATURE_PIN.json` with `source_manifest_sha256` and `feature_packet: {path, sha256}` relative to the shared report root. The hash-bound packet has `owner: workstream1`, timezone-aware `input_freeze_at` (actual feature freeze), `model_training_cutoff_at`, `contracts`, `players` and optional original `controls`.

Each contract binding contains `candidate_id`, `original_candidate_sha256` (SHA-256 of sorted compact UTF-8 JSON without newline), and original as-of `role`. Each player observation contains `player_id`, `player_id_namespace` matching the canonical candidate (or a WS1-verified crosswalk applied upstream), `event_id`/`game_id`, `team`, `stat`, `period` (`full` or `full_game`), `position`, `role`, `game_end_at`, original `available_at`, actual `source_received_at`, `appearance` and `value`. Only `appearance: appeared` contributes to likelihoods. Unknown/DNP values never become zero. Per-row end/availability/receipt timestamps must precede the real historical cutoff. No schedule-plus-hours availability reconstruction is accepted.

WS1 may publish a different native table schema. This normalized interface is implemented and tested, but is **not yet a verified adapter to the forthcoming native tables**. Inspect and adapt the consumer to actual WS1 files before claiming real forecast execution. No feature pin has been invented by WS2.

Controls, if originally present, must bind the exact original candidate hash, original forecast timestamp and frozen production version, and carry q_over/q_under/q_push. Missing controls affect only S6/S7. S6 has null push and moments when threshold-only probabilities do not identify them.

## Verification

55 targeted tests currently pass (existing mathematical/adversarial tests plus native executor regression tests). These are software checks, not real forecast evidence. A numerical integration forecast remains blocked until WS1 supplies legitimate historical player identities, roles, observations and a real feature freeze. Old archives currently inspected use nflverse IDs versus canonical ESPN IDs and contain retrospective availability conventions. They are not silently admitted.

Rollback: remove the standalone executor; no production, calibration, NUTS, Tier or source changes are made. PR #132 remains a draft. No outcome or performance claim is authorized.
