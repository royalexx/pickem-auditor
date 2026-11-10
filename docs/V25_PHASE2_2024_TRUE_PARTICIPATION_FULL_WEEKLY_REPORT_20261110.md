# Phase 2 2024 — full week-by-week participation and confidence experiment

**Executed:** 18/18 weeks, 512 simulated attempts/role/player scenarios per team, initial 2021–2023 training (815 games, 1,630 team-games), sequential 2024 results added only **after** the week's forecast and prior-week-only calibration were frozen and hashed.

**Status:** **Confidence calibration improves, but full count-distribution model fails promotion**. This is development-exposed, retrospective research, not a pristine untouched test. 2024 originals lack independent pregame provider capture timestamps. Historical *snaps* are not receiver *routes*. Research lines are synthetic and no betting performance is implied.

**GitHub branch:** chatgpt/v25-phase2-role-calibration-ablation-20261110, stacked draft PR #97 on Phase 2 PR #95.

**Evidence:** Deepnote executed run 2a83f3ee-6e04-476b-982b-74e6962f465f; [immutable JSON first-run summary](./phase2_nfl_2024_true_participation_first_replay_receipt.json); [source / acceptance protocol](./V25_PHASE2_TRUE_PARTICIPATION_2024_REPAIR_PROTOCOL_20261110.md).

## Overall model outcome

| Measure | Original target-only | New participation + snaps | New role-Platt calibrated |
|---|---:|---:|---:|
| Scorable player-target observations (not necessarily identical sets) | 4046 | 4249 | 4249 |
| Player-target CRPS (lower better) | 1.3941 | 1.4114 | **1.4114** (calibration does not change counts) |
| Conditional binary Brier (lower better) | 0.2675 | 0.2558 | **0.2387** |
| Log loss (lower better) | 0.7852 | 0.7169 | **0.6707** |
| Forecast minus actual mean targets | -0.746 | **-0.912** | **-0.912** |
| Original research target candidates | 6,186 | 6,186 | 6,186 |
| Scorable candidate coverage | 65.4% | 68.7% | 68.7% |

**Paired, matched event/player comparisons (n=4,042)** are required for model claims, because the raw coverage differs:

- New minus old **raw Brier** = -0.0105, week-cluster 95% descriptive interval [-0.0166, -0.0050]. Better on 15/18 weeks.
- New minus old **target-count CRPS** = **+0.0282**, interval [-0.0137, 0.0679]. Negative would be better; it improved only 5/18 weeks.
- New minus old **raw log loss** = -0.0662, interval [-0.0981, -0.0399].
- On the new model's same 4,249 event/player outcomes, previous-weeks-only role calibration changed binary Brier by -0.0171, log loss by -0.0462, improving Brier on 17/18 weeks. This *does not* alter count CRPS.

## Complete 18-week performance

Each row reports the original and new models' **own scored cohorts**, which differ; per-week CRPS figures are descriptive and must **not** be read as matched differences. The correct aggregate matched comparison appears above. Brier is computed on scored conditional Over/Under at the original diagnostic research line.

| Week | Original n | New n | Original count CRPS | New count CRPS | New raw Brier | New calibrated Brier |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 166 | 178 | 1.233 | 1.511 | 0.2291 | 0.2291 |
| 2 | 158 | 158 | 1.467 | 1.507 | 0.2427 | 0.2260 |
| 3 | 181 | 181 | 1.394 | 1.435 | 0.2500 | 0.2351 |
| 4 | 229 | 233 | 1.668 | 1.546 | 0.2417 | 0.2295 |
| 5 | 211 | 215 | 1.871 | 1.744 | 0.2754 | 0.2467 |
| 6 | 209 | 221 | 1.516 | 1.402 | 0.2585 | 0.2388 |
| 7 | 232 | 242 | 1.425 | 1.308 | 0.2426 | 0.2337 |
| 8 | 262 | 279 | 1.361 | 1.390 | 0.2697 | 0.2451 |
| 9 | 241 | 252 | 1.363 | 1.356 | 0.2576 | 0.2407 |
| 10 | 219 | 230 | 1.265 | 1.275 | 0.2364 | 0.2311 |
| 11 | 233 | 248 | 1.266 | 1.347 | 0.2576 | 0.2378 |
| 12 | 217 | 229 | 1.180 | 1.278 | 0.2570 | 0.2411 |
| 13 | 258 | 274 | 1.388 | 1.432 | 0.2685 | 0.2424 |
| 14 | 201 | 215 | 1.521 | 1.488 | 0.2541 | 0.2359 |
| 15 | 264 | 273 | 1.358 | 1.409 | 0.2517 | 0.2393 |
| 16 | 251 | 271 | 1.216 | 1.313 | 0.2655 | 0.2472 |
| 17 | 267 | 279 | 1.224 | 1.302 | 0.2415 | 0.2330 |
| 18 | 247 | 271 | 1.458 | 1.489 | 0.2863 | 0.2527 |

