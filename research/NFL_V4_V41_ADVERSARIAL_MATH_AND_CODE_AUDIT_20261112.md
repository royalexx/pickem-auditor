# Pick'em Auditor — V4/V4.1 adversarial methodology audit
Date: 2026-11-12 UTC
Scope: original 175-week 2016–2025 synthetic-line NFL research replay (13 markets)
Status: **STATIC/SIMULATION AUDIT COMPLETE; TWO TEN-SEASON RUNS STILL IN PROGRESS ON FIRST INSPECTION**
PRODUCTION ACCEPTANCE: **BLOCKED**.

## Research-only source limitations
- Retrospective nflverse player and QB depth records acquired in 2026, **not original authenticated pregame publication captures**.
- Synthetic contract lines equal `floor(median(previous eight observed player games)) + 0.5`, **not historical sportsbook/Pick'em lines or prices**.
- Active participation, 2024 and earlier QB depth and announced starters are not independently certified. Prior-week depth can be stale. 2016 Week 1 had zero QB passing-attempt offers because no prior-season qualified depth QB1.
- Forecasts are conditional on an offered, prior-history player being in official postgame observations. This excludes unavailable/nonparticipants without a true pregame participation model. Consequence: aggregate hit rates are not prospective wagering hit rates.
- Original V2 shared opportunity, V3 and V4 outputs must remain immutable; no retroactive model promotion.

## A. Critical: V4.1 QB repair breaks joint team-rushing conservation
Sample: 2016 Week 2, 3,712 qualified team-game simulation scenarios **per variant**.
- Original V4 profiles: 0 occasions where `sum(RB carries)+QB rushing attempts > team rush attempts`.
- V4.1 *recent* profile: **254 / 3,712 (6.84%)** violations; maximum 7 excess attempts; 81 scenarios over by more than 2 attempts.
- V4.1 *long* profile: **250 / 3,712 (6.73%)** violations; maximum 8 excess attempts; 77 scenarios over by more than 2.
- Both runs had zero instances of total target opportunities exceeding team passes in this sample.

Cause: `nfl_v4_1_qb_share_repair_model_20261111.py` calls `super().forecast_game()` (which has already assigned RB carries using the original QB rush draw), then replaces QB rushing outcomes with a fresh QB component draw but **does not reallocate RB carries**. The adjustment also regenerates QB passing attempts, completions and passing yards after the target pool is already allocated, risking passing-yard accounting inconsistency.

**Required repair:** Generate QB1 attempt and rushing allocations *upstream* inside the single shared game scenario, then allocate remaining team rushing attempts to RBs, and only afterward generate dependent QB passing stats, RB rushing yards, and receiving outcomes. Assert per-scenario constraints before emitting any draw.

## B. High: QB Beta share shrinkage was indeed mis-specified in inherited V3/V4
The inherited QB1 passing-share prior is `Beta(12 + 35*s, 12 + 35*(1-s))`. At historical share s=.95, the **prior expected share is .76695**, not .95. It pulls qualified QB attempt volume toward 50%.
In a separate sample of 124 matched QB attempts in early weeks, mean projected QB attempts were **29.89 versus 34.56 observed**, an average error of **-4.68**; this is diagnostic, not a causal estimate of the Beta bug.
V4.1 changes that prior to `Beta(1+60*s, 1+60*(1-s))`, with mean .9355 at s=.95. The direction of this repair is mathematically justified, but the downstream accounting bug makes the full implementation unacceptable.

## C. High: V4 versus V4.1 is not a clean single-factor ablation
V4 runner seeds global scenario-family masks with `seed(VERSION,year,week,game_id, ...)`. The V4.1 runner changes `VERSION`. Therefore per-scenario source family selections differ **even in non-QB markets**. Subsequent market stacking and global factor updates also diverge because QB scores change.

Report V4.1-minus-V4 as a **stochastic policy comparison** (paired same contracts), not the independent effect of QB share repair. A proper repair-only experiment must use common random numbers, frozen source-family masks, identical preweek weights, and isolate the affected downstream family.

## D. Major methodological mismatch: this is not pure ten-year training
Initial V4 probability scenario weights: frozen V3 .85, newly modeled short-context .075, newly modeled long-context .075. Frozen V3 itself uses 75% V2 historical opportunities with a three-season history limit. Thus initially `0.85*0.75 = 63.75%` of V4 scenario draws are legacy V2 three-year-derived paths. The V4 alternative historical factors are only **15% combined** at initialization. Historical access to ten years is real for the new profile models but does not imply a full 13-market ten-year refit.

## E. Medium/high: opportunity-factor adaptation is global rather than per market
`FactorWeights` updates a single 3-element source mixture from mean factor losses across all 13 markets, giving equal weight to each market. It cannot separately learn that targets need more recent usage, passing rate benefits from older population patterns, and tackles need defensive opportunity exposure.

Grouping highly correlated markets by 13 independent-looking losses double-counts structural signals (e.g. tackles+assists, solo tackles, assists; QB pass attempts, completions, passing yards). Replace with hierarchical opportunity-family weighting and market-specific residual correction.

## F. Medium: defender recency factor not applied as advertised to all tackle models
V4 overrides `_last()` to use five or twelve appearances depending on profile, but inherited `GameContextModel.forecast_game` computes defender historical tackle rates from `self.byplayer[pid]...[-PLAYER_APPEARANCES:]`, where module-level `PLAYER_APPEARANCES=8`. That bypasses V4's profile-specific five/twelve-game limit for core defender conversion rates. The profile modifies population priors and opponent-play multiplier, but does NOT fully apply the intended history-factor variation for defender tackles.

## G. Medium: quality gates depend on overlapping offers, not independent games
`OnlineMarketStack` begins to trust its marketwise candidate after eight prior evaluated weeks, >400 prior scored contracts, and an exponentially averaged prior Brier excess below zero. Because props within a game and across linked markets are correlated, 400 contracts should not be interpreted as 400 independent validation units. Estimate effective sample sizes using game/week clusters, and gate strong confidence separately.

## H. Metric safeguards
- Use paired per-market Brier and log loss; use CRPS/WIS **per market or normalized by precommitted units**, not an average across yards, passing attempts and tackle counts.
- Report directional accuracy, balanced Over/Under accuracy, probability reliability for 70%/80%/90%/95% cohorts with actual denominators.
- Use week/game cluster bootstrap, season-level robustness and early versus late history availability. Ten seasons of retrospectively model-exposed data are not an untouched test.
- Simulated scenarios per contract: only 128, limiting resolution at confidence extremes.
- No real sportsbook odds, payout-adjusted edge, or ROI claims allowed.

## Existing completed supporting evidence (separate earlier experiment)
A previous three-source logistic stack fitted on 2016–2023 was evaluated chronologically on 2024–2025 (83,925 paired research contracts). Brier V3=.23442003 vs stack=.23317234; directional accuracy V3=60.0346% vs stack=60.6720%. Week-clustered Brier delta 95% interval [-.00145457,-.00104312]; game-clustered [-.00147286,-.00102355]. This supports investigating stacking, **not approval of V4**, and is development-exposed.

## Decision
**No production promotion of V4 or V4.1.** V4 remains a shadow challenger until the full 175-week ledger and per-market distribution audit are clean. V4.1 is blocked already by confirmed impossible rushing allocation. Independently fix structural allocation, run paired common-random-number ablation, and validate on authentic prospective source captures before altering Tier gating.

This memo covers confirmed code/simulation defects and previously completed validation only. It does not claim the running ten-season V4/V4.1 final scorecards are already complete.
