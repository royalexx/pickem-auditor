# NFL 2024 volume-only replay — audit note (2026-11-09)

## Policy and deployment

The user approved excluding NFL touchdown markets (passing/rushing/receiving/anytime), QB hits, and passes defended from ranking. The separate production-only ranking policy was **merged to `main` as PR #77**, squash SHA `5d98a6efd893e6d60c15983b67a76ce9e4f2d0d9`. It is enforced in `slate_candidate_ranking.py`, `research_ranked_board.py`, `verified_board.py`, and `conditional_tier3_board.py` using `nfl_volume_market_policy.py`. NBA/NHL unaffected.

The research replay does not merge its ridge forecasting engine, modified source collection, synthetic line settings or historical weights into production.

## Replayed market universe

Exactly 11 NFL markets: pass attempts, completions, passing yards, targets, receptions, receiving yards, carries, rushing yards, tackles + assists, solo tackles, tackle assists.

Markets absent from both frozen predictions and training updates: passing touchdowns, receiving touchdowns, rushing touchdowns, QB hits, passes defended. Anytime TD also blocked in ranking policy, although not a 2024 count-model market.

## Training/evaluation methodology

- Source: nflverse normalized 2021–2024. Initial model training includes **2021–2023 only**. Every 2024 week is predicted, all 11 market forecasts hash-locked, then settled, and the next week's sufficient statistics updated afterward.
- Independent verification checked **18/18** locks with exactly 11 markets and **17/17** prior-week parameter training increments. No forbidden market appeared in the receipts.
- Uses previous five/ten played-game medians and role reference for **synthetic** research lines; these are **not bookmaker quotes**.
- Historical player availability is reconstructed from past snaps/appearances, not contemporaneous active lists, and the model/line methodology was developed retrospectively after 2024. This is NOT a genuinely untouched 2024 prospective validation.
- Data from the previous audit was kept and not deleted.

## Aggregate result

| Statistic | Value |
|---|---:|
| Frozen forecasts | 40,351 |
| Graded | 31,613 (78.35%) |
| Ungraded/unmatched | 8,738 (21.65%) |
| Correct directional picks | 18,799 |
| Matched directional accuracy | 59.47% |
| Always-Under on same research thresholds | 56.26% |
| Apparent lift over always-Under | +3.21 percentage points |
| Selected Under share among graded | 71.23% |
| Brier score on synthetic lines | 0.23670 |
| Research top-ten selected | 180 |
| Research top-ten Under selections | 173 of 180 (96.11%) |
| Research top-ten matched | 111 of 180 |
| Research top-ten known misses | 29 (82 hits) |
| 90%+ confidence, matched | 35 |
| 90%+ confidence, claimed mean / realized | 92.66% / 60.00% |

The **90%+ confidence bucket is seriously miscalibrated** on this limited subset and the 180 top-ten research selections remain disproportionately Under. The model is **not publication eligible**, and no claim of an actual sportsbook edge is supported.

## Weekly matched results

| Week | Graded | Matched accuracy | Unmatched |
|---:|---:|---:|---:|
| 1 | 1,430 | 63.64% | 1,429 |
| 2 | 1,700 | 60.29% | 214 |
| 3 | 1,820 | 58.74% | 326 |
| 4 | 1,831 | 59.42% | 410 |
| 5 | 1,571 | 59.71% | 377 |
| 6 | 1,582 | 60.49% | 460 |
| 7 | 1,761 | 60.93% | 480 |
| 8 | 1,869 | 57.73% | 529 |
| 9 | 1,782 | 59.03% | 495 |
| 10 | 1,708 | 60.89% | 455 |
| 11 | 1,731 | 59.33% | 411 |
| 12 | 1,607 | 57.00% | 344 |
| 13 | 1,919 | 57.27% | 440 |
| 14 | 1,564 | 59.72% | 365 |
| 15 | 1,988 | 61.17% | 392 |
| 16 | 1,992 | 59.14% | 438 |
| 17 | 1,936 | 57.39% | 486 |
| 18 | 1,822 | 59.66% | 687 |

## Reproducibility

- Research code: `scripts/nfl_weekly_blind_volume_only.py` and `scripts/nfl_research_prop_eligibility_v2.py`.
- Pre-run tests: `tests/test_nfl_volume_only_policy.py`, `tests/test_nfl_plausible_prop_eligibility_v2.py`, `tests/test_nfl_adversarial_invariants.py`; all passed.
- Production gate six dedicated test suites passed in detached Deepnote run `0e8c87fc-82de-47a8-a3d7-a21ad33ca364`.
- Research replay detached Deepnote run `f6d4286c-4404-4c66-8773-5f7701298b2a` completed; reports stored under `reports/nfl_2024_volume_only/` and full per-prop ledgers under Deepnote `pickem_runs/2024_volume_only_blind_retrain_20261109/`.
- The original report CSV name says `2024_18weeks_x_16markets.csv`; its content has 11 markets. The GitHub-published copy is correctly named `2024_18weeks_x_11markets.csv`.

