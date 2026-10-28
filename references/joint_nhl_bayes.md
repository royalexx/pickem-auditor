# Next-generation NHL joint Bayesian pilot — historical foundation

**Status: experimental shadow only.** This is the first end-to-end sport/stat implementation, not proof of predictive superiority and not a promotion of any production probability, tier, or blend.

## Scope and source

Start with NHL regular-season **shots on goal per skater**, with official NHL completed-game boxscore and exposure in minutes of ice time. NHL game IDs and player IDs are authoritative, and game/player observations retain the official boxscore URL and SHA-256 hash of the original full JSON. Only completed official games, integer shots, parsable positive skater ice time, team/opponent code, forward/defense and unique game/player IDs are admitted. No goalie observations. Avoid inferring zero games from non-appearances. Offseason, no-game days, postponed games, and source unavailability remain visible through the backfill cursor, never silently imputed.

Public NHL endpoints: `https://api-web.nhle.com/v1/score/YYYY-MM-DD` and `https://api-web.nhle.com/v1/gamecenter/GAME_ID/boxscore`. Historical start October 1, 2018 (2018–19), through yesterday; scheduled twice per day with bounded game/daily quotas and retry/backoff including HTTP 429. A successful run commits only verifiably completed calendar dates to the cursor. An interrupted day is retried, with already verified games skipped. The initial push performs a smaller bounded batch; later scheduled runs continue until caught up.

## Data architecture

Data live **only** on independent branch `data/bayesian-history`, under `data/bayesian_warehouse/nhl_shots/YYYY-MM.jsonl.gz`, compressed with deterministic gzip bytes. One row per skater/game, monthly partition, immutable existing player-game content, source and content integrity. `data/bayesian_warehouse/backfill_state.json` has the next unfinished date. `scripts/history_warehouse_store.sh` fails closed if any previous game disappears, a game record changes, or counters regress. GitHub Actions publishes an explicit coverage receipt, so status must be assessed from completed game and row counts, not file size.

Historical ingestion never calls PropLine, Odds API, GitHub secrets, or the existing pick generation/rank/settlement pipeline. The warehouse is deliberately not fed to the production Bayesian A/B source-identity checker, which requires today's verified collector packet. New historical data are for posterior inference and date-isolated backtesting only.

## Joint generative model

`scripts/joint_nhl_bayes.py` uses PyMC 6 NUTS with non-centered, correlated player random effects for **log minutes** and **log shots per minute**. Their population means and covariance are unknown Bayesian random variables: the LKJ prior samples the player-level workload–conversion correlation instead of treating it as fixed.

For skater i and game g:

    (u_i, v_i) ~ MVNormal(0, Sigma_population)
    log(TOI_ig) ~ Normal(mu_minutes[position] + u_i + season_TOI[season], sigma_game_TOI)
    shots_ig ~ NegativeBinomial(mu=TOI_ig * exp(mu_rate[position] + v_i + season_rate + opponent_rate + home_rate * is_home), alpha=dispersion)

Population mean, variances, covariance, season and opponent hyperparameters, player effects, and negative-binomial dispersion are sampled **jointly**, not point-estimated first. The posterior predictive forecast samples game-to-game workload, conditional shots and all relevant population/player uncertainty; it is conditional on the skater appearing and therefore must **not** be used to substitute for confirmed lineups and injury information.

One important constraint: using observed ice time as an offset for fitting shots is legitimate; future games require drawing new ice time from the workload likelihood, not conditioning on postgame minutes. The forecast helper does this. Nothing is automatically ranked or published.

## Diagnostics and safeguards

The independent training workflow fits 4 NUTS chains with default 1,000 warmup and 1,000 posterior draws each. It computes rank-normalized R-hat (<=1.01), bulk ESS (>=400), and zero divergences on key population/likelihood hyperparameters. Missing diagnostics or failed convergence return nonzero status. Raw `posterior.nc` and `manifest.json` remain downloadable as GitHub Actions artifacts even if convergence fails. Status is experimental, not calibrated or publication eligible, even if sampling diagnostics pass. CI contains a separate synthetic **real NUTS** smoke run in addition to stdlib-only ingest/recovery tests.

## Chronological validation roadmap

The repository's Phase 4 current validation only scores precommitted historical forecasts and never backfills new Bayesian predictions postgame. For this new model, the **next stage** will use rolling, dated refits and strictly earlier boxscores, freezing forecasts and derived hyperparameters for future periods, then evaluate held-out games against observed stats and verified contemporaneous sportsbook lines where available. A retrospective predictive simulation without historical lines cannot claim historical sportsbook pick profitability. Evaluate per-player and per-game dependence, calibration, log loss, Brier, availability, prior predictive checks, computational scaling and inference geometry before promotion.

## Run and monitor

GitHub Actions `NHL Bayesian history warehouse backfill` automatically initiates on merge of its workflow and subsequently runs twice daily; a manually dispatched run also accepts game/day budgets. The branch `data/bayesian-history` is the source of truth for its progress, not `main`. To fit the joint model, dispatch `NHL fully Bayesian joint offline training` with an exclusive historical cutoff such as `2026-10-28`, after the receipt shows a sufficiently large verified dataset. Sampling outputs belong in Actions artifacts, never in a checked-in production configuration.

Local source tests:

    python -m unittest discover -s tests -p test_joint_nhl_history.py -q

The CI job `joint-bayes-nuts-smoke` installs requirements-joint-bayes.txt and validates the actual probabilistic graph and small synthetic multi-chain NUTS sampling. Full four-chain convergence requires substantial historical coverage and is not inferred from this smoke test.

 
## New-model heldout scoring
 
After a successful converged NUTS fit, the manual training workflow reads
the next 28 calendar days of completed historical skater games **without
passing those observations into the model's features**. Frozen posterior
predictions are compared on the same player-games to a transparent
pre-cutoff, position-shrunk Gamma–Poisson baseline, at a *fixed test
threshold of 2.5 shots*. Proper binary log loss, Brier, reliability and
coverage are saved as `reports/joint_nhl/holdout_validation.json`.
The heldout period must not overlap training, and postgame exposure
minutes are never used as an offset for future forecasts. This is a
retrospective **player-stat model benchmark**, not a backtest of
contemporaneous prop offerings or line availability.
 
Tests: `test_joint_nhl_history.py`, `test_joint_nhl_holdout.py`, and a
separate real NUTS sampling `test_joint_nhl_pymc_smoke.py`.
