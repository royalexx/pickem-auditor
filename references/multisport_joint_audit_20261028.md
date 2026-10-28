# Multi-sport joint Bayesian versus simple statistical baseline — independent audit

**Run date:** October 28, 2026. **Status:** exploratory frozen historical comparison, no production eligibility or tier changes.

## What actually ran

An independently executed GitHub Actions 4-chain NUTS test fit the shared `multisport-joint-bayes-v1` per sport/stat strictly on historical player-game records older than the stated cutoff. The model predicted later previously completed player-games using posterior draws of unknown game workload (minutes or snaps) and a negative-binomial production likelihood (counts), or Student-t (signed yards). Each control forecast used a Gamma–Poisson position-shrunk count model or a regularized Student-t signed-yard model fitted on the SAME earlier source-owned observations. Records matched exactly by game and player before scoring. Reported lines are fixed **research thresholds**, not historical bookmaker offerings.

**Historical source window:** NHL cutoff 2018-10-18, holdout 2018-10-18 through 2018-10-25 inclusive. NBA cutoff 2018-10-23, heldout through 2018-10-25. NFL cutoff 2018-11-12, heldout through 2018-12-31. Cohorts were deterministically selected from pre-cutoff most-frequent players by position and then applied identically to each model. Each fit used 4 chains, 1,000 posterior draws and 1,100 warmup draws per chain; Rhat <=1.01, bulk ESS >=400, zero divergences and minimum chain BFMI >=.30 were required for scoring.

| Market | Fixed test line | Matched records | Heldout dates | Joint Brier | Baseline Brier | Joint log loss | Baseline log loss | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| NHL shots on goal | 2.5 | 117 | 7 | 0.171163 | **0.165325** | 0.517151 | **0.503700** | Inconclusive; baseline point estimate better |
| NHL hits | 2.5 | 117 | 7 | 0.113299 | **0.108576** | 0.375191 | **0.361722** | Inconclusive; baseline point estimate better |
| NHL blocked shots | 1.5 | 117 | 7 | 0.158026 | **0.157908** | 0.483883 | **0.478207** | Inconclusive; essentially tied Brier |
| NBA assists | 4.5 | 197 | 3 | **0.107414** | 0.109341 | **0.344901** | 0.359396 | Inconclusive; joint point estimate better |
| NFL targets | 5.5 | 217 | 18 | **0.154077** | 0.154742 | **0.459858** | 0.460194 | Inconclusive; essentially tied |
| NFL tackles + assists | 5.5 | 738 | 20 | 0.166779 | **0.162538** | 0.513868 | **0.496124** | 95% date-cluster intervals favor simple baseline on both scores |
| NFL receiving yards | 49.5 | 217 | 18 | **0.152576** | 0.162634 | **0.478006** | 0.497870 | Inconclusive; joint point estimate better versus **Student-t**, not Poisson |

All seven actual joint fits passed the corrected hyperparameter sampler diagnostics with zero divergences and publication eligibility FALSE. **No point-estimate advantage in fewer than 20 distinct dates is interpretable as an established performance advantage.** Only the NFL tackles result has >=20 heldout dates AND >=300 same-cohort observations, with paired date-cluster 95% intervals excluding zero on both scores: Brier challenger-minus-control [+0.002336,+0.006034], log-loss [+0.008414,+0.025277]. The experiment explored seven stats and makes **no familywise multiple-testing correction**. Treat even this stronger tackles result as descriptive, not independent proof on other seasons.

## Material defects discovered in the audit and corrected

1. **Systemic false convergence veto:** Earlier multi-sport fits sampled but every comparison was rejected because the constant 1.0 diagonal of the player's LKJ correlation matrix had undefined Rhat/ESS. Diagnostic code now checks the *stochastic off-diagonal correlation* and still requires finite Rhat/ESS, zero divergences and adequate energy diagnostics; a regression test explicitly requires genuinely stuck parameters to fail.
2. **NFL off-position zero contamination:** Historic NFL players were recorded for irrelevant markets (e.g. QB receiving targets and WR passing attempts), creating structurally all-zero population groups. Those historical source records are kept immutable; the trained source reader excludes them with explicit sport/stat/position eligibility and future nflverse collection no longer writes those misleading stat-position combinations.
3. **NHL source mismatch:** The completed-game boxscore must agree with the requested official scoreboard game ID. When the source game date is present it must agree with the dated scoreboard as well.
4. **Backfill memory/CPU and partial failure:** Every NHL/NBA completed date now normalizes all game boxscores first, then writes one batch per date. Network failure cannot persist part of a completed day, and larger multi-season shards are not decompressed/recompressed repeatedly for every game. File-system interruptions during shard writes still resume idempotently under immutable row matching.
5. **NBA historic made 3PM:** Already merged PR #13 parses source 3PT made–attempt strings and retains a separate monotonic missing-three-point replay without rewriting other market archives.

## Research readiness by market

**Verified source-ingestion and numerical count model:** NHL SOG/hits/blocked shots; NBA points/rebounds/assists and combinations; NFL passing/rushing/receiving volume, defensive snaps/tackles and signed yardage. **Verified real proper-score evaluation:** seven markets above; not all supported stats. NHL goalie saves are source-collected but 186 games before the pilot cutoff were below the general 300-record NUTS pilot minimum; fit and heldout calibration for goalie saves have NOT been established. NBA made-threes were initially omitted and the verified historical repair now stores the stat; no mature posterior holdout has been completed. Multi-season hyperparameter benefits have not been tested in the reported single-season train splits.

**Production integration:** The elaborated model remains isolated to research and manual evaluation workflows. It is not yet a trusted replacement for production Engine A, does not alter Tier probabilities, and does not produce verified today's picks or sportsbook market performance. A new inference status `joint_better_on_heldout` is not sufficient for release: require multiple true calendar seasons, forward heldouts, representative player cohort (not just the training-selected sample), correction for multiple candidate stats, timestamped role/lineup contextual research, independent score calibration and live precommitted forecasts.

## Reproducible GitHub evidence

- Initial sample-size audit: https://github.com/royalexx/pickem-auditor/actions/runs/40751380689
- Six genuine sport/stat NUTS fits and paired scores after fixes: https://github.com/royalexx/pickem-auditor/actions/runs/40753085871
- Independent NHL SOG re-test: https://github.com/royalexx/pickem-auditor/actions/runs/40753105338
- Corr-matrix regression + full CI: https://github.com/royalexx/pickem-auditor/actions/runs/40753305238

## Conclusion

The underlying model is now **operational as an isolated historical research and model-comparison engine**, with real inference and proper-score evaluation across count and continuous stats. It is **not validated as a uniformly better prop probability engine**. In this limited experiment Gamma–Poisson holds the edge on NHL SOG/hits/blocks and more decisively on NFL tackles+assists. The joint model shows preliminary gains on NBA assists, NFL targets and NFL receiving yards, all with confidence intervals crossing zero. The sensible next step is to preserve both models, grow multi-season populations and let pre-specified sport/stat walk-forward validation determine any eventual promotion.
