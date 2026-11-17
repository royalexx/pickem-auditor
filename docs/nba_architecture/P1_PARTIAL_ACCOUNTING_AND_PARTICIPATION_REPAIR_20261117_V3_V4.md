# P1 partial accounting and nonparticipation repair v3/v4

Authority: PA-V25-MASTER-2026-11-09 / v1.1. These additive owner repairs follow further pre-P6 implementation quality-control findings. They do not supply authentic source admission or amend accepted G0. Earlier owner heads, failed probes, raw sources and v1/v2 reports remain unchanged. Current source/test digests are versioned below; older manifests bind their own exact tested source commits.

## F-P1-NATIVE-04: necessary partial-source accounting

At owner head `b745b048f3ea871419272aee4c16798f455ee091`, P1 `_stats` accepted incomplete but impossible count sets such as `points=1, threes=2`. Full equality checks did not close absent-field bypasses. P5's implementation owner identified the points/three-pointer example during cross-owner quality control. Permanent red tests further expose impossible partial point maxima, two-point makes versus attempts, rebound components and combination minima. All inputs and fitted examples remain synthetic.

Source fix `c1d669f7b8091cf6b632a4f34a3b91e6c93b5205` retains unknown fields and enforces only necessary constraints from known nonnegative counts. Known field-goal/three-point/free-throw contributions impose point minima; known makes/attempts and free throws impose finite maxima when possible. Three-point makes cannot exceed total attempts; two-point makes cannot exceed two-point attempts. Known rebound components cannot exceed total rebounds. A combination cannot be smaller than its known components, while complete components still require exact equality. Valid incomplete counts remain accepted; no missing attempt/count is invented. Existing error codes and full arithmetic assertions remain.

Nine new tests preserve the failing inputs and verify raw native export, historical builder and vault rejection before publication, plus legitimate partial and full positive controls. The before/after logs are in `p1_partial_accounting_20261117_v3/`.

## F-P1-NATIVE-05: contradictory native nonparticipation

The orchestrator preserved an exact red witness at `b745b048f3ea871419272aee4c16798f455ee091`: direct native export accepted DNP with retained positive counts and source `played=0` plus positive credits. Its nonplayed return preceded structural/source-stat validation, bypassing the history builder's stronger checks. Original input, raw source and output remain in `p1_nonparticipation_20261117_v4/orchestrator_red_b745b04.json`.

Source fix `d5cafda47a2f881a88974bfb7bcbb90372fe69c2` applies the normalized participation/minute/count invariants at shared `adjudicate_player` before any nonplayed return. DNP/unknown input requires null displayed minutes and empty retained statistics; invalid participation, booleans and nonfinite/negative played minutes reject. DNP source must explicitly say `played='0'`; unknown source must omit the flag, use null, or explicitly say `unknown`. Unknown never masks explicit played/DNP evidence. For either nonplayed state, any supplied source clock must be exactly zero and every recognized raw source count must be zero/absent. Positive credits or exposure remain quarantined, with all bytes preserved.

Played-zero remains separate: `played='1'`, zero exposure and zero counts can remain played zero. True-zero positive raw credits reject even if the caller omitted those counts from its retained subset; omission cannot hide an unresolved source contradiction. Rounded subminute reconciliation and exact rational physical decisions remain intact. P2 and P5 owners received the explicit source contract and independently implemented their consumer checks.

Eight new tests exercise direct/native, builder and vault paths with valid DNP, unknown and played-zero controls. Raw source contradictions do not become DNP or zero-filled outcomes. No record is erased or rewritten.

## Verification, publication and remaining prerequisites

At exact source commit `d5cafda47a2f881a88974bfb7bcbb90372fe69c2`, the portable runner passed **369 architecture tests, 9 preflight tests, 83 unchanged P6 controls**, plus immutable original negative probe, v3 adversarial controls and separate green-after-fix wrapper. Zero failures/errors/skips. Logs and exact commands/source SHA are retained in `p1_nonparticipation_20261117_v4/exact_d5cafda/receipt.json`. These are owner quality-control executions; independent P6 acceptance remains required. Final documentation-only owner heads are rerun and published through PR #167.

Run `python scripts/nba_p1_native_handoff_check_20261117.py --output work/p1-additional-fresh` with a fresh output directory. Versioned source/test/raw-output digests are in the v3/v4 `SHA256SUMS` files. Accepted G0 implementation, schemas and tests remain unchanged. Native export schema/shape remains v1; source-parser and history-validator digests changed and consumers were notified.

B-P1-01 and B-P1-02 remain BLOCKED for original pregame roster/availability and first-defensible clocks, dated player/team/game/trade mappings, complete official schedule/result/DNP/played-zero/unknown populations and corrections, admissible fitted priors, genuine duration/exception evidence and independent source admission. Synthetic accounting and compatibility tests do not supply those prerequisites. G2, historical fitting/evaluation/weights, NUTS restart, production, schedules, promotion and automatic merge remain unauthorized.
