# Pick'em Auditor V2.5 — Phase 1.5 implementation

Status: **implemented in isolated shadow branch; predictive promotion blocked.**

Purpose: diagnose where already-frozen NFL forecasts fail *before* paying the
complexity cost of a logistic-normal allocation model or joint simulator.
This is an **observational diagnosis**, not a new betting engine.

## Commands

Run adversarial tests (Python standard library; no paid data or NUTS fitting):

    python -m unittest discover -s tests -p 'test_phase15_diagnostics.py' -v

Run against the archived 2024 frozen synthetic-line replay:

    python scripts/phase15_diagnostics.py \
      --contracts pickem_runs/2024_hybrid_weekly_blind_retrain_20261109/PERFORMANCE_REPORT/every_2024_prop_frozen_prediction_and_settlement.csv \
      --cohort-status synthetic_historical \
      --bootstrap 1000 \
      --output reports/phase15_frozen_2024.json

The Deepnote project has a separate, unscheduled **V2.5 Phase 1.5** shadow
notebook that reads the archived CSV and saves an evidence receipt. It does
not touch the existing daily notebook, production weights, or training state.

## What the contract diagnostic measures

- Full input denominator, including unmatched, push, and missing-baseline rows.
- Exact contract identity guard for week/game/player/stat/line; duplicates fail.
- One Bernoulli outcome per contract, not two independent Over/Under legs.
- Paired Brier and log loss against the archived baseline on the **same rows**.
- Model Over probability minus actual Over frequency (directional bias).
- Selected Over/Under shares, observed hits, forecast-vs-hit calibration,
  per-market breakdown, and all 80%-plus candidate counts.
- Paired bootstrap intervals with **game** and **week** resampling (each
  clustered independently); no per-prop IID bootstrap.
- Input SHA-256 receipt and explicit shadow/no-promotion mode.

The archived 2024 CSV uses **synthetic** research lines, so these scores can
help evaluate distribution and direction, *not historical sportsbook edge*.
The model family may have been exposed to some 2024 information during
development; do not represent this as an untouched, prospective holdout.
An improvement over a historical baseline may be diagnostic only.

## Optional structural-opportunity diagnostic

A second CSV can be supplied with \`--components path.csv\`, containing:

- identity: \`week,game_id,player_id,market\`
- time: timezone-aware \`forecast_at,event_start_at\` (strictly pregame)
- pregame predicted fields:
  \`pred_team_volume,pred_participation,pred_share,pred_efficiency\`
- retrospective actual fields:
  \`actual_team_volume,actual_participation,actual_share,actual_efficiency,actual_stat\`
- optional \`predicted_stat_mean\`, which must match the product of predicted
  components to numerical tolerance.

Here \`participation\` and \`share\` must lie in [0,1], and each opportunity
family must have a coherent definition of these factors. Do **not** force the
schema onto player stats without a multiplicative opportunity structure.
The engine must actually have recorded each pregame prediction: missing
forecasts cannot be reverse-engineered from postgame box scores.

The evaluator forms the four-factor predicted mean and performs exact
four-input Shapley **oracle substitution** of realized factors. It reports
the attribution of squared-error reduction to team volume, participation,
share and efficiency, plus week/game-clustered descriptive intervals.

This measures postgame sensitivity of a particular factorization. It is **not
a causal attribution**, a deployable pregame forecast, a guarantee that a
replacement model can attain oracle results, or a reason to leak actual volume
into any feature generator. Interactions may produce negative contributions;
the four terms sum to total oracle error reduction by construction.

If no such originally frozen pregame factor forecasts are available, the
receipt records \`point_in_time_predicted_and_realized_opportunity_components\`
as **missing evidence**. There is deliberately no synthetic reconstruction.

## Exact Tier claim power

The module performs an **exact one-sided fixed-n binomial test**. For
prespecified null hit rate p0 vs true rate p1, it finds the first n for which
there exists a rejection threshold k with
P(X >= k | p0) <= alpha and P(X >= k | p1) >= target power.

Default: alpha .05, power .80; comparisons 70→80, 75→80, 80→85, 85→90, 90→95.
Set \`--weekly-independent\` for a planning-rate illustration. This parameter
is **not estimated** from raw prop volume. Game-cluster correlations invalidate
the independent Bernoulli test if ignored. For rho .05/.15/.30 the tool reports
an *illustrative* design effect, not a validated n_eff. Repeated looks, multiple
Tier tests, candidate selection, and regime shifts require additional controls.
No result in this report authorizes Tier certification.

## Phase 1.5 stop/go decision card

**Gate A — evidence integrity:** source SHA, complete denominator, exact
outcome/line semantics and strict separation of pregame forecasts from
postgame oracle actuals. On failure: stop, repair source pipeline.

**Gate B — directional diagnosis:** inspect signed Over residuals,
80%-plus miscalibration, per-stat errors and Over/Under concentration on
frozen, paired cohorts. If baseline improves materially: prioritize a
simpler calibrated baseline, not additional architecture.

**Gate C — opportunity diagnosis:** require enough authentic frozen pregame
component forecasts and resolved outcomes. If unavailable: classify
component attribution as **unmeasured**, not zero, and collect it prospectively.
If volume dominates: prioritize game-state models. If participation dominates:
prioritize role availability. If allocation dominates: prototype constrained
shares. If efficiency dominates: prototype conditional outcomes. Treat ties or
wide clustered intervals as inconclusive.

**Gate D — economic edge:** real immutable pregame two-sided prices, matching
settlement contracts and payout rules are mandatory for market-relative
claims. Synthetic-line scores cannot pass. No model promotion, profitable
claim or Tier guarantee without independent future evidence.

**Gate E — complexity:** promote a challenger only if a precommitted, paired
time-ordered score or a separately locked dependence/operational metric
improves with defensible uncertainty, without integrity regression. Otherwise
keep the simpler champion and pause expensive simulator work.

## Safety and missing data

No model fitting, historical posterior alteration, daily schedule change,
unverified market imputation, decision authority, retrospective certification
or Tier unlocking occurs. This stage is designed to run **in parallel** with
Phase 0R and Phase 1 infrastructure work, while their actual deployment gates
remain strict. It must not imply that a source is certified simply because
there are row-level historic forecasts in Deepnote.

All reported errors and oracle gains are squared-statistic diagnostics.
Do not compare raw magnitudes across markets with different units without
normalization and a predeclared weighting plan. For market-relative Brier,
pair the *same exact contract and quote timestamp*; historical synthetic
baselines are not a substitute.
