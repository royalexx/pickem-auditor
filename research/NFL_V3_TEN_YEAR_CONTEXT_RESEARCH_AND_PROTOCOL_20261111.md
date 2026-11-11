# Pick'em Auditor — NFL V3 Ten-Year Context Experiment
Date: 2026-11-11
Status: **RESEARCH ONLY — NO PRODUCTION PROMOTION**
Git branch: chatgpt/nfl-v3-ten-year-opponent-context-20261111

## Research question
Can a learned, opponent-aware game-opportunity layer and longer historical population context improve the old 2016–2025 chronological 13-market NFL replay, while correcting QB role identity, defensive play exposure, and previously observed overconfidence?

## Literature reviewed and its implications

1. **Dynamic attack/defense strength and decay:** Crowder et al. (2002), "Dynamic Modelling and Prediction of English Football League Matches for Betting", Journal of the Royal Statistical Society Series D. https://academic.oup.com/jrsssd/article/51/2/157/7120674. Attack and defense drift over time; historical context should use decayed/reverting effects rather than treating every decade-old matchup as current.
2. **Sport context and mixed populations:** "Dynamic team attack and defense strength in international rugby union", Journal of Quantitative Analysis in Sports (2026), https://doi.org/10.1515/jqas-2026-0073. Discusses random walks, autoregressive team ability and Dixon–Coles exponential decay; reinforces separating stable population information from changing roster-level ability.
3. **NFL actual opportunity and independent team matchup features:** the NFL Edge model describes learned team pace, opponent plays allowed, pass rate and player shares. https://chefjulio.github.io/nfl-edge/model/. This implementation borrows the **principle**, not the model's fitted coefficients, bookmaker features or validation results.
4. **Player opportunity x efficiency model:** SportsDataverse nfl_player_props documentation, https://sportsdataverse-py.sportsdataverse.org/docs/nfl/reference/additional/analytics. Cautions on strict week-as-of features and separate role/efficiency/matchup components.
5. **Tackle opportunity:** NFL Next Gen Stats introduction to Tackle Probability and the 2024 Big Data Bowl winning entry, https://www.nfl.com/news/next-gen-stats-new-advanced-metrics-you-need-to-know-for-the-2024-nfl-season. A genuine tackle-opportunity model needs play-by-play or tracking exposure. This experiment uses a coarser opponent-play count proxy; it **does not** claim to reproduce player-level tracking tackle opportunities.
6. **Proper probabilistic scoring:** Gneiting and Raftery (2007) "Strictly Proper Scoring Rules, Prediction, and Estimation", https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jasa.pdf. Use Brier and log loss at binary thresholds and CRPS for full predictive distributions. Never average raw CRPS across counts and yards as if their units were comparable.
7. **Temperature scaling/calibration:** Guo et al. (2017), "On Calibration of Modern Neural Networks", https://proceedings.mlr.press/v70/guo17a; and Gneiting, Balabdaoui and Raftery (2007), https://agupubs.onlinelibrary.wiley.com/doi/10.1111/J.1467-9868.2007.00587.X. Accuracy and calibration are separate. Strong 80%/90% claims require independent reliability checks, not only raw Brier improvement.
8. **Online shift-aware calibration:** Huang, Ma, Michailidis (2026), "Model-Agnostic Online Certificate-Driven Calibration for Time Series Forecasting Under Distribution Shift", https://proceedings.mlr.press/v337/huang26b.html. A correction that reverts to the established backbone when unsupported is a more defensible experimental design than an unconstrained replacement. Our fixed scenario ensemble is only a **prototype**, not their certified method.
9. **Game pace shared by both teams:** Early Downs projected snaps methodology, https://earlydowns.com/methodology/. Both offenses share a clock. Any new shared latent pace remains a coarse approximation without drive-level possession structure.
10. **NFL player prop usage pipeline:** GameDay Analytics methodology https://nfl.gamedayanalytics.net/props/methodology and publicly described NFL usage data sources, https://www.edgelineff.com/stats/. They motivate lagged player usage, teammate availability and opponent defense as separable inputs. This experiment cannot certify historical injury, route, coverage or snap inputs absent the original dated archives.

Literature findings are **modeling motivation**. They are not empirical proof that any specific context feature improves our 13 target distributions. That must come from the independent paired research replay and later live shadow data.

## Experiment protocol and source validity

