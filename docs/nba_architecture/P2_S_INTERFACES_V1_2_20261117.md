# P2 remediation contract 1.2 — declared cutoffs and native source inspection

Authority: PA-V25-MASTER-2026-11-09 / v1.1. This is bounded G1 engineering remediation in PR #165, based on audited P2 `7ca4269c98a27def485eaa8122ea7148cd0c2c0a`. Accepted G0 remains immutable at `59d28dc23be97de2a6a82d22be8338151e31f5b6`. The S-to-J envelope schema remains `nba-S-P1-P3-P4/1.1.0`; no G0 or public distribution semantics change.

## Correctness repairs

F-P2-02 was reproduced with the original independent v3 program. `before_p6_v3.json` retains its red case, and `before_cutoff_regression.log` retains the new paired regression's two failures. Both public `predict` and `joint_conditional` now call `validate_prediction_cutoff` before evaluating conditional laws. The rule is:

```
fitted.training_cutoff_at <= pregame.training_cutoff_at <= pregame.input_freeze_at
```

Exact equality is legal. A model after the declared P cutoff but before freeze rejects `MODEL_AFTER_DATA_CUTOFF`; post-freeze models preserve `MODEL_FIT_AFTER_FREEZE`. Positive controls cover before/equal cutoff and all four count-stat interfaces; negative controls include one microsecond late and later-but-before-freeze. Source, model-code, artifact, target-game exclusion, scenario and roster joins remain active.

The owner pre-P6 audit found an additional internal chronology gap: a reserialized synthetic fitted artifact could retain an outcome release after its own declared training cutoff while preceding the input freeze. The original admitted fit does not produce that artifact, but prediction accepted its inconsistent content. `before_artifact_chronology.json` and `before_artifact_regression.log` retain the accepted adversarial case and new red tests at the earlier cutoff repair commit. The exact code SHA in the JSON receipt is authoritative. Both entrypoints now recheck each retained training row: game start is strictly before model cutoff, released outcome is no later than cutoff and strictly after game start. An inconsistent row rejects `TRAINING_ROW_AFTER_MODEL_CUTOFF` or `TRAINING_ROW_RELEASE_CHRONOLOGY`. This validation establishes internal chronology, not source or fitted-artifact authentication.

The original F-P2-01 duration controls remain unchanged: legal 56-minute two-OT exposure is accepted under the source-specific 58-minute cap; over-cap exposure, missing duration and post-cutoff duration receipts reject. Historical fixture meanings and the original P6 probe are preserved.

## Latest native P1 export

`v2/nba_s_family/p1_native.py:inspect_p1_export(export, pregame=..., stat=...)` consumes actual P1 `nba-p1-native-handoff/1.0.0` prior exports. It independently decodes all original and ancestor raw bytes, checks their SHA-256 and capture ancestry, parses duplicate-free JSON, validates provider/game/player/team/opponent/date, finished duration and overtime, exact/display minutes, retained statistics and separate retrieval/ingestion clocks. Raw HTTP-shaped byte hashes are kept separate from normalized model or receipt digests. It preserves original source profile, participation, uncertainty, nullable clocks, role fields, source status and the entire exported object.

P1 1.0.0 has **no independent source-admission path**. Therefore structurally consistent inputs produce a lossless `BLOCKED` inspection with attempted/checked/admitted/quarantined denominators **1/1/0/1**, an empty training-row list and explicit missing prerequisites. Caller-written admission strings, role strings and optimistic availability timestamps reject. This adapter does not fit, access a vault, synthesize a role or turn a reconstruction into an original pregame capture. Its synthetic positive control proves usable structural handoff while retaining the evidence block; corruption controls prove it does not simply trust labels or hashes.

B-P2-01 remains **BLOCKED by evidence**. Required external prerequisites, owned by P1/source admission and independently reviewed by P6, are authentic prior-game duration/stat/correction bytes; first defensible availability and outcome-release clocks; dated player/team/role evidence; and admissible existing fitted artifact bytes tied to those sources and lawful cutoffs. Zero authentic fitted priors were obtained or created in this remediation. No historical fitting is authorized to fill this gap.

The earlier `history_from_p1` interface remains available for explicit synthetic compatibility and preserves its stricter absent-clock/role quarantine. Its `P1_VERIFIED` fixture label is not an authentication mechanism. No real source-admitted fit or independent G1 acceptance is claimed from either route.

## Latest P3 consumption and distribution laws

`nba_p2_latest_interop_v1_2.py` materializes exact P1/P3 code and synthetic fixtures into a disposable environment and records every copied module hash. It runs the actual latest P3 O2 producer, never a replacement model. Unknown unconditional participation remains unknown and abstains. Played-conditional S1/S2 integration uses the exact O scenario minutes, DNP states, IDs and weights. The independent synthetic reference reconstructs each NB law from raw fitted history sufficient statistics and mixes the actual scenario weights for PTS/REB/AST/3PM. No O resampling or independent stage voting occurs. S3 retains scenario-bound projected integer attempts, then fitted conditional conversion; no target realized attempts enter.

Analytical full-count support, zero mass, S1 posterior uncertainty, S2 dispersion and explicit finite serialization/tail bounds remain intact. `full_count_law` provides full-support analytic queries; bounded PMFs normalize conditional on retained support and disclose omitted tails. P4 must propagate the law or obtain independent acceptance of a controlled constrained-law contract; this P2 change grants no acceptance to a mean-only projection.

## Reproduction and receipts

Run from the P2 owner checkout:

```bash
python -m unittest discover -s tests/nba_s_family -v
python -m unittest discover -s tests/nba_architecture -v
PYTHONPATH=.:tests/nba_architecture python /workspace/work/repo/scripts/nba_p6_g1_remediation_adversarial_v3_20261116.py P2
PYTHONPATH=.:tests/nba_architecture python /workspace/work/repo/scripts/nba_p6_g1_owner_negative_probes_20261116.py P2
python scripts/nba_p2_latest_interop_v1_2.py --repo /workspace/work/repo --p1-sha 626a288c4dc9bef5e71cc8ba15d71de98ac1c151 --p3-sha 191b3f654b3a3ca7dc813edbfc9aacdf35729dff
```

For the last command, substitute fresh exact submitted P1/P3 heads for final latest-head verification; the script requires full 40-character SHAs and records them. The recorded final command in the versioned receipt identifies exactly which heads were actually tested. The old and new before/after outputs are append-only. The first integration-runner attempt omitted `nba_o_bridge.py` and failed import; its failed output and exact runner source are retained. Adding the missing actual P3 module repairs only the test harness.

All numerical fits in these commands are synthetic. No historical predictive score, historical weight fit, holdout outcome access, NUTS restart, G2 execution, deployment, schedule change or Tier promotion occurs. Tests and owner execution receipts are supporting evidence; only the separate P6 reviewer may award independent criterion or family acceptance. Rollback is an isolated owner-branch revert, preserving failed receipts and all prior audits.