## Next release gates

Before using these research probabilities as real betting probabilities, obtain independent timestamped sportsbook lines and two-sided odds, pregame active player confirmation, explicit DNP/void/zero grading taxonomy, walk-forward probability calibration by side and market, and an abstention-capable shortlist. Evaluate performance against realistic market benchmarks, not arbitrary synthetic thresholds.

## Post-run diagnostic: does weekly regression retraining improve accuracy?

A 2026-11-09 independent paired ablation reconstructed **all 40,351 original probabilities exactly** and compared two setups on **identical 31,613 graded contracts**: (1) reusing regression coefficients and dispersion fit through December 2023, and (2) recomputing those coefficients each week after 2024 settlement. Both receive the same updated recent player histories, role/position baselines, hypothetical lines, and availability candidates. This **isolates the effect of updating regression coefficients only**, not every aspect of online learning.

| Metric | Frozen end-2023 regression | Weekly refit |
|---|---:|---:|
| All-season directional accuracy | **59.507%** | 59.466% |
| 2024 W1–W9 accuracy | **60.009%** | 59.892% |
| 2024 W10–W18 accuracy | 59.034% | **59.064%** |
| All-season Brier | 0.23670580 | 0.23670076 |
| Accuracy effect of refitting | baseline | **-0.0411 percentage points** |
| Brier improvement from refitting | baseline | **0.00000504** |

20,000 week-cluster bootstrap replicates: online-minus-frozen accuracy difference 95% interval **[-0.116, +0.040] percentage points**; Brier difference 95% interval **[-0.0000381, +0.0000268]**. This experiment found **no meaningful evidence that global ridge coefficient refitting adds predictive value**. It does not evaluate or invalidate Bayesian/NUTS updating and does not rule out improvement from updating player-level historical features.

By Week 18, pass-attempt training examples increased from 1,950 to 2,571 and tackles+assists from 25,256 to 32,953; fit weights changed. But they did not yield reliable new directional accuracy.

The model is intentionally simple: nine features per market, no opponent-specific response or injury and lineup inputs; complete prior-season statistics retain weight over later weeks. Both versions rank versus synthetic research thresholds rather than verified sportsbook quotes. Weekly accuracy is also affected by severe and changing outcome-matching selection (Week 1 1,430/2,859 matched, ~50%; Week 18 1,822/2,509 matched, ~73%).

### Four provably incorrect Week 1 player/team assignments in selected top-ten

| Player | Forecasted 2024 team | Real 2024 team | Synthetic research pick | Claimed Under |
|---|---|---|---|---:|
| Mac Jones | New England | Jacksonville | Carries Under 3.5 | 98.93% |
| Sam Howell | Washington | Seattle | Carries Under 3.5 | 97.73% |
| Joe Flacco | Cleveland | Indianapolis | Carries Under 2.5 | 97.10% |
| Tim Settle | Buffalo | Houston | Solo tackles Under 1.5 | 95.75% |

Sources: 2024 NFL March trade records https://www.nfl.com/transactions/league/trades/2024/3 ; Patriots confirmation https://www.patriots.com/news/patriots-trade-qb-mac-jones-to-jacksonville ; Colts signing https://www.colts.com/news/joe-flacco-signed-free-agent-agency-2024-backup-anthony-richardson ; Houston Texans signing https://www.houstontexans.com/news/houston-texans-transactions-03-15-2024 .

All four are **UNMATCHED**, not winning picks. The 2024 research replay reused past team affiliation, including Week 1 stale last-season identities; it had no pregame official roster confirmation. This demonstrates a **hard roster eligibility failure**, not just a poor probability estimate. The current research replay must **not** be promoted.

Reproducible forensic assets (file names): `reports/nfl_2024_volume_only/diagnostics/online_vs_frozen_ridge_ablation.json`, `weekly_online_vs_frozen.csv`, `learning_and_name_audit.json`, and `all_top10_with_verified_source_names.csv`. The separate Deepnote notebook `2024 NFL online learning ablation — frozen 2023 ridge vs weekly updated ridge on identical props` completed successfully.

**Required next iteration**: contemporaneous roster as-of join (fail closed when unverified), correct player-team assignment, offered line/odds archive, DNP/void settlement taxonomy, plus opportunity-based/player-and-opponent-level predictive model. Compare frozen vs online forecasts and calibrated market-edge performance on genuinely independent future slates, not just average hit-rate drift.
