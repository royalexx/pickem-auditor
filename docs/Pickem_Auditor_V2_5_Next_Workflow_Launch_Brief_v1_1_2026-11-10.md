# Pick’em Auditor V2.5 — Next Workflow Launch Brief (v1.1)

**Document ID:** PA-V25-LAUNCH-2026-11-10  
**Version:** 1.1, 2026-11-10 — **supersedes** `Pickem_Auditor_V2_5_Next_Workflow_Launch_Brief_2026-11-09.md` (v1.0).  
**Governing source of truth:** [`Pickem_Auditor_V2_5_Master_Implementation_Plan_v1_1_2026-11-10.md`](Pickem_Auditor_V2_5_Master_Implementation_Plan_v1_1_2026-11-10.md).  
**Status:** Actionable instructions; **not** a claim that Phase 0R is closed, Phase 1.5 is independently validated, or any model is promoted.  
**Execution owner:** ChatGPT-controlled engineering workflow; no GitHub coding agents. Keep legacy forecasts, paused NUTS artifacts, historical source/settlement ledgers and the old model comparison chart.

## 1. What changed since the v1.0 brief

The next workflow is **not** a demand to complete an inventory, all fixes, a live dry run, and an adversarial signoff in one session. It starts with a bounded **Phase 0R-A diagnostic**, followed by targeted 0R-B repairs. In parallel, retain as much trustworthy prospective quote/source evidence as possible without falsely certifying it. A new **mandatory Phase 1.5** must characterize directional and opportunity-model errors, quantify Tier statistical power, and decide which limited Phase 2/3 challenger is worth building. **Phases 4–8 are earned research options**, not committed sequential implementation.

Three logically distinct claims must never be conflated:

1. **Engineering integrity:** point-in-time reproducible, properly certified pregame forecasts.
2. **Predictive accuracy:** improvements on matched chronological proper scores against simple baselines, with game/date-clustered uncertainty.
3. **Economic edge:** prospective performance at real, compatible and timestamped sportsbook offers, with full payout semantics and valid market comparators.

A synthetic-line historical Brier improvement is neither a pregame certification nor proof of economic edge. An oracle substitution involving actual game exposures is a postgame diagnostic, never an available pregame feature.

## 2. Verified-to-date checkpoint — reconcile with the live state

**Phase 0R (November 9 recorded checkpoint, not live verification):** The recorded run had **1,490 generated forecasts, 0 certified**, and **1,387 accepted vs 658 rejected quote observations**. Some captured items lacked event IDs; invalid/missing `input_freeze_at` and `model_training_cutoff_at` provenance were also identified. Do not assume each forecast has only one failure code, or that quote rejection is the same as forecast-certification rejection. Reconcile recorded counts to fresh artifacts before coding.

**Phase 1.5 implementation (November 10):** Dedicated branch `chatgpt/phase15-error-power-diagnostics-20261110` was verified with HEAD **`aad99119283c154a9d8d5b7327fe52336dbe2b6a`**. It includes:

- `scripts/phase15_diagnostics.py`: read-only paired probability/side error scoring, cluster-bootstrap summaries, optional offline four-factor Shapley oracle decomposition, and exact fixed-n Tier power calculator.
- `tests/test_phase15_diagnostics.py`: **19/19** adversarial unit tests passed in a detached Deepnote execution.
- `docs/PHASE_1_5_DIAGNOSTICS.md`: methodology, limitations, command examples and stop/go framework.
- Unscheduled Deepnote notebook **“V2.5 Phase 1.5 — frozen error decomposition and tier power (shadow only)”**; completed research run, saved output `pickem_runs/phase15_20261110/frozen_2024_diagnostic_receipt.json` (verify its presence and SHA).

**First 2024 archival result:** **107,319** synthetic-line contracts examined; **71,009** matched/scored, **36,310** `UNMATCHED`; **272** games, **18** weeks. Frozen diagnostic Brier: **0.1928184** vs historical baseline **0.1951962** (paired difference **−0.0023778**). Selected **Under 92.8502%** of scored contracts. Mean predicted Over **0.278598** vs observed Over frequency **0.312425**, i.e., signed Over-calibration residual **−0.033827**. These are descriptive historical *synthetic-line* results, potentially exposed to model-development decisions. This does **not** prove real-market performance, independent holdout validity, or a causal error source. The original 4-component pregame forecasts were **not available** to the initial oracle diagnostic.

**Do not report the branch as merged to `main` or Phase 1.5 as independently validated** without fetching its current PR/commit state and passing the audit. None of these checkpoints authorizes Tier 1/2 publication, a NUTS restart, or the disabled afternoon publishing schedule.

## 3. Session 1 — Phase 0R-A diagnosis only

