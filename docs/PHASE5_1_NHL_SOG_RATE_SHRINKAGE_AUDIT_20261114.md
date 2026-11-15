# Phase 5.1 — Registered NHL SOG S1 posterior-mean shrinkage (research-only implementation and independent audit)

**Experiment:** EXP-V25-NHL-SOG-RATE-SHRINKAGE-PROSPECTIVE-001  
**Governing document:** PA-V25-MASTER-2026-11-09 v1.1  
**Original main HEAD:** `912bc7010058092ea735dcda0aa941429194474b`  
**Research branch:** `research/phase51-sog-rate-shrinkage-prospective-20261114`  
**Preregistration commit (BEFORE implementation and first eligible target):** `abc2a5c825ec4271d2034769fc013fdee52e12dc`  
**Original spec SHA-256:** `0d6f0766e832442a2f7c8c98b0d8e853e6b53231fb52560a21cb5733fed4c876`  
**Outcome-blind protocol clarification:** `config/experiment_specs/EXP_V25_NHL_SOG_RATE_SHRINKAGE_PROSPECTIVE_001_CLARIFICATION_V1.json`, commit `24435861b0c8ff1ffaf3a4281864a0a8904e25de`. This is an append-only clarification of the already frozen original specification, not an edit or result-driven hyperparameter change.

## 1. Scientific question and locked model

S1 uses exactly the Gamma posterior parameters of the existing pregame fixed-exposure M2 model, without integrating posterior rate uncertainty.

Let `r_peer = sum(peer SOG)/sum(peer raw played TOI minutes)`, and `tau=60` minutes, using original source-verified, position-matched prior eligible played games. Then

```
a = 60 * r_peer + sum(last up to 20 prior own played-game SOG)
b = 60 + sum(last up to 20 prior own played-game TOI minutes)
w0 = median(last up to five prior own played-game TOIs in minutes)
mu_s1 = w0 * (a / b)
S1(Y = k) = exp(-mu_s1) * mu_s1^k / k!
```

`M2` is the untouched Gamma–Poisson mixture with shape-rate `a,b` and same `w0`, yielding mean `mu_s1` and variance `mu_s1 + w0² a/b²`. `S1` has mean and variance `mu_s1`. M0 own-rate Poisson, M1 exposure-mixture own-rate Poisson, M3 Gamma+exposure mixture, and fixed-shape M4 NB2 are separate controls, not ensemble votes. All full-count PMFs, integer-line three-way probabilities and scoring calculations derive from each model's one immutable distribution.

The existing `v2/nhl_sog_exposure_shadow.py` is imported read-only. Existing C03 Gamma production of signed source and original quote remains intact. No new source endpoint, bookmaker quota request, retraining, NUTS, 60/40 edit, Tier publication or schedule is introduced by this branch.

## 2. Exact prospective population and limits

- Start **2026-11-15 America/Toronto**, fixed end **2027-04-20**. The first *terminally written* original Gamma daily research manifest by UTC filename is the only daily source selected, including when that batch failed. Selection never searches later successful batches to increase apparent coverage.
- Source-selected only: the existing C03 daily generator caps frozen original forecasts at four per run. This is NOT a census of all NHL skaters, offers or games. Cohort selection is dictated by preexisting collection architecture, not S1 outcomes.
- Every source-reverified, strictly pre-event C03 successfully frozen player/event becomes a new, distinct S1 study candidate, conditional on an official played-game result. Original study forecast files, IDs, selections and outcome ledgers stay unchanged. Original quote supports separate D2 three-way analysis where legitimate; it does not imply product payouts or profit.
- Player-game deduplication is by official event ID + original NHL player ID. Rejected candidates and failures are counted in the attempt/source-stage ledger and never silently converted into matched scores. If the player has no official played-game row, classification is unscored (not zero or a bookmaker void). No current-game participation is used to choose a forecast.
- S1 uses only successful C03 Gamma source batches; a *standalone* reduction in the Gamma model's historical exposure-binning abstentions CANNOT be established under this adapter. A distinct future source-producer preregistration would be needed to establish that coverage benefit.

## 3. Registered inference and additional safety guardrails

