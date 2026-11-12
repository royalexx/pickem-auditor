# Pick'em Auditor — NFL V3 10-year context, complete 2016–2025 weekly replay
Date: 2026-11-12 (UTC)
Status: **COMPLETE RESEARCH ONLY; NO PRODUCTION PROMOTION**
Branch: chatgpt/nfl-v3-ten-year-opponent-context-20261111

## Executive conclusion

The 175-week/ten-season experiment does **not** demonstrate that the V3 advantage over V2 strengthens as more historical seasons become available. V3 has a small aggregate Brier-score gain that shrinks rather than expands toward the end of the decade. Longer historical memory separately improves matchup **passing fraction** slightly in a controlled 10-year-versus-3-year ridge experiment, but provides no reliable advantage for offensive play count.

The result must not be treated as a live betting backtest: original player/line histories were collected retrospectively in 2026, quotes are synthetic and many offered players were not verified as active before kickoff.

## Identical paired comparison universe

- 10 NFL seasons, 175 regular-season weekly cycles, 13 volume markets.
- 556,094 original synthetic contracts offered.
- 410,807 matched to official player-game observations (73.9%).
- 407,476 scored with both V3 and original V2 forecasts.
- 175/175 saved settlement file hashes recomputed successfully. Reconstructed weighted season, market and total metrics match the archived scorecards with no discrepancies.
- Original frozen 2016–2025 V2 forecast and settlement inputs are unchanged.

## Season-by-season Brier difference

Negative = V3 advantage; positive = V2 advantage.

| Season | Matched paired | V3 − V2 Brier |
|---|---:|---:|
| 2016 | 38,953 | -0.000966 |
| 2017 | 40,151 | -0.000383 |
| 2018 | 39,742 | -0.000331 |
| 2019 | 39,109 | +0.000032 |
| 2020 | 40,125 | -0.000237 |
| 2021 | 42,310 | -0.000230 |
| 2022 | 42,042 | -0.000233 |
| 2023 | 41,119 | -0.000057 |
| 2024 | 41,353 | +0.000285 |
| 2025 | 42,572 | -0.000255 |
| **All ten years** | **407,476** | **-0.000234** |

- Overall V3 Brier = 0.23521197; V2 Brier = 0.23544619; approximately 0.10% relative loss reduction.
- 2016–2020: V3 0.23563008, V2 0.23600591; delta **-0.00037583**.
- 2021–2025: V3 0.23481646, V2 0.23491672; delta **-0.00010026**.
- Advantage falls approximately 73% from first half to second half.
- Weighted Brier-difference slope over chronology: **+0.00006748 per season** (positive means V3 advantage weakens).
- Ten-season block-bootstrap slope 95% interval **[-0.0000038, +0.0001279]**; includes zero. Do not claim a definitively worsening trend or interpret it causally.
- Recent seasons: 2024 favors V2, 2025 narrowly favors V3.

## All 13 markets: aggregate V3 minus V2 paired Brier

| Market | Difference |
|---|---:|
| Completions | -0.001936 |
| Pass attempts | -0.001715 |
| QB rushing attempts | -0.001452 |
| QB rushing yards | -0.000812 |
| Carries | -0.000621 |
| Receptions | -0.000546 |
| Passing yards | -0.000344 |
| Receiving yards | -0.000268 |
| Solo tackles | -0.000199 |
| Rushing yards | -0.000181 |
| Tackle assists | -0.000112 |
| Tackles + assists | -0.000096 |
| Targets | +0.000158 |

12/13 markets show numerically lower paired Brier for V3 in aggregate, but most improvements are **tiny**, and per-market time slopes are positive (shrinking advantages) for every listed market except solo tackles. These are descriptive; no multiple-testing- or clustering-adjusted per-market claims are made. Binary threshold scoring cannot replace full-distribution CRPS assessment by market.

## Confidence-tail evolution

| Period | V3 80%+ selected | Mean stated confidence | Observed hit |
|---|---:|---:|---:|
| 2016–2020 | 1,160 | 83.66% | 76.12% |
| 2021–2025 | 309 | 86.03% | 87.38% |

