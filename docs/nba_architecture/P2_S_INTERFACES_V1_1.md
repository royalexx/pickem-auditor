# NBA P2 S-family interfaces 1.1.0 and renewed G1 handoff

Governing authority: PA-V25-MASTER-2026-11-09 / v1.1. Bounded research engineering remediation of F-P2-01, not statistical promotion. Branch `research/nba-p2-s-family-g1-20261116`; parent `96d210a6100085640e7e82928ab1c864839fc454`. The commit containing this document and its raw-file receipt is the review target; the PR review request records its exact SHA without a circular self-hash.

## Disposition

| Layer | Disposition | Evidence / remaining condition |
|---|---|---|
| Duration-aware fit and source/time/identity rejection | implemented and owner-tested; engineering review-ready | 0–3 OT caps and an additional-period extension, 56-minute two-OT positive control, missing evidence quarantine |
| S0 Poisson, S1 hierarchical conditional Gamma–Poisson, S2 NB2, S3 beta-binomial | preserved; synthetic numerical testing | analytic moments, p(0), recurrence, finite mass plus survival, full-support analytic queries |
| Actual P1 generated feature transformation | deterministic on synthetic P1 output with explicit synthetic supplements | unaugmented actual P1 interface correctly blocks; no authenticated clocks/roles/durations supplied |
| Actual P3 O producer → S_O | synthetic interoperability tested at pinned owner source | unknown participation abstains; explicit played-conditional mixtures validate unchanged G0 |
| S → J distribution sidecar | implemented and synthetic-tested interface proposal | P4 owner adoption/acceptance pending; not wired into existing P4 physical event sampler |
| Historical source evidence / G1 | **BLOCKED** | zero authenticated training rows exercised; independent P6 acceptance pending |

G0 remains pinned to `59d28dc23be97de2a6a82d22be8338151e31f5b6`. Neither G0 contract code, schemas, validators, fixtures nor its tests are modified. No NUTS, weights, outcome comparison, collector, production, calibration or schedules are changed. Current main inspected at `912bc7010058092ea735dcda0aa941429194474b`; recent Actions runs inspected read-only; workflow training-pause guards remain intact. This task does not certify live Deepnote training state.

## P1 → S training source manifest v1.1

`fit` retains the exact historical row fields from 1.0: `game_id`, `player_id`, `team_id`, `stat`, `role`, `game_start_at`, `outcome_available_at`, `source_receipt_sha256`, `source_raw_sha256`, `count`, `minutes`, `three_attempts`. The exposure is a **prior completed game's** actual minutes. Three-attempt history is permitted only as a historical conversion denominator. Training cannot contain the target game and every outcome/source must be available by the model cutoff.

The source manifest is an S-side P1 handoff, outside frozen G0. It maps receipt SHA-256 to `raw_sha256`, `available_at`, `status` (`P1_VERIFIED`) and `games`. `games` maps each historical game ID to exactly:

- `overtime_periods`: nonnegative integer; bool, unknown, fractional, negative and string values fail.
- `game_start_at`: exact official historical event clock, equal to the training row clock.
- `players`: map from verified historical player ID to its historical team ID. A current team is not substituted after a trade.
- `duration_receipt_sha256`: receipt key resolving to P1-verified raw source bytes and availability. A separate duration receipt may supply only the base receipt fields. Its clock must be no later than cutoff and no earlier than the row's outcome availability.

P1 must authenticate that the named raw duration source actually establishes this game's OT count, game clock and identities. A caller-written `P1_VERIFIED` flag or a digest alone proves none of those claims. If a single receipt establishes box score and duration it may be reused; otherwise use separate receipts. All duration receipts are included in the artifact's receipt set and canonical manifest hash.

The official player cap is `48 + 5 * overtime_periods`, including additional periods without a fixed maximum. A 56-minute two-OT appearance passes the 58-minute cap. A 48.01-minute regulation appearance fails, as do 53.01 in one OT, 58.01 in two, and 63.01 in three. Missing duration fails with `HISTORICAL_DURATION_UNRESOLVED`; there is **no default OT count**. The whole requested fit pool is quarantined on any failure. The caller must retain the attempted row count and exception rather than silently filtering rejected rows and refitting a changed cohort.

