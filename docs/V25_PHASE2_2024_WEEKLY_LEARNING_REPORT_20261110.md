# Phase 2 NFL — 2024 chronological learning and confidence audit

**Status:** RETROSPECTIVE RESEARCH ONLY — Phase 2 route-aware model **NOT** certified, no production promotion.

**Reproducibility**: frozen code SHA `284d1367ca9dc72f75e8c6fe31028c270f514893`; Deepnote detached independent audit run `86f727b4-ca9b-4386-852b-40ada8be75be`; underlying original offline report digest `90959af55dae516a3236c08bf70622c2ec2c2105561155f73800608dd6fd7e8e`; machine-readable [audit receipt](./phase2_nfl_2024_target_only_replay_20261110.json).

## Experiment and isolation

The Phase 2 **target-only** ablation trains initial team-volume and target-allocation models on 2021–2023 NFL regular-season box scores (815 games, 1,630 team-game observations); forecasts each complete 2024 week; freezes and hashes the results in a separate child process; reveals that week's official outcome only after the child exits; then updates its as-of history. Week 1 updated and frozen 2023 controls produce **identical simulation samples** thanks to shared random streams. Each weekly input includes only 2021–2023 data and 2024 game results through week `w-1`, together with outcome-free identities for week `w`. No final/current/future team attempts, player targets, realized snaps, routes, scores, odds or market data are given to the forecasting function. The separate parent/orchestrator does hold the settlement oracle, but it does not pass it to the forecast subprocess. Code and as-of file audits reject current/future labels and any outcome-bearing schedule fields.

The collected history does **not** establish receiver routes, legitimate complete pregame roster availability, verified absences or true live provider publication clocks. Accordingly, this is an ablation of **team passing volume + Dirichlet target allocation**, **not** the full route-capped/ZIDM Phase 2 model. Archived target research lines are synthetic, not verified market lines. The original as-of 2024 sample was already exposed in previous research, so this is not a pristine external holdout.

## Overall predictive-quality findings

| Metric | Weekly-updated target allocator | Frozen pre-2024 control | Independent Poisson control |
|---|---:|---:|---:|
| Team pass attempts, CRPS (544 team-games) | 4.641 | 4.795 | n/a |
| Team pass attempts, MAE | 6.510 | 6.662 | n/a |
| Targets, CRPS (method-specific observed cohort) | 1.394 (n=4046) | 1.480 (n=2542) | 1.401 (n=4046) |
| Targets, conditional binary Brier on diagnostic lines | 0.2675 | 0.2752 | 0.2690 |

**Use matched comparisons for causal learning diagnostics**, not the unequal-denominator raw target score table. For `2433` identical player/game target contracts, online-minus-frozen CRPS = **-0.1109** (18-week clustered descriptive interval [-0.1494, -0.0740]); improved on **17/18** weeks. Team pass-attempt online-minus-frozen CRPS = **-0.1536** (interval [-0.2688, -0.0390]), improved on **14/18** weeks.

On 4046 identical targets, the more complex allocator beats independently fit Poisson by only **-0.0071 CRPS**, with an 18-week descriptive interval [-0.0123, -0.0023]. This is a *small* gain relative to complexity, not a reason to promote.

**Coverage:** the source supplied 6,186 archived target research candidates. The online allocation could score 4,046 (65.4%); the frozen allocation could score 2,542 (41.1%). An unobserved or unrecognized player is **not** treated as an observed zero. The compared full-universe coverage denominator is essential.

## Complete 18-week matched performance and high-confidence outcomes

**Δ CRPS = online − no-refit**, so negative is better. The team difference is on the same team-games; target difference is on exactly the same player/game contracts available to both models. Confidence sample sizes/accuracy are from the **updated target-only allocator**; confidence is not a recommendation or wager outcome.

