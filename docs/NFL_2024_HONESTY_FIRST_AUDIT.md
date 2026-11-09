# NFL 2024 honesty-first adversarial audit — 9 November 2026

**Status: RELEASE BLOCKED.** This audit is not evidence of an actual 70% betting hit rate. Both runs use synthetic historical-derived research lines and retrospectively reconstructed potential rosters. The original 2024 replay is **not** the production Bayesian NUTS model. The new code and reports are on an isolated audit branch, **not merged or deployed**.

## Model acceptance objective

Accuracy, Brier, and log loss are **not sufficient** to approve a model on artificial lines. For promotion require: archived pregame bookmaker offer and odds, independently confirmed event/player/market identity, timestamped active status, explicit void/push/no-play semantics, rolling pregame training without future-derived decisions, calibration and uncertainty by market+side, and a positive real-price out-of-sample expected-value improvement. All must be checked without guaranteed quota of ten picks. A higher Brier on synthetic thresholds can be more honest, but cannot by itself establish improvement.

## Independent 2024 rerun comparisons

| Diagnostic | Hybrid log1p-response ridge | Raw-response arithmetic-mean ridge |
|---|---:|---:|
| Forecasts | 107,319 | 107,319 |
| Matched outcomes | 71,009 | 71,009 |
| Unmatched | 36,310 (33.83%) | 36,310 (33.83%) |
| Directional accuracy (matched only) | 70.19% | 68.90% |
| Always-Under accuracy, same lines | 68.76% | 68.76% |
| Lift over always-Under | +1.43 pp | +0.14 pp |
| Week-bootstrap 95% CI of lift | [+1.19, +1.69] pp | [-0.27, +0.55] pp |
| Under share of matched forecasts | 92.85% | 79.89% |
| Brier vs synthetic threshold | 0.19282 | 0.19470 |
| Historical baseline Brier | 0.19520 | 0.19520 |
| Log loss | 0.56241 | 0.56532 |
| Top-ten selections | 180/180 Unders | 180/180 Unders |
| Top-ten matched | 73/180 | 84/180 |
| Top-ten known hits | 71/180 | 80/180 |
| Mathematical full-180 hit range under unknown outcomes | 39.44%–98.89% | 44.44%–97.78% |
| Actual pregame sportsbook quotes | **NONE** | **NONE** |
| Approved for production | **NO** | **NO** |

**Interpretation:** Raw-response target fitting reduces a key Under-bias mechanism but does not fix unavailable markets, missing participation, synthetic thresholds or overconfident selected picks. Reject both for live deployment. The old lower Brier is not a reason to prefer the old model on a dishonest benchmark.

## 34-point audit checklist: precise outcomes

