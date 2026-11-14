# Phase 5 — NHL SOG historical rolling-origin benchmark, November 14, 2026

**Experiment:** EXP-P5-NHL-SOG-HIST-20261114  
**Research class:** RETROSPECTIVE EVENT-TIME RECONSTRUCTION / NOT CERTIFIED HISTORICAL AS-OF  
**Historical evaluation:** 2023–24, 2024–25, 2025–26 regular-season played games  
**Production authority:** NONE. Existing 60/40, Tier gates, frozen prospective experiments, Bayesian/NUTS artifacts, collectors and settlement are untouched.

## A. Source availability and exact denominators

The frozen cohort consists of **108 skaters (72 F, 36 D)** who played in all three NHL regular-season games scheduled on **October 10, 2023**. The cohort was identified from the 2023 opening-date official box scores, not from any future SOG performance. No additional player was selected based on subsequent high or low shooting results. This is an opening-day cohort spanning the three seasons, **not a representative full-league census**; 2023–24, 2024–25 and 2025–26 have 108, 101 and 94 matched distinct players, respectively.

Original official HTTP records were re-fetched in November **2026** from NHL web API schedule and player-season game logs. All 324 requested player-season logs completed successfully, 3,934 schedule games were reconstructed, and 20,096 official historical played-player games were linked and archived. Breakdown: 7,213 (2023–24), 6,762 (2024–25), 6,121 (2025–26). Two 2024–25 official log rows were unmatchable to retrieved schedule games and were excluded from the observation store; these are source-incomplete records, not invented game IDs. The source report recorded no HTTP failures. Original raw HTTP bytes and receipts are stored with content SHA-256; **source capture time in 2026 is not original 2023–26 publisher or forecaster availability.**

Data fields used: official game ID, historical game date, regular-season season identity, historical played-team abbreviation, official SOG, official MM:SS time on ice and frozen F/D cohort position. Scheduled event ID, game date, teams and start UTC came from the official schedule re-fetch. Official historical roster *participation* and sportsbook original pregame offers were not available for all targets. Source classes:
- **NHL current official historical game logs:** genuine revised official retrospective outcomes, original capture timestamp November 2026, not certified as of historical cutoff.
- **Historical team:** game-log team abbreviation from that appearance; the replay uses only a **prior** appearance to infer target-team eligibility. No use of current rosters.
- **Pregame historical TOI:** modeled from strictly earlier played-game rows, never target final TOI. The replay cutoff is an event-time proxy.
- **News, historically captured lineups, role announcements, authenticated two-sided original sportsbook offers:** not available to this study; excluded.

**Uncertainty about historical source revisions is irreducible:** the November 2026 responses may differ from what an NHL endpoint returned before a historical game. Game start times can also reflect later schedule corrections. This is not certified contemporaneous wagering-market forecasting.

## B. Engine, feature contract and run reproduction

Study freeze: config/experiment_specs/EXP_P5_NHL_SOG_HIST_20261114.json was committed **before any 17,723-row performance result was observed**. Historical target starts November 1, 2023, ends April 25, 2026; only scheduled regular-season games appear.

1. Start with every scheduled historical game in the evaluation interval.
2. Define the simulated cutoff as scheduled start UTC minus 60 minutes. Historical features must have a **strictly earlier game date** and estimated result-availability boundary (prior start UTC + 8 hours) strictly earlier than that cutoff. The 8-hour lag is deliberately a research proxy, **not** publisher-timestamp certification. Same-date current and other-game outcomes are barred.
3. Candidate skaters are chosen from earlier recorded played-team appearances at most 21 calendar days before each target; no current-game participation/box outcome is used in candidate construction. Unknown current active roster may cause false candidate inclusion or missing new-team arrivals.
4. Derive previous player/peer SOG and TOI, fixed parameterization and five entire count PMFs. Keep explicit abstention reasons if history/exposure is invalid. Write content-addressed forecast JSONL **before** joining the target official played-game outcome.
5. After the sealed forecast artifact exists, join official outcomes by historical game ID and player ID. An absent official played-game row is **unscored, not assigned zero**, and cannot be classified as a bookmaker void because there was no book contract.
6. Compute paired count CRPS and negative log likelihood. Carry unmatched, abstained and unscored denominators. Aggregate score results at player-game, game and slate-date resolutions.

