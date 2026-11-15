# First next-engine experiment after integration

Decision: **one NBA points support-and-tail experiment**, not a joint simulator.
Status: proposed bounded research card; no new likelihood implemented in WS4.
Freeze this card, numeric margins, folds and producer SHAs before collecting
confirmatory predictions. November 10 is development-exposed regression data.

## Why this experiment

The independent replay finds NBA Bayesian B unavailable for 25/250 contracts
because of negative Normal predictive mass; **16 of these 25 are points**, out
of 47 offered points contracts. Bayesian A has 19/47 points support abstentions.
Consensus has only 9/47 points probabilities, with its own reliability gate;
these exclusions must not be assumed to have one common cause. Across the
entire 250-contract cohort, last-five and pooled Poisson nominal 90% intervals
cover only 74.0% and 78.4%; that is evidence to test tails/heterogeneity, not proof
that conditional NB2 fixes the cause. Minutes error and conditional dispersion
are not yet independently separated. Start with one market and one mechanism.

## Locked comparison

After WS1/WS2/WS3 independently pass their engineering boundaries:

- Population: **all** eligible original full-game OT-inclusive NBA points offers
  under one fixed book/quote policy, including likely DNP and low-minute cases.
  Preserve every source rejection and every model abstention. Do not restrict
  the primary population to favorable old-model coverage.
- Freeze WS2 opportunity/availability draws, their source manifests, means and
  random seeds identically for the two new arms.
- Ask WS3 to supply two existing support-valid conditional likelihood arms:
  Poisson control and one preregistered NB2 challenger. Keep conditional mean,
  training pool, availability mixture, opportunity draws and covariates fixed;
  estimate dispersion only on earlier training folds. If WS3 cannot isolate
  that mechanism with its artifacts, block this comparison rather than changing
  both minutes and likelihood at once. Do not build another model in WS4.
- Keep historical recent/pooled controls, Engine A/B, Bayesian A/B, strict NUTS
  where genuinely available, frozen 60/40, and original compatible no-vig market.
  No model blending. Report each own coverage and paired common-support scores.
- Primary: paired count CRPS on all valid, settled, played player-games under
  the fixed availability estimand. Secondary: NLPD, zeros, 90%/95% intervals,
  randomized PIT, upper-tail events, threshold Brier/log-loss, source rejection,
  participation/DNP, selected-vs-eligible behavior and runtime.
- Freeze both participation probabilities and the played-conditional count law
  before the game, with the joint participation/count law retained. Primary
  count CRPS scores that pre-issued played-conditional law among verified played
  games; it is explicitly a conditional estimand. Score participation separately
  on the full eligible universe. Joint log score is -log P(A) minus the count log
  mass when A=1; A=0 has no manufactured count target. Operator void is separate.
  Never score a mixture with DNP zero mass only on played cases and call that an
  unconditional improvement, or refit a conditional law after learning status.
- Threshold/market-relative tests use exact original offers. Count-distribution
  outcomes without authentic original quotes remain distribution research only.
  No fabricated prices, lines, EV or pick'em payout claims.
- Negative controls: disabled dispersion (Poisson limit), frozen opportunity
  identity across arms, permuted prior-only contextual features when present,
  timestamp-shift/current-game exposure mutations and reversed side extraction.
  Require zero critical violations and full reject ledgers.

## Prospective design and stopping

Use prior source-backed chronological data for development/calibration. Seal a
new future cohort beginning only **after** the protocol and all producer hashes
are registered. Proposed fixed collection window: first 40 eligible slate dates,
with at least 100 distinct games; these are budget/sample planning floors, **not**
a power calculation or guaranteed certification. If the game floor is unmet at
the fixed endpoint, report BLOCKED-BY-DATA rather than extending until favorable.
Choose the exact date/block-cluster method and simulation-based power using only
prior game/date residual structure before launch. If adequate effective sample
power is infeasible at that budget, classify the pilot diagnostic, not confirmatory.
No efficacy peeking or choosing a favorable last date.

Proposed minimum useful CRPS gain: **1%** of the locked control's prior-development
mean CRPS, with the numeric absolute margin frozen before evaluation. Require
the upper paired dependence-aware 95% interval for challenger-minus-control CRPS
below the negative margin, and log-loss noninferiority within a preregistered
0.005 nats per contract. Require zero unexplained coverage loss, source/invariant
failures, or material preregistered zero/tail/participation regression. If the
proposal changes after reviewing prior data, record a new version before the
untouched cohort. Proper-score improvement does not authorize market-edge claims.

Keep both new arms **uncalibrated** for the primary likelihood comparison. A
separate prior-OOF points-specific Platt challenger may be registered as secondary;
it must pass untouched-fold proper-score/noninferiority gates and multiplicity
review. Never apply one correction to assists and threes, whose Nov10 signed
errors have opposite directions.

Budget proposal: at most 2 CPU minutes and 512 MiB incremental memory per slate
for this one-market shadow comparison, no NUTS, one bounded offline fit before
launch and only registered update points. Measure actual WS2/WS3 inference cost;
these are proposed caps, not achieved simulator measurements.

Stop on integrity failure; retain the frozen controls if scores fail or remain
inconclusive. Proceed to a tiny fixed-marginal shared-state/dependence experiment
only if the marginal/source findings and a distinct joint-event hypothesis
justify it. A dependency gate passed by code alone never unlocks full simulation.
