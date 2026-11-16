# NBA V2.5 P5 — preregistered **future** C experiment protocol

Status: ENGINEERING RESEARCH ONLY. This file freezes proposed analysis rules **before** any P8/P9 result inspection. No historical coefficient/mixture fitting performed by P5.

## Governing source and gates

- PA-V25-MASTER-2026-11-09 v1.1; NBA G0 `nba-sojc-contract/2.0.0`, exact independently accepted SHA `59d28dc23be97de2a6a82d22be8338151e31f5b6`.
- P5: build scoring/storage/optimization tools and synthetic controls only. P8 chronological retrospective 2022–23 development and P9 historical W2/W3 fitting require **G1 for all owners, G2 integrated acceptance, and separately authorized experiment**. P10 2023–24 is a locked forward validation period and is not to be opened during P5.
- Do not use 2023–24 results, actual target-game minutes, target-game outcomes as pregame features, retrospective historical input clocks disguised as genuine prospective captures, hypothetical original offers, or late official corrections at a prior origin.
- **S, O, G and J are stages of a single conditional law, not separately exchangeable votes.** Eligible alternatives: complete S_ONLY, complete S_O, complete S_O_J player-statistic distributions. Joint combinations require SAME coherent game-scenario draw. Neither independent S/O/J stage weights nor Monte Carlo paths as independent real games are allowed.
- Legacy Engine A/B, Bayesian A/B, NUTS and frozen 60/40 are read-only reference comparisons, never the new weight components.

## Freeze before future history evaluation

1. Create the canonical full-eligible player-game-stat universe from P1 only, including PTS, REB, AST, 3PM and PR/PA/RA/PRA, for the entire chosen game cohort. Exact game/player/team/period/conditioning identities and model/feature/code/source SHA required.
2. Distinguish `historical_reconstruction` (date-only as-of proxy limitations) from `original_prospective` (truly original pregame timestamps). Preserve missing/DNP/played-zero, unknown eligibility, failures, abstentions, model noncoverage and all rejection denominators.
3. Freeze each pipeline's complete PMF and model cutoff before target tip-off; G0 validation plus source/evidence joins are mandatory. Store immutable distribution manifests separately from official outcome vault and join only in independent scorer. Retain versioned corrections.
4. Register cutoffs: pre-2022 training history, 2022–23 chronological development, 2023–24 untouched validation. Enforce strict labels-released-before-each-test-freeze and date/game-block embargo; report developer/model-choice exposure from earlier historical work.
5. Precommit official statistic semantics: full-game including OT; eligible count when PLAYED/PLAYED_ZERO_MINUTES. Separate DNP/void, push/actual product contract semantics. No fabricated no-vig odds or economic edge.

## W-series hypotheses and comparison

- **W0**: frozen simple S_ONLY complete-distribution champion, chosen before test-set labels.
- **W1**: equal mixture of matching, valid complete pipelines; not equal S/O/J stage votes.
- **W2**: one global simplex-constrained nonnegative weight vector; minimize *mean full-count CRPS* on prior out-of-fold 2022–23 development predictions, with preregistered L2-to-equal shrinkage and no candidate selection from 2023–24.
- **W3**: separate per-statistic weights, shrunk to W2, with minimum distinct-game/date coverage; sparse stats revert to W2. Freeze shrinkage rule and cohort thresholds before prospective evaluation.
- **W4**: contextual gating is DISABLED until minimum cluster size, stability, covariate as-of evidence, out-of-fold learning and multiplicity control are independently approved. No silent conditional decisions.
- Primary marginal score: mean full-count CRPS, **paired on identical forecast/game/player/stat/period/participation cohorts**. Secondary: NLPD, MAE/RMSE, signed forecast-minus-actual count bias, randomized PIT and 50/80/90/95% central coverage, calibration at zero and prespecified tail thresholds, complete denominator/abstention counts.
- Joint family P4/J: Energy Score and VS_0.5 (prespecified unordered pair weights; identity/scale alignment), same-draw multi-statistic joint-event coverage, plus marginal CRPS/NLPD guard. Energy and Variogram do not certify single-leg sportsbook benefit.
- If a finite PMF assigns zero probability to the realized count, NLPD = +infinity; no silent epsilon clipping. Flag missing support and score separately.
- Report both *group-level mean* and absolute count units; avoid unnormalized comparison between PTS and AST with different magnitudes. Aggregate across stats only via prespecified stat-balanced stratification. Reject post-hoc best-tail region selection.

## Time-respecting inner selection and independent outer measurement

At each rolling test date, training inputs and *released official labels* must predate that test's freeze. Fit calibration/weights only on earlier **out-of-fold predictions**, never training-set in-sample forecasts and never target test labels. Group same game (both teams, all players/props) into one fold. Handle dates with multiple games as single blocks. Games/dates must not cross test or bootstrap boundaries. Embargo must be fixed ex ante.

Compare W0, W1, W2, W3 on their matched common-support cohort, and also preserve each method's complete eligible denominator with missing/abstention reasons. Compute paired bootstrap by game blocks; date-block bootstrap sensitivity and multiple-comparison controls (Holm or prespecified gatekeeping). Monte Carlo simulated paths **are numeric integration draws**, not effective independent real games. Design-aware uncertainty has game/date as sampling units, not 5000/20000 paths.

## Numerical reproducibility and computational budget

- Seeded scenario generation and seeded simplex sampling, with exact code/feature/source/manifests and hash receipts. Compute a PMF once per complete pipeline per target and cache cumulative arrays / quadratic CRPS Gram coefficients. **Never rerun games per weight trial.**
- Use 5,000 scenarios as cheap prototype, 20,000 as high-precision challenger. On the same synthetic known discrete law, compare probabilities, CRPS, quantiles, zero/tails, MC uncertainty; the expected raw standard error ratio is 2. Do not treat any particular sample result as guaranteed pass. For real J, preserve common random seeds/paired draws if suitable; check precision by independent random replicate and report between-run uncertainty, not just internal weighted ESS.
- Use CPU-only SciPy SLSQP, bounded cache shape and exact deterministic configuration. Record runtime, process RSS, seed, cache count, date/game counts, version hashes and independent numerical reference tests.
- Implement all synthetic/analytical score references before performance. Independent CRPS reference: full integer-CDF sum, pairwise absolute expectation and NB(2,p=.5) at y=0 with exact 26/27. Verify ES and VS against small explicitly enumerated joint law. Negative controls: label shuffle, future source timestamp, wrong identity, invalid PMF, leakage of actual minutes, duplicate games, zero-mass tail, malformed mixture, score without official source, and false ESS.

## Future conditional go/no-go

Do not open P10 until all family engineering at G1 and G2 are accepted, the matched P8/P9 protocol and hyperparameter-selection decisions are frozen, and independent P6 audit signs off. Do not claim superiority if paired cluster intervals are inconclusive, if missingness differs materially, if source chronology cannot be certified, or if results are developer-exposed. W2/W3 remain research until genuinely prospective 2026–27 observations justify further reliability testing. Tier 1/2 and production authority remain blocked throughout P5.
