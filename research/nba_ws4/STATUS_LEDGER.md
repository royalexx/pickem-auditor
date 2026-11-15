# NBA WS4 status ledger — November 15, 2026

Governing: `PA-V25-MASTER-2026-11-09 / v1.1`; bounded Phase 1/1.5 research.
Base: `912bc7010058092ea735dcda0aa941429194474b`.
Branch: `audit/v25-nba-ws4-validation-20261115`.

| Deliverable | Status | Receipt |
|---|---|---|
| Original benchmark | independently replayed | original_replay_v2.json; scored_v3/scores.json |
| Single-contract semantics | implemented / tested; standalone | evaluator.py; 33 WS4 test methods |
| Chronological evaluator / denominators | implemented / tested | protocol universe, per-model ledgers, original_attempt_ledger.json.gz |
| Multi-model source matching | independently replayed | CSV and 145-contract shared control support |
| Calibration framework | implemented / tested; improvement blocked-by-data | calibration.py; no earlier authentic OOF dates supplied |
| Adversarial controls | tested | 84 targeted tests including 33 WS4 methods and mutation subtests |
| Joint readiness interface | implemented / tested fixture | versioned specification and synthetic JSON fixture |
| Integration acceptance | blocked-by-data for actual new workstreams | acceptance_matrix.json |
| Draft PR / SHA / rollback | review-only | Draft PR and external handoff receipt; PR_BODY.md |
| First next-engine experiment | proposed, research-only | NEXT_EXPERIMENT.md; single-market points likelihood comparison |

No scientific promotion or accepted release. The new audit implementation still
needs external code review. The report-pin mismatch is an unresolved FAILED gate.
No original forecasts, source archives, schedules, production policy, WS1/WS2/WS3
modules or posteriors were changed. Close the draft and stop calling this package
for rollback; if later merged as research tooling, revert its audit commit.

Full offline regression after CI compatibility repairs: **1,644 tests pass, nine skipped**; optional PyMC/NUTS sampling was absent. The initial CI run exposed a missing optional calibration dependency and a historical source-label text-scan conflict. Isotonic now uses weighted SciPy PAVA; the original attempt ledger is stored in verified lossless gzip. No workflow/production rule was changed. See `evidence/full_offline_execution.json` and `evidence/attempt_ledger_archive_receipt.json`.
