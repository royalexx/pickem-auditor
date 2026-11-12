# Pick'em Auditor — NFL shared-game-state repair (V5/V5.1)

**Date:** 2026-11-12
**Scope:** NFL offense + defense, all 13 researched prop markets
**Status:** **ENGINEERING SHADOW IMPLEMENTED + SCENARIO INTEGRITY TESTED — PREDICTIVE REPLAY REJECTED FOR PRODUCTION**
**Development branch:** `chatgpt/nfl-v5-shared-game-offense-defense-20261112`
**Production:** unchanged; V2/V3/V4/V4.1 frozen artifacts and training retained.

## Why this repair was mandatory

The V4.1 candidate called the V4 forecasting function to simulate QB1 and RBs, receivers, and defensive tackles, then independently re-sampled the game environment and **overwrote the QB's pass and rush outputs**. That could produce contradictory same-scenario stories: QB attempts incompatible with receiver targets/completions, RB carries exceeding the team's rush pool, and defensive tackle exposure not bound to the offensive event budget.

The earlier architecture also used `v3_draws` per individual offered player/stat as a major source of the V4 ensemble. A global source-mask alone cannot guarantee joint conservation if a source distribution itself is a marginal-only historical blend.

These are physical/accounting defects. They must be fixed independently of Brier scores, historical tuning weights, or calibration.

## Architecture now implemented

For each scheduled two-team game, each profile draws exactly one shared offensive environment. The same scenario is then used for **both teams**, and for all supported statistics and defensive outcomes:

```text
Forecast-frozen historical evidence + QB1 identity + game context
       |
One shared game/tempo and opposite-side pass-script scenario
       |
+------------- Team A offense ----------------+
| Team A plays = A pass attempts + A rushes    |
| QB1 + residual passer attempts = A pass     |
| Team attempts -> targets (including residual)|
| Targets -> receiver catches -> signed yards  |
| QB1 completions/yards = exact sum of catches |
| QB rush PBP components -> available team rush|
| Remaining team rush -> RB carries + residual |
+----------------------------------------------+
       |
Team B defense receives EXACT SAME Team A rush and completed-pass events
       |
Tackleable events -> solo OR assisted event budgets -> named/residual credits
       |
+------------- Team B offense ----------------+
| Same structure, simultaneous shared pace     |
+----------------------------------------------+
       |
Team A defense receives EXACT SAME Team B opportunities
       |
Per-game, per-scenario complete opportunity and player-stat snapshot
       |
P(Over), P(Under), P(Push) counted from one unchanged joint sample set
```

- No QB output is rewritten after the receiving or rushing allocations.
- A backup QB cannot acquire a named forecast without the original prior-only qualified QB1 identity.
- No receiver can have receptions beyond their own targets or team targets beyond pass attempts.
- QB passing completions and passing yards are the sums of the *same receiver catch outcomes* attributed to QB1, including a residual unnamed receiver category.
- RB carries and QB rush attempts plus unnamed rushing plays sum to the same simulated team rush count.
- Solo and assisted tackles are credited against a finite opponent offensive-event pool, never an independent defensive Poisson exposure. Two assisted credits may arise from one assisted event; their recipients must be distinct unless the recipient is unnamed/unscored.
- Both teams share latent pace and opposing game-script shocks in the original game environment.
- Scenario-level profile selection (recent/balanced/long) is one choice for *all players, both teams, and all stats in the same game draw*. Individual-market V3 substitution is forbidden.
- V3 and V2 remain read-only comparison benchmarks, not members of the V5 joint sample mixture.
- Player participation is a latent scenario variable estimated from prior observed rosters only, with an explicit unassigned category. This does not retrospectively verify that a named player was active.

## Design tradeoffs and remaining defects

V5 initially conserves opportunities but forecasts too many targets, RB opportunities and tackles across previously observed players, some of whom are inactive in the future game. V5.1 adds prior-only probabilistic participation, allowing excluded-player shares to redistribute **within the same finite game pool**.

The model does not yet have true event-level NFL play-by-play possession, pass dropback/sack, tackle-location, coverage, and verified pregame depth-chart state. Its tackleable event pool uses opponent rushes and completed passes, and its QB component model uses projected QB pass attempts as a dropback proxy. Thus the simulator conserves *its declared approximate opportunity graph*; it is not a verified complete NFL official play accounting engine.

## Executed tests and reproducibility

### V5 initial two-week frozen pilot

- 2016 weeks 1 and 2; 32 games; 7,025 research contracts; 3,928 matched paired scored contracts.
- 11/11 focused invariants and adversarial unit tests passed.
- Brier: 0.284363 vs frozen V3 0.235969; CRPS aggregate 4.2014 vs 3.6374.
- This is a **large loss regression**. The test is not a valid reason to promote, even though conservation passes.

### V5.1 scenario participation pilot