`history_from_p1` in `v2/nba_s_family/integration.py` pivots P1's actual `player:<player_id>:<field>` features grouped by exact receipt and player. It maps `prior_game_id`, `historical_team_id`, requested stat, `minutes`, and `fg3a`; duplicate fields fail. It checks receipt-backed source raw hashes, game date, identity, target-game exclusion, and calls `fit` to validate clocks/exposure before returning canonical sorted rows. An annotations map keyed by the same receipt supplies exactly `player_id`, `role`, `game_date`, `game_start_at`, `outcome_available_at` (the official game date is explicit, never inferred from a UTC calendar boundary). These are explicit P1 obligations, never inferred from target outcomes, starter status, calendar midnight, retrieval clocks or eventual participation. Roles must be genuinely established prior to the applicable model cutoff. Annotations are part of resulting content-addressed training rows, not additions to G0.

### Actual P1 coverage assessment

Inspected P1 `e0b8703887d327c8d8ac34807078e75e7b59a540`, `p1_history.py`: normalized player payload has game date, IDs, historical minutes/counts, participation and starter, but **no official OT or event-start field**. Generated features have `available_at=None` and `prior_game_date_only`. They supply neither rate-model role nor genuine original availability clocks. Receipts describe retrospective retrieval; original pregame authentication remains unproven. Its strict payload validator rejects extra fields, so adding OT to its existing payload would require a P1-owned version change. This proposal uses supplementary manifests and never mutates P1 or G0 in the P2 branch.

Authenticated real histories exercised here: **0**. Source-qualified regulation/one-OT/two-OT/three-OT games exercised: **0/0/0/0**. Real projected-3PA scenario bundles: **0**. Synthetic coverage: regulation through four OT, two players, three prior games, all four S stat interfaces. P1's archive/shard inventory is not re-certified by this run, and no coverage percentage for an unavailable authenticated source cohort is invented. Actual historical fitting and historical S/O/J forecasts remain blocked until P1 supplies original duration evidence, receipt/availability clocks, role evidence and joined player/team IDs. Retrospective receipt time cannot be backdated to unblock a historical fit. Valid fitting after retrieval still cannot pretend the model existed at an earlier freeze.

## P3 → S_O

Inspected actual P3 `80dbed35f983839f962250ad1c0236061dc6ee00`. `build_opportunity(p,g,priors,model=...,seed=...,variant=...,home_team_id=...,home_team_source_receipt_sha256=...)` returns `(o, sidecar)`; pass **o** to `predict`, and g to `game_state`. P3 owns priors, participation, minutes, rotation and conserving scenario generation. S does not reinterpret projected possession opportunities as integer 3PA.

`predict` validates the unchanged G0 envelope, exact hashes, G/O IDs, weights, player/team joins and clocks. It integrates S1/S2 over the exact supplied scenario minutes and DNP mass; it never resamples O, estimates independent votes or trains O priors. Unknown participation yields `UNKNOWN_APPEARANCE_PROBABILITY` for unconditional forecasts. A caller can explicitly request `conditional_on_participation`, disclosed in the envelope. P3's hypothetical history-prior probabilities remain unknown, even though its scenarios can be sampled. S0 remains a simple per-game Poisson S_ONLY control; S3 pregame `predict` abstains until integer projected shot attempts exist.

The disposable interoperability run loads exact P3 source, not a substitute builder. It checks both abstention and played-conditional S_O output, plus a source-bound J kernel. All its inputs are synthetic. This proves callable engineering compatibility, not that P3's priors or source data have historical validity.

## S → P4/J conditional distribution proposal v1.1

`joint_conditional(fitted, pregame=..., game_state=..., opportunity=..., scenario_id=..., player_id=..., team_id=..., role=..., projected_attempts=...)` validates frozen pregame/G/O objects, cutoff, target-game exclusion and exact roster/scenario identity. It returns a sealed `nba-S-P1-P3-P4/1.1.0` sidecar: source snapshot, G/O hashes, scenario ID and canonical scenario hash, model artifact, source receipt set, cutoff, family/stat, projected exposure, PMF, tail bound and posterior parameters. DNP/zero exposure returns a point mass at zero. This is conditional on the chosen scenario, not a marginal participation claim.