**Primary paired estimand:** each slate-date mean of player-game `CRPS_S1-CRPS_M2`, then an equal-date average. Noninferiority null `H0: delta >= +0.001`; one-sided alpha 0.025. Precommit 10,000 7-calendar-day moving-block date resamples, fixed seed 20261115, final upper one-sided 97.5% bound below +0.001. Repeat-player and same-game dependence are addressed by shared-date grouping, with game and two-week-block sensitivity checks. **No unapproved lag3/lag5 HAC method.**

Fixed future horizon ending April 20, 2027, one final inferential look, no early favorable stopping; at least **60 scored dates spanning 16 calendar weeks** are required, but not claimed to deliver 80% power. The separate outcome-blind clarification preregisters zero-SOG, six-plus SOG, interval-coverage and full denominator safeguards. Noninferiority is unavailable if these or source integrity cannot be assessed.

Power stress, independent DATE assumption only, Normal planning approximation, one-sided alpha .025 and 80% power:

| Assumed SD(date paired CRPS difference) | True delta 0 | True delta +0.000389 |
|---:|---:|---:|
| 0.003 | 71 dates | 190 dates |
| 0.005 | 197 dates | 526 dates |
| 0.010 | 785 dates | 2103 dates |
| 0.020 | 3140 dates | 8410 dates |

These are deliberately *hypothetical*, not estimated from held-out 2026–27 S1 data, and clustering can increase required calendar span. The current horizon may prove insufficient, which yields **INCONCLUSIVE**, not post-hoc threshold changes.

## 4. Versioned changes and Deepnote project workspace

| File | Purpose |
|---|---|
| `config/experiment_specs/EXP_V25_NHL_SOG_RATE_SHRINKAGE_PROSPECTIVE_001.json` | Original registered hypothesis, primary/secondary analysis, exact limits, fixed period, no-look rules |
| `config/experiment_specs/EXP_V25_NHL_SOG_RATE_SHRINKAGE_PROSPECTIVE_001_CLARIFICATION_V1.json` | Explicit terminal-batch selection, source-coverage limitation and calibration safety checks |
| `v2/nhl_sog_rate_shrinkage_prospective.py` | Small pure S1/M0/M2 mathematical path; frozen M1/M3 and M4 reference; original-source verifier and append-only run_day |
| `tests/test_v25_phase51_sog_shrinkage.py` | 27 red-team unit/receipt/integrity tests with synthetic signed priors |
| `scripts/v25_phase51_independent_scipy_audit.py` | Independent SciPy Poisson/NB2 PMFs, Count CRPS, zero/tails and three-way thresholds |
| `scripts/run_nhl_sog_rate_shrinkage_prospective.py` | Explicit exact-commit, on-demand Deepnote-capable research launcher (not scheduled) |
| This document | Traceable evidence, restrictions and release review |

Deepnote detached QA workspace also contains *copies* of pinned original GitHub verifier dependencies so that tests do not edit the original collector notebooks. The original signed archives and source receipts remain unmodified.

**Source version checks:**

- Frozen Gamma module SHA-256 `2043306301d0e07c851c965371d89397988b7f431d7dd455341588ee3ee3bd81`; identical to original Phase 5 historical documented source hash.
- S1 module SHA-256 after binding clarification `20680262dc49ae9914024fa3d3bea35624e01488c3a2fd0ce56fd7df810fbc13`.
- Unit test source SHA-256 `69904eef458bb5eb8b09b164c99a1c86994f53c42d68fa13fb6a10485fa8c94a`.
- Independent SciPy audit source SHA-256 `dbf03cfd2127028a191ff9399f6a0644184c4eec3ed3d6542d3191e3a42d705e`.

## 5. Executed tests and separate numerical review

**Deepnote**:

- 27/27 registered and adversarial tests: detached run `3c8600d7-6e45-44d6-9f4d-4a9fd8080ec4`; previous 27/27 run `9779c33a-12d5-4bc3-bb4c-ede0cedb1c0e`.
- Separate SciPy implementation verified 164 Poisson means, 1,142 count CRPS scores, 120 Gamma shape/rate/exposure tuples and 3,600 Gamma masses: detached run `2526e165-c91e-4c66-9895-2b50af1f245b`. Max absolute Poisson PMF error `4.24e-15`, Gamma NB error `3.36e-14`, count CRPS error `7.11e-14`, zero mass `1.11e-16`, six-plus tail `2.22e-16`; ~0.91 CPU seconds for SciPy reference.
- Negative controls actually reject invalid or mismatched source SHA; duplicate player-game; current-game SOG/TOI; finalized postgame features; naive/event-late/source-late/future model timestamps; altered a/b; wrong player/event; zero played TOI; and immutable forecast overwrite. Raw three-second played TOI is preserved as 0.05 minutes and never DNP.
- Test-first source committed ahead of S1 code. Initial Deepnote red-run attempts were blocked by missing `pytest` and then import-path/dependency issues (not legitimate mathematical red failures); these environmental issues were corrected using stdlib `unittest` and pinned frozen dependencies. One initial real red regression (degenerate Poisson returning twenty extra zero masses) was repaired; an idempotent source-attempt accounting omission was also repaired before green acceptance.
- The separate SciPy scorer is an **independent numerical code path**, not an independent human reviewer and not an independent prospective outcome study.

