# NFL V5.6 — History-calibrated, single-game conditional-participation upgrade

**Project:** Pick'em Auditor
**Experiment date:** 2026-11-12
**Code branch:** `chatgpt/nfl-v5-historical-workload-calibrated-joint-20261112`
**Status:** **research implemented; first two weeks structurally audited; full decade replay launched but not yet completed**.
**Production:** unchanged. Tier authority remains blocked.

## Design objectives

1. Model each two-team NFL game ONCE per scenario, including both offenses and defenses.
2. Learn opportunity and conversion parameters from prior actual history only (up to ten years as available).
3. Preserve finite team/defense accounting and player presence at every scenario.
4. Distinguish unconditional P(stat) from conditional P(stat | participant appeared), because historical synthetic matched-boxscore rows exclude many nonparticipants. Neither conditioning nor player appearances are inferred from target outcomes in the forecast.
5. Use earlier-week settlement labels only AFTER the relevant weekly forecast and state hashes have been frozen.
6. Reject future source and training rows on original timestamp lineage; never certify the retrospective synthetic data with missing original source receipts.

## Evidence motivating changes

In the first two 2016 research weeks, among players with recent history:
- last-five targets 4.19 vs current outcome 4.38; V5.2 projected 2.38;
- last-five RB carries 9.25 vs outcome 8.12; V5.2 projected 5.86;
- last-five tackles + assists 3.67 vs outcome 3.62; V5.2 projected 2.24.

Those discrepancies identified **model-induced dilution of known roles**, rather than absence of predictive value in historical player workloads. Numbers from this already-exposed pilot were used during development; **do not call the cohort a clean holdout**.

## Code sequence and causal structure

### V5.2: historical opportunity and efficiency priors

- Historical player/role rates estimated exclusively from rows earlier than target (season,week).
- Ten-year-accessible prior population, with each profile's exponential age decay.
- Receiver completion probability, yards/catch, target pool coverage, prior roster participation, and defensive tackle-event/solo/assist rates learned from prior actual game data.
- Additional source-identifiable omitted/special-event tackle opportunity proxy stays in the shared game state and is tied to the opponent defense; its statistical mechanism remains approximate and requires source verification.

### V5.3: whole-game entropic scenario reweighting (optional research)

- Archived *frozen* V4 prior-week probability serves as a **soft research reference**, never as a player-stat-specific scenario substitution.
- 3 candidate scenario tilt strengths with a 25% ESS floor, and one common scenario mask across both teams/stats.
- Game-level tilt strength updated after completed weeks only using prior binary scores.
- Baseline/V4 anchor is **not independent evidence** of new model skill; an improvement caused by borrowing V4 forecasts cannot be represented as an independent learned result.

### V5.4: history-moment opportunity allocation

- Player-target, RB-carry, solo/assisted tackle expected opportunities use **their prior individual game history**, lightly pooled by role.
- Preweek team-level target/rush/tackle capacities cap allocations via finite, nonnegative, scenario-level multinomials.
- Unobserved/new roster opportunities remain in explicitly modeled residual buckets; zero-appearance scenarios cannot receive player statistics.
- Historical two-game roster coverage is estimated by reconstructing prior target games from still-earlier team rosters. It is not determined from the target current game's participation.
- QB, receiver, RB and defender outcomes are all constructed from one original game-state draw, never overwritten after allocation.

### V5.6: conditional on simulated active participation

- For every player, retain one binary activity indicator across all that player's statistics and the complete game.
- Output **both** `P(active)` and unconditional `P(Over/Under/Push)`.
- Separately compute `P(Over/Under/Push | simulated active)` by restricting the **same joint simulated game scenarios** to those where that player appears.
- Current retrospective scorecard uses the conditional statistic for the subset with official matched observations. There is no hardcoded certainty of activity, no source based on actual target-game status.
- For real products, actual DNP/void settlement terms and authentic original offers MUST be obtained before deciding whether and how to use the conditional probability. Do not present this pilot as betting-edge evidence.
- Multi-leg correlation must condition jointly on the actual set of required players, not multiply independently conditional player probabilities.

## Initial matched pilot (2016 weeks 1–2, 3,928 contracts)