Run **4c5d4d3f4dc840db3b42** consumed 20,096 official observations and 3,934 scheduled games. In the evaluation window it attempted 3,794 scheduled games and 21,569 player-game candidates, produced 20,333 frozen forecasts (94.27%), and matched 17,723 actual played-game observations (82.17% of candidate player-games), spanning **2,705 games and 482 slate dates**. Unscored frozen forecasts: **2,610** missing from available official played-game results (possible nonappearance, unavailability or other missingness; do not assume book void). Abstained **1,236** candidate player-games: 1,222 invalid exposure bins, 14 inadequate own history. All M0–M4 models share these exact matched records; no post-hoc per-model selection.

**Reproducible code:**
- scripts/v25_phase5_nhl_official_collect.py — official retrospective source retrieval, original bytes and source manifests
- scripts/v25_phase5_nhl_sog_historical_replay.py — point-in-time proxy replay, matched scores, immutable forecasts and coverage
- scripts/v25_phase5_independent_audit.py — independent original source/forecast/SciPy distribution verification
- scripts/v25_phase5_posthoc_attribution.py — explicit post-hoc mean/dispersion ablation, not original experiment registration
- tests/test_v25_phase5_nhl_sog_replay.py — adversarial fixtures
- frozen production math imported without modification from **v2/nhl_sog_exposure_shadow.py** at main commit **a0e555b36da0e852793870fbbc162832a42fd80e**; raw code SHA-256 **2043306301d0e07c851c965371d89397988b7f431d7dd455341588ee3ee3bd81**.

**Deepnote project:** 9cc31536-93be-44db-bdeb-06fba3f61410. Source collection completed as detached run **ee4e385b-45a0-4453-95e6-c91823608198**, full M0–M4 replay as **c164f685-c6a2-497b-8b37-9118a86d3b96**, initial numerical replay unit tests as **3ee42b7a-262b-42ef-99aa-2b8e0bfd8074**, full 19-test regression as **e46e3065-aa59-47c2-86ec-01d23936c6b0**, independent SciPy audit as **c8c34de4-1d31-438e-9555-82ae1e7cb578**, M3–M2 forensic as **909ee120-96bf-4637-9d05-a7e086d306e6**, post-hoc attribution as **bef99fd9-7cd3-4783-bd54-0cb3e5cd7f25** and charts as **791fb923-0946-4323-8e8d-11a0c4107668**.

**Deepnote source folder:** reports/phase5_nhl_sog_historical/20261114T222036350236Z/  
**Immutable replay folder:** reports/phase5_nhl_sog_historical/20261114T222036350236Z/replay_20261114T222703744622Z/4c5d4d3f4dc840db3b42/  

| Content | SHA-256 |
|---|---|
| Official played observations JSONL | d321e8f3af9d127589c6cbcb9e9477717ebd61eb062f30e587a7a9268468671a |
| Official schedule JSONL | d9139bffcdeea57a37068b364a58621e20fdd02833b47bb71a3fbdec64a9aa1e |
| Original-source archive manifest | 83b07dd21c764ddf3716729a3c6991f6b246048dc1c72d4f4a9a9adf7b9d1794 |
| Immutable before-outcome forecast JSONL | 12c267b7ca629d75a69f8cfd429a5a55e8510f4be7cb914ec5860c18097553dc |
| Matched scored outcomes JSONL | 75f1343ca3125cd9665f1ff917b91268c9aa8cb1d78223d7c47842ba79568629 |
| Frozen score report JSON | 36239fb0e7d4c188cdeacf7e0f54970d148ceeeee5d129bb7ea9d2ce8fb3ffd8 |
| M3-vs-M2 / bin-abstention forensic JSON | 8d8a824655973096b7c2018ed63a8d49a4d990583a535b4ddba79c0a133b5457 |
| Explicitly post-hoc source-factor decomposition JSON | 24247df8de2eea927d440bd9027c760922cc0f69d61ea9112c6312703e476277 |

