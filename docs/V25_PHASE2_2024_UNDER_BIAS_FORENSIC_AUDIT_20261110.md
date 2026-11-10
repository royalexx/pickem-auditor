# Phase 2 — why 2024 high-confidence NFL targets are overwhelmingly Under

**Disposition:** Structural bias reproduced, isolated and quantified. No model promotion, no retrospective fitting of a winning correction. This is a **target-only historical research prototype**, not the full Phase 2 route/absence-aware allocator.

**Forensic receipts:** [machine audit](./phase2_nfl_2024_high_confidence_under_root_cause_audit.json), [earlier 18-week prequential evaluation](./V25_PHASE2_2024_WEEKLY_LEARNING_REPORT_20261110.md). Independent Deepnote audits: `4baa5f1e-f458-4085-9eec-e75f8e71c3ee` and `1757340b-904b-4f3c-b1ef-b6f6685e2b13`. Source code used is `scripts/v25_phase2_target_only_forecast.py` at its previously tested algorithm, with 2021–2023 initialization and exactly the preceding 2024 weeks disclosed at each forecast.

## Definitive findings

| Result | 2024 observed audit |
|---|---:|
| Identical graded synthetic target-line contracts | 4,046 |
| ≥80% confidence contracts | 1,306 |
| ≥80% selected **Under** | 1,282 (98.2%) |
| ≥80% predicted confidence / actual correct | 89.7% / 64.1% |
| ≥90% Under | 634 of 638 |
| ≥95% Under | 316 of 316 |
| ≥80% forecast / observed target mean | **1.52 / 2.93** |
| All scored targets forecast / observed mean | **2.96 / 3.71** |
| Mean synthetic line in ≥80% group | **3.13** |
| Historical 10-game target mass attributed to older-only players | **43.45 / 344.06 attempts** |
| Residual category historical pseudocount | **80.05 / 344.06 attempts** |
| Same prototype, independent Poisson control ≥80% Under | **1,299 of 1,330** |
| 2024 Week 1–6 ≥80% actual correct | 62.5% |
| 2024 Week 13–18 ≥80% actual correct | 63.0% |

The overall target-only 2024 model forecasts 34.19 team pass attempts against 35.34 observed, but its player targets are much further below the actual. Within the ≥80% cohort the player mean is **1.41 targets too low**, making a superficially ordinary research line of 3.13 seem extremely unlikely to be exceeded. This is principally a **location/participation bias**, not a bug in the Over/Under complement or a mere absence of Monte Carlo draws.

## Exact root cause in code

In `scripts/v25_phase2_target_only_forecast.py`, an eligible receiver must appear in either of the previous **two** team games, whereas that receiver's estimated share uses the last **ten** team games. The unassigned-attempt Dirichlet category is then:

```python
roster = union(player_ids_present_in_last_two_team_games)
targets_i = sum(last_ten_targets_for_i)   # ONLY if i is in roster
E = sum(last_ten_team_pass_attempts)
alpha_i = 0.5 + targets_i
alpha_residual = 2.0 + E - sum(targets_i for i in roster)
```

Decomposing the residual:

```
residual = 2 + genuinely_non_target_attempts
             + historical_targets_for_players_outside_two_game_roster
```

Consequences:

1. Departed/rotated players' historical opportunities are effectively assigned to a **permanent unattributed category** instead of being conditionally redistributed to current eligible teammates.
2. New entrants are absent altogether until they appear in the short prior roster. The as-of roster is a target box-score proxy, **not a verified active-player roster**; the candidate coverage is just 4,046 of 6,186 original research target lines (65.4%).
3. Players with only one to five appearances get very small individual Dirichlet alpha relative to the entire team's ten-game attempt denominator. Instead of widening uncertainty, the simulator can become extremely confident that their target count will be close to zero.
4. Whole-team historical pass attempts dominate the concentration denominator, treating many attempts as if they provided strong information against any currently short-history receiver receiving targets.
5. Once a week is revealed, the rolling ten-game count changes, but **the representation and long-run residual assumption do not**. Weekly updating can improve CRPS without repairing mean direction, role reassignment or calibrated extreme-tail confidence.

### Real-game stratification of this mechanism

| Team game historical turnover quartile | Earlier-player share of past attempts | Simulated targets for known current roster | Actual targets for same roster | Gap |
|---|---:|---:|---:|---:|
| Q1: low turnover | 1.7% | 29.90 | 29.04 | −0.87 actual minus forecast |
| Q2 | 7.3% | 28.32 | 29.99 | +1.67 |
| Q3 | 13.9% | 26.01 | 28.85 | +2.84 |
| Q4: high turnover | 27.9% | **21.40** | **28.35** | **+6.95** |

These are *team-game* comparisons, not independent player observations. With higher historical roster turnover, actual known-roster target opportunities are fairly stable, but model-assigned opportunities collapse. Q4 accounts for 431 of the 1,306 ≥80% confidence contracts and scores **61.0%** correct; Q1 has 222 such contracts, **64.0%** correct. This is direct empirical evidence consistent with the residual-mass mechanism. It does not prove that every vacated target would belong to a player in the last-two-game proxy.

### Short-history cohort and position breakdown

| Prior appearances within 10 historical games | ≥80% contracts | Under | Mean claimed confidence | Actual accuracy | Forecast targets vs actual |
|---|---:|---:|---:|---:|---:|
| 1–2 | 72 | 72 | **96.4%** | **65.3%** | 0.30 vs 1.89 |
| 3–5 | 637 | 637 | **92.5%** | **63.7%** | 1.09 vs 2.80 |
| 6–10 | 597 | 573 | 85.9% | 64.3% | 2.13 vs 3.19 |

