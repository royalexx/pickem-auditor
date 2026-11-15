# NBA joint-engine readiness specification v1

Status: implemented boundary fixture; **no joint simulator authorized**.
Version: `nba-joint-readiness-v1`. Scope: NBA, full game including all overtime.
Governing pipeline:

`Pregame feature store -> game state -> player opportunity -> conditional outcomes
-> coherent joint simulations -> threshold extraction -> calibration -> decision`.

## Boundary schemas

All three envelopes carry `schema`, `event_id`, `scenario_id`, `seed`,
`source_manifest_sha256`, `input_freeze_at`, `code_sha`, `artifact_sha256`,
`training_cutoff`. The first six shared fields must match exactly. Code/artifact
provenance is component-specific; input-source lineage is shared. Full manifests
must carry model IDs, exact versions, trained data hashes, fit completion times,
feature definitions, environment/lockfile, calibration versions and runtime.
The canonical evaluator additionally verifies raw bytes and source clocks.
The fixture validates structural provenance; it does not authenticate sources.

| Producer | Required component payload | Consumer obligation |
|---|---|---|
| WS1 | `event_start`, exactly two `team_ids`, `market_anchor` (`none` or `explicit_separate_arm`); original event, player/team roster as-of freeze, injury/lineup availability, receipt/quote manifests | Reject missing/conflicting identity or clock evidence; no postgame injury/minute information |
| Game-state adapter | Shared scenario ID, regulation length and nonnegative overtime count, possessions/pace/score-state realization, availability realization, anchor arm | Sample shared state once per scenario, then pass the same realization to both downstream producers |
| WS2 | `overtime_periods`, `players` with unique `player_id`, `team_id`, `minutes`, `active`; full contract additionally availability probabilities and draw lineage | Check player support and conservation separately from predictive minutes calibration |
| WS3 | `players` with unique `player_id`, matching `team_id`, integer `points, rebounds, assists, threes, fgm, fga, ftm, fta`; `team_points` | Require matching opportunity/scenario; conditional draws respect opportunity and shared pools |
| Threshold extraction | Original canonical offered contract, statistic vector/PMF or scenario array, scenario weights and ordered IDs | Compute Over/Under/Push together from one law; never seed sides separately |
| Calibration | Original probability triplet, stat/line/side domain, calibrator provenance and prior OOF cutoff | Preserve complementarity, keep raw and calibrated outputs separate; abstain when unsupported |
| Decision | Product-specific offer/payout/rules, original eligible universe, explicit strategy/selection version | No economic output without authentic original terms; no production authority from this fixture |

The JSON fixture has ten active players solely to make conservation checks small.
Real production envelopes include all rostered players, inactive/uncertain
players, probabilities, and realistic substitution/rotation state. The fixture is
not a statistical participation/minutes model and its values are not learned.

## Deterministic seeds and scenario identity

`seed_for(master,event_id,scenario_id,component_version)` takes the first 64 bits
of SHA-256 over a versioned delimiter-separated string. Never use Python's
process-randomized `hash`. IDs/version strings must not contain the delimiter
`|`; adapters must reject ambiguous IDs. Master seeds and component versions are
frozen before evaluation. Use stable scenario IDs, ordered coordinates and
fixed scenario counts. Changing worker count/order must not change a scenario.
Persist scenario weights and original draw IDs. The shared envelope seed
identifies the common scenario; component substreams derive from the common
seed and component version. Do not run independent shared-state draws in WS2
and WS3 and then label them one game.

## Physical and numerical invariants

The executable fixture checks:

1. Exactly two distinct teams; unique player IDs; matching player/team sets.
2. `game_minutes = 48 + 5 * overtime_periods`; each player's exposure lies in
   `[0, game_minutes]`; each team's minutes sum to `5 * game_minutes`.
3. Inactive players have zero minutes and zero realized outcome statistics;
   zero minutes cannot carry nonzero statistics in the supported fixture policy.
4. All count outputs are nonnegative integers; `threes <= fgm <= fga`,
   `ftm <= fta`; `points = 2*fgm + threes + ftm`.
5. Player points sum to scenario team points; team assists do not exceed team FGM.
6. Combo values equal same-player, same-scenario primitive sums exactly.

Additional simulator gates, not falsely asserted by the small fixture:

- Legal five-player lineups, substitutions, foul-outs, injuries/ejections, team
  possession/shot/free-throw pools, simultaneous exposure and overtime states.
