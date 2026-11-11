# Ten-Year versus Three-Year NFL Matchup Memory: Controlled Rolling-Origin Ablation
Date: 2026-11-11
Status: research-only; no betting or production certification.

## Objective
Isolate the effect of historical lookback length while holding the ridge architecture and hyperparameters fixed. Targets: team plays (pass attempts + rush attempts) and pass-play fraction. No current-week actual was passed as an input.

## Study protocol
- NFL 2016–2025, 175 regular-season weekly folds, 5,278 team-game observations.
- Retrospective sources collected in 2026; original historical pregame publication not certified.
- For each season/week, fit identical ridge models on earlier three or ten seasons plus previous weeks in the current year; no future games.
- Opponent-aware features: offense recent plays, defense plays allowed, offense and opponent pass fractions, short-term team momentum.
- Ridge penalty 32; exponentially weighted records with 2.5-year half-life.
- Paired 175-week-cluster bootstrap for the 10-year minus 3-year MSE difference.

## Primary results

| Score | Three-year | Ten-year | Difference (10 - 3) |
|---|---:|---:|---:|
| Offensive plays MSE | 71.022666 | 71.021784 | -0.000882 |
| Offensive plays MAE | 6.705488 | 6.703151 | -0.002337 |
| Pass-share MSE | 0.010777467 | 0.010736522 | -0.000040945 |

95% week-cluster interval for plays MSE delta: [-0.14244, +0.14363]; effect indistinguishable from zero.
95% week-cluster interval for pass-share MSE delta: [-0.00005962, -0.00002324]; modestly favorable ten-year memory in this development-exposed cohort (0.38% relative MSE).

## Learned relationships at 2025 Week 1
Ten-year training provided 5,246 past team-game examples (2015–24), versus 1,630 over 2022–24.
The 2025 Week 1 ridge plays intercept was 61.10674, offense prior plays normalized slope +3.74599, opponent plays allowed slope +1.44222 and short-term offense momentum slope +0.97234.
The pass-rate intercept was .56731, offense pass tendency slope +.10071 and opponent allowed pass tendency slope +.05833.
Normalization: play-volume deviations are divided by 12; pass-fraction deviations from .57 multiplied by 5.

These are predictive associations, NOT causal effects. Schemes, routes, injuries, current snap counts and original betting quotes were not available for authentic as-of joins in the archived source.

## Conclusion
The evidence does not justify forcing a ten-year lookback into *every* short-horizon distribution. Use a ten-year accessible population library for stable relationships and prefer statistically validated feature-specific memory and recency. Player history still needs short-term position/usage windows.

Saved Deepnote artifacts:
- reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V3_TEN_VS_THREE_YEAR_MATCHUP_ABLATION/V3_MATCHUP_10Y_VS_3Y_ABLATION.json
- reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V3_TEN_VS_THREE_YEAR_MATCHUP_ABLATION/V3_ALL_MATCHUP_WEEK_RESULTS.csv
- executable research/nfl_v3_matchup_10v3_year_ablation_20261111.py

No model promotion or Tier confidence may be inferred from this ablation.
