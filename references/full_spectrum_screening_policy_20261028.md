# Full-spectrum source screening — October 28, 2026

## Provider coverage and limits

- NBA live PropLine requests now include **points, rebounds, assists, threes, PRA, PR, PA, RA**. A zero-row market is still a missing market, never a zero-valued forecast.
- NHL shots on goal, blocked shots, and goalie saves were already requested. Oct 28 had zero normalized blocked-shot prices. `reports/market_coverage.json` now lists every expected market and its actual quote count, distinguishing source absence from a successful ingestion.
- NHL **hits** are supported by player historical game logs, game-by-game team usage/lineup histories, and external two-sided fixture odds imports. The published PropLine NHL player-market list does **not** include `player_hits`; therefore the production PropLine request intentionally does not include this unsupported market. Nothing about hits becomes a bet or tier without real, approved external prices. Do not invent or substitute odds from another statistic. A new actual provider can be integrated separately when supported.

## Production early-season history bridge

- Engine A continues to use current-season window count for `current_role_n`. If `usage_baseline.verify_a` independently validates every source game ID, a same-role prior season (bounded at 20 observations) may lift a *3–4 current-game* sample past the sample block only when the robust estimator has effective N >= 10 and at least 10 prior game IDs.
- Engine B uses 3+ current-season usage records, 10–20 accepted prior-season records at a **0.40 observation weight**, and a 25% inflation to mean standard error to account for role drift. This can support 3–9 current-season games. It fails closed on dated source, team/player, workload, game identity, role consistency, checksum, or sampling discrepancies. A 5–9 game sample with no verified prior retains its previous strict thin-history label.
- A prior-backed grade receives an extra uncertainty flag and cannot become Tier 1 just from historical pooling. Past seasons are *not* backdated into current-season games, and no unverified prior counts are used.
- The new history bridge is **not a validated Bayesian calibration**. Tier probability estimates remain provisional pending chronological holdout and settled-slate evidence.

## Selection and source recovery

- Research candidates from all priced sports/stats are rotated by `(sport, stat)`. Deduplication is now per **player/stat/fixture**, not just player. Both sides of one player-stat remain deduplicated to one prioritized investigation; independent markets stay separate.
- The first two-thirds of the research budget go to existing primary candidates. When present, up to one-third is reserved for source-recovery subjects that have actual bookmaker evidence but no valid published grade because of sample/context/market/engine problems.
- A recovery may use raw, date-stamped **Engine A probability** and same-line sportsbook odds solely as provenance-labeled diagnostics for source-review triage. The potentially extreme values from 3 games are *not predictions eligible for Tier ranking*. Recovery-only items are **explicitly excluded** from research-ranked and approved verification, and can be reconsidered only after collecting corrected evidence and issuing a **new immutable forecast**.
- A high but unreliable NHL goalie-saves grade is a recovery candidate rather than being silently dropped; starting goalies still need game-specific confirmed status.
- No market/model gap threshold was changed. The 8 percentage-point Watchlist cap remains pending separate review of chronological backtesting and settlement results. One winning goalie prop alone does **not** validate overriding a guardrail.

## Real-data replay and tests

- October 28 historical replay reads the archived immutable forecast rows and never calls paid or live odds endpoints. It demonstrates source-recovery subjects in previously unrepresented NBA markets; detailed source-only replay logs remain in the one-off GitHub Actions run.
- The daily market-coverage receipt is uploaded with existing artifacts, independently of whether any prop gets tiered. Quota checks and other market-vig calculations remain unchanged.
