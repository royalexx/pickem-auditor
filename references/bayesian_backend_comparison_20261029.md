# Three-backend joint Bayesian benchmark — October 29, 2026

**Decision: retain Python/PyMC production. Keep CmdStanPy as an independently tested research/training alternative. Do not promote any posterior or change ranking weights.**

All 9 actual historical fits completed on GitHub Actions under identical frozen per-sport source hashes. Evidence: [NHL run 40891642870](https://github.com/royalexx/pickem-auditor/actions/runs/40891642870), [NBA/NFL run 40892490073](https://github.com/royalexx/pickem-auditor/actions/runs/40892490073), [merged PR #30](https://github.com/royalexx/pickem-auditor/pull/30).

Configuration: 4 NUTS chains, 300 draws/chain, 450 warmup/chain, target accept .95, same position-group/2D correlated player workload-conversion hierarchy, LKJ priors, season/opponent effects, NB count or Student-t yardage likelihood; same fixed historical player-game train/holdout records. Scores are for **non-bookmaker research thresholds** conditional on appearing in each historical game. Training years are not latest 2026 seasons.

| Sport | Engine | Train rows | Held-out rows | Total compile+fit s | Minimum ESS/s | Max Rhat | Divergences | Brier | Log loss |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| NHL hits | PyMC | 392 | 119 | 77.9 | 4.12 | 1.0155 | 0 | .07752 | .25369 |
| NHL hits | Nutpie | 392 | 119 | 60.0 | 1.83 | 1.0342 | 0 | .07786 | .25423 |
| NHL hits | CmdStanPy | 392 | 119 | 43.3 | 6.75 | 1.0166 | 0 | .07792 | .25426 |
| NBA points | PyMC | 697 | 261 | 62.7 | 4.89 | 1.0138 | 0 | .05466 | .20850 |
| NBA points | Nutpie | 697 | 261 | 54.5 | 3.69 | 1.0321 | 0 | .05469 | .21026 |
| NBA points | CmdStanPy | 697 | 261 | 70.8 | 5.65 | 1.0114 | 0 | .05467 | .20681 |
| NFL receiving yards | PyMC | 469 | 63 | 76.1 | 3.59 | 1.0098 | 11 | .16649 | .50216 |
| NFL receiving yards | Nutpie | 469 | 63 | 41.5 | 3.40 | 1.0354 | 8 | .16722 | .50326 |
| NFL receiving yards | CmdStanPy | 469 | 63 | 55.5 | 4.55 | 1.0166 | 4 | .16674 | .50278 |

- Source SHA-256 digests for **both training and heldout data matched for all three backends** in each market.
- Stan had the highest *minimum ESS per fit-second* in all three cases, but Nutpie was faster by fit-wall-clock for NBA and NFL. Compile+fit numbers exclude the substantial clean-run CmdStan installation, and do not prove Stan is faster end-to-end on ephemeral runners.
- No fit met the entire strict production convergence gate (Rhat<=1.01, ESS>=400, zero divergences and BFMI>=.30). Stan NBA ESS=400.316 but Rhat=1.01145, for example. NFL yardage had 11, 8, 4 divergences (PyMC, Nutpie, Stan).
- Held-out predictions were close across backend implementations, which supports—but does not prove—model encoding equivalence. Differences in Brier were tiny; all samples small and within-day correlated.
- NFL receiving yards predicted P(over 49.5)=.354-.355 while observed over frequency was .190 in 63 observations over 14 dates, indicating an independent calibration/model concern that changing sampler cannot eliminate.

No sportsbook line, live odds, payout, injury status, or publication probability is inferred from these historical tests. Stan implementation remains *research-only*. R/RStan provides a Stan frontend rather than an independently improved inference engine, so a full transition from Python to R is not justified.

**Next model-quality work:** improve NFL Student-t hierarchy and residual tail/appearance handling; check source/position coverage; longer multi-seed frozen NUTS runs with all diagnostics passed; repeat comparisons on verified *contiguous* multi-season recent data and actual frozen sportsbook lines; cache CmdStan build if a training-only migration is subsequently justified.