Among ≥80% contracts, WR target mean = **1.99 forecast vs 3.89 observed** (587 contracts; 59.5% actual correct); TE = **1.31 vs 2.67** (334; 65.3% correct); RB = **0.98 vs 1.69** (385; 70.1% correct). The strongest missing-opportunity effect concentrates in short-history and higher-opportunity receiving roles.

### Not a Dirichlet-only defect

The *independent Poisson* target control, fed the same player history and synthetic lines, selected **1,299 Unders among 1,330 ≥80% contracts** (97.7% Under, 64.4% correct). Both likelihood families inherit broadly similar conservative individual workloads. The Dirichlet count-pool allocation amplifies a genuine problem but cannot be considered the sole explanation for near-universal Unders.

## Counterfactual falsification (2024 exploratory analysis only)

All alternatives preserved the **same sampled team pass attempts**, never used current/future games as *forecast input*, and assigned exactly one category to each attempt (players or residual). However, the variants were **invented after inspecting 2024**, so **none is a valid 2024 holdout result or model-selection winner**. They are mechanism tests, not approved models or implementation prescriptions.

| 2024 post-hoc sensitivity | Target mean vs observed 3.71 | Mean binary Brier, lower better | Fraction Under among all 4,046 eligible contracts | ≥80% confidence n, accuracy |
|---|---:|---:|---:|---:|
| Original | **2.96** | 0.2675 | 82.7% | 1,306; 64.1% |
| Recycle **50%** historical departed-player target mass from residual to eligible players | **3.14** | 0.2621 | 77.9% | 1,138; 64.7% |
| Recycle **100%** departed-player mass | **3.37** | 0.2600 | 71.2% | 1,041; 66.9% |
| Fivefold **broader Dirichlet share distribution**, original mean | **2.96** | 0.2663 | 86.0% | 1,219; 64.1% |
| Recycle 50% and broaden share distribution | **3.14** | 0.2606 | 80.8% | 1,076; 65.3% |

Interpretation: removing mass from the residual makes eligible-player means more realistic and substantially reduces the direction imbalance. Merely broadening posterior shares does **not** fix the mean or the Under dominance (despite reducing the count of extremely confident predictions). **Even the optimistic 100%-recycling counterfactual remains severely overconfident: 88.9% claimed confidence versus 66.9% actual accuracy for its ≥80% cohort.** Therefore both opportunity *location* and probability *calibration* must be independently fixed.

Important caveat: historical targets thrown to a previously present player might not be fully reassigned after a personnel change, and some belong to a genuinely unmodeled receiver. Naively setting residual to zero or recycling 100% can also create a physical/ecological modeling error; the above experiment is not a recommendation to hardcode a recycling percentage.

## Does the Under problem explain stagnant learning?

**Yes, it plausibly explains the stagnant *high-confidence hit accuracy*, but not the absence of all learning.** Team passing volume CRPS improved against the frozen 2023 baseline, and the shared-history target distribution improved 17/18 weeks on the matched player cohort. However, the model never explicitly learns the probability of *participating* or how empty volume is transferred when player roles change. It also never updates a calibration model based on past forecast residuals, so 2024 outcomes cannot teach it that “90% Under” was frequently closer to 65% empirically. Compare early Weeks 1–6 high80 actual 62.5% to late Weeks 13–18 actual 63.0%. The historical churn share falls from 21.3% to 9.1% between these high80 periods, yet the confidence reliability deficit persists.

Additionally, research lines are *synthetic diagnostic thresholds* borrowed from an older 2024 forecast archive; 2024 was exposed previously to modeling choices, original quotes and line publication times are unverified, and only 65.4% of archived target candidates are scored. Thus 2024 should be treated as **development/diagnostic evidence**, not a definitive untouched validation experiment or an estimate of high-confidence real-market performance.

## Engineering remediation priority (not yet implemented in production)

1. **Fix the opportunity/roster state first:** create a player availability + roster-to-role participation process using actually time-released weekly depth-chart and snap/route histories; retain an explicit non-roster/unassigned receiver class. Never create fake current-game routes or assume 100% recycling.
2. **Represent dynamic roster turnover:** model the appearance/absence hazard and role-level capacity redistribution, separating legitimate no-target outcomes from a player who was absent, newly activated or moved between roles.
3. **Improve cold-start uncertainty:** introduce league/role-aware hierarchical priors and player-specific uncertainty that widens with limited history; a recent two-game absence is **not** evidence of a near-certain Under.
4. **Separate epistemic and aleatoric variance:** estimate game-to-game workload volatility as well as sampling posterior uncertainty; ten games of attempts do not justify treating a rookie's share as almost deterministically zero.
5. **Add strictly prequential calibration:** fit calibrated CDF/Over/Under transformations *only* from previous weeks; use side-conditional and role-conditional log loss, Brier, CRPS, reliability diagrams, predicted-versus-actual target mean, and nominal interval coverage. Correct count distribution before a cosmetic confidence adjustment.
6. **Strengthen promotion criteria:** review original candidate denominator, abstentions, higher-turnover teams, WR/TE/RB, cold starts, both directional tails, and data publication provenance; compare on identical contracts with a simple Poisson control. If the new allocator cannot show robust accuracy and calibration gains on untouched future data, keep the simpler model.

**Final research gate: BLOCKED.** No high-confidence Tier or pick recommendations authorized. No 2024-tuned reallocation variant has been promoted, and no original production ranking or source archive was touched.