- Reuse **exactly the original 2016–2025 175-week settlement and synthetic contract-line universe**, never relabel the old universe. Original final SHA-256: 47db4d35984eabfa298758b96b04460127119fc558b33e93c8cd98e054b190f9.
- As-of weekly prediction histories: trailing maximum **ten historical seasons** plus completed weeks of current season. Earliest warmup 2014; 2016 can only use 2014–2015, not fictitious older data. In 2025, 2015–2024 provide ten full seasons for league/matchup pattern fitting.
- The player-specific recency window remains eight past appearances. Stable population-role distributions are learned from up to ten earlier seasons with a 2.5-year exponential half-life; opponent offense-vs-defense matchup coefficients are learned by chronological ridge regression (penalty 32), never on current outcomes.
- The latent game simulator has one common tempo factor for both offenses and an opposite-sign game-script factor for pass fraction; it conserves pass + rush = simulated plays **for each team**.
- The QB1 **must** be the independently selected prior-depth QB; the projected leading passing workload must not be randomly assigned to a different historic QB. Unverified starters or backups remain research only; no late injury facts are used as current-game features.
- Defensive tackle expectation is scaled by opponent's **projected offensive plays** and player historical tackles per opponent play. This is *not* a substitute for true defensive snaps, tackle chance per play, tracking proximity or tackle opportunity.
- A two-week initial pure context simulator pilot **failed** both Brier and high-confidence reliability, so it was rejected as a replacement. A conservative 25% scenario-level context/V2 ensemble with isolated QB fallback was then precommitted **before the remaining full ten-season replay**. The ensemble still includes a legacy V2 component with only three-year historical context. Do NOT describe it as a complete ten-year retraining of every component.
- A revised online Bayesian market×side×confidence-bin calibrator trains **only on completed previous weeks**; retains past results with weekly decay 0.997. A week preimage SHA is frozen *before* settlements, repairing the prior 175-week mislabeled receipt defect.
- Each forecast is generated inside an isolated subprocess receiving only the preweek history, prior QB PBP, prior calibration, original static offered lines and **V2 frozen forecast draws**. It does **not** receive current-week official labels. New predictions and postweek settlements are separate, immutable SHA-receipted files.
- Probability simulations: 128 samples (resource constraint). These are exploratory and cannot establish 95% or 99% confidence to the precision claimed; future production tests require far more draws and epistemic uncertainty checks.
- **Original quote lines are synthetic**, derived from earlier player medians, not actual sportsbook offered markets. Historical source data were downloaded retroactively in 2026, not certified authentic archived pregame captures. No economic edge, ROI or Tier claims are authorized.

## Frozen comparators and score requirements

A. V3 standalone opponent-context challenger, scored raw at old synthetic lines.
B. V3/V2 research ensemble, 25% V3 scenarios + 75% old V2 scenarios, with tightly limited QB legacy-proxy override.
C. Original V2 shared-opportunity incumbent (unchanged scores and 3-year context).
D. Original player-history control (unchanged scores).

For each week, each of 13 markets, and each season, retain:
- exact offered, matched, paired, abstained and unmatched denominators;
- Brier, log loss, CRPS by market, side hit, mean residual, 80% interval coverage;
- ≥70, ≥80, ≥90 and ≥95% confidence groups: N, mean claimed confidence and realized hit rate;
- miscalibration of high-confidence picks and QB1 availability/disagreement;
- week/game bootstrap for paired Brier differences;
- stratification early season vs late, year-by-year stability, 10-year vs 3-year contribution;
- negative feature ablations: no opponent, no long-term history, no QB repair and no tackle exposure. **Not run yet**; preserve as follow-on experiments rather than presenting as completed.

## Explicit promotion blockers

- Any malformed source identity, forward-look feature, improperly updated calibrator, unfrozen forecast, or receipt mismatch.
- Any unverified pregame source, line, participation, starter or hidden backup treated as live betting input.
- Significant aggregate Brier gain alone without separate CRPS, distribution bias and high-confidence calibration checks.
- Lack of out-of-sample gains against both V2 and player-history; deterioration in targets, receptions, carries or tackle markets without a documented market-specific rollback.
- Historically development-exposed 2016–2025 seasons cannot become a pristine untouched holdout merely because the replay is chronological.

## Status

The full replay is a shadow research comparison on the connected Deepnote Basic machine. A successful process exit is not model acceptance. The finalized scores and audit receipts must be reviewed before any deployment decision.