- Same weeks, games, offers and outcomes; 12/12 focused tests passed.
- Brier: 0.273679 vs V3 0.235969; aggregate CRPS 4.12067 vs 3.63739.
- Numerically better than V5 initial but still **unacceptable as replacement**.
- Selected 80%+ group: 1,794; claimed 88.27%, observed 65.61%. Strong overconfidence.
- Mean signed predicted Over residual ≈ -0.167: directional Under bias persists.
- The two-week sample is too small and historically exposed to identify a stable calibration or longer-history effect.

### Independent archived output audit

V5.1 freeze and game-state audit read the original persisted forecast/settlement files without invoking the model code:
- 2 complete weeks, 32 two-team games, 4,096 whole-game scenarios.
- 7,025 offers, 3,928 paired scored.
- Exact forecast preimage SHA binding checked.
- All game-state offense/defense conservation equations checked independently.
- Per-stat CDF complementarity checked from the original saved draws.
- No per-contract legacy source fallback.
- **Zero integrity violations**.

## Original V4.1 defect reproduced with archived research inputs

An isolated re-simulation of 2016 Week 2 using the frozen preweek packet found:

| Scenario conservation condition | Original V4 | Repaired-QB V4.1 |
|---|---:|---:|
| Recent factor: QB + RB rush > team rush | 0 of 3,712 | **254 of 3,712 (6.84%)** |
| Long factor: QB + RB rush > team rush | 0 of 3,712 | **250 of 3,712 (6.73%)** |
| Max rushing attempts overallocated | 0 | **8 attempts** |

This directly confirms the underlying post-hoc QB rewrite bug. It also establishes why a successful V4.1 *probability arithmetic* audit cannot certify *joint physical consistency*.

### Existing V4 and V4.1 full-decade result and repaired audit

The corrected independent V4/V4.1 forensic auditor completed all 175 weekly settlement files (2016–2025) on the same **407,476 matched contracts**, with **zero hash/chronology/settlement arithmetic violations**. The previous undefined `th` variable failure was removed and its two-week smoke regression passed before the full decade audit.

| Aggregate metric | V4 | V4.1 | Frozen V3 |
|---|---:|---:|---:|
| Brier score | 0.23507765 | 0.23508627 | 0.23521197 |
| Directional hit rate | 59.8897% | 59.8919% | 59.8909% |
| Mean CRPS across mixed incompatible stat units (diagnostic only) | 3.46535 | 3.45362 | 3.45510 |

V4.1 minus V4 Brier = **+0.00000863**, i.e. V4.1 did *not* improve the full-cohort binary proper score compared with V4, despite the QB repair. Mixed-market CRPS must not be a release comparator; compare each market separately. The original V4.1 simulator is **rejected on physical conservation grounds** regardless of its marginal Brier.

Evidence files:
- `reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V4_INTERIM_INDEPENDENT_AUDIT/V4_V41_INTERIM_FORENSIC_REPORT.json` (now 175 weeks, despite legacy directory name)
- `reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V4_1_GAME_CONSERVATION_SMOKE_20261112.json`

## Remaining release requirements

1. Improve participation/opportunity/efficiency distributions on matched chronological historic cohorts, not by manually rewriting final probabilities.
2. Add authentic point-in-time roster/depth, sacks/dropbacks, defensive snaps, verified matchup and source-time data when available.
3. Demonstrate Brier, per-market CRPS, both-side calibration and joint dependence improvement under game/week-clustered evaluation; apply the hard score guard even when a model is physically consistent.
4. Audit genuine prospective market lines and payout terms before using the word 'edge' or authorizing Tier 1/2 picks.
5. Do **not** launch an expensive 175-week V5 replay merely to hide failed preflight; do it only when a frozen improved candidate passes the protocol's staged gate.

## Executable code/artifacts

- `research/nfl_v5_joint_shared_game_model_20261112.py` — initial complete game simulator.
- `research/nfl_v5_joint_decade_replay_20261112.py` — original 175-week capable replay harness.
- `research/nfl_v5_1_shared_game_participation_20261112.py` — scenario participation challenger.
- `research/nfl_v5_1_joint_decade_replay_20261112.py` — participation replay harness.
- `research/nfl_v5_independent_game_state_audit_20261112.py` — independent saved-state forensic checker.
- `research/tests/test_nfl_v5_one_shared_game.py` — 11 conservation/negative tests.
- `research/tests/test_nfl_v5_1_shared_participation.py` — 12 updated tests.
- `research/tests/test_nfl_v5_independent_archived_state.py` — adversarial output tampering controls.
- `reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V5_SHARED_TWO_WEEK_PILOT_20261112T133206Z/`
- `reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V5_1_SHARED_PARTICIPATION_PILOT_20261112T133929Z/`
- `reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V5_1_SHARED_SCENARIO_INDEPENDENT_AUDIT_20261112.json`

**Disposition: KEEP SHADOW IMPLEMENTATION, REJECT PRODUCTION PROMOTION.**

The software inconsistency is fixed for the new research challenger. Correctness of a generative scenario does not establish useful predictive accuracy, source certification or financial profitability.