| # | Priority | Audit item | Status and finding/fix |
|---:|---|---|---|
| 1 | P0 | Real sportsbook quotes, lines, two-sided odds | **FAIL / BLOCKED:** Neither replay has actual historical quotes; 2024 research lines are fabricated from prior statistics. Added fail-closed offer validator. |
| 2 | P0 | Pregame active/starting status and offered-player roster | **FAIL / BLOCKED:** Candidates originate from last observed games, not timestamped active or offered rosters. Validator requires pre-kickoff active evidence. |
| 3 | P0 | Classify DNP, missing, void, true zero, data-unavailable | **OPEN / P0:** 36,310/107,319 (33.83%) remain UNMATCHED; cannot responsibly relabel missing as zero or loss. |
| 4 | P0 | Audit Under bias by market, role, and confidence | **FOUND / PARTIAL:** Hybrid 92.85% Under, raw-response challenger 79.89% Under. 12/16 hybrid markets >90% Under; top-10 180/180 Unders in both. Role drilldown underway. |
| 5 | P0 | Compare with always-Under and historical baseline | **VERIFIED:** Hybrid accuracy 70.19% vs always-Under 68.76% (+1.43 pp); raw 68.90% (+0.14 pp). Raw uplift CI includes zero. |
| 6 | P0 | Audit top-10 preselection and unsupported markets | **FAIL / BLOCKED:** Hybrid 71/73 matched winners but 107/180 missing; raw 80/84 winners but 96/180 missing. All selected picks are Unders, mostly not verified offers. |
| 7 | P0 | Missing-outcome selection and coverage biases | **FOUND / NOT FIXED:** Matched-only hit rate not representative. Hybrid top-ten unconditional all-fail/all-win bounds: 39.44%–98.89%; raw: 44.44%–97.78%. |
| 8 | P0 | NFL grading/stat-definition reconciliation | **PARTIAL / OPEN:** Reviewed source join, snaps filter, and tackle+assists 3-component sum; independent official stat-source reconciliation and missing-stat taxonomy still required. |
| 9 | P0 | Pre-kickoff timestamp and leakage controls | **PARTIAL VERIFIED:** 18 sequential locks, no current-week outcomes in forecast packets, prior-week updates verified. No contemporaneous bookmaker quotes; retrospective data/design cannot prove prospectivity. |
| 10 | P0 | Duplicate, game-correlated, repeated contracts | **PARTIAL VERIFIED:** Frozen ledger unique (week/game/player/market); analyzed with 20k week- and 5k game-cluster bootstraps. Full portfolio joint dependence model open. |
| 11 | P0 | Reference-check Student-t, NB, normal, Poisson probabilities | **PARTIAL VERIFIED:** Regression tests compare Student-t CDF, negative-binomial and Normal SF to SciPy; tests pass. Additional count distributions/integer pushes require broader end-to-end audit. |
| 12 | P0 | Tail dispersion, parameterization and variance | **FOUND / OPEN:** Replay uses fixed count NB dispersion 8, floor=7 for continuous residual sigma, and no posterior parameter integration. Not justified by 2024 holdout. |
| 13 | P0 | Over/Under/push and integer-vs-halfpoint settlement | **PARTIAL VERIFIED:** Research lines are half-points (zero pushes). Historical Bayesian engine contains 3-way push handling, but real integer-line score parity/odds still not complete. |
| 14 | P0 | Trace A/B, Bayesian A/B, NUTS, consensus | **PARTIAL VERIFIED:** These 2024 replays are ridge challengers, not production NUTS; inspected production weighted win/push/loss and shadow release guards. Complete live probability provenance per pick open. |
| 15 | P0 | Missing feature coercion and negative-stat clipping | **CONFIRMED DEFECT:** Replay training does y=max(0,value), clipping legitimate negative yards. Hybrid line history accepts negative yards; training transform still requires correction and retest. |
| 16 | P0 | Propagate opportunity, model, line, role uncertainty | **FAIL / MODEL LIMITATION:** Ridge research scores do not integrate posterior uncertainty or offer uncertainty; NUTS path partially samples snap and conversion rates, without verified availability. |
| 17 | P1 | Reproduce chronological 18-week replay | **VERIFIED:** 18 locks, 16 markets/week, 288 frozen market snapshots; previous-week training counts match next-week counts. |
| 18 | P1 | Zero-2024 initial weights and saved transforms | **PARTIAL VERIFIED:** Initial state fit only 2021–23; training updated after each 2024 settlement; historical data/research choices retrospectively touched 2024, so no true untouched design. |
| 19 | P1 | Brier and log loss vs market and baseline | **PARTIAL VERIFIED:** Log1p ridge Brier .19282 vs historical .19520; raw .19470 vs .19520. No true market comparator. Proper-score ranking on synthetic lines is not an acceptance test. |
| 20 | P1 | Calibration by market, side, position, confidence | **PARTIAL VERIFIED:** Confidence buckets and per-market/side scores computed; 0.6, 0.7 and 0.8 bins overclaim >3pp for log1p replay; position-conditional sample and true-odds calibration remain open. |
| 21 | P1 | Separate top-ten settled validation from full pool | **VERIFIED / BLOCKED:** 180 per challenger; hybrid 73 and raw 84 matched, 180/180 Under both. Selected confidence is misleading; top-ten selection is not production eligible. |
| 22 | P1 | Bad-week frequency and tail-risk | **PARTIAL VERIFIED:** No full-market weekly accuracy <=30% in synthetic replay; inadequate substitute for real candidate slates and historical 30%-bad-week assessment. |
| 23 | P1 | Week- and game-cluster bootstrap intervals | **VERIFIED:** 20,000 week and 5,000 game bootstrap replicates. Raw edge vs always Under week 95% CI -0.27 to +0.55 pp; log1p +1.19 to +1.69 pp on synthetic lines. |
| 24 | P1 | Leakage permutation and negative controls | **OPEN:** Packet lock and training chain tests pass; randomized opponent/labels/quote timing and negative controls not yet executed. |
| 25 | P1 | Sensitivity to artificial line construction | **VERIFIED:** Position-median synthetic accuracy 74.54%, player last5/last10 hybrid 70.19%, raw target hybrid 68.90%. Non-comparable to real quoted lines; all still Under-heavy. |
| 26 | P2 | Posterior predictive checks, PIT, SBC | **BLOCKED:** Replay is ridge, not posterior sampler; cannot pass Bayesian SBC without separate NUTS rerun and correct model-data pairing. |
| 27 | P2 | R-hat, bulk ESS, divergences, BFMI per model | **PARTIAL / BLOCKED:** NUTS release code checks diagnostics; no new converged 2024 16-market posterior training was done or validated by this replay. |
| 28 | P2 | Opportunity/snaps vs conversion model | **PARTIAL:** NUTS targets model explicitly has snap and per-snap rate effects; research replay only one regression with prior snap input, not decomposition. |
| 29 | P2 | Pregame injuries, role changes, opponent effects | **FAIL / OPEN:** Research features ignore opponent and pregame injuries; roster uses last observed team; role reference from coarse position cannot identify a MIKE or box safety. |
| 30 | P2 | Correlated within-game and cross-market props | **PARTIAL:** Game-cluster bootstraps address inference uncertainty but not the joint predictive distribution or multi-leg correlation. |
| 31 | P2 | Past-only recalibration by side/market | **PARTIAL / OPEN:** Existing reform_step10 calibration shadow uses chronological splits; insufficient evidence and not promoted. Replay probabilities not re-fitted to calibration. |
| 32 | P3 | Verified sportsbook edge, odds, ROI, CLV | **BLOCKED:** No historical offered quotes/odds; cannot report win-rate edge, ROI, CLV, or profit from this replay. |
| 33 | P3 | Enforce release assertions and provenance | **PARTIAL IMPLEMENTED:** Added 2024 adversarial release gate, 11 numerical/validation tests (passed), fail-closed bookmaker quote validator, and corrected source-derived hybrid provenance ledger 107,319 rows. Integration into live ranking still outstanding. |
| 34 | P3 | Fully prospective unseen live validation | **BLOCKED:** Needs timestamped real offers, settled active-player outcomes, and pre-registered post-fix slates. None supplied by this replay. |

