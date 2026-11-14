# C10 — November 14, 2026: inference reconciliation and outcome-blind release receipt

**Decision: research-only; confirmatory inference BLOCKED; model promotion prohibited.**

Governing card: EXP-V25-NHL-SOG-EXPOSURE-EB-001, unchanged from docs/V25_NHL_SOG_EXPOSURE_EB_001_EXPERIMENT.md. No production selection, paid compute or new training.

## 1. Preregistered NHL SOG primary estimand

The original full-game SOG player/stat/period/book/line contract is scored only when the same original pregame offer, Poisson own-rate baseline, exposure Gamma–Poisson challenger and nonvoid official settlement were independently archived and source-qualified.

For each eligible slate date d, first average contract-level three-way Brier differences (Gamma–Poisson minus the simple Poisson control). Then average **equally over distinct eligible dates**, not over raw contracts. Over, Under and Push must remain separate. Multiple alternate lines, same-game skaters and repeated markets do NOT create independent slate dates. Count all rejects, abstentions, postponements, DNPs and voids in a complete coverage ledger.

Original fixed horizon: **exactly 40 eligible slate dates by January 31, 2027 America/Toronto**, without data-dependent extension or interim hypothesis testing. One-sided alpha **0.025**, null theta >= 0, alternative theta < 0, and a second minimum useful *point-estimate* threshold theta <= -0.002. To claim improvement of at least 0.002, an upper confidence bound additionally must fall below -0.002; this is distinct from the original null. None of these decisions grants production authority.

The initial paired-date t(39) method was explicitly a **conditional candidate** pending independent pre-outcome dependence, distributional and power verification. It was not an independently signed final confirmatory method.

## 2. Reconcile two competing C10 simulation candidates

Both candidate implementations and original simulation receipts are preserved as separate research methods, not merged into one statistical test:

| Property | Lag 3 candidate | Lag 5 candidate |
|---|---|---|
| Source | v2/c10_serial_inference.py | v2/c10_sog_fixed_horizon.py |
| Scenario grid | 36 | 96 |
| Bartlett HAC bandwidth | 3 | 5 |
| Null threshold | Largest 97.5% negative t-statistic quantile | Smallest 1% positive t-statistic quantile |
| Scenario structure | AR1 0/.3/.6; normal, positively skewed lognormal, t3; alternating volatility, thin/mixed game clusters | AR1 0/.3/.6/.8; normal, negatively skewed exponential, t3; alternating volatility, sparse/dense clusters; assumed SD .01/.04 |
| Previously reported max held-out null rejection | .0273333 | .0096 |
| Previously reported power at effect -.002 | Minimum 0 | Minimum 0; median .0028; maximum .034 |
| C10 status | Simulation diagnostics only | Simulation diagnostics only |

**These are not interchangeable**. The lag-5 candidate adopts a 1% lower-tail cutoff rather than the original alpha 2.5%; both grids differ in distribution assumptions and scale. One cannot pick the more favorable method, combine its p-values, or use the observed validation score to choose bandwidth. A finite worst-case simulated grid is NOT distribution-free error control. The legacy 12- and 20-date lag-3 runs are planning sensitivity simulations only, not authorized extra interim looks.

The original branch source blobs and documentation remain independently identifiable, so this C10 merge does not falsify their provenance. In particular the old lag-5 result field named eligible_dates_collected=0 means its synthetic simulation used zero real outcomes; it must never be mistaken for a current live collector status.

## 3. Independent outcome-free known-variance power test

Read-only Deepnote notebook 3fd82bce13524b2b9990c1af830b7649, run 7ccb4772-aada-490c-8c92-8b30e5554c1a, independently computed finite-n stationary Gaussian AR1 date-average variance without importing either C10 candidate, sports data, forecasts, or NHL outcomes.

