# Pick'em Auditor V2.5 — Phase 0R / 1 / 1.5 implementation audit and remediation

**Audit date:** 2026-11-10 UTC.  
**Governing specification:** \`Pickem_Auditor_V2_5_Master_Implementation_Plan_v1_1_2026-11-10.md\`, Sections 3, 5, 6, and 7.  
**Execution:** ChatGPT-controlled repository and separate Deepnote read-only QA. **No GitHub coding agents.**  
**Release status:** \`BLOCKED\`. No Tier 1/2 release, profitable-edge claim, NUTS restart, or automatic slate publication enabled.

## Pinning and live repository reconciliation

- Beginning of audit: \`main=db85f795c278ef42818365d98b243428cfb153a2\`.
- [PR #94](https://github.com/royalexx/pickem-auditor/pull/94) is **merged** (Phase 1.5; original 24/24 Deepnote tests). Older v1.1 planning snapshots saying that PR was unmerged are stale.
- [PR #90](https://github.com/royalexx/pickem-auditor/pull/90) was a **draft**, not merged at audit start. A separate combined code-tree QA against Phase 0R and 1.5 passed, and six additional source-byte integrity tests were added. The shadow library was then merged at \`35559f7175b76b583a1bb0b434ad543b9ce7c7d5\`. This is an **inactive code integration**, not Phase 1 operational acceptance.
- Phase 0R PRs #79–89, #91–93 were merged. Their historical receipts confirm non-promotion. Automated morning settlement was previously active; afternoon publishing was disabled. Operational schedules require a fresh account-level verification for release decisions.
- Remediation branch: \`chatgpt/v25-early-phase-audit-remediation-20261110\`, forked from the original audit \`main\`. This branch carries only defensive checks, more precise rejection taxonomy, research diagnostic cross-checks, and documentation. It never modifies numerical ranking weights or already-frozen data.

## Phase 0R: audit against P0R-01–08

| Contract | Actual evidence | Status |
| --- | --- | --- |
| P0R-A original forecast/reject root causes | **Exact 2026-11-09 23:05 archive**: 1,490/1,490 forecasts uncertified, all first-failure code \`missing_or_imprecise_timestamp:model_training_cutoff_at\`; quotes 2,045 incoming, 1,387 accepted, 658 rejected as combined \`market_update_unverified_or_future\` | **RECONCILED** at original aggregate granularity |
| Later timeline/event defects | Later November 9 scans exposed missing event/player IDs, unverified prices and quote clocks; do not merge these different run denominators with the 1,490 checkpoint | **DOCUMENTED** |
| Older source byte integrity | 6,528 archived source objects independently SHA-checked with zero reported mismatches across 2,624 original forecast rows; current strict verifier still certified **0/2,624** because pre-evaluation numerical input pinning was not original | **VALID NEGATIVE CONTROL**, not prospective release |
| Immutable pre-evaluation input freezing | [PR #91](https://github.com/royalexx/pickem-auditor/pull/91) added isolated frozen numerical inputs, usage, original quotes, research/policy and model cutoff receipts; safe historical fallback | **IMPLEMENTED/TESTED** |
| Original quote identity versus evaluated book | Separate hashes did not prove that \`candidate.books\` matched the original archived event/book/player/stat/line/side/odds. The remediation adds \`phase0_quote_binding.bind_original_quotes\`, executed before evaluation and again by the strict certificate | **DEFECT PATCHED IN REVIEW BRANCH** |
| Event ID provenance | Original numeric candidate's event ID could be absent while the snapshot row carried an external event ID. The remediation requires the candidate event ID to be present and equal to the record's ID | **DEFECT PATCHED IN REVIEW BRANCH** |
| Quote rejection taxonomy | Historical 658 combined rejects are preserved as originally recorded; future capture now distinguishes \`market_update_timestamp_missing_or_invalid\` vs \`market_update_timestamp_after_capture\` | **FUTURE COUNTERS PATCHED; historical split not inferable from aggregate** |
| Genuine pregame live final-code run | No accepted final merged code-run demonstrates nonzero strictly certified outcomes, full original offer association, lineup/source truth and source availability before event start | **BLOCKED BY NEW PROSPECTIVE EVIDENCE** |
| Release safeguard | Historical report explicitly says \`publication_eligible:false\`; Tier 1/2 suspended; paused NUTS not restarted | **PASS — keep blocked** |

### Original quote bridge compatibility control

A **historical schema-only**, non-certifying check loaded the original November 9 source packet (2,045 source quote rows) and reconstructed 1,512 prepared candidate sides using the current preparation function. With the original collection-time cutoff, **690** candidate sides passed the exact original-book join; **822** were rejected as \`market_original_quote_after_freeze\`. This check does not certify the original predictions; it demonstrates that the new guard is able to accept source-compatible actual bookmaker rows and fail shut on later quotes. Existing November 9 forecasts remain uncertified.

Importantly, the original pre-PR83 archived forecast \`inputs\` lacked event IDs even where the wider container had them. An event ID cannot be added retroactively to make that original numerical forecast look certified.

## Phase 1: audit against P1-01–06

| Ticket | Evidence | Status |
| --- | --- | --- |
| P1-01 forecast, quote, source, distribution contracts | \`v2/contracts.py\`, \`v2/stat_registry.py\`: source/quote identity, time checks, three-way O/U/push and signed distribution support | **SHADOW IMPLEMENTED** |
| P1-02 frozen original + simple baselines | \`v2/baselines.py\` and \`v2/legacy_adapter.py\`; older archived November 9 legacy 60/40 comparisons correctly reject all final-certification-ineligible pairs rather than generating a synthetic baseline | **PARTIAL — no verified full real cohort** |
| P1-03 rolling-origin evaluation | \`v2/evaluation.py\`, \`v2/rolling.py\`, \`v2/experiment.py\` with deterministic matched scores and game/date clustering | **FIXTURE-TESTED; authentic data integration remains** |
| P1-04 score/probability/leakage tests | 27 contract tests plus 25 exit tests, and integrated Phase0R tests passed against assembled latest code | **PASS FOR COVERED FIXTURES; no full release acceptance** |
| P1-05 joint scoring | \`v2/joint_evaluation.py\`: Energy/Variogram/CRPS helpers and analytic test examples | **IMPLEMENTED; no authenticated joint scenario feed** |
| P1-06 locked 2024 protocol and holdout exposure | \`config/experiment_specs/v25_rolling_2024.json\` discloses synthetic historical lines and excludes 2025 from untouched claims | **DRAFT PROTOCOL; prospective original-source cohort missing** |
| Original source-byte verification | Added \`v2/source_bytes.py\`, \`--original-archive-root\`, and six mutation/traversal tests. A 64-character checksum without actual bytes is explicitly marked **unverified**. | **PATCHED AND INTEGRATED, shadow only** |

**No monetary edge conclusion** is permitted on historical synthetic lines. Source-byte verification itself is not proof of external publication date or original bookmaker execution. There is no accepted V2.5 Phase 1 complete experiment over genuine full eligible original quote/settlement cohorts yet.

## Phase 1.5: audit against P1.5-01–09

- Merged [PR #94](https://github.com/royalexx/pickem-auditor/pull/94) implemented \`scripts/phase15_diagnostics.py\`, \`scripts/phase15_qb_archive_bridge.py\`, test suites, documentation and Deepnote research outputs.
- Historic synthetic-line contracts: **107,319 input / 71,009 matched and scored / 36,310 unmatched**, covering 272 games and 18 weeks. Frozen model Brier \`0.1928184015\`, historical baseline \`0.1951961994\`, difference \`-0.0023777978\`. **92.8502%** of selected sides are Under. P(Over) minus observed Over rate = \`-0.03382738\`. All are diagnostic only; no live real-market advantage demonstrated.
- 2024 QB attempt bridge: **547 graded QB candidate rows across 270 games**, with **321 ungraded rows** reported. Mean QB mean \`23.9978\` versus actual \`28.8665\`; mean team attempt forecast \`35.7900\` versus actual \`35.4059\`. Two-factor Shapley reductions: candidate QB share \`107.9601\`, team volume \`45.0338\` squared-error units. This is **postgame oracle sensitivity**, not causal evidence.
- After adverse-review repairs, rerunning untouched original inputs reproduced both old results and revealed **527 QB candidate team-game groups**, **297** with multiple forecast QB candidates, zero with the sum of predicted QB attempts exceeding predicted team attempts, and zero disagreement in team-level predicted attempts within group. This points to investigating **starter/eligible-player uncertainty** rather than simplistic pool overflow. It does not validate a deployable correction or prove actual causes.
- Follow-up code rejects discordant archived \`actual_over\`, \`HIT/MISS\`, \`hit\`, \`selected_model_probability\`, nonboolean graded labels, and official QB team attempt conservation failures. Tests on the source archive remain non-promoting.
- **Independent numerical check:** the exact one-sided binomial sample sizes (alpha=0.05, power=0.80) were recalculated with SciPy's \`binom.sf\` on the five rate pairs; results match **119, 437, 365, 281, 179**. These are IID design counts; no real effective-game sample, multiplicity policy, or Tier certification follows.
- **Remaining:** genuinely frozen four-factor role/participation/share/efficiency forecasts for non-QB markets, official matched player outcomes and prospective market offers. Postgame reconstructed features must not be used to fake them. Better side-bias calibration and QB starter allocation are the lowest-complexity candidate experiments, **not promoted models**.

## Audited repairs and evidence

1. **P0R original offer-to-numeric input binding:** \`scripts/phase0_quote_binding.py\` plus edits in \`phase0_pre_eval.py\`, \`phase0r_contract.py\`, \`jobs.py\`. Tests \`test_phase0_quote_binding.py\`, \`test_phase0r_pre_eval.py\`. Immutable original quote bytes still anchored by the independently validated receipt.
2. **P0R quote rejection precision:** \`market_odds_archive.py\`, \`test_market_odds_archive.py\`. Does not rewrite old rejection codes or backfill old quote timestamps.
3. **P1 byte integrity:** \`v2/source_bytes.py\`, \`v2/contracts.py\`, \`scripts/v25_phase1_replay.py\`, \`tests/test_v25_source_bytes.py\` on PR #90. The underlying library was merged without production execution/promotion.
4. **P1.5 archived label and QB conservation:** \`phase15_diagnostics.py\`, \`phase15_qb_archive_bridge.py\`, their tests and dated documentation addendum.
5. **Read-only QA:** QA runs used detached Deepnote free Basic CPU, isolated source trees and read-only persistent mount. All named targeted suites passed; replays did not alter existing frozen source files. Integration preview on latest main plus the Phase 1 tree passed 27+25 contract/exit tests and Phase0R/Phase1.5 control tests. PR90's new byte-level suite passed 6/6. The subsequent repaired original 2024 contracts and QB replay both succeeded.

## Required remaining evidence, in priority order

**Blocker R1 — final-prospective Phase 0R certification:** Run a genuinely future pregame event using the exact current merged source and original source archive. Count all incoming quotes and excluded/accepted forecasts, verify event, player, source, market and cutoff identity, and independently rerun strict certification before game start. No historical remapping.

**Blocker R2 — full eligible cohort Phase 1:** Produce a one-command deterministic historical or prospective evaluator manifest with source bytes, exact offer identity, raw rejected and abstained contracts, 2024 validation exposure and proper-score matched baselines. No invented V1 60/40 output.

**Blocker R3 — Phase 1.5 prospective mechanism evidence:** Capture original pregame estimates of opportunity volume, participation, player share and conditional efficiency for qualifying markets and compare under chronological folds. Log missing factors as missing, not as zero or model estimates. Audit selective top-k and model calibration on real offers when available.

**Blocker R4 — statistical economic gate:** Market odds/terms, genuine same-contract no-vig comparisons where identifiable, effective cluster size, repeated-look rules, payout-aware results, and sufficiently many future slates. No Tier 1/2 promise absent this evidence.

## Decision

- **Phase 0R:** \`IMPLEMENTED / HISTORICAL_NEGATIVE_CONTROL_PASSED / NEW_LIVE_CERTIFICATION_REQUIRED\`.
- **Phase 1:** \`MERGED_SHADOW_CODE / FIXTURE_TESTED / FULL_COHORT_AND_SOURCE_INTEGRATION_OPEN\`.
- **Phase 1.5:** \`MERGED_SHADOW_CODE / REPLAY_REPRODUCED / QB_ORACLE_ONLY / OTHER_COMPONENTS_BLOCKED_BY_DATA\`.
- **Phase 2/3:** conditional cheap QB eligibility/allocation plus directional-calibration challenger after an experiment card; **no** costly new joint simulator or NUTS fit is authorized by these results.
- **Production:** no promotion, no after-the-fact certificate, no Tier 1/2 publication, no automatic retraining or afternoon schedule change.

This audit does **not** claim to have executed an independently certified real future pregame slate, measured real-money returns, or validated every statistic-specific likelihood. Those cannot be repaired by historical source edits or synthetic fixtures.
