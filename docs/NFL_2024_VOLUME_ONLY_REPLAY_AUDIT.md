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
