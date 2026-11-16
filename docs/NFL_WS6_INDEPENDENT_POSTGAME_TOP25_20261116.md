# NFL November 15, 2026 — independent J2 player-stat error ranking

**Source:** Deepnote `reports/nfl_20261115_prospective/ws6_independent_postgame_20261116_v1/secondary_diagnostics_v1.json` SHA-256 **`a03da706021ed83b9052a8f08f12305663d6fec7d1c7639fc47b499417ff85f5`**. Executed in project `9cc31536-93be-44db-bdeb-06fba3f61410`, notebook `55763ef482de4d6e8bc73cec67eed0a1`, run `b23b5d45-d964-4d78-a17a-06e6b5200a1d`, success.

The ranking uses one J2 v0.4.2/v0.4.3 frozen predictive distribution **per exact ESPN event/player/stat** rather than duplicating alternate lines or bookmakers. Official player outcomes are ESPN FINAL stats extracted from original archived HTTP response bytes; absent players/category rows remain missing, never zero. These are **outcome prediction errors, not established causal errors in a specific pregame parameter**. Original sportsbook/provider terms remain uncertified.

Input: original frozen J ledger SHA `759dc467ef3bdc589b3588c7adb59254076e5d071dbf35bf167c408447e56431`. 416 distinct forecast groups, 396 observed, 18 player not boxed, 2 category not boxed. Separate 56 missing original draw-series keys do not exclude corresponding point forecasts.

## 25 largest standardized point forecast errors

Standardized error is `(official_result - pregame_mean)/sqrt(pregame_variance)`, with variance read from the original SHA-checked J2 simulation. Largest absolute standardized residual first. Positive means the model underpredicted; negative means the model overpredicted.

| Rank | ESPN event | Player | Market | Frozen J2 mean | ESPN final | Actual − predicted | Standardized error |\n|---:|---|---|---|---:|---:|---:|---:|
| 1 | 401873058 | Emmett Johnson | rush_attempts | 3.18 | 22 | 18.82 | 7.41 |
| 2 | 401873061 | Devin Duvernay | receiving_yards | 1.74 | 35 | 33.26 | 7.25 |
| 3 | 401873057 | Tony Pollard | receiving_yards | 6.79 | 66 | 59.21 | 7.11 |
| 4 | 401873063 | Deebo Samuel Sr. | rushing_yards | 8.01 | 78 | 69.99 | 5.76 |
| 5 | 401873059 | Ollie Gordon II | receiving_yards | 4.09 | 39 | 34.91 | 5.28 |
| 6 | 401873063 | Christian McCaffrey | receiving_yards | 37.51 | 161 | 123.49 | 4.90 |
| 7 | 401873058 | Emmett Johnson | rushing_yards | 19.40 | 101 | 81.60 | 4.68 |
| 8 | 401873059 | Anthony Gould | receptions | 0.09 | 2 | 1.91 | 4.49 |
| 9 | 401873055 | Chuba Hubbard | receiving_yards | 16.96 | 80 | 63.04 | 4.00 |
| 10 | 401873059 | Anthony Gould | receiving_yards | 1.39 | 28 | 26.61 | 3.90 |
| 11 | 401873061 | Konata Mumpfield | receiving_yards | 13.44 | 81 | 67.56 | 3.84 |
| 12 | 401873064 | Ja'Marr Chase | receiving_yards | 77.35 | 231 | 153.65 | 3.58 |
| 13 | 401873057 | Tony Pollard | receptions | 1.81 | 8 | 6.19 | 3.42 |
| 14 | 401873059 | Seth McGowan | rushing_yards | 23.22 | 77 | 53.78 | 3.35 |
| 15 | 401873060 | Jordan Mason | rush_attempts | 5.69 | 16 | 10.31 | 3.04 |
| 16 | 401873057 | Tyjae Spears | rushing_yards | 7.28 | 28 | 20.72 | 2.85 |
| 17 | 401873058 | Olamide Zaccheaus | receiving_yards | 3.53 | 17 | 13.47 | 2.79 |
| 18 | 401873057 | Josh Cameron | receiving_yards | 15.58 | 67 | 51.42 | 2.65 |
| 19 | 401873054 | Breece Hall | receiving_yards | 16.44 | 67 | 50.56 | 2.65 |
| 20 | 401873061 | Blake Corum | rushing_yards | 44.82 | 100 | 55.18 | 2.57 |
| 21 | 401873057 | Trevor Lawrence | rushing_yards | 7.19 | 27 | 19.81 | 2.57 |
| 22 | 401873061 | Simi Fehoko | receiving_yards | 1.84 | 21 | 19.16 | 2.52 |
| 23 | 401873057 | Cam Ward | rushing_yards | 12.86 | 39 | 26.14 | 2.52 |
| 24 | 401873057 | Bhayshul Tuten | rush_attempts | 13.19 | 26 | 12.81 | 2.45 |
| 25 | 401873063 | George Pickens | receptions | 4.17 | 11 | 6.83 | 2.43 |

## 25 largest absolute point forecast errors

Absolute differences mix yards and counts and must **not** be interpreted as directly comparable model failures; this table is an artifact-discovery aid. Compare within a single market before prioritizing mechanisms.

