# Historical blind-validation campaign — independent-year scoreboard

Updated 2026-11-09. Production 60/40 and `.training-control/PAUSED.json` are unchanged. **Research only.**

## Predefined experimental protocol

- NFL tackles + assists, fixed 65 expected defensive plays, role-specific training-history median half-integer research lines, same contracts and outcomes for both challengers.
- 3 stages: source preparer writes sanitized packets and separate sealed vault; subprocess forecaster reads **only** packets, checks temporal cutoff and locks SHA-256; separate settlement validates forecast/vault SHA before reading outcomes.
- Per-season independent historical walk-forward, first 45 eligible slate dates in October–December for 2023/2024. Historical source availability is *retrospectively approximated* as kickoff +18 hours; not independently authenticated.
- No real sportsbook odds/lines, original production consensus, or bookmaker edge measured.
- Report date-cluster paired bootstrap intervals (1200 replicates, fixed season-specific seed), and by-position 400 replicates. No holdout-driven tuning.
- Selection is conditioned on prior player appearances. Unmatched candidates cannot be graded and may create material selection bias. Need full-slate participation/absence outcomes and explicit coverage before promotion.
- Promotion requires statistically credible improvement across **multiple seasons**, Brier and log loss and directional accuracy, position stability, and actual pregame market-line verification.

## Completed original sealed runs

| Season | Dates | Games | Forecasts | Scored | Unmatched | Challenger Brier | Control Brier | Challenger log loss | Control log loss | Challenger accuracy | Control accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025 pilot | 28 | 100 | 2616 | 1837 | 779 | .223007 | .228671 | .636449 | .652756 | 64.725% | 63.800% |
| 2024 | 45 | 159 | 4598 | 2978 | 1620 | .214904 | .215679 | .619992 | .627199 | 66.622% | 66.353% |
| 2023 | 45 | 160 | 4310 | 2948 | 1362 | .209249 | .211357 | .606726 | .616720 | 67.741% | 67.164% |

Scored = exact observed defender/game participation match; not all pregame forecasts. Lower Brier/log loss better.

## Paired date-block bootstrap 95% intervals (challenger minus control)

| Season | Accuracy difference (pp) | Accuracy 95% CI (pp) | Brier difference | Brier 95% CI | Log-loss difference | Log-loss 95% CI |
| --- | ---: | --- | ---: | --- | ---: | --- |
| 2024 | +0.269 | [-0.800, +1.201] | -.000775 | [-.003434, +.001775] | -.007207 | [-.015672, +.001305] |
| 2023 | +0.577 | [+0.064, +1.195] | -.002108 | [-.005547, +.001226] | -.009994 | [-.020798, +.000981] |

The **2023 aggregate directional-accuracy interval excludes zero**, but 2024 does not. Neither season shows a date-block CI excluding zero for Brier or log loss. There is **no demonstrated robust aggregate improvement in probability quality**, and 2025's date-block CI has not yet been computed.

## Important position instability

- **2024 cornerbacks:** n=470, directional delta +3.62pp, CI [+0.92,+6.73]pp; Brier delta -.0110, CI [-.01868,-.00516]. Promising single-season subgroup.
- **2024 off-ball linebackers:** n=814, Brier delta **+.00887** CI **[+.00410,+.01415]** (worse), log loss +.01585 CI [+ .00095,+.03144] (worse). Accuracy -0.61pp.
- **2023 cornerbacks:** n=335, accuracy delta +1.19pp CI [-2.05,+4.28]pp (not established); log-loss delta -.03446 CI [-.06651,-.00105].
- **2023 off-ball linebackers:** n=809, Brier +.00133 CI [-.00325,+.00550], no demonstrated improvement.

These subgroup results are exploratory and are **not multiplicity-corrected**. Do not promote position-specific models on them.

## SHA-256 original forecast receipts

- 2025: `a70f53bd0a8c48f802c0fededaedf720d3d44b7502d711ffa83b869897dbc8a8`
- 2024: `e79f2f27a7b26fb6ac824bd449d65b20b90f74a6daf752549afe030a3dab99db`
- 2023: `b0b95d092e2848c6bfe2dd93dbafccc11c60be338e77bc5f844878db83d552b8`

## Execution references

- Deepnote 2024 run `260756a9-2503-442d-adf7-e4672587c765`: success.
- Deepnote 2023 run `b86cbadf-4787-485b-a959-da358a2db1ce`: success.
- Deepnote 2025 run `04a39da4-8e78-446f-ae69-afefe934fda0`: success.
- Main-branch GitHub offline CI: success; NUTS smoke skipped per training pause.

## Outstanding gates

- [ ] Verify independent 2022 (and optionally 2021) historical season with same frozen protocol and position/date intervals.
- [ ] Compute date-block CIs for original 2025 pilot and aggregate season-block intervals, rather than treating thousands of correlated player rows as independent.
- [ ] Quantify pregame roster participation and unobserved candidates; avoid treating 779/1620/1362 unmatched forecasts as wins or losses without source-backed participation status.
- [ ] Fix pregame source-time provenance with archived source snapshots and provider timestamps.
- [ ] Compare original production 60/40, Engine A/B, Bayes, NUTS and market on exact archived **real sportsbook lines** with no postgame leakage.
- [ ] Check high-confidence Over/Under direction, calibration by probability bin, edge by market, position stability, and predeclared significance thresholds before promotion.
- [ ] Maintain original production model and paused expensive Bayesian training until an explicitly reviewed promotion decision.
