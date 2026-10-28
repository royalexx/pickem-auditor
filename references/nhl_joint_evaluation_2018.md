# October 2018 NHL shots: precommitted Bayesian cohort experiment

**Purpose:** Frozen-after-October-19 historical evaluation of the experimental fully joint NHL shot production model, with strict no-leakage, convergence, and nonpublication controls. This is not a 2018 sportsbook prop backtest.

## Verified historical cohort

Source: Official NHL scoreboard and gamecenter player boxscores, checksum-verified in `data/bayesian-history`; read only games before their respective training/score cutoff. Training cutoff exclusive 2018-10-20; holdout end exclusive 2018-10-28.

Training: 3,636 skater-game observations, 101 completed games, 645 seen players across 16 NHL game dates. Heldout: 2,052 skater-game observations across 57 completed games and 8 dates; 1,983 records involve players observed pre-cutoff. The remaining 69 are excluded from per-player comparisons, not assigned manufactured player effects.

The unchanging baseline is a pre-cutoff position-shrunk Gamma–Poisson shots-per-game control with five equivalent prior player-games. Evaluated at fixed 2.5 shots on the 1,983 same-cohort observed appearances: **Brier 0.1775539285; binary log loss 0.5352071350**. Predicted average P(shots >= 3) 0.266057047, observed rate 0.264246092. By position: D n=657 Brier=0.161632, log loss=0.498293; F n=1326 Brier=0.185443, log loss=0.553497.

Reproducible source evaluation: https://github.com/royalexx/pickem-auditor/actions/runs/40728100996

## Model fitting and fixes (separate from scoring)

The initial **precommitted top-60 forwards plus top-60 defenders by training-period game count** NUTS cohort has 855 training player-games across 90 completed games, yielding a tractable first-stage comparison. This is a subset, so it must only be compared to the Gamma–Poisson baseline *on that exact subset*; never compare a subset's performance directly against the 1,983-record full-coverage baseline.

First NUTS fit (500 warmup + 500 posterior draws, 4 chains): 11 divergences, max R-hat 1.013646, min bulk ESS 237.05. It failed the explicit convergence gate, and no shadow probabilities were published. Run: https://github.com/royalexx/pickem-auditor/actions/runs/40728723504

Fix: One observed season cannot identify a season-to-season variance and an unconstrained single-season offset is confounded with population means. Use a deterministic zero offset for single-season fits; retain centered random season effects and inferred variance only for actual multi-season data. Center opponent effects to separate population intercept and opponent deviations. Raise NUTS target acceptance from .95 to .99, with 1000 warmup steps. Keep the existing R-hat <=1.01, bulk ESS >=400 and **zero divergences** acceptance criteria, without loosening any public forecast gate.

Second NUTS fit (1000 warmup + 800 posterior draws, 4 chains): **zero divergences**, but max R-hat 1.013837 and min bulk ESS 333.62, so still rejected. The extended 2,000-draw/four-chain experiment is therefore a numerical convergence test; it is not a tuning exercise against observed heldout labels.

Holdout scoring fix: Earlier scorer repeatedly converted the entire posterior DataTree for every skater/game and sampled an extra shot-count result. Cache the frozen posterior once, then analytically integrate the conditional negative-binomial CDF/tail over the posterior workload/rate draws. This preserves the model's posterior predictive target while lowering Monte Carlo noise and evaluation time; record numerical MC standard error separately from model uncertainty. Cached and uncached seeded predictions must match in independent real PyMC CI tests.

## Validation boundaries

Only if diagnostics pass can strictly later skater games be scored, conditional on documented player appearance. No later actual shots, ice time, or team changes enter frozen model features. The Gamma–Poisson comparator must be scored on identical player-games. Proper Brier/log loss differences are descriptive because the original holdout spans only **eight** dates and the single-season sample is small. No parameter, research context, Tier ranking, production blend, odds or betting profitability claim can be promoted on this evidence.

All failed sampler manifests remain as downloadable Actions artifacts, with explicit `publication_eligible=false`. The accepted reference for full predictive calibration must ultimately use the larger multi-season warehouse, a sealed future test period, verified source/odds provenance and properly clustered uncertainty estimates.