| Week | Team games | Team Δ CRPS | Matched targets | Target Δ CRPS | Δ vs Poisson CRPS | ≥80% correct (n) | ≥90% correct (n) | ≥95% correct (n) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 32 | 0.000 | 166 | 0.000 | -0.016 | 80.6% (31) | 92.3% (13) | 100.0% (7) |
| 2 | 32 | -0.037 | 142 | -0.015 | -0.004 | 52.8% (36) | 58.8% (17) | 55.6% (9) |
| 3 | 32 | -0.150 | 155 | -0.038 | -0.005 | 70.6% (51) | 65.6% (32) | 73.7% (19) |
| 4 | 32 | 0.274 | 148 | -0.029 | -0.028 | 64.4% (104) | 66.7% (72) | 73.2% (56) |
| 5 | 28 | -0.148 | 130 | -0.028 | -0.021 | 55.1% (98) | 60.3% (58) | 57.9% (38) |
| 6 | 28 | -0.117 | 124 | -0.121 | 0.017 | 61.3% (93) | 67.8% (59) | 69.2% (26) |
| 7 | 30 | -0.018 | 137 | -0.148 | -0.000 | 64.9% (97) | 69.1% (55) | 82.4% (17) |
| 8 | 32 | -0.161 | 145 | -0.113 | -0.011 | 65.9% (123) | 70.9% (55) | 83.3% (18) |
| 9 | 30 | -0.274 | 132 | -0.163 | 0.002 | 63.3% (90) | 88.2% (34) | 80.0% (10) |
| 10 | 28 | -0.231 | 122 | -0.231 | -0.003 | 69.2% (65) | 73.1% (26) | 62.5% (16) |
| 11 | 28 | -0.468 | 129 | -0.077 | 0.004 | 68.4% (57) | 76.0% (25) | 80.0% (15) |
| 12 | 26 | -0.314 | 113 | -0.131 | -0.001 | 69.6% (56) | 76.2% (21) | 72.7% (11) |
| 13 | 32 | -0.617 | 141 | -0.055 | -0.008 | 54.0% (63) | 69.6% (23) | 72.7% (11) |
| 14 | 26 | -0.497 | 101 | -0.156 | -0.013 | 63.9% (61) | 57.7% (26) | 45.5% (11) |
| 15 | 32 | 0.290 | 140 | -0.091 | -0.022 | 65.8% (73) | 65.4% (26) | 80.0% (10) |
| 16 | 32 | -0.382 | 135 | -0.160 | -0.008 | 51.7% (60) | 52.0% (25) | 61.5% (13) |
| 17 | 32 | -0.119 | 145 | -0.281 | 0.003 | 75.3% (77) | 75.7% (37) | 86.7% (15) |
| 18 | 32 | 0.068 | 128 | -0.228 | -0.014 | 63.4% (71) | 67.6% (34) | 57.1% (14) |

## High-confidence calibration: fails reliability requirement

| Minimum claimed confidence | n | Average claimed | Actual directional accuracy | Over / Under |
|---|---:|---:|---:|---:|
| 70% | 2114 | 84.0% | 62.3% | 93 / 2021 |
| 80% | 1306 | 89.7% | 64.1% | 24 / 1282 |
| 90% | 638 | 94.9% | 68.8% | 4 / 634 |
| 95% | 316 | 97.3% | 70.9% | 0 / 316 |

The allocator underestimates target opportunities on the scored cohort: mean forecast **2.960 targets**, mean actual **3.706**; the nominal 90% target prediction interval contains only **85.9%** of observations. The team-volume model forecasts **34.194** attempts versus **35.338** observed, while its nominal 90% predictive interval covers **90.8%**. This isolates the larger bias in **player allocation/participation**, not just team pass volume. In the ≥95% confidence group **all 316** cases were Under, and only 70.9% were correct. **High-confidence reliability is therefore not established.**

## Leakage, invariants and independent audit

- **18/18** forecast inputs exclude 2024 outcome labels with week ≥ forecast week; calendar ordering enforced by strict input schema and child process.
- **18/18** week receipt hashes and code/input linkages matched; all 544 team games retained for volume scoring.
- **Zero** target allocations exceeded the forecast team's sampled pass-attempt count. Scenarios use a finite target simplex plus an unassigned-attempt category, without inventing receiver routes.
- **Week 1** online and frozen controls are identical sample-for-sample; later divergence comes from historical updates rather than differently seeded Monte Carlo draws.
- **9** added source-isolation unit/property tests and **22** preexisting Phase 2 tests passed; GitHub CI passed on the research branch. Deepnote independent audit run `86f727b4-ca9b-4386-852b-40ada8be75be` recalculated the frozen input and scoring invariants.
- **Not proven:** historical upstream source publication timing, lineup/role availability, routes, structural-zero inactivity, fully independent 2024 test data, or the full Phase 2 route-aware challenger's real-game skill.

## Decision

**PASS as a confined historical learning-signal experiment; FAIL as a high-confidence calibrated probability model; NO promotion.** Weekly model updating provides a meaningful improvement over a frozen 2023 target-allocation model. But independent Poisson is nearly as good on target CRPS, and the extreme Under bias remains. The next Phase 2 research should validate **true pregame route/availability features and a participation hurdle**, then calibrate probabilities using only previously revealed weeks and rerun on a new, unexposed chronological cohort.
