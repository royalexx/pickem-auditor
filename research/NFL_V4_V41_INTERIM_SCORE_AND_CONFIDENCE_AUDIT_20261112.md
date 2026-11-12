# NFL V4/V4.1 independently retrieved partial replay results
Date: 2026-11-12 UTC
**THIS FILE IS INTERIM. Neither 175-week run was complete at capture.**
Data: reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V4_FAST_SETTLEMENT_ONLY_AUDIT_20261112.json

## Cohort and overall proper scores

V4: **133/175** completed weeks, 309,274 matched paired contracts.
- Brier calibrated V4 0.23527245; same-forecast V3 0.23540266; V2 0.23572106.
- Paired Brier V4 − V3 = **−0.00013021**.
- Hit rate V4 59.8760%; V3 59.8770%; delta **−0.0010 percentage points**.
- CRPS V4 3.477835; frozen V3 3.466825; **+0.011010 (worse)** when unsafely averaged across markets (market-specific CRPS should be used).
- >=80% confidence n=1,367; mean stated 83.977%; observed hit 77.542%; overconfidence approximately **6.43 pp**.
- >=90% confidence n=130; mean claimed 91.754%; observed hit 84.615%.
- Mixture at latest audited 2023 week: [0.896581 frozen V3, 0.053117 recent, 0.050302 long].
- Market CRPS worse in 12 of 13 markets, improves only rushing yards.

V4.1: **81/175** completed weeks, 187,829 matched paired contracts.
- Brier V4.1 .23554753; matched frozen V3 .23565588; delta **−.00010835**.
- Directional hit rate identical to frozen V3 to six decimals, 59.7538%.
- CRPS 3.465268 vs frozen V3 3.463235; **+0.002033 (worse)** on mixed units.
- >=80% confidence n=1,170; mean stated 83.663%; realized 75.983%; overconfidence approximately **7.68 pp**.
- >=90% confidence n=107; claimed 91.690%; realized 85.981%.
- Mixture at latest audited 2020 week: [0.863410 frozen V3, 0.070237 recent, 0.066353 long].
- Market CRPS improves in 4 of 13 markets (QB pass attempts, completions, passing yards and RB rushing yards), worsens in 9 of 13.

## Matched cohort policy comparison

Exactly **81 common completed weeks, 187,829 paired contracts**:
- V4.1 Brier minus V4 = **+0.000008146** (V4.1 slightly worse).
- Hit-rate delta V4.1 minus V4 = **+0.000010648** (approximately +0.0011 pp; negligible).

This is **not a clean isolated QB causal comparison**: V4.1 scenario selection uses a different `VERSION`-dependent seed and learns different global adaptive weights. Also V4.1's QB rushing allocation fails conservation in 6.7–6.8% of simulated scenario checks (see companion static/simulation audit). It must not be promoted.

## Market-level finding

V4: zero Brier change for targets, carries, receiving yards and rushing yards, indicating online stack safety gate largely retained incumbent probabilities for these markets. Small gains were concentrated in defensive tackle categories and completions, but most market full-distribution CRPS worsened.

V4.1: similar negligible effects outside quarterback markets; QB passing yards CRPS improved by roughly 0.805 on the early 81-week cohort, but the joint QB+RB allocation violation invalidates promotion. The base scenario source remains the older uncorrected V3 mixture for most draws.

## Interpretation
The first partial experiment rejects the claim that the new factors materially fix directional accuracy, and does not establish longer-history learning improvement. It does show adaptive factor downweighting when new profiles do not outperform.

All original lines are synthetic prior-player medians +.5, not archived bookmaker offers, and QB active status is not verified original pregame.

**Status:** no production promotion. The final 175-week report, all-market and all-season confidence audit, and independent SHA audit are pending their respective running computations. No claimed full-decade result exists in this memo.