| Model | Brier (lower better) | Notes |
|---|---:|---|
| V5.1 | 0.273679 | physically invalid QB rewrites |
| V5.2 | 0.267116 | historical opportunity priors |
| V5.3 | 0.260606 | V5.2 + soft V4 anchor |
| V5.4 | 0.247976 | prior workload constrained allocation |
| V5.5 | 0.246437 | V5.4 + soft V4 anchor |
| Frozen V3 | 0.235969 | research benchmark |
| **V5.6** | **0.233954** | prior workload + conditional-active evaluation, **no V4 anchor used** |

V5.6 hit rate **61.4053%** vs frozen V3 **60.9216%**; log loss **0.664400** vs **0.666117**; aggregate mixed-unit CRPS **3.40806** vs **3.63739** (do not use mixed-market CRPS for model promotion; evaluate per-stat distributions). On 2016 Week 1 V5.6 Brier **0.242499** remained worse than V3 **0.236431**; Week 2 V5.6 Brier **0.228726** vs V3 **0.235687**. The improvement is heterogeneous across weeks.

V5.6 80%+ confidence cohort: **468** matched contracts; nominal mean **85.91%**, realized hit **76.92%**. **High-confidence calibration still FAILS** and Tier 1/2 authority remains suspended.

## Integrity, negative controls and archiving

- V5.6 model: **19/19** conservation, shared-opportunity, lineup exclusion, future-history and active-mask adversarial tests passed.
- V5.4 future-source gate: **17/17** synthetic fixture tests passed, including missing original first-availability/ingestion receipts, source published after freeze, training after cutoff, unknown pregame QB1, target event used as training, final score injected as pregame feature, and quote identity mismatch.
- Previous V5.3 scenario entropy test: **6/6** passed.
- V5.6 independent saved-game-state audit: **2 weeks, 32 games, 4,096 game scenario paths, 7,025 research contracts, 3,928 paired outcomes, ZERO integrity/conditional-CDF/hash issues**.
- Every historical replay is written to a fresh append-only output directory containing immutable frozen preweek file, forecast SHA-256, settled follow-up receipt, and the original legacy comparator SHA.

### Prospective source safety

`research/nfl_v5_4_prospective_source_gate_20261112.py` enforces:

```text
source_first_available_at <= input_freeze_at <= forecast_at < event_start_at
source_ingested_at <= input_freeze_at
model_training_cutoff_at <= input_freeze_at
historical_game_end_at <= model_training_cutoff_at
historical_source_available_at <= model_training_cutoff_at
quote_timestamp <= forecast_at
```

The gate also requires original source SHA, event identity, verified QB1 identity and source receipt, and prohibits explicit target-game or postgame fields inside pregame features.

**These controls are tested, but have not been demonstrated end-to-end on authentically timestamped prospective NFL source/quote captures.** The current V5.6 inference runner intentionally accepts **research_only=True, pregame_certified=False** packets and rejects claims of certified status. Therefore, 0 violations in synthetic test fixtures is not proof of zero real-world leakage, and the actual daily production collection path is not certified by this experimental branch.

### Full 175-week research continuation

Detached connected Deepnote notebook:

- Notebook ID: `0dc32db08c0445568ab3c0886076f7cc`
- Run ID: `8efaef4c-dc8d-487f-9ddd-425953c1fcad`
- Scope: 2016–2025, all 13 researched NFL markets, 175 prequential weekly forecasts and post-freeze settlements.
- Expected output class: `reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V5_6_SHARED_GAME_175_WEEK_FULL_*/`.
- Independent audit and market-specific proper-score review are REQUIRED AFTER completion; do not claim 175-week improvement or source certification from the initial pilot.

## Promotion decision

**Keep V5.6 as a research challenger. Do not merge to `main` or deploy decisions.**

First two weeks achieve the user's **experimental** V3 benchmark without reusing V4 probabilities as score anchors, and independent same-game accounting passes. However they are small/development-exposed, synthetic-line conditional cohort scores. The large historical run, cluster-uncertainty comparison, original pregame certification and confidence Tier calibration remain open.

Required for production: 175-week independent forensic audit, per-market CRPS and score calibration, full eligible/unmatched denominator, stable later-season improvement under game/week clustering, authentic pregame source timestamps with original quote terms, active/DNP settlement terms and independently prospective shadow validation.