## C. Five frozen benchmark models and results

Frozen peer prior: 60 minutes of peer-rate exposure; recent exposure distribution shrunk by 3 peer pseudo-games. Up to 20 own/peer previous games and 10 player previous exposures; at least 5 player games, 20 peers, and 200 peer games. Historical cohort/peer selection is an explicitly disclosed **adapter**; it is not a claim that original pregame 2023 source packets were available.

- **M0 own-rate Poisson:** own played-game SOG/TOI rate multiplied by median of previous up to five TOIs.
- **M1 plug-in Poisson exposure mixture:** same own-rate estimate, integrated over the peer-shrunk empirical TOI distribution.
- **M2 fixed-exposure Gamma–Poisson:** posterior shooting-rate Gamma with original 60-minute peer prior, using M0's fixed exposure.
- **M3 full Gamma–Poisson:** Gamma rate posterior and peer-shrunk modeled TOI mixture.
- **M4 fixed-dispersion NB2:** exactly r=4, with the identical own-rate plug-in mean as M0, not an additional opportunity predictor.

For posterior Gamma shape a, rate b, own exposure w0 and exposure masses (w,π), M2 is NB(a,p=b/(b+w0)), M3 is Σπ·NB(a,p=b/(b+w)), and M4 is NB(r=4, μ=M0 mean). Models 0–3 use the original frozen mathematical implementation; NB2 is the registered same-mean fixed-dispersion research control. Positive masses are normalized, and three-way push semantics are tested at integer lines, without generating synthetic sportsbook contracts for D2.

### Primary full-count results, same 17,723 observations

| Model | Count CRPS | Δ CRPS vs M0 | Count NLL | Δ NLL vs M0 |
|---|---:|---:|---:|---:|
| M0 — Own-rate Poisson | 0.719662 | 0 | 1.595861 | 0 |
| M1 — Exposure plug-in Poisson | 0.719222 | −0.000440 | 1.593408 | −0.002453 |
| **M2 — Fixed Gamma–Poisson** | **0.714701** | **−0.004961** | **1.586318** | **−0.009544** |
| M3 — Full Gamma exposure mixture | 0.715737 | −0.003925 | 1.586680 | −0.009181 |
| M4 — Fixed-shape NB2 r=4 | 0.722642 | +0.002981 | 1.605040 | +0.009179 |

M2's observed pooled CRPS reduction is about **0.69% relative** to M0; a small but consistent proper-score improvement on the explored opening-cohort distribution. M3 improves over M0, but does **not** beat M2 on pooled CRPS. M4 is worse than M0 on both scores.

| Season | Matched played player-games | M0 CRPS | M1 CRPS | M2 CRPS | M3 CRPS | M4 CRPS |
|---|---:|---:|---:|---:|---:|---:|
| 2023–24 | 6,233 | 0.743784 | 0.743802 | 0.738643 | 0.740276 | 0.749034 |
| 2024–25 | 6,606 | 0.713587 | 0.712557 | 0.707893 | 0.708224 | 0.715174 |
| 2025–26 | 4,884 | 0.697093 | 0.696866 | 0.693354 | 0.694581 | 0.699063 |

M2's pooled CRPS gain versus M0 is present in all three seasons; M3 remains slightly worse than M2 on season-pooled CRPS in each. Season absolute levels reflect changing player mix and SOG frequency, not direct evidence of improving model skill over time.

### Player-position and opportunity cohorts — CRPS difference vs M0