| Rank | ESPN event | Player | Market | Frozen J2 mean | ESPN final | Actual − predicted | Standardized error |\n|---:|---|---|---|---:|---:|---:|---:|
| 1 | 401873064 | Ja'Marr Chase | receiving_yards | 77.35 | 231 | 153.65 | 3.58 |
| 2 | 401873064 | Joe Burrow | passing_yards | 265.99 | 409 | 143.01 | 1.64 |
| 3 | 401873063 | Brock Purdy | passing_yards | 259.98 | 389 | 129.02 | 1.44 |
| 4 | 401873063 | Christian McCaffrey | receiving_yards | 37.51 | 161 | 123.49 | 4.90 |
| 5 | 401873054 | Geno Smith | passing_yards | 268.54 | 148 | -120.54 | -1.34 |
| 6 | 401873062 | Fernando Mendoza | passing_yards | 262.64 | 143 | -119.64 | -1.37 |
| 7 | 401873064 | Jaylen Warren | rushing_yards | 109.40 | 15 | -94.40 | -2.37 |
| 8 | 401873058 | Michael Penix Jr. | passing_yards | 200.04 | 286 | 85.96 | 1.15 |
| 9 | 401873058 | Patrick Mahomes | passing_yards | 265.14 | 348 | 82.86 | 0.90 |
| 10 | 401873057 | Parker Washington | receiving_yards | 70.11 | 152 | 81.89 | 1.78 |
| 11 | 401873058 | Emmett Johnson | rushing_yards | 19.40 | 101 | 81.60 | 4.68 |
| 12 | 401873063 | Dak Prescott | passing_yards | 261.62 | 343 | 81.38 | 0.93 |
| 13 | 401873063 | George Pickens | receiving_yards | 67.24 | 145 | 77.76 | 1.58 |
| 14 | 401873061 | Carson Beck | passing_yards | 182.58 | 108 | -74.58 | -1.17 |
| 15 | 401873063 | Deebo Samuel Sr. | rushing_yards | 8.01 | 78 | 69.99 | 5.76 |
| 16 | 401873061 | Konata Mumpfield | receiving_yards | 13.44 | 81 | 67.56 | 3.84 |
| 17 | 401873057 | Cam Ward | passing_yards | 165.66 | 231 | 65.34 | 1.09 |
| 18 | 401873057 | Trevor Lawrence | passing_yards | 287.54 | 352 | 64.46 | 0.66 |
| 19 | 401873055 | Chuba Hubbard | receiving_yards | 16.96 | 80 | 63.04 | 4.00 |
| 20 | 401873057 | Tony Pollard | receiving_yards | 6.79 | 66 | 59.21 | 7.11 |
| 21 | 401873062 | Brock Bowers | receiving_yards | 76.74 | 18 | -58.74 | -1.24 |
| 22 | 401873059 | Daniel Jones | passing_yards | 166.25 | 108 | -58.25 | -0.86 |
| 23 | 401873056 | Denzel Boston | receiving_yards | 73.46 | 16 | -57.46 | -1.15 |
| 24 | 401873054 | DJ Moore | receiving_yards | 34.75 | 90 | 55.25 | 1.81 |
| 25 | 401873061 | Blake Corum | rushing_yards | 44.82 | 100 | 55.18 | 2.57 |

## Forecast distribution diagnostics without bookmaker-line repetition

| Market | Unique observed distributions | MAE | Signed actual−predicted mean | Draw-backed | 90% interval coverage |
|---|---:|---:|---:|---:|---:|
| pass_attempts | 21 | 6.193 | 0.092 | 21 | 100.0% |
| pass_completions | 21 | 4.642 | -0.542 | 0 | Not available |
| passing_yards | 21 | 61.238 | 9.530 | 21 | 100.0% |
| receiving_yards | 123 | 23.932 | 4.936 | 123 | 88.6% |
| receptions | 123 | 1.630 | 0.121 | 123 | 95.9% |
| rush_attempts | 35 | 4.267 | 1.248 | 0 | Not available |
| rushing_yards | 52 | 19.716 | 2.964 | 52 | 73.1% |

The archived J2 player-stat mean error across quarterback pass attempts is +0.092 attempts (21 observed) but MAE is 6.19. A low **average** QB opportunity bias does not imply individual game volumes are accurate.

The following actual extra passers appeared alongside the primary named QB in independently archived ESPN final box scores: Geno Smith's team recorded 20 attempts by Cade Klubnik; Jordan Love's team recorded 2 by Tyrod Taylor; Kyle McCord's team recorded 1 by Malik Washington; Aaron Rodgers's team recorded 3 by Mason Rudolph. The original J2 forecast was for the primary passer only, not the entire team. These postgame facts diagnose workload/availability uncertainty; they do not establish what should have been known or changed pregame.

## Interpretation and scientific blockers

Standardized residuals reveal tail/role vulnerabilities. For example Emmett Johnson's 22 rush attempts against 3.177 expected is a +7.41 predictive-SD outlier; Tony Pollard receiving yards 66 against 6.794 expected is +7.11 SD. These are striking errors but neither shows whether the original cause was role, volume, share, conditional efficiency, injury, game script or an incorrect primary-source feature.

All 21 QB-completion and 35 rushing-attempt original predictive series are presently unresolved by exact player-stat key, so their CRPS and interval scores remain unavailable even though their pregame point means and ESPN actuals are valid. J2 rushing yards 90% intervals cover 73.1% (52 observed player-stats), compared with 100% for QB pass attempts (21) and 95.9% for receptions (123); one date is insufficient for long-run certification.

Other restrictions: original provider offer-equivalence has unresolved mismatches; defensive GSIS tackle-credit parity remains unverified; no validated four-factor pregame decomposition was available; date clustered uncertainty is not estimable for one day; selection and model-development exposure compromise independent holdout claims. Do not make economic or promotion decisions from this report.

**Verdict: RESEARCH DIAGNOSTIC / SHADOW ONLY.**