## 6. November 14 source audit, genuine-source limitations

Original C03 batch:
`reports/v25_sog_source_cert_sprint/2026-11-14/daily_original_gamma_poisson_research_20261114T214814871555Z/daily_research_generation_manifest.json`

- Source manifest SHA-256 `385e07708d8cfae0943ccbdab67aafbe3c2377e621b7b4c3a0bcc25d28c3028a`.
- Original raw PropLine HTTP response: **1,578,063 bytes**, verified SHA-256 `89015f7bb08d9ff84cb8c07e56b975cef3843b2f06245c68c657667c01d3eb4a`.
- 603 original two-sided offer rows, 12 future provider events, 0 original frozen Gamma forecasts/attempts. Batch status `BLOCKED_FAIL_CLOSED`. Nonexclusive source failures: 1 live-score HTTPS error, 1 event-too-close and 1 fatal missing signed fallback. Counts represent stages, not distinct individuals/contracts.
- Original provider upstream publisher timestamps are not authenticated; possession times and raw source bytes are tracked separately. No actual publisher availability date is invented.
- On-demand S1 research preflight, Deepnote run `362785ee-e7b9-4bff-be5f-74442b1f4d06`, executed at `2026-11-15T04:08:42Z` (November 14 ET), BEFORE registered Nov15 local date. Status `NOT_STARTED`, **0 new S1 forecasts, 0 S1 scored outcomes, 0 S1 selection or settlement rows**. Distinct content-addressed attempt-audit SHA-256 `cc7a42a1f717dc49898678e0112d252b6c98b6ec3be26570f24cde1820746f90`.
- November 13 previously recorded original C03 successful three forecast attempts were inspected for **source shape and scope only**; their already observable outcomes were not read for parameter selection, stopping policy or pseudo-holdout confirmation. They are ineligible for the S1 prospective cohort.

## 7. Scientific and engineering gate

**Software decision:** ACCEPT FOR FURTHER PROSPECTIVE EVALUATION, *subject to review of this isolated PR and a first successful live original-source canary*. Mathematical QA passes and a blocked-source capture fails closed. No positive genuine future player-game S1 snapshot exists yet, so source-native full positive-path integration and downstream settlement/scoring remain unverified in a qualifying live run.

**Prospective statistical decision:** INCONCLUSIVE. No future scored S1/M2 matched player-games; cannot claim noninferiority, superiority, predictive calibration, a bettor's side advantage, or profitability.

**Operational limitations and no-go:**

1. The original Nov14 source collector failed, and its signed fallback was absent. No retrospective relabeling. Investigate C03 live-score HTTPS source and signed-fallback generation in a *separate* collector ticket, without rewriting original archives.
2. Original per-day Gamma source success is a hard eligibility dependency; S1 standalone coverage gain is not measured. Keep separate stage rejection denominators.
3. Native model source verifier's complete positive path remains unexecuted with an in-window Nov15+ newly frozen study input. No auto Tier, production promotion or automatic enablement of disabled publication.
4. Bootstrap and proper-score inference at the fixed final horizon require eligible **new** settlements and date-cluster counts; there are zero. If registered power remains inadequate, stop or collect under a separately registered future test, never secretly extend this one.
5. Do not claim a full regression suite ran from Deepnote's minimal source QA workspace; only the named focused and independent numerical suites were executed. A broader existing CI review and PR merge gate remain separate.

**Rollback:** revert only isolated Phase 5.1 research commits or PR, preserving immutable Deepnote source, forecast and attempt receipts. Existing Gamma/NB2/40-date trial, 60/40, NUTS pause, schedules, source archive and publication authority require no rollback because they were not modified.