| Cohort | n | M1 | M2 | M3 | M4 |
|---|---:|---:|---:|---:|---:|
| Forwards | 11,706 | −0.000500 | −0.005257 | −0.004063 | +0.002940 |
| Defensemen | 6,017 | −0.000323 | −0.004384 | −0.003656 | +0.003061 |
| Historical TOI under 13 min | 2,629 | +0.000647 | −0.006470 | −0.004515 | +0.000363 |
| TOI 13–20 min | 10,932 | −0.000691 | −0.004986 | −0.004793 | +0.002255 |
| TOI 20+ min | 4,162 | −0.000466 | −0.003941 | −0.001272 | +0.006540 |
| Expected SOG under 1.5 | 8,359 | +0.000380 | −0.005304 | −0.004421 | +0.001722 |
| Expected SOG 1.5–3.5 | 9,131 | −0.000681 | −0.004151 | −0.002970 | +0.003464 |
| Expected SOG 3.5+ | 233 | −0.020419 | −0.024408 | −0.023579 | +0.029176 |
| 5–9 previous own games | 137 | +0.003266 | −0.018124 | −0.012239 | +0.003661 |
| 10–19 previous own games | 1,069 | +0.000571 | −0.009115 | −0.006497 | +0.004165 |
| 20 previous own games | 16,517 | −0.000536 | −0.004583 | −0.003689 | +0.002898 |
| Stable TOI (<3 min historic SD) | 16,278 | −0.000482 | −0.005147 | −0.004177 | +0.002940 |
| Volatile TOI (≥3 min SD) | 1,445 | +0.000038 | −0.002861 | −0.001082 | +0.003442 |

The rate-pooling gain is most pronounced in small-history and lower-TOI cohorts, consistent with a shrinkage mechanism, though cohorts with 137 or 233 observations have substantial uncertainty and overlapping comparisons are not independent. M3 does not clearly repair the volatile-exposure subgroup.

Conditional realized SOG ≥6 is a **postgame-defined diagnostic group** (n=380), never a pregame eligibility rule. In that small tail group M4's CRPS improves relative to M0 by −0.0503 but its full-population overprediction of tails more than offsets the benefit. No conclusion about a selectable high-SOG strategy is justified from realized-outcome strata.

## D. Calibration and mathematical checks

| Model | Mean forecast SOG | Mean error (forecast–observed) | Mean predicted variance | Residual mean-square | Predicted P(0) | Predicted P(6+) |
|---|---:|---:|---:|---:|---:|---:|
| M0 | 1.6700 | +0.0135 | 1.6700 | 1.8601 | 24.15% | 2.19% |
| M1 | 1.6460 | −0.0105 | 1.7459 | 1.8589 | 24.69% | 2.09% |
| M2 | 1.6725 | +0.0160 | 1.7462 | 1.8394 | 23.81% | 2.10% |
| M3 | 1.6499 | −0.0066 | 1.8213 | 1.8451 | 24.36% | 2.03% |
| M4 | 1.6700 | +0.0135 | 2.5255 | 1.8601 | 29.22% | 3.92% |

**Observed:** mean SOG **1.6565**, zero SOG **24.50%**, six-plus SOG **2.14%**. M3's average predictive variance is closest to residual mean-square, but has slightly worse pooled CRPS than M2; variance calibration alone does not determine full-distribution scoring. M4's fixed dispersion greatly overshoots zero and upper-tail frequencies. Its tail advantage conditional on having *already observed* a six-shot game does not overcome aggregate miscalibration. Discrete randomized PIT deciles and zero/tail charts are saved as referenced artifacts.

Independent SciPy probability/reference review (first separate code path) validated 250 deterministic sampled forecasts across five models: maximum absolute PMF discrepancy **1.60×10⁻¹⁴**, maximum absolute NLL discrepancy **1.57×10⁻¹³**, identical matched CRPS and log-loss aggregates, valid nonnegative support and normalization, source hashes and player-game identity. A second original-body replay cross-check was also initiated as a distinct source-native audit; receipt must be checked before any claim of complete source-chain verification. Unit fixture suite 19/19 passed, including exact integer push and zero/tail/moment behavior.

## E. Adversarial leakage, coverage and robustness audit

**19/19 executable adversarial fixture tests passed** in detached Deepnote, including current-game SOG and final TOI tampering, future-game injected labels, final-score and postgame lineup contamination, strict calendar-day and availability cutoff, source identity and historical roster, target-game absence (no outcome-dependent candidate selection), negative time source, duplicate game/player rows, immutable rerun output, original PMF numerical equivalence, NB2 mean/variance, exact integer-line push and micro-TOI fail-closed behavior.