**Primary objective:** Identify the smallest set of source/contract/provenance defects responsible for the recorded 0/1,490 certification outcome, plus an **independent** root-cause distribution for the 658 rejected market quotes.

### Required inspection sequence

1. Fetch `main` HEAD, open/merged Phase 0/0R PRs and the Phase 1.5 branch; inspect exact implementation and actual active schedules/Deepnote notebook revisions before treating old reports as current facts. No assumptions from test-count summaries alone.
2. Read the November 9 archived forecast list, certification outcome ledger, original input/source and model cutoff receipts, quote acceptance/rejection ledger, and available network/provenance logs. Compute SHA-256 hashes and record source artifact paths; if files are unavailable, mark the precise blocker.
3. Build a row-level table of certification failure codes, **counts per code**, number of failed rows, co-occurrence intersections, distinct event/game/player/market identities, failures by producer/consumer stage, and top upstream root causes. **Do not sum overlapping codes as distinct failed forecasts.** Reconcile 1,490/0 with any current live reruns without rewriting old counts.
4. Independently classify the **658 quote rejections** by reason (identity, timestamp, unsupported market, stale, duplicate, invalid terms, missing source, parse failure, or observed actual codes). Reconcile provider observations against 1,387 accepted; do not silently discard or merge rejected quotes with forecast failures.
5. Make a bounded **go/no-go** decision: name the first one or two repair tickets with exact call sites, tests and expected measurable coverage recovery. Include rollback and failure-state preservation. Do not undertake a broad speculative refactor before the data inventory.

**First-session deliverables:** `phase0r_state.json` or equivalent verified ledger, forecast failure-code and intersection counts, distinct quote-rejection reason counts, repository/Deepnote/schedule inventory with SHA/commit receipts, and prioritized 0R-B repair ticket(s). A legitimate live dry run is **not required** in this diagnostic-only session.

**If critical archived data cannot be retrieved:** report which inputs, source references, permissions or original receipts are absent and exactly which prospective capture steps would unblock analysis. Never invent failure percentages, validate with postgame proxies, or certify history retrospectively.

## 4. Parallel prospective capture — time-sensitive, fail-closed

This can proceed without waiting for Phase 0R-A or all certification fixes. Preserve original immutable **real quote** text/terms, source availability and observed times, event/game/team/player/stat/period/line identity, provider and product/payout terms, training cutoff, forecast freeze, model predictions, and optional pregame component forecasts where they are genuinely produced. Include **accepted and rejected** quotes, eligible-but-not-modeled, explicit abstentions, pushes/voids and later official settlement. Complete market comparison still requires **compatible two-sided prices/de-vig and payout rules**; do not fabricate missing odds.

An item without all mandatory certification lineage remains **`UNCERTIFIED/SHADOW`**. Captured raw evidence is useful for later investigation, but post-event reconstruction may not retroactively establish that the original pregame information existed. If there is no accessible pregame window, save a clear blocked-state packet, do not manufacture a live acceptance run, and use the next legitimate available event.

## 5. Parallel Phase 1.5 independent validation — existing code, not a rebuild

Perform the following against the **existing, isolated** branch and original source artifacts; preserve production configurations and NUTS archives:

1. **Reproduce and challenge the archived run:** verify input SHA, cohort counts (107,319 total, 71,009 scored, 36,310 unmatched), 272/18 clusters, contract uniqueness, original baseline matching, probability/settlement semantics, signed Over residual and side-conditional calibration. Re-run 19 tests and audit implementation for missing checks, not just successful fixtures. Validate the 2024 data provenance and model-development/selection exposure.
2. **Adversarial code/math review:** tamper outcome labels, swap Over/Under sides, duplicate lines, corrupt game IDs, introduce naive/postgame timestamps, change selected-vs-eligible membership, and verify the exact fixed-n binomial tail/power numbers independently. Validate game- and week-clustered bootstrap algorithms, random seeds and completeness denominators; these are *descriptive*, not promotion-grade statistics.
3. **Investigate material loss sources:** quantify errors in team pass volume, role/participation, player share allocation, conditional efficiency, zero/tails, signed directional calibration and top-k selection *only where legitimate pregame components and settled outcomes actually exist*. Explicitly mark **unmeasured** factors. Oracle/Shapley replacements may use realized values **only inside postgame diagnostic scoring**; they are neither causal attribution nor attainable forecast gains. Normalize errors within market definitions before ranking mechanisms.
4. **Tier statistical power:** verify exact one-sided fixed-n planning counts for null→true hit rates of 70→80 (**119**), 75→80 (**437**), 80→85 (**365**), 85→90 (**281**), 90→95 (**179**), assuming α=0.05, 80% power, independent prespecified Bernoulli outcomes. Add planned event-frequency, actual date/game dependence, repeated-looks and multiple-tier adjustments as data become available. **Raw prop count ≠ effective sample size.**
5. **PR and merge gate:** prepare/review the existing Phase 1.5 branch diff and acceptance receipt; merge only after issues are resolved and the appropriate repository test suite passes. Document the actual resulting commit and rollback path. No automatic model promotion from an infrastructure merge.