## High-confidence reliability and directional imbalance

| Variant | ≥80% selections | Actual accuracy | Mean claimed | Under selections | ≥90% n / accuracy | ≥95% n / accuracy |
|---|---:|---:|---:|---:|---:|---:|
| Original raw | 1305 | 64.1% | 89.7% | 1281/1305 | 637 / 68.8% | 315 / 70.8% |
| Original role calibrated | 122 | 72.1% | 86.3% | 122/122 | 24 / 75.0% | 12 / 83.3% |
| New participation raw | 1012 | 68.1% | 85.2% | 1003/1012 | 142 / 73.2% | 9 / 77.8% |
| New participation global calibrated | 106 | 70.8% | 83.6% | 101/106 | 3 / 66.7% | 0 / — |
| New participation role calibrated | 122 | 75.4% | 83.6% | 116/122 | 3 / 66.7% | 0 / — |
| New without hurdle, role calibrated | 98 | 66.3% | 85.1% | 96/98 | 14 / 64.3% | 1 / 0.0% |

**Main finding:** the new model's ≥80% raw-confidence Under dominance persists (1,003 of 1,012 = 99.1%). Chronological role calibration reduces the ≥80% set to 122 (116 Under, 6 Over), with 75.4% actual accuracy versus 83.6% mean confidence. No ≥95% calibrated predictions remain. The reduction in false certainty is useful but **not** proof of good 90–95% reliability—there are only three ≥90% calibrated observations.

The model still **underpredicts actual targets** on its own scored cohort by 0.912 targets per player (original underprediction 0.746). That is a serious remaining structural deficiency; calibration merely reduces how aggressively a poor count distribution is interpreted.

## Hurdle ablation

Without the participation hurdle: n=4249, target-count CRPS 1.4711, raw Brier 0.2721. With the hurdle: n=4249, CRPS 1.4114, raw Brier 0.2558. Cohorts match, and the hurdle improves both metrics relative to its own no-hurdle ablation. However neither result justifies replacing the simpler Poisson or original-count model without improved matched CRPS.

## Audit status and statistical decision

- 39 targeted tests passed: 9 true lagged participation, 11 original-source availability gate, 9 historical as-of isolation, 10 role/calibrator property tests.
- Every forecast child input excluded future/current-week target outcomes and realized current-week offensive snaps; injury updates were timestamp-filtered before game freeze. Prior weeks were revealed only after forecast and calibration freeze. Week 1 used zero 2024 outcomes.
- Every eligible simulated attempt is assigned once to an actual modeled player, a separate unrepresented receiver, or a non-target attempt; target count cannot exceed the player's projected offensive snaps. No false route-count claim.
- **Not proven:** original capture of 2024 in-week injury/roster data, true receiver routes, complete pregame candidate coverage, independently untouched 2024 outcome validation or NFL deployment readiness.
- This analysis reflects retrospective 2024 model development, not an independent prospective proof; bootstrap confidence intervals are descriptive with 18 week clusters.

**Decision:** keep the original simpler count model as a diagnostic champion; retain the new hurdle/participation and chronological calibration only as research candidates. The new calibrated probability behavior is better, but the worsening matched count CRPS and remaining strong Under mean bias **fail the full Phase 2 acceptance gate**. Production, automatic Tier 1/2 selection and paid heavy training remain blocked.
