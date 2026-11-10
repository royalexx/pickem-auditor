# Phase 1.5 completed shadow diagnostics — November 10, 2026

Execution receipts:
- Deepnote notebook: "V2.5 Phase 1.5 — frozen error decomposition and tier power (shadow only)"
- Deepnote run (full): 47cef69a-b4a2-4e58-823a-deff2c4cd3cd
- Contract receipt: pickem_runs/phase15_20261110/frozen_2024_diagnostic_receipt.json
- QB opportunity receipt: pickem_runs/phase15_20261110/qb_volume_allocation_receipt.json
- Tests: **24/24 passed** in isolated detached Deepnote; no GitHub Actions minutes used.
- Production config, Tier publication, existing archives, daily notebook, and NUTS: **unchanged**.

## Contract-level replay: 2024 hybrid synthetic lines

- Total frozen contracts: 107,319; matched and graded: 71,009.
- Unmatched: 36,310, retained in denominator and explicit count.
- Cohort: 272 games, 18 weeks.
- Every scored line was \`synthetic_preweek_position_median\`, not a
  real authenticated sportsbook offer.
- Model Over Brier **0.1928184** vs recorded paired baseline **0.1951962**;
  difference **−0.0023778** (lower is better).
- Matched game-bootstrap 95% descriptive interval for difference:
  **[−0.0032797, −0.0015639]**; week-bootstrap:
  **[−0.0037096, −0.0009811]**.
- Model Over log loss **0.562414** vs baseline **0.566007**.
- Average modeled P(Over) **0.27860**, actual Over fraction **0.31243**:
  mean directional Over underestimation **−3.38 percentage points**.
- Selected Unders: **92.85%** of graded contracts.
- Under selections: **65,932**, mean selected confidence **74.30%**,
  observed hits **70.97%** (overconfidence **3.33 percentage points**).
- Over selections: **5,077**, mean selected confidence **55.89%**,
  observed hits **60.02%** (underconfidence **4.13 points**).
- At >=80% selected claimed confidence: **23,280** synthetic-line
  selections; **20,458** hits. This **cannot** validate a betting Tier:
  contract selection is retrospective/research, lines synthetic,
  observations correlated, model design possibly exposed to 2024.

Selected per-market paired Brier differences, model minus baseline:
- Targets **−0.01696**; receptions **−0.01031**; receiving yards **−0.01418**.
- QB pass attempts **−0.00541**; completions **−0.00806**.
- Tackle assists **+0.00622**; solo tackles **+0.00205**; passing TDs **+0.00183**.

The synthetic-line baseline improvement does not establish improvement
against the no-vig market or positive expected return.

## QB mechanism analysis: separate 2024 expanding-replay archive

A separate research cohort was built by joining each week’s original
SHA-locked \`FROZEN/week_XX.json\` QB forecasts to \`REVEALED/week_XX.json\`
and the postgame \`oracle_2024.json\` team outcomes. Every revealed QB row
must match the immutable frozen ID, line, model mean, team mean, and
forecast P(Over); altered hashes, future-week training and duplicate rows
are rejected. These are date-level research freezes, **not certified
intraday bookmaker snapshots**.

- Graded individual QB attempts: **547** across **270 games**, 18 weeks.
- Ungraded QB forecast rows: **321**, explicitly counted.
- Mean predicted team pass attempts **35.78996** vs actual **35.40585**.
- Mean predicted individual QB pass attempts **23.99778** vs actual **28.86654**.
- Mean implicit QB allocation share **0.67152** vs realized **0.81425**.
- One QB forecast per team-game (211 graded): mean QB error
  **+0.629 attempts** (predicted minus actual).
- Multiple candidate QBs per team-game (336 graded): mean QB error
  **−8.321 attempts**.

Exact two-factor oracle Shapley mean squared-error reductions:
- QB allocation share: **107.9601** (week-bootstrap descriptive
  95% interval [83.27, 131.68]).
- Team volume: **45.0338** (week-bootstrap descriptive
  95% interval [38.16, 53.59]).
- Share accounts for roughly **70.6%** of the two-factor substitution
  error reduction. This is not a *causal* or *deployable* gain: replacing
  predicted QB share with its realized value is prohibited at inference.

The source-locked bridge does **not** score the same 2024 cohort as the
107,319-contract hybrid replay. Do not aggregate their denominators or
compare their squared errors without separate normalization.

## Phase 1.5 stop/go recommendations

- **Gate A / source integrity:** Completed for the archival research
  joins, unit tests and SHA receipts. **Live Phase 0R certification
  remains separate and unresolved by these tests**.
- **Gate B / directional behavior:** **Failed reliability hypothesis**.
  Evidence of severe Under concentration and side-specific bias is
  sufficient to trigger targeted correction research, not Tier promotion.
- **Gate C / opportunity decomposition:** **Measured for QB attempts
  only** via source-locked archive. Allocation/participation is the
  preferred first NFL challenger. Receiver role, RB workload and
  defensive snap opportunity remain unmeasured in the four-factor
  interface; add genuine archived pregame components before attribution.
- **Gate D / sportsbook edge:** **Not evaluated**. No authenticated
  historic real two-sided market line/payout cohorts in this experiment.
  Prospective collection remains critical.
- **Gate E / complexity investment:** Defer expensive generic NFL
  joint simulators and full-history NUTS. First run a small candidate
  *starting-QB/eligibility and role-allocation* correction with locked
  chronological matched comparisons. Reuse simple baselines and do not
  fit to prior holdout results while evaluating on that same holdout.

## Power computation

Exact one-sided fixed-n binomial alpha=0.05, desired power=0.80:
- 70% vs 80%: **119 independent** observations.
- 75% vs 80%: **437 independent**.
- 80% vs 85%: **365 independent**.
- 85% vs 90%: **281 independent**.
- 90% vs 95%: **179 independent**.

These numbers **exclude** cluster correlation, sequential peeking,
multiple Tier tests, adaptively selected legs and changing regimes.
Approximate design-effect sensitivity is available in the JSON receipt.
No Tier is certified.

## Next change, not part of this PR

The next predictive experiment should separately model starting-QB
availability, active participation and allocation from the finite
team passing pool, with a fallback to a simple single-QB prior.
Prespecify the model and selection rule before a genuinely future
cohort. Do not patch the original 2024 predictions or promote a new
ranking weight using these exposed results.