**Missing-input recovery:** No verified archived four-factor pregame forecasts were supplied for the first run. Implement or specify only the *minimal prospective immutable factor capture* needed to observe team volume, participation, share and efficiency under the Phase 0R time contract. Until authentic data exist, classify structural opportunity decomposition as **blocked-by-data**, not finished, successful or estimated from postgame boxes.

**Phase 1.5 exit:** independently reproducible directional and power receipts; documented evidence gaps; complete status/coverage ledger; validated factors *or* an explicit blocked-by-data/instrumentation handoff; and a written Phase 2/3 **invest/defer/retain simple baseline** decision. The current 19/19 tests and archived run alone do not satisfy scientific completion.

## 6. Sessions 2+ — targeted repairs, Phase 1 baseline, earned modeling tickets

**Phase 0R-B:** Patch verified dominant failure paths in event identity, `input_freeze_at`, `model_training_cutoff_at`, original source and quote receipts, duplicate/idempotent execution and relevant runtime dependencies. Run time-travel/property regression suites; capture one *legitimate future* pregame dry run if feasible. Keep every failed row and quote in denominators. Phase 0R closes only when every row labeled certified has proven pregame/event/model/contract integrity, no invalid certified rows exist, and the live record actually demonstrates the rule—**not** just unit tests.

**Phase 1:** Reconcile, implement and validate canonical distribution/probability contracts and a deterministic rolling-origin evaluator that preserves the frozen 60/40 baseline, Engine A/B, Bayesian A/B, strict NUTS, market (when valid), and the familiar comparison chart. Historical 2024 synthetic lines are for distribution diagnostics; actual offerings and prospective data alone support market-relative evaluation.

**Phase 2/3:** Read the signed Phase 1.5 error-priority report **before** deciding the first model. If team-volume error dominates, pilot an inexpensive market-optional team opportunity model; if participation/role dominates, pilot role uncertainty; if allocation dominates, compare simple DM/independent-count allocation with logistic-normal; if efficiency or tails dominate, prioritize conditional distributions; if calibration/selection dominates, improve those first. Document matched proper-score gain, uncertainty, cohort integrity, and costs. **Do not build a logistic-normal allocator merely because it is described in the original V2.5 specification.**

**Phases 4–8:** Individually conditional. A joint simulator can earn investment for preregistered *joint-event/dependence* improvements without a single-leg Brier gain, but it cannot claim single-leg sportsbook edge on that basis. Market conditioning, robust decisions, NHL/NBA extensions, and advanced AI models must each pass their own evidence and cost gates. Small, cheap data collection for NHL/NBA can continue in parallel; no automatic training campaign.

## 7. Per-ticket evidence standard and operating restrictions

For high-stakes certification or release candidate changes: record code/branch SHA, frozen input/output hashes, exact scope and cohort, missing/unmatched/rejected denominators, proper score and uncertainty, adversarial test results, independent check and rollback receipt. Prefer executable canaries and immutable hash controls over narrative self-review. For small **shadow-only** prototypes, use a lighter bounded experiment card with clear no-release status; full review occurs before any accepted release or investment gate.

**Hard prohibitions:** no GitHub coding agents; no paid-data dependency; no prior prediction rewriting; no postgame exposure in pregame features; no retroactive quote/certification fabrication; no high-confidence Tier publication before preregistered prospective reliability; no unapproved historical NUTS restart; no silent afternoon automation reactivation; no overwrite of frozen V1 comparisons. If no authentic market comparator exists, `p_market` and payout-aware edge remain unavailable.

## 8. Final handoff contract

End the first working session with only defensible state transitions: `implemented`, `tested`, `independently verified`, `blocked-by-data`, `shadow-only`, `rejected`, or `release-approved` with precise proof for the last two. Cite the actual commit/PR and original Deepnote source receipts, not presumed status. State which of 0R, 1 and 1.5 is open, which specific gate is blocking Phase 2 investment, and the next bounded ticket. **“Code complete” and “scientifically validated” remain separate statuses.**

---

**Change control:** All numerical checkpoint statements above were derived from the November 9/10 recorded artifacts or prior execution report. They are **not newly re-certified current production state**. This brief adopts Phase 1.5 into the roadmap while maintaining every original source/lineage and rollback safeguard in the v1.0 master plan.