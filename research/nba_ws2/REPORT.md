# NBA WS2 — probabilistic minutes and opportunity, November 15, 2026

**Decision: retain M0 as the benchmark; do not adopt or promote either challenger.** M2 improves aggregate historical conditional-minute forecasts, but low-minute and overtime stress behavior regresses. Participation and authenticated future-slate validation remain blocked by data. Status: implemented, tested, historical exploratory shadow; not independently statistically verified.

The corrected replay scores **25,641 matched played player-games**, **1,231 games** and **164 dates**. M2 CRPS improves **10.18%** against the probabilistic M0 control. Its central-estimate MAE improves **0.255 minute (4.86%)** against the actual last-five median. These are reconstructed historical results, not authenticated pregame forecasts or attainable prop-probability gains.

## Evidence and scope

The November 11 forensic audit (`docs/V25_FULL_NOV11_FORENSIC_AUDIT_AND_PHASE2_GATE.md`) and `v2/nhl_nba_phase1.py:433` identify the original simple evaluator’s exposure as the median of five archived played games. The audit’s source-backed 250 NBA contracts were from five games on one date; they do not identify how much residual count dispersion comes from minutes. This study evaluates minutes directly and does not modify event likelihoods or claim to explain that earlier count variance.

Governing plan: PA-V25-MASTER-2026-11-09 / v1.1. The current user authorizes this bounded NBA workstream. Base main: `912bc70`; fitting/scoring commit: `df22657d0ee51005e0d7417a4a61468939217736`. Inputs are pinned to data-branch commit `97a8bb566826afe5a3e5a7b8c632043d8a1dca24`. No active GitHub training runs were observed during inspection; NUTS CI remains explicitly disabled. The Deepnote project was inspected through MCP; its operational machine was stopped. Only a separate unscheduled handoff notebook and WS2-owned files were added.

Raw population: **52,608** positive-minute rows across two NBA source shards. Identity audit excluded **68** All-Star exhibition rows before histories: 24 rows in one training game and 44 rows in three evaluation games. WEST/EAST/CHK/KEN/CAN/SHQ are outside the fixed 30-franchise identity set. This local adapter correction is documented in `integrity_amendment.json`; the initial unfiltered report, model and predictions remain preserved. No source collector was edited.

Clean population: **52,540** appearances. Training: 2023-11-02–2024-04-14, **23,533** eligible rows. Evaluation: 2024-10-22–2025-04-13. Five-prior-appearance exclusions: 2,776 training and 590 evaluation rows, retained in `rejected_ledger.csv.gz`. Competition scope is franchise NBA games in these source shards, including the Cup final where present; this is not a claim that every row is a regular-season standings game.

All source minutes are integer-rounded. The raw population’s team totals include the exhibition failures; clean regulation/OT totals still have normal rounding discrepancies. No historical retrieval/publication clocks are available. Prior calendar dates are enforced, but availability before each historical decision time cannot be authenticated. Team identity/home context is reconstructed; position comes from the player’s prior appearance. Current or future game minutes, final margin, fouls, starting status and overtime never enter feature construction.

Descriptive positive-game minutes have overall SD 10.91 minutes, versus median within-player SD 6.74. Both describe playing-time variability conditional on observed appearance. Neither estimates participation uncertainty, which requires the missing roster/DNP universe.

## Models and statistical protocol

- **M0:** last-five played median. Its point forecast remains intact. For proper-score comparison, M0-P adds train-only role-specific residual variance and the same legal minutes family as the challengers. A pure deterministic M0 has CRPS equal to point MAE, degenerate intervals and no valid continuous NLPD, so those scores must not be compared as if it supplied a calibrated distribution.
- **M1:** last-ten played mean shrunk with five pseudo-games toward training-only position × prior workload-role cohorts. Player and cohort residual variance are shrunk with ten pseudo-games. Roles are historical low (<14), middle (14–<28) and high (≥28) minute states; they are not confirmed starter labels.
- **M2:** a single ridge regression (alpha 100), fitted once with training-only standardization. Features are prior median/means, variability, recent trend, calendar rest, prior missed-team-game proxy, team continuity, home and historical workload state. Mean is bounded by expected game length including OT; variance uses the same shrinkage structure. No market, current injury status, realized lineup or teammate-absence effect is invented.

The conditional minutes law is a scaled beta share of game length with a pregame geometric overtime mixture. Overtime has unlimited theoretical count support. Beta and a truncated lognormal were compared only on a deterministic 2,000-row training sample; beta had the better CRPS and log score. This does not establish beta as universally adequate, especially for early exits. Variances represent empirical predictive game-to-game spread conditional on fitted parameters; cohort/ridge hyperparameter posterior uncertainty is not integrated. No neural network, NUTS, dynamic substitution chain or outcome simulator was trained.

Train-only OT probability is 0.0487; continuation probability is 0.1304. OT labels for fitting are reconstructed from both teams’ rounded minute totals with a ±6-minute integrity tolerance. They are outcomes used to estimate a training frequency, never target-game input features. Numerical OT-series omission is below 1e-12; the conservative minute-tail bound beyond 120 is 2.01e-14.

The committed preregistration (`975dc89`, experiment SHA `470ef7262de1a13c2075a7494577e42b6b28417fc411866cc80fc0558fc41d90`) preceded model scores. Primary objective: CRPS; minimum 1% gain, paired 97.5% upper CI below zero for two challengers, MAE within 0.2 minute and coverage guardrails. Calendar date is the primary bootstrap cluster, 1,000 paired draws; game and additional calendar-week sensitivities are reported. Repeated players, temporal dependence, historical design exposure and the disclosed integrity correction prevent a confirmatory interpretation. No hyperparameters were changed after scores.

## Matched evaluation

Point MAE uses each model’s central estimate; predictive-median MAE is shown separately because beta skew makes M0-P’s predictive median differ from the original median point forecast. Lower CRPS/NLPD is better. NLPD is −log probability of the observed integer-rounded minute bin (±0.5), not a continuous density.

| Model | N | Point MAE | Predictive-median MAE | CRPS | Rounded-bin NLPD | 50% coverage | 80% coverage | 90% coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M0 | 25,641 | 5.2427 | 5.5182 | 3.9561 | 3.4209 | 54.03% | 81.85% | 90.58% |
| M1 | 25,641 | 5.2647 | 5.2441 | 3.7246 | 3.2797 | 51.56% | 80.48% | 88.97% |
| M2 | 25,641 | 4.9878 | 4.9712 | 3.5533 | 3.2540 | 52.12% | 80.46% | 89.19% |

| Challenger − M0 | CRPS difference | Date-cluster 97.5% CI | Game-cluster 97.5% CI |
|---|---:|---|---|
| M1 | -0.2315 | [-0.2673, -0.1978] | [-0.2670, -0.1978] |
| M2 | -0.4027 | [-0.4391, -0.3717] | [-0.4330, -0.3715] |

Both challengers pass the preregistered aggregate numerical gates. That is insufficient for adoption under the user’s no-material-regression rule. M1’s central-estimate MAE can slightly worsen even while its distribution score improves. M2 remains the more promising bulk-minutes candidate, with important tail failures below.

## Cohort diagnostics

Cohorts overlap. High/mid/low roles, recent changes, return gaps, team changes and early-season status use only prior observations. Early exits, low realized minutes, overtime, starters and final-margin groups are postgame diagnostic strata. Their outcome-conditioned interval coverage is not expected to equal the unconditional nominal level; regressions against M0 still identify stress weaknesses.

| Cohort | N | M0 CRPS | M1 CRPS | M2 CRPS | M0 90% coverage | M2 90% coverage |
|---|---:|---:|---:|---:|---:|---:|
| back_to_back_appearance_proxy | 3,937 | 4.044 | 3.803 | 3.611 | 90.4% | 88.5% |
| changed_role_proxy | 4,112 | 4.805 | 4.891 | 4.261 | 85.6% | 88.8% |
| early_exit_proxy | 51 | 22.406 | 22.483 | 20.987 | 0.0% | 0.0% |
| early_season | 4,777 | 4.308 | 4.039 | 3.740 | 88.5% | 88.9% |
| high_historical_minutes | 8,839 | 3.302 | 3.094 | 3.027 | 91.8% | 90.2% |
| inferred_overtime_outcome | 1,129 | 5.603 | 5.774 | 5.566 | 77.1% | 68.0% |
| low_historical_minutes | 5,062 | 4.939 | 4.293 | 4.112 | 89.9% | 87.0% |
| low_minute_outcome_le5 | 2,154 | 4.002 | 4.571 | 4.475 | 80.7% | 72.3% |
| mid_historical_minutes | 11,740 | 4.025 | 3.954 | 3.709 | 90.0% | 89.4% |
| return_after_missed_team_games_proxy | 1,797 | 4.628 | 4.143 | 3.971 | 87.3% | 90.0% |
| stable_role_proxy | 21,529 | 3.794 | 3.502 | 3.418 | 91.5% | 89.3% |
| team_change | 196 | 5.905 | 4.930 | 4.981 | 77.6% | 83.2% |

The beta family does not capture the early-exit/low-minute component well enough. The early-exit proxy means actual <10 minutes after a prior high-minute role; it is not an authenticated injury/ejection label. Overtime outcomes also expose a coverage regression: merely adding a small OT mixture does not learn who receives the extra exposure. Changed-team and changed-role rows remain difficult. Return-gap improvement is not evidence of injury recovery modeling because absence reasons are unknown.

Rotation workload-state error rates: M0 31.54%, M1 31.77%, M2 30.39%. This is three-bin workload classification, not a validated starting-lineup forecast.

The separate source-backed 32-boxscore sample contains 861 roster entries, including 148 explicit postgame DNPs; 682 played entries match the evaluation. All 32 retrievals succeeded. Sample selection used chronological spacing before model scores. Starter/bench and margin information is reporting-only.

| Postgame-only sample | N | M0 CRPS | M1 CRPS | M2 CRPS |
|---|---:|---:|---:|---:|
| bench_outcome_sample | 364 | 3.770 | 3.405 | 3.296 |
| closer_game_outcome_lt20_sample | 499 | 3.670 | 3.342 | 3.249 |
| starter_outcome_sample | 318 | 3.535 | 3.321 | 3.175 |
| substantial_blowout_outcome_ge20_sample | 183 | 3.634 | 3.430 | 3.215 |

The actual postgame starter sample is small; no broad causal starter/blowout claim follows. Teammate-absence effects, verified return-from-injury effects, authenticated team rest and market/spread ablations are blocked by missing pregame evidence. Days between player appearances can conflate rest and missed games.

## Controls and participation

M2 mean-context-disabled CRPS: 4.3614; deterministic context-permutation CRPS: 5.0719. These controls support the value of causal workload continuity within this reconstruction. Disabling coefficients is not a separately refitted reduced model, and permuting context changes the joint feature distribution; these are negative controls, not unbiased feature-importance estimates.

**Participation false-positive and false-negative rates are unavailable, not zero.** Appearance-only source shards do not contain the pregame candidate universe or complete inactive/DNP labels. The 148 sampled postgame DNP entries cannot retroactively define that universe. No participation classifier is claimed as trained or validated.

The contract distinguishes confirmed inactive, confirmed active, probable participant, questionable participant and unverified status. Active roster membership does not guarantee playing. Supplied participation probabilities and uncertainty intervals retain their own provenance. A missing probability remains unknown and causes unconditional-opportunity abstention; it is not converted to absence. Confirmed inactive/ineligible yields participation probability zero and an explicit abstention. Conditional minutes remain distinct from product-specific DNP/void and partial-game eligibility rules.

## Team opportunity and integrity

A team scenario samples a restricted eligible roster and shared game OT, then projects conditional exposure onto a box/simplex with total 240+25×OT and each player capped only by game length or an explicitly supplied latent early-exit scenario limit. No generic 35/40-minute physical cap is imposed. Selected participants retain positive exposure to numerical precision. Underfilled rosters, contradictory zero-exposure participation and infeasible early-exit limits are retained as invalid scenarios rather than silently repaired.

A constructive clock-interval decomposition verifies five distinct players on court in every segment. Both teams reproduce the same OT when supplied the same game seed and OT parameters. This is an opportunity witness, not a learned substitution model. Projection changes player marginals and dependence; the team-consistent joint law needs separate validation before an outcome sampler relies on it.

In the 1,000-scenario deterministic roster fixture, independent sampling violated team totals in 100% of cases: mean absolute error 20.42 and maximum 141.89 player-minutes. Constrained error was at most 1.71e-13, with **zero** conservation or five-on-court violations. The fixture included 53 OT and 90 unusual-rotation states. Mean absolute projection adjustment was 2.04 minutes/player. These are mechanism tests, not historical accuracy estimates.

## CPU, verification and prospective capability

The full frozen fitting/comparison plus two controls took 224.93 wall seconds and 224.57 CPU seconds, with peak RSS 357.1 MiB, using one BLAS thread. Per-model evaluation includes a quarter-minute numerical CDF grid, CRPS, rounded-bin log score and quantiles, so it costs more than production-style inference.

| Model | CPU seconds for 100 forecast contracts |
|---|---:|
| M0 | 0.849 |
| M1 | 0.744 |
| M2 | 0.798 |

The 1,000 team-scenario fixture took 0.415 CPU seconds. Exact dependency versions are in `requirements.txt`. The scoring helper uses SciPy trapezoidal integration for compatibility with Deepnote’s older NumPy; the first hosted compatibility failure and successful rerun are retained in `deepnote_receipt.json`.

The local suite has 25 passing WS2 tests, including randomized conservation/lineup witnesses, independent CRPS quadrature, temporal corruption, current/future outcome mutation, duplicate identities, exhibition exclusion, unknown participation, DNP conditioning, invalid rosters, deterministic seeds, latent early exits and immutable freezes. Existing untouched NBA phase-1/population/phase-1.5 suites add 34 passing regression tests. These executable checks are a sequential engineering audit, not independent WS4 statistical validation.

The manual `research.nba_ws2.shadow` CLI accepts independently supplied pregame adapter records, sets execution-time forecasts, rejects already-started events, retains failed candidates and creates files exclusively. An end-to-end synthetic fixture generated one explicitly synthetic conditional forecast and retained one past-event rejection. **Actual authenticated future-slate forecasts created: zero.** The capability exists; a genuine future NBA roster/availability/source packet was not supplied. No synthetic fixture is relabeled as a real shadow forecast.

## Integration handoff and stop decision

- **WS1:** provide the local `OpportunityFeatureAdapter` / `PregameOpportunityInput` fields with source availability and ingestion clocks, source hashes, current candidate/active-roster identities, verified status/probability provenance and independently computed causal features. Investigate the four All-Star source games; only WS2’s local adapter filters them here. No WS1-owned schema was edited.
- **WS3:** consume `NBAOpportunityForecast/1.0.0` conditional moments/quantiles or valid shared game-scenario minute allocations. Preserve scenario IDs and deterministic seeds. Product eligibility is separate. The `FutureOutcomeSampler` protocol intentionally does not implement per-minute production or prop likelihoods.
- **WS4:** independently test the exact locked models against M0, preserving all rejected/unavailable candidates, using genuine prospective availability/roster receipts. Assess participation FPR/FNR, tail calibration, dependence, and whether opportunity improvements yield better prop probabilities. None of those claims is established here.
- **Decision:** M1/M2 show aggregate historical CRPS gains; both remain shadow research. Material stress regressions and missing prospective participation evidence block adoption. Retain M0 as benchmark. No Tier, production decision, schedule, model promotion or heavy training is authorized or performed.

Reproduce from the repository root with `bash research/nba_ws2/reproduce.sh`, then run `python -m research.nba_ws2.benchmark_forecasts`, `python -m research.nba_ws2.audit_results`, and `python -m research.nba_ws2.write_report`. The script uses pinned source branch bytes and the original experiment. Full matched predictions, exclusion ledgers, model parameters, source/output hashes and initial superseded evidence are included. Rollback removes this isolated WS2 module, tests and research directory; no production import or configuration needs restoration.

See `results/evidence_manifest.json`, `results/audit_receipt.json`, and `results/deepnote_receipt.json` for exact hashes and execution/hosting identifiers. The draft PR remains unmerged and requires independent review before acceptance.
