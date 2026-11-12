# Pick'em Auditor V4 — chronology-safe history and opportunity factor tuning
Date: 2026-11-11 Eastern (execution artifacts UTC 2026-11-12)
Status: **RESEARCH-ONLY — no mainline merge, no automatic Tier promotion**

## User objective and what changed

Manual tuning here means defining plausible, inspectable **causal-structure-inspired factors** for the historical data used to predict opportunities: historical decay, positional pooling, recent role usage, opponent strength, shared projected play volume and defensive exposure. Manual tuning does **not** mean choosing arbitrary upward/downward probability overrides.

The new experiment learns factor/profile weights from **settled prior weeks only** and separately learns how to combine three pregame forecast probabilities (V4 raw factor mixture, frozen V2, player-history baseline) with an online per-market logit stack. In early weeks the stack defaults exactly to the frozen V3 probability.

It does NOT claim causal identification, genuine preseason injury/lineup availability, authentic sportsbook quotes, or a full new ten-year model for all legacy components.

## History weighted as long-term population + local role

For record age in seasons `a`, weight `2^(-a / h)`, with profile half-life `h`.

- Recent context profile: half-life 1.35 years, last five player appearances, per-player appearance recency factor 0.86, positional pseudo-history equivalent 0.8 prior games, ridge penalty 50.
- Long context profile: half-life 5 years, last twelve player appearances, recency factor 0.95, positional pseudo-history equivalent 3.0 prior games, ridge penalty 48.
- Frozen V3 backbone: originally half-life 2.5 years, eight player appearances, ridge 32, and a 75% blend of frozen V2 scenarios plus 25% original V3 context scenarios. Consequently the V4 backbone includes historical three-year dependence from V2.
- Maximum context history = ten prior seasons, with 2014 and 2015 available for 2016 warmup; no inaccessible older games fabricated.

Empirical Bayes-like player usage prior:

`share = (Σ_i d_i * usage_i + κ * mean_team_exposure * positional_prior_rate) / (Σ_i d_i * team_exposure_i + κ * mean_team_exposure)`

The positional prior uses the ten-year-accessible population archive and age discount; shorter individual usage histories can supersede population rates.

## Opponent effects and defensive opportunity

For pregame opponent-adjusted team play count `mu_raw`, neutral-opponent offense projection `mu_neutral`, and strength `alpha`:

`mu_context = clip(mu_neutral + alpha * (mu_raw - mu_neutral), 38, 84)`.

The same formula applies to projected team passing fraction with clipping 0.35–0.80.

- Recent profile: opponent strength 0.65 (damp historic opponent tendencies).
- Long profile: opponent strength 1.35 (amplify prior-only opponent tendencies).

The simulator retains shared game-tempo and opposite-sign passing-script shocks. It renormalizes per-team passing and rushing opportunities so simulated pass + rush = projected plays and the opposite defense sees those same projected plays.

For tackle exposure, an opponent-play deviation from 62 is weighted:

`adjusted_opponent_plays = 62 + beta * (simulated_opponent_plays - 62)`.

Beta = 0.65 (recent) or 1.15 (long), applied before reconstituting solo and assisted tackle counts. This remains a **coarse team-play proxy**, not actual defender snap/tracking exposure.

## Factor optimization: prior-only and distribution-aware

Each game scenario selects one of three candidates, using the **same scenario mask for all markets in that game** to maintain scenario-level covariance as much as compatible legacy sources permit:
1. Frozen V3 distribution, initial prior 0.85.
2. Recently weighted historical/opportunity variant, initial prior 0.075.
3. Long historical/opportunity variant, initial prior 0.075.

After each completed week only, each factor profile receives a mean loss for each of 13 markets:

`0.65 * Brier(q_i, y) + 0.35 * mean_{tau=.1,.5,.9} pinball(tau, forecast_tau, actual) / fixed_market_scale`.

Fixed scales differ by market and are *precommitted*, not estimated from the current game. Equal weight is given to each market's mean loss, not to its number of player offers. A centered exponentially decayed average of profile excess losses updates prior mixture weights. There is an 8% prior exploration component to stop immediate collapse to one candidate.

No current-week result enters a forecast packet, factor receipt, stack receipt or regression training example before the forecast file is frozen.

## Probability stacking and safety gate

For each market, learned simplex weights combine *historically available* logits from (V4 raw mixture, frozen V2 raw, player-history raw) plus a learned intercept. The weights and intercept update via small-step logistic-gradient feedback only after weekly settlement.

Before enough evidence exists, candidate stacking is ignored:

- at least eight completed prior weeks and at least 400 prior matched observations per market;
- candidate's prior-week Brier must outperform the frozen V3 probability;
- stack trust ramps gradually and is capped at 75%; otherwise output remains frozen V3 probability.

The earlier ungated two-week prototype had overconfidence and worse Brier. It was rejected. The gated two-week prototype reproduces frozen V3 Brier and direction exactly at the start while testing the new factor distributions in shadow.

## Prior validation milestone completed

Separate regularized three-source stacking (not the V4 online stack) fitted on 2016–2023 and evaluated on 2024–2025, n=83,925, development-exposed retrospective synthetic quotes:
- V3 Brier 0.23442003 vs stack 0.23317234 (delta -0.00124770).
- Hit 60.0346% vs stack 60.6720% (+0.6375 percentage points).
- Game-cluster 95% Brier-delta interval [-0.00147286,-0.00102355]; weekly interval [-0.00145457,-0.00104312].
- Game-cluster hit-delta interval [+0.004518,+0.008278].
- Markets are heterogeneous: pass attempts and QB rushing attempts worsened under that simple global recipe.
- This was NOT untouched prospective validation: the 2024–2025 seasons had been inspected in other project development.

Source audit file:
`reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V4_STACK_PROSPECTIVE_STYLE_CLUSTERED_VALIDATION/CLUSTERED_VALIDATION_RECEIPT.json`.

## Full historical replay

Deepnote notebook: NFL V4 full 2016–2025 175-week adaptive history + opportunity-factor replay vs frozen V3.

- 175 weekly cycles, 13 NFL markets, strict forecast/settlement separation.
- Identical 556,094 original synthetic offers, conditional 407,476 paired scored official outcomes.
- New source files and integrity receipts are append-only under `reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V4_ADAPTIVE_FACTORS_10YEAR_FULL_*`.
- Every week: immutable preweek history and factor-state file; isolated forecast child; SHA check; official settlement read; update weights and stack for **next** week.
- Archived V3, V2 and player-history frozen comparator predictions remain unchanged.
- Every market: Brier, log loss, directional hit, quantile/CRPS scores, mean residual, high-confidence reliability, candidate profile weights; compare year-by-year and by weeks. Only new shadow scores.
- Any failure of integrity, distributional quality or high-confidence reliability blocks production.

## Limitations and release policy

Historical data and synthetic offer lines were retrospectively assembled; these do not constitute true historical sportsbook odds or authenticated original pregame snapshots. Results depend on matched participants; 26% of offers originally lacked official matched observations. There is no certified realistic backup QB injury predictor or tracked tackle-opportunity feed.

Even a positive retrospective week/game-clustered Brier improvement cannot certify real-market profitability, Tier 1/Tier 2 selection or an independently untouched holdout. Prospective authentic line/starter source snapshots are required after the retrospective factor experiment.

Do not promote V4 until all 175 weeks finish, an independent receipt audit succeeds, separate market CRPS and high-confidence reliability pass, and prospective shadow validation confirms.
