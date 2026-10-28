# Multi-sport joint Bayesian population expansion

**Experimental shadow infrastructure only. No production A/B, tier weights, research gates, market lines, API credit usage or live forecasts are changed.**

## Historical population sources and markets

| Sport | Market coverage | Source | Workload | Likelihood |
| --- | --- | --- | --- | --- |
| NHL | shots on goal, hits, blocked shots, goalie saves | Official NHL gamecenter completed regular-season player boxscores | Skater or goalie TOI minutes | Negative binomial |
| NBA | points, rebounds, assists, made threes, steals, blocks, turnovers, PRA, PR, PA, RA | ESPN public regular-season scoreboard + player game summary | Played minutes | Negative binomial |
| NFL | pass attempts, completions, targets, receptions, carries, passing/rushing/receiving touchdowns | nflverse per-week player stats, matched unique game/team/person to PFR offensive snaps | Offensive snaps | Negative binomial |
| NFL | passing, receiving and rushing yards including signed negative yardage | Same matched nflverse weekly data | Offensive snaps | Student-t with uncertain hierarchical signed yards per snap |
| NFL | tackles + assists, solo tackles, tackle assists, QB hits, passes defended | nflverse player weekly defensive stats and unique game/team/player PFR snap match | Defensive snaps | Negative binomial |

**Exclusions and statistical meaning:** NHL goalies are modeled conditional on appearance; saves use observed past goalie TOI, NOT postgame shots faced in a future prediction. NHL skater hits/blocks are not SOG substitutes. NHL goalie saves cannot use a skater-trained prior. NBA points and combinations are count totals over minutes. NFL snap records have distinct PFR identifiers; joins require an exact player name or an independently unique first-initial+surname among both weekly players and snap rows in the same game/team/week. Distinct source player IDs are never equated. Missing or ambiguous snap workload records are rejected and reported. NFL tackles + assists are defined explicitly as nflverse solo tackles plus tackles-with-assist plus tackle assists, each present and count-valid. Offensive production uses offensive snaps; LB/DB/DL defense production uses defensive snaps. Kicker and special-teams-only props remain unsupported; this expansion does NOT claim universal NFL prop coverage.

ESPN endpoints are public and undocumented, and may rate-limit or change field shape. Every completed game lacking verified boxscore structure fails closed; there is no hidden replacement by season averages. NBA and NHL historical source ingestion proceeds by dated scoreboard/gamecenter calls; NFL by bulk nflreadpy player/snap/schedule seasons. The collector uses no PropLine/Odds API, no research investigator and no external sportsbook odds.

## Storage and provenance

Existing historical source of truth remains the independent `data/bayesian-history` branch. `data/bayesian_warehouse/populations/{sport}/{market}/{season}.jsonl.gz` stores one immutable observation per sport/market/game/player. Each observation carries the original source URL, full source JSON/selected NFL joined-row SHA256 digest, game, player, position, opponent, date, count or signed yards and verified observed workload.

Separate, monotonic date/season checkpoints in `data/bayesian_warehouse/states/{nhl,nba,nfl}.json` prevent an error in one sport from causing progress in another; the historical storage script verifies all previous row contents and cursor counters. The older NHL SOG archive and its checkpoint are preserved independently.

GitHub Actions `Multi-sport Bayesian population backfill` starts on merge and then runs once daily with bounded requests and serialized access to the history branch, shared with the existing NHL history collector. Its three sport steps continue individually on failures and preserve completed source work; job conclusion fails if any source is blocked. Check the receipt artifacts and the actual data branch for nonzero coverage; a code-green test is not evidence that a source is available.

## Model

`scripts/joint_population_bayes.py` implements a full PyMC NUTS joint Bayesian model for player-level log-workload and log-production-rate effects with LKJ covariance. It estimates population means, random-player effects, season effects (zero when only one season is observed), centered opponent effects, home effects and count overdispersion or signed-yards Student-t variance together. Predictions draw unobserved next-game workload, then integrate the relevant count or continuous likelihood over posterior draws. **Never condition a future forecast on observed future minutes/snaps.** Only completed historical player games strictly before the training cutoff are included. New opponents/players/season effects without identified priors are explicitly rejected rather than guessed.

Samplers require four NUTS chains in GitHub's evaluation workflow, max Rhat <= 1.01, minimum bulk ESS >= 400, zero divergences, and BFMI >= .30. A failed diagnostic blocks scoring; even passing sampling checks does not authorize ranking.

## Per-stat empirical test

The `Multi-sport Bayesian stat-by-stat heldout evaluation` GitHub Actions workflow takes exact `sport`, `stat`, exclusive `as_of` and `until` dates, and an **explicit fixed research line**. It freezes the posterior trained on earlier games, scores later already-completed games for the same eligible player population and compares on exactly matched player-games to:

* count markets: position-shrunk Gamma–Poisson game-total control;
* NFL signed yards: position-shrunk Student-t game-total control.

It publishes proper binary Brier and log loss, paired date-cluster bootstrap differences, coverage, player-game provenance and posterior sampling diagnostics. A market is described as better on heldout only with >=300 same-cohort player-games and >=20 distinct future dates and favorable intervals for **both** scores. This is still exploratory research with multiple testing across stats; it cannot by itself authorize rankings. **No fake historical sportsbook lines, payouts, CLV, or profit claims.**

Expected development path: accumulate genuine multi-season history, benchmark each market on large untouched rolling holdouts, then introduce non-pregame-leaking role/injury features with their own verified timestamped sources. For NHL 2018 limited data the SOG full joint model had no significant advantage; do not assume every stat benefits from complexity.

## Tests

`test_population_multisport.py` checks provenance, immutability, dated resumption, NBA/NHL normalization, NFL snap matches, signed yardage and publication vetoes. `test_population_joint_pymc.py` fits real synthetic NBA and NFL PyMC multi-chain posteriors, tests diagnostics and predictive output. CI keeps legacy testing isolated from optional PyMC dependencies.