For S3, `projected_attempts` must be a sealed object with exactly `schema`, `content_hash`, `basis`, `source_snapshot_sha256`, `opportunity_sha256`, `scenario_id`, `player_id`, `team_id`, `three_pa`. Schema is the integration version and basis must be `projected_shared_shot_allocation`. All identity/hash joins must match the exact call; `three_pa` must be nonnegative integer (up to the numerical safety limit 4096). J supplies this allocation **before** 3PM conversion; realized-target basis, wrong player/scenario or missing evidence fail. The returned sidecar records its hash. Hash binding is an audit trail, not proof a dishonest caller did not relabel an actual outcome: P4 owns the legitimate pre-conversion shot allocation.

`full_count_law` supplements finite G0 serialization with analytic `pmf(k)`, `sf(k)`, `mean()`, `var()` and full integer support, including arbitrarily high positive counts for Poisson/NB. S3 has exact 0..n support. The G0 list enumerates every count from zero through its retained cutoff and explicitly normalizes conditional on retained support, with omitted tail upper bound ≤1e-11 (G0 permits ≤1e-8). It does not claim an infinite array or exactly zero omitted mass. `predict` records rate-posterior SD, predictive moments, O scenario ESS, source profile/certification and tail uncertainty; these are not calibrated accuracy evidence.

P4 inspected at `b3729c53509cb063e2e451b7e4feb0ac2c6a9552`: `validate_s_rates` only accepts `NBAJointSRateAdapter/1.0.0`, `adapter_basis=synthetic_fixture`, with per-player primitive rate means. It explicitly rejects real likelihood adapters. Feeding means alone would discard S1 uncertainty and S3 conditional conversion, while independent S draws could violate P4 shot/rebound/assist accounting. **No such bridge is fabricated.** P4 must version its own consumer, retain the shared G/O draw and physical event ledgers, allocate attempts then invoke S3 conversion, and obtain independent review. The conditional sidecar is review-ready; integrated physical S/O/J execution is BLOCKED pending that owner work.

## Tests, receipts and reproduction

`docs/nba_architecture/p2_remediation_v1_1/receipt.json` contains package versions, all exit codes, exact QA pin, unchanged G0 contract raw hashes and SHA-256 for code/tests/scripts/logs. `SHA256SUMS` supplies raw-file receipts. Logs retain full per-test output. These are owner-executed results, not a new independent P6 audit.

From repository root with numpy, scipy and jsonschema installed, use a full clone containing pinned owner objects:

```bash
git fetch origin e0b8703887d327c8d8ac34807078e75e7b59a540 80dbed35f983839f962250ad1c0236061dc6ee00 31435bd571ae1b4a9b7f1e1bbf05e55cef61126f 59d28dc23be97de2a6a82d22be8338151e31f5b6
python scripts/nba_p2_remediation_evidence.py .
```

Recorded results: original S tests **22/22**, full S tests **30/30**, accepted G0 regression **267/267**, G0 plus all five pinned P6 controls **350/350**, synthetic four-stat example and pinned owner interoperability **PASS**. These suites overlap and are not 669 unique cases. No model scoring or fitted weights occur.

The exact P6 reproducer is retained byte-for-byte from audit head, including its old explanatory text. It changes minutes to 56 but supplies no two-OT witness. With the updated regulation fixture it correctly rejects with `HISTORICAL_EXPOSURE_PHYSICS`; its emitted old label is not evidence that the repaired code still has a hard 53-minute cap. New `test_p6_56_minutes_requires_two_ot_witness` supplies 2 OT and passes, then removes duration evidence and verifies explicit quarantine. Other tests cover late receipts, wrong player/team, forbidden target inputs, target-game history, invalid 3PM/3PA, future cutoff, malformed/negative/non-normalized PMF, deterministic scenario hashes, unknown participation and source-bound projected attempts. Independent numerical formulas test Poisson p0, Gamma–Poisson/NB moments, beta-binomial moments and exact p0, NB recurrence, mass plus survival, negative-count zero and nonzero right tail.

## Renewed handoff and rollback

Request independent P6 re-review at the exact new commit on PR #165, linked to F-P2-01 / #168. Request P1 acknowledgement of the supplementary duration/clock/role manifest and real evidence coverage; P3 acknowledgement of actual producer compatibility; P4 acknowledgement/versioning of the conditional distribution consumer. Owner acknowledgement is not preclaimed. Keep G1 NO-GO, G2 and downstream gates closed until source evidence and independent review are satisfied.

Rollback: revert the remediation commit on this isolated branch or close the draft PR. Preserve old audit evidence, accepted G0 and all raw logs. No production rollback is needed because production is untouched.