The later 80%+ tail is smaller and closer to (even exceeds) its own claims, which is consistent with increasingly selective online calibration. It is **not** proof that opportunity distributions improve with ten-year historical memory. The later 90%+ tail includes only 23 selections with a large confidence gap.

## Confidence-only benchmark, fixed on same 407,476 paired contracts

| Forecast | Brier |
|---|---:|
| V3 conservative context ensemble plus its online calibration | 0.23521197 |
| Original V2 online calibrated | 0.23544619 |
| V2 probability pushed 10% toward 50% | 0.23544695 |
| V2 probability pushed 25% toward 50% | 0.23605418 |

Uniform probability shrinkage alone does not reproduce V3's small gain. The comparison **does not identify a causal gain from additional history**: V3 changes joint opportunities and online calibration simultaneously.

## Controlled 10-year versus three-year matchup-memory ablation

This is a separate matched walk-forward test of **the same** ridge architecture with different history windows over 5,278 team-game observations, 175 weekly folds.

| Matchup outcome | 3-year MSE | 10-year MSE | Difference |
|---|---:|---:|---:|
| Team offensive plays | 71.02266591 | 71.02178378 | -0.00088213 |
| Team pass-play share | 0.010777467 | 0.010736522 | -0.000040945 |

For pass share, 10-year history reduces MSE approximately **0.38%**; its week-cluster 95% interval for the absolute difference is [-0.00005962, -0.00002324]. For total offensive plays, the interval crosses zero [-0.14244,+0.14363]. Benefits are not monotonically increasing in every season.

## Architecture and reliability limitations

1. V3 contextual population/matchup estimator accesses ten years (from 2024 onward) with an exponential 2.5-year half-life, while player role recent-appearance windows remain shorter.
2. The conservative scenario ensemble uses **25% V3 contextual simulations and 75% frozen V2 simulations**; the latter still uses up to three seasons. Therefore this is **not a complete ten-year refit of every volume stat**.
3. The pure V3 context simulator **failed the initial two-week preflight**; do not claim it is independently superior.
4. The QB1 selection is based on retrospective prior depth snapshots, not authenticated original pregame starters. Player participation/availability is not certified. Source uses synthetic prior-player median lines rather than actual historical bookmaker quotes.
5. 128 samples per contract are inadequate to certify extreme model confidence.
6. Raw CRPS values are in incompatible count/yard units; analyze per market and by full predictive distribution.
7. Ten years of historical modeling and experimentation are development-exposed; untouched prospective shadow observations are required for genuine validation.

## Decision

**Do not promote V3 or loosen Tier thresholds.** The main evidence is a modest, non-increasing improvement on a historical synthetic-line cohort.

Next experiment should use selective long-memory learning for stable pass-share patterns; retain shorter player-use memory; build dated pregame opponent injury/depth/role/coverage/snap features when available; verify QB starter source independently; perform precommitted ablations on opportunity allocation and calibrator; and evaluate prospective real-contract quotes with uniform capture.

## Deepnote artifacts

- Complete full experiment: reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V3_CONTEXT_10YEAR_FULL_20261111T233046Z/
- 175 weekly time comparisons: reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V3_TEMPORAL_TREND_FINAL_175_WEEKS/V3_ALL_175_WEEKLY_TREND.csv
- Weekly ×13-market comparisons: same path, V3_ALL_WEEK_MARKET_TRENDS.csv
- Full longitudinal metrics, intervals, history and confidence: same path, V3_WEEKLY_LEARNING_CURVE_AUDIT.json
- Fast independent reconciliation receipt: reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V3_FAST_WEEKLY_RECONCILIATION_20261112.json
- Fixed shrinkage control: reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V3_DECADE_FIXED_SHRINK_BASELINES_20261112.json
- Controlled 10-year vs 3-year matchup ablation: reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V3_TEN_VS_THREE_YEAR_MATCHUP_ABLATION/V3_MATCHUP_10Y_VS_3Y_ABLATION.json

Source code and protocol on GitHub branch: chatgpt/nfl-v3-ten-year-opponent-context-20261111.

No economic ROI, bookmaker edge, statistically certified wagering tiers or production promotion follows from this replay.
