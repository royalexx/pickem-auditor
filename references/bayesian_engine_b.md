# Phase 2: Engine B Bayesian workload/conversion shadow

**Status:** `usage-bayes-v1` is an uncalibrated, empirical-Bayes challenger to
the collector-owned `scouting-v7` production model. Not authorized to rank
props or change Engine A, blending, thresholds or prospectively settled
history. It does not use the sportsbooks as model input.

## Scope and observation provenance

- One sport/stat peer cohort; no cross-stat, cross-sport or inferred-position
  pooling. Minimum five **other, distinct player IDs**, each having at least
  five positive-exposure games. Subject likewise needs five.
- Read collector-owned `usage-history-v2` observations. Every game needs a
  dated unique ID, measured workload and measured production. Source JSON
  and immutable snapshots require a valid SHA-256 checksum, a trustworthy
  retrieval timestamp <= pregame forecast time and earlier observation dates.
  Independently run `verify_a` against the collector's source history.
- Only one latest pregame source version per peer contributes. Never allow
  the subject to contribute to their own peer prior. `team`/player identity
  is matched on the subject before computation. Inference is computed using
  production and workload from the same source observation.
- Exposure of zero with production nonzero is invalid. Zero-exposure rows are
  omitted from the **positive-part** workload likelihood; they are not
  automatically modeled as player DNP/OUT or credited as Under wins. The
  player must still pass the independent status/availability research gates
  before any future publication eligibility.
- Numeric NFL week identifiers without safely resolved dates do not qualify
  for the peer model. This may reduce NFL coverage: missing evidence is
  `unavailable`, never reconstructed with an assumed game date.

## Bayesian likelihood and prior approximations

### Workload

For each player, assume `log(exposure) ~ Normal(mu, sigma²)` *conditional on
positive exposure*, with `(mu,sigma²)` receiving a Normal-inverse-Gamma
prior. Fit the prior hyperparameters from *other players'* within-player log
workload variance and between-player dispersion, with bounded effective prior
weight (2–10 games). Update analytically using the subject's historical
positive-exposure observations. The posterior predictive for log workload is
Student-t. Positive future workload is `exp(log_workload)`, with a
17-node deterministic equal-mass Student-t quantile integration.

This allows future minute/ice-time/snap workload uncertainty, not merely
a historical average. The Student-t predictive heavy-tail assumption and
equal-mass integration grid are approximations, not calibrated guarantees.

### Conversion / per-unit production

- **Poisson counts:** `Y_i | W_i, lambda ~ Poisson(W_i * lambda)`.
  Place a peer-informed Gamma prior on `lambda`, update exactly using the
  subject's paired sum of counts and sum of exposures. At each workload
  quantile, analytically integrate lambda (Gamma–Poisson/negative-binomial)
  and then numerically average across workloads.
- **Overdispersed counts:** `Y_i | W_i, lambda, r ~ NB(mean=W_i*lambda,
  var=r*W_i*lambda)` with a fixed, collector-derived dispersion ratio
  `1.10 < r <= 3`. A Gamma prior on `lambda` is updated with the
  **actual NB likelihood**, integrated by deterministic 121-node log-rate
  quadrature including the log-rate Jacobian. Predictions marginalize
  the rate posterior and workload quantiles. Sampling uncertainty in
  dispersion `r` is **not** estimated here.
- **Normal-valued stats:** conditional
  `Y_i | W_i, beta, sigma² ~ Normal(W_i * beta, sigma²)`,
  with a peer-informed Normal-inverse-Gamma prior on conversion beta
  and residual variance. Update analytically from paired game data.
  The future production distribution conditional on workload is Student-t;
  both conditional conversion and workload uncertainties are integrated
  with deterministic quantiles. Whole-number lines use continuity-corrected
  pushes. A nonnegative prop with excessive mass below zero abstains;
  signed NFL yards can be negative.
- The workload and production likelihoods factor **conditional on the
  observed workloads**. Their within-game dependence is represented by
  the regression/conditional count likelihood, not by treating the two
  historical series as independent unconditional samples.
- Hyperparameters are **empirically estimated** and held fixed. Full
  uncertainty over shared population parameters and omitted regime changes
  is not represented. Future Phase 3 can add correlated game-state simulation
  after evidence-backed model validation.

## Operational lifecycle

The 4 p.m. GitHub job first completes existing source collection and its
production `scouting-v7` shadow snapshot. The new
`scripts/bayesian_b_shadow.py` then independently reads that same pregame
snapshot and the collector-owned game-log snapshot.

It appends a sidecar to `data/bayesian_b_shadow/YYYY-MM-DD.jsonl`, persisted
through `data/shadow-calibration` and copied into GitHub Actions artifacts.
A receipt `reports/bayesian_b_shadow_receipt.json` records forecast and
abstention counts; the stage fails visibly if the sidecar is corrupt.
Existing rows cannot be recalculated, overwritten or silently deleted.
It writes `q_win`, `q_loss`, `q_push`, workload and conversion posterior
summaries, source fingerprints and the original `scouting-v7` comparator
when available. Every record is `publication_eligible=false`.

Manual offline example:

```bash
python scripts/bayesian_b_shadow.py --date 2026-10-28 \
  --snapshots data/prop_snapshots.jsonl --data-root data \
  --out data/bayesian_b_shadow/2026-10-28.jsonl \
  --receipt reports/bayesian_b_shadow_receipt.json
python -m unittest discover -s tests -p test_bayesian_usage.py -q
```

## Prospective validation and known limitations

Before changing production rankings, evaluate a settled chronological holdout
by sport and stat; compare proper win/push/loss log loss, Brier, reliability,
coverage, calibration and uncertainty against the *original pregame* B
predictions and existing A-only results. Require incremental evidence that
Bayesian B improves the out-of-sample blend.

Current source-owned game logs may lack complete NFL week-to-date resolution,
player position/subrole or high-quality exposure metrics. These are
**coverage blockers** rather than reasons to invent source dates or exposures.
An observed teammate-absence effect and game-script speculation must remain
in the separate verified shared-context layer, not Engine B's baseline.
