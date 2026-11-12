# Pick'em Auditor NFL V5.6 — Frozen Decade Replay Contract
Date: 2026-11-12
Status: **research-only, no production or Tier promotion**
Experiment: V5.6-2016–2025-175W-PRIOR-ONLY-20261112

## Hypothesis
A single two-team NFL game simulator whose offense, QB, receivers, RB and defensive tackle budgets are physically conserved can reduce the gap to frozen V3/V4 when its player usage and residual categories are calibrated from **actual previously completed historical games**.

## Immutable architecture
- One jointly sampled environment and opposing game script per game/scenario; finite team passing/rushing pools.
- Receiver target/catch/yard outcomes sum into the same QB passing outcomes.
- RB carries plus QB rushes and unassigned category equal team rushes.
- Defense takes its opportunities from the *same opponent offense scenario*: opponent runs and completed passes.
- Team tackle event count partitions into solo and assisted events; two distinct assisted credits per assisted event, with unknown defender category.
- Scenario-profile selection recent/balanced/long is one game-level choice for all markets; no leg-level distribution fallback or independent probability stacking.
- No synthetic offer, line, current-game player actual, or frozen V3 probability is permitted to affect scenario generation. Synthetic lines are evaluated only after the scenario is created.

## Actual-history fitted factors (strict target-week cutoff)
- Team pass attempts/plays and opposing style: up to 10 prior seasons, with profile-specific historical half-lives and ridge pooling.
- Player historical target/rush/defensive usage, regularized by role and recent observations: current-week results excluded.
- Team target-attempt probability and catch-on-target probability learned from prior official player/team stats.
- Solo/assisted event-type probabilities learned from prior official team defensive stats against prior opponent offensive events.
- Player roster reappearance transitions learned from sequential *already completed* team-games.
- Team positional active-count budget sampled from the previous 12 games, never current outcome.
- Two-prior-game roster opportunity coverage learned from earlier games; during the 2016 initial warmup this was approximately 94.9% targets, 94.5% RB carries, 93.4% solo tackles, 93.6% tackle assists.
- Historical profile weights update **only after the matching weekly forecast and settlement receipt are frozen**.

## Retired candidates and nonadoption
- V5.3 per-market usage activation worsened the two-week Brier and was rejected.
- V5.4 game-wide KL projection used the synthetic contract list to choose anchors. Because the retrospective offer universe was assembled after outcomes were known, this could indirectly reveal which players recorded statistics. It was rejected as invalid for a zero-leakage historical experiment despite not reading current labels directly.
- V5.7 defender shrinkage CV selected a two-game prior using 2014–2015 rolling historical outcomes, but incremental two-week improvement over V5.6 was tiny, and CRPS worsened. Retain as an unpromoted ablation, not the frozen benchmark.

## Locked retrospective validation
- Seasons 2016–2025, every eligible archived regular season week; exactly 175 weekly origins.
- Frozen original V3 and V2 score cohorts from the same player/game/stat/line/settlement contract keys. V4 on the same matched pool for context.
- Full contract universe, unmatched/abstained/void records retained and separately counted.
- Each week: freeze all historical input and factor prior hash; generate V5.6 predictions in isolated child with **no official current-week result object**; persist forecast SHA; only then read settlement and update priors for week t+1.
- Primary: paired Brier vs V3 on the same 13 market types. Secondary: game/week-clustered paired Brier intervals, directional hit rate, per-market CRPS and calibration of declared 70/80/90% confidence; model coverage and directional Over bias.
- Physical constraints and exact Over/Under/Push complementarity enforced per scenario. Independent immutable archive auditor checks hashes, game state, offer probability, single-game allocation and historical cutoff.
- Any current-week or later stat inserted in history/PBP is a hard failure; altering the retrospective *synthetic offer list* must not change the shared game distribution.

## State of preliminary evidence (development-exposed)
- 2016 weeks 1–2: 3,928 paired contracts. V5.6 Brier 0.244191 vs V3 0.235969.
- 2016 all 17 weeks: 38,953 paired contracts; V5.6 Brier 0.241285 vs V3 0.236193; V5.6 hit 60.0724% vs V3 59.7618%; CRPS 3.423898 vs 3.422427.
- 2016 confidence ≥80%: 6,254 selected, declared mean 85.85%, observed 73.90%. This **fails** high-confidence reliability and blocks any Tier claim.

## Certification and economic safety
The historical data were retrospectively reconstructed. Source first-seen availability timestamps, genuine archived sportsbook quotes/payouts, current-starter verification, and market integrity have **not** been independently authenticated. Chronological code-level checks do not prove original information was actually available before kickoff. All retrospective scores are exploratory, especially when model design was informed by earlier evaluation of historical seasons. No market-edge, profit, independently untouched holdout, or prospective Tier claim is permitted.

Full-decade output may justify continuing prospective shadow research, not automatic model promotion. The frozen V3/V4 archives and production configuration are never rewritten.