**Critical history-source limitation not fixable by tests:** the original official NHL source was *retrieved after target games*; there is no evidence that exact historical revised response fields or schedule timestamps were truly available before that game's puck drop. The model is explicitly **retrospective event-time**, not source-certified pregame replay.

**Discovered robustness defect — one three-second TOI:** NHL official game **2025020963** on March 3, 2026, player **8482062**, has **0.05 minutes** of recorded TOI. Frozen half-minute TOI binning cannot represent it as a positive bin. The shared peer history makes this single genuine record trigger **1,222** invalid-exposure-bin forecast abstentions (5.67% of all candidate player-games). Do not silently truncate the record, weaken the frozen experiment, or remove these rejects from denominators. A versioned repair candidate must be tested separately.

**Unresolved limitations:**
- Pre-event authenticity of historical source availability, original historical real offers and two-sided prices, lineup truth, injury/role news, DNP/void rules are unavailable.
- Model and peer-population design were established after some historical seasons and may be historically development-exposed; 2023–26 is **not an untouched holdout**, even with strict computational cutoffs.
- The opening-day cohort excludes later debutants and many teams. A source-complete *full NHL* benchmark has not been run.
- Game/date bootstrap captures some but not all player-repeated and temporal dependence; 482 date clusters are not necessarily 482 independent draws.
- No external human review or independent publisher as-of certification is claimed.

## F. Dependence-aware statistical interpretation

Matched pooled differences are descriptive. Independently recomputed equal-date and game-equal bootstraps (2,000 draws, specified seed in the independent audit) show a similar direction for the two Gamma candidates; **these intervals were chosen and reviewed retrospectively**, not an approved confirmatory inference method.

| Comparison | Equal-date mean Δ CRPS | Exploratory 95% date-cluster interval |
|---|---:|---:|
| M1 − M0 | −0.001389 | [−0.003052, +0.000286] |
| M2 − M0 | −0.005195 | [−0.006335, −0.004108] |
| M3 − M0 | −0.005241 | [−0.007548, −0.003052] |
| M4 − M0 | +0.002550 | [+0.000980, +0.004139] |
| **M3 − M2** | **−0.000046** | **[−0.001679, +0.001629]** |

M3 minus M2 has *pooled* CRPS difference **+0.001036** (favors M2) and *equal-date* −0.000046 (near tie, weakly favors M3); the date-cluster interval crosses zero. For NLL M3 minus M2 is pooled +0.000363, equal-date −0.000852. It is not defensible to say the complete opportunity mixture has established incremental value over the simpler fixed-exposure Gamma–Poisson.

**Original prospective inference restrictions remain in force:** EXP-V25-NHL-SOG-EXPOSURE-EB-001 remains 40 dates, primary equal-date matched original-contract three-way Brier, one-sided nominal α 0.025, threshold −0.002, confirmatory inference NOT APPROVED. This experiment is separate; no historical proper-score result changes its registered inference or permits promotion. Separate fixed-shape NB2 prospective study retains its own plug-in Poisson control.

### Post-hoc explanatory decomposition — descriptive only

A second mathematical decomposition was run **after viewing the original M0–M4 historical results**. It is not a preregistered baseline and cannot support independent model selection. Using only already-sealed parameters, it computed:

| Post-hoc ablation | CRPS |
|---|---:|
| M0 original own-rate Poisson | 0.719662 |
| S1 posterior-mean *shrunk-rate* Poisson, original fixed exposure | **0.715090** |
| M2 fixed-exposure Gamma–Poisson | 0.714701 |
| S2 own-rate Poisson, modeled mean exposure | 0.719770 |
| S3 shrunk-rate Poisson, modeled mean exposure | 0.716413 |
| S4 shrunk-rate Poisson, exposure mixture | 0.715866 |
| M3 full Gamma + exposure mixture | 0.715737 |