## Smoking-gun root cause: candidate eligibility, not a miraculous Bayesian edge

An independent forensic join of **every** top-ten selected contract to its SHA-256-locked pregame packet identified the following exact composition:

| Selected research prop type | Log1p hybrid | Raw-mean challenger |
|---|---:|---:|
| WR rushing touchdowns (typically threshold 0.5) | **105/180** | **112/180** |
| WR rushing attempts/carries | **49/180** | **66/180** |
| RB carries | 24/180 | 1/180 |
| QB pass attempts | 2/180 | 1/180 |
| **Verified bookmaker offers** | **0 documented** | **0 documented** |

Both top-ten boards contain **180/180 Unders**. Most candidates are rare-event WR contracts, with extremely low player baselines and no verified bookmaker offer. Thus most of the 99.9% confidence is manufactured by ranking arbitrary, typically unoffered synthetic thresholds.

**Correction of earlier preliminary audit figure:** An initial top-ten `model_mean / max(baseline, 0.01)` median of ~0.12 was **a denominator-floor artifact** for near-zero touchdown baselines. Recomputed without that artificial floor, all cases satisfy the research code's 30% historical-baseline floor for nonnegative stat means. The extreme confident Unders primarily reflect **tiny target probabilities on fabricated/uncorroborated contracts**, not necessarily a model mean violating the 30% blend. The log1p retransformation *also* induces bias, as confirmed by the raw-response replay, but did not fix the top-ten selection pathology.

**Action:** `scripts/nfl_prop_offer_validation.py` now requires verifiable, timestamped pregame quote+two-sided odds and active-player evidence and returns **zero** picks for synthetic-only candidates. This protection is implemented on the isolated audit branch and is **not yet connected to production ranking**.

Supporting records: `reports/nfl_2024_adversarial/top10_priors_comparison.json`, `top10_pregame_priors_log1p.csv`, `top10_pregame_priors_raw.csv`.

## Week by week: exactly the same 2024 player/game/market contracts