- Rebounds reconcile missed eligible shots, live/dead-ball rebounds, team
  rebounds and period-ending possessions; no simplistic rebounds=all missed
  shots identity. Assists link to eligible made field goals.
- Team point equality by quarter/period, opponent possession transitions,
  event-level 2/3/FT accounting and optional score-state consistency.
- Distribution means/quantiles/support and conditional sample agreement; exact
  scenario weights nonnegative and normalized; no hidden truncation repair.

A constraint violation blocks the scenario/model; record its reason and retain
it in the attempted ledger. Do not silently resample only valid-looking games
without accounting for changed law and rejection rate.

## Overtime, DNP and uncertain availability

Full-game contracts include every overtime period; conditional opportunity and
outcome distributions must use the same sampled overtime count. An OT count
cannot be substituted after seeing the actual game. Regulation-only markets
require a different policy, schema version and extraction path; v1 rejects them.
Observed zero is distinct from DNP/void. Availability is a pregame mixture;
simulations draw active status once and share it across all same-player markets.
Do not condition forecasts on eventual participation without labeling that
conditional estimand. An operator DNP void probability is separate from count
zero/push mass and must be integrated at the decision layer using actual rules.
Partial-game injuries, abandoned games and operator-specific participation
minimums require explicit policies. Unresolved status remains pending.

## Combination settlement

For each player and scenario, derive `PR=P+R`, `PA=P+A`, `RA=R+A`,
`PRA=P+R+A` from the **same** primitive draw. A threshold probability is an event
on that sum; do not sum marginal probabilities, multiply correlated outcomes,
independently draw each combo, or double-count duplicate players. Settlement
uses official primitive totals with the same overtime/period policy and checks
against any directly reported combination. Provider discrepancies are quarantined
with both receipts, not resolved by choosing the favorable value.

## Anchors, independence and future joint scores

Unanchored and market-conditioned arms are different models with different
provenance and comparable offered universes. An anchor is not an independent
benchmark after entering the model. Never count information shared by Engine
A/B/Bayes as multiple votes. Calibrate the whole arm using earlier OOF outputs;
keep uncalibrated original marginals available.

The first dependence experiment, only after marginal/source gates are met,
compares a fixed-marginal independent coupling with one shared-state coupling.
Hold player marginals, WS2 opportunities, priors and computational budget fixed.
Use original same-game multivariate outcomes with precommitted coordinate order,
unit/scale normalization fitted only on training data and explicit missingness.
A shuffled-dependence negative control must preserve each marginal and expose
conservation breakage; invalid shuffled states cannot be considered valid games.

For ensemble draws `x_1,...,x_M`, outcome `y`, and registered norm/scales:

`ES = mean_m ||x_m-y|| - 0.5*mean_{m,n} ||x_m-x_n||`.

Specify whether the empirical predictive measure includes the diagonal; use the
same convention for every arm. Do not change M or use the unbiased off-diagonal
estimate for only one competitor. Report Monte Carlo error and CPU/RAM.

`VS_0.5 = sum_{i<j} w_ij ( |y_i-y_j|^0.5
                          - mean_m |x_mi-x_mj|^0.5 )^2`.

Pair weights, dimension/units, exposure/availability, scaling, period and
coordinate identities are frozen before outcomes. No outcome-dependent pair
selection. Use paired game/date uncertainty and prespecified same-game joint
threshold events, plus marginal CRPS/Brier/log-loss and coverage. Energy Score
alone may be insensitive to dependence; Variogram and joint-event calibration
are required. Existing `v2/joint_evaluation.py` is an implementation reference,
not evidence of an NBA original scenario ensemble. Nov10 multivariate scores
remain **BLOCKED-BY-DATA**; do not fabricate retrospective original scenarios.

## Abstention and integration decision

Abstain on unverifiable clocks/identities, stale traded-team mapping, incomplete
rosters, unavailable original quotes for economic evaluation, unsupported market
policy, missing fit/source provenance, invalid support/probability mass,
nonconserved opportunity, inconsistent scenario IDs, unsupported calibration
regime, unacceptable Monte Carlo error or explicit model reliability failure.
Separate source rejection from model abstention and decision abstention.

A deterministic fixture pass verifies an interface, not calibrated minutes,
conditional distributions, joint-event skill or market edge. WS1/WS2/WS3 must
supply immutable branch/SHA manifests and untouched-fold predictions before
scientific integration acceptance. No merge of those branches occurs here.