- Fixed n=40, alpha=.025, hypothetical effect=-.002, known true Gaussian SD and true AR1 rho (deliberately optimistic compared with unknown variance/HAC).
- Four assumed date-level SDs: .01, .02, .04, .08. Three rhos: 0, .3, .6. 12 scenarios.
- Independent seeded 20,000-replicate null and alternative synthetic streams for every scenario.
- Maximum theoretical power **0.2435110687**; minimum **0.0301231784**. Maximum observed alternative rejection **0.2463**, maximum null rejection **0.0265**.
- Canonical synthetic result SHA256: d8d4c33ff523a4589fd97cf002478a592e89a94331bdaa2155f84ea87f6b7b36.
- Every scenario had theoretical power below 80%. With SD .01 and independent dates, the optimistic known-variance 80% power benchmark is about 196 distinct dates, not 40. Assumed variance is not estimated from held-out NHL evaluations.

This is planning-only, not a valid confidence bound under arbitrary real-life drift, missingness, dependence, unknown SD, heavy tails or adaptive eligibility.

## 4. Current real evidence and interim-look contamination risk

The connected research-only NHL SOG prospective daily validator report for 2026-11-14 (reports/v25_nhl_sog_prospective_daily_validation/2026-11-14/run_20261114T192153458052Z/prospective_daily_validation_manifest.json) reports **one eligible local slate date**, **seven settled matched contracts**, and **eleven originally successful attempt records**. These are observed collector counters, not independently validated population counts for final inference.

That existing report also stores date_equal_GP_minus_poisson, paired_GP_minus_poisson, paired_daily_mean_metrics, model_metrics and scored_outcomes. Some interim descriptive comparisons were displayed in earlier work. They should **not** be reframed as authorized statistical interim tests, used for test selection, tuning, rank or Tier changes. Preserve old source and report bytes, but quarantine those premature comparisons as **exploratory**. From now on operator health summaries should read only source/date/coverage status, not realized paired scores, and avoid result-dependent methodological decisions. This action cannot retroactively restore a wholly blind primary trial.

## 5. Integrated fail-closed inference gate

The additional research module v2/c10_sog_inference_gate.py checks reported experiment ID, original horizon, source/clock flags, synthetic-score exclusion, date counts, contract count consistency and SHA256 of the exact collector manifest. It does not consult proper scores, paired performance or realized outcomes.

The module reports:
- RESEARCH_COLLECTING_CONFIRMATORY_BLOCKED when eligible dates are fewer than 40 and deadline has not passed.
- ADMINISTRATIVELY_INCOMPLETE_40_DATES after deadline without 40.
- FORTY_DATES_MET_NO_APPROVED_INFERENCE even with all 40 dates, because no C10 procedure is independently approved for the present experiment.

Every report has p_value=null, confidence_interval=null, independent_statistical_signoff=false, automatic_model_promotion=false. It emits a separate append-only hash-bound technical health receipt. The 12 planning-power calculations are explicitly noninferential.

Adversarial tests use a mapping that raises on any attempt to access observed score, model metric, or paired difference; they test false source publication claims, synthetic contamination, temporal flag drift, wrong horizon, date/contract-count errors, invalid SD/rho, passed deadline, and receipt mutation. This code is incapable of granting Tier/model promotion.

## 6. Scientific disposition

The existing 40-date trial remains useful for **descriptive** proper-score diagnostics, source coverage, abstention, opportunity/exposure and count-tail analysis, but must not support a retrospectively selected significance test or claim of economic edge. Continue the originally declared collection without silently extending, tuning, republishing, or redefining the cohort.

A new genuinely confirmatory trial would require a newly versioned preregistration **before the first eligible quote**; independent audit of point-in-time source and matched scoring; one chosen calibrated test at one frozen final look; assumptions and realistic power supported by entirely prior data; explicit signed independent scientific approval; and no opportunistic subgroup rescue.

Production selection, legacy consensus 60/40, Tier rules, all frozen Bayesian/NUTS models, morning settlement, and current NHL capture schedules remain unchanged. On present evidence, retain the simple Poisson control as the scientifically preferred comparison benchmark.

**C10 decision: independently audited simulation methods, scientific power inadequate, NO-GO for confirmatory inference, no predictive model changes authorized.**