| Week | Matched contracts | Log1p hybrid accuracy | Raw-mean challenger accuracy | Unmatched | Log1p top10 matched | Raw top10 matched |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2927 | 71.64% | 71.44% | 4031 | 1/10 | 2/10 |
| 2 | 3711 | 71.06% | 70.04% | 696 | 7/10 | 8/10 |
| 3 | 4096 | 69.75% | 68.43% | 1043 | 8/10 | 10/10 |
| 4 | 4091 | 69.62% | 68.83% | 1493 | 8/10 | 9/10 |
| 5 | 3649 | 69.17% | 67.99% | 1555 | 6/10 | 5/10 |
| 6 | 3713 | 69.46% | 68.44% | 1702 | 5/10 | 5/10 |
| 7 | 4014 | 72.10% | 70.18% | 2010 | 5/10 | 7/10 |
| 8 | 4392 | 69.40% | 68.60% | 2306 | 5/10 | 5/10 |
| 9 | 4074 | 70.08% | 68.78% | 2205 | 4/10 | 5/10 |
| 10 | 3771 | 71.86% | 70.19% | 2198 | 4/10 | 4/10 |
| 11 | 3859 | 70.56% | 69.47% | 2026 | 3/10 | 4/10 |
| 12 | 3516 | 69.51% | 67.18% | 1844 | 3/10 | 4/10 |
| 13 | 4235 | 68.85% | 67.77% | 2380 | 3/10 | 2/10 |
| 14 | 3428 | 70.39% | 68.12% | 1952 | 3/10 | 3/10 |
| 15 | 4451 | 72.16% | 69.45% | 2132 | 3/10 | 3/10 |
| 16 | 4396 | 69.63% | 68.77% | 2227 | 2/10 | 4/10 |
| 17 | 4448 | 69.69% | 68.44% | 2127 | 3/10 | 4/10 |
| 18 | 4238 | 68.97% | 68.64% | 2383 | 0/10 | 0/10 |

Each week is frozen and hashed before outcomes are exposed; after grading its models update before the following week. All 18 training increment checks passed. Neither run uses original, timestamped sportsbook prices, and no posterior NUTS inference was retrained here.

## Changes implemented and validated (audit branch only)

1. `scripts/nfl_prop_offer_validation.py`: fail-closed contract validator. Requires real pre-kickoff quoted two-sided odds, bookmaker ID, time, source hash, active/identity confirmation; synthetic or absent records produce *no selections*. No forced top-ten quota.
2. `scripts/nfl_2024_adversarial_release_gate.py`: independently verifies 18 forecast locks, forecast uniqueness, sequential learning, all-market settlement, ungraded coverage, market imbalance, calibration and proper scores. The 2024 replay fails its release gates; no auto promotion.
3. `scripts/nfl_weekly_blind_multimarket_raw_response_challenger.py`: separate research-only challenger trains against raw arithmetic stat outcomes rather than back-transforming a log1p target. Completed full 2024 weekly replay and paired comparison.
4. `tests/test_nfl_adversarial_invariants.py`: 11 tests passed including Student-t and NB/Normal comparisons with SciPy, hybrid leakage checks, negative yard-line handling, and pregame offer validation.
5. `scripts/nfl_replay_provenance_repair.py`: verifies all locked forecast/pregame SHA hashes and repairs line source labels in a **new** 107,319-row immutable ledger; original incorrectly said `synthetic_preweek_position_median`; actual `player_last5_last10_role_v1` confirmed in original packets.
6. Independent 20k-week/5k-game bootstrap paired benchmark, plus top-ten missing-data bounds. Both protect against false precision from 71k correlated contracts.

## Unresolved release blockers

- Missing actual historical sportsbook quotes and market availability is the **principal** blocker; no ROI, CLV or true market edge can be calculated.
- Unmatched/void/DNP taxonomy and timestamped pregame active roster verification.
- Remaining all-Under forced ranking (180/180 both runs), even after fixing log-response bias.
- Research model clips negative yard outcomes in training; an additional correction and replay are required.
- Bayesian 16-market hierarchical model did not run in this replay, so posterior predictive checks and NUTS acceptance still need a **separate** posterior-level audit.
- Research conclusions have retrospective design exposure to 2024; only prospectively captured slates can clear the final gate.

## Reproducible evidence

- Historical hybrid replay: `reports/nfl_2024_hybrid_weekly_blind/`.
- Arithmetic-response research challenger: `reports/nfl_2024_raw_response_challenger/`.
- Full independently verified Deepnote receipts: `pickem_runs/2024_hybrid_weekly_blind_retrain_20261109/INDEPENDENT_ADVERSARIAL_AUDIT/`.
- Source: `scripts/nfl_weekly_blind_multimarket_hybrid.py`, `scripts/nfl_weekly_blind_multimarket_raw_response_challenger.py`.

**Decision: NO-GO.** Neither synthetic-line replay is authorized to calibrate real-money probabilities or justify high-confidence tiers. Live selections should abstain until a genuine offered-market/availability feed is verified and out-of-sample calibration is established.