Adding the posterior-mean shrinkage at fixed exposure, **S1−M0 = −0.004572 CRPS**, explains about **92.16% of the observed M2−M0 CRPS change** algebraically. The extra Gamma uncertainty **M2−S1 = −0.000389** gives the remaining ~7.84%. This is a descriptive factorization and not evidence of causal effects or future attainability. Modeling the exposure **mean** alone at the own rate S2−M0 is **+0.000109 CRPS** (slightly worse); its exposure-mixture distribution M1−S2 is **−0.000549**. S4−S3 is **−0.000547**, while M3−S4 (adding Gamma rate uncertainty at modeled TOI) is only **−0.000130**. Overall, rate shrinkage looks more valuable than increasing exposure architecture complexity in this explored source cohort.

## G. Integration, test and rollback receipt

**Branch:** research/phase5-nhl-sog-rolling-origin-20261114  
**PR:** https://github.com/royalexx/pickem-auditor/pull/127  
**Repository baseline:** a0e555b36da0e852793870fbbc162832a42fd80e  
**Purely research code/config/tests/report added; no production call path changed.**

The research PR is intentionally draft until final exact-head CI and the completed source-native independent verification receipt pass. At any failing gate, do not merge; retain original source/archive evidence. If merged, rollback is a standard Git revert of this isolated research-only PR commit range (or a revert PR), retaining Deepnote immutable records; no baseline weights, thresholds, trained NUTS or automations require restoration because none were modified. The **research study's historic source and score receipts are immutable** even if the code branch is later rejected.

## H. Research decision table — no production authorization

| Model | Decision | Explanation |
|---|---|---|
| M0 own-rate Poisson | **RETAIN AS BASELINE** | Strong, cheap, clearly identifiable control, reasonable zero and tail calibration |
| M1 exposure-mixture own-rate Poisson | **INSUFFICIENT EVIDENCE** | Negligible pooled CRPS gain and date-cluster CRPS interval overlaps zero |
| M2 fixed-exposure Gamma–Poisson | **PROMISING RESEARCH CHALLENGER** | Pooled CRPS and NLL better than M0 in every evaluated season; gain mostly from rate shrinkage; not independent holdout |
| M3 full Gamma + exposure mixture | **REQUIRES REPAIR** | Better than M0, no convincing M2 incremental improvement; single 0.05-minute prior observation produces widespread fail-closed peer-binning abstentions |
| M4 fixed-dispersion NB2, r=4 | **REJECT UNDER TESTED CONDITIONS** | Worse pooled and season CRPS/NLL; inflated zero/tail variance relative to this historical cohort |

These verdicts do not override prospective frozen trial outcomes, change licensed parameters, or assert economic profitability.

## I. Highest-value next experiment

**Preregister a source-certified prospective *posterior-mean shrunk-rate Poisson* as a simple challenger to both M0 and M2.** It uses the already frozen 60-minute peer prior and strictly prior own history, but avoids mixing Gamma parameter uncertainty into the predictive PMF and avoids the half-minute exposure-peer bin that caused 1,222 abstentions. Use exactly the same source-certified played-game/offer cutoff contracts and preserve separate D1 full-count and D2 original-offer evaluations. Freeze the model, eligible universe, no-look horizon and inference method before the first new target; **never select or tune it using the existing 2026–27 prospective 40-date experiment's outcomes**.

Pass criteria for exploratory investment: source integrity, improved or acceptably noninferior precommitted count CRPS/NLL versus M2 across matched dates (e.g., register a clinically useful noninferiority margin rather than optimizing it after seeing results), no zero/tail regression, reduced abstention and lower compute cost. Separate original-offer prospective calibration and actual payout economics are needed before any market or Tier claim. For genuinely confirmed improvement, choose an appropriately powered precommitted future period and dependence-aware inference **without borrowing the unapproved lag-3/lag-5 HAC strategy** of EXP-V25-NHL-SOG-EXPOSURE-EB-001.

**Scientific conclusion:** in the historical opening-day cohort, the useful signal appears to be robust rate estimation and shrinkage. Greater exposure mixture complexity was not established as additive value. The frozen prospective trial must continue untouched.
