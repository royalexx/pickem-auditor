# Phase 3 — Posterior predictive Monte Carlo (shadow-only)

**Model:** `posterior-mc-v1` (uncalibrated). This is an independent, append-only
numerical diagnostic **of** the existing Bayesian Engine A and Engine B models,
**not** a third independent evidence source or a substitute for scouting.
No scoring model, source verification, market selection, research gate,
tier threshold, calibrated blend or production ranking is changed.

## Why simulate?

Phase 1 already integrates Poisson/Normal uncertainty exactly and NB by
quadrature; adding naive samples to those predictions does **not** improve their
accuracy. Phase 2 integrates workload uncertainty using only 17 evenly spaced
Student-t quantile nodes and hence has deterministic integration bias.
Phase 3 samples posterior workload and conversion/mean uncertainty to
cross-check those approximations, expose numerical disagreement and enable
future extensions to correctly identified *correlated* game-state models.

## Generative representation

- Engine A Poisson: `lambda ~ Gamma(alpha,beta)`, with alpha/beta from
  Phase 1's posterior (beta is rate). Draw latent lambda and integrate
  `Y | lambda ~ Poisson(lambda)` tail probabilities exactly.
- Engine A Normal: draw residual variance from the inverse-Gamma posterior;
  integrate the posterior mean conditional on variance to get a Normal
  predictive with variance `sigma²(1+1/kappa)`. Whole-number lines retain
  continuity-corrected pushes.
- Engine A NB: recompute the 401-node posterior **latent rate grid from
  source-verified, original historical observations** and the stored
  empirical-Bayes prior. Sample a latent rate node and evaluate the
  conditional NB tail with the phase-1 variance ratio.
- Engine B: draw next-game positive workload from the log-workload
  posterior Student-t (not a normal approximation), then draw conversion
  rate from the posterior or integrate conversion mean conditional on
  residual variance. Count stats use Gamma–Poisson or the verified
  121-node NB posterior, reconstructed from the original dated workload/
  production pairs. Normal stats draw posterior variance, integrate beta
  and evaluate a conditional Normal predictive.
- Every Monte Carlo replication integrates **observation noise
  conditionally**, instead of adding an extra noisy game-outcome draw.
  This Rao–Blackwellization preserves the posterior predictive expectation
  while reducing numerical Monte Carlo variance.
- Over, Under and Push remain unconditional, mutually exclusive, and
  sum to one. Results never count a push as a win or infer availability
  of a player from history.

The **seed is SHA-256 of immutable pregame forecast identity, engine and model
version**; random generators do not share global state. Sample sizes adapt
from 1,024 to at most 8,192 for a target 95% numerical-integration halfwidth
of 0.008, with explicit recorded standard error, CI halfwidth and draw count.
The 95% interval is a **numerical error interval, not an uncertainty interval
around the true sporting win probability**. An analytic disagreement is
recorded; it cannot make a play eligible or change its rank.

### Source and version safeguards

The new process only evaluates already recorded pregame Phase 1/2
source-verified Bayesian sidecars, matched to the original shadow forecast's
exact forecast timestamp, event start, sport, stat, player, side, line and
run ID. Missing, unavailable or incompatible sidecars become unavailable,
not imputed probabilities. NB source reconstruction requires the original
collector reference, original pregame cutoff, verified checksums and matching
source digest. Reject a changed peer cohort or changed NB posterior. A/B
model versions remain locked at `history-bayes-v1` and `usage-bayes-v1`.

**Do not manufacture joint correlations:** A and B both reuse history and are
not two independent samples of the player outcome. Within-game multiple prop
dependence requires verified aligned event/game observations; no numerical
covariance or team game-script latent variables are inserted at this stage.
The existing context verification is independent and unchanged.

## Workflow and storage

On a successful afternoon production snapshot, existing Bayesian A and B
shadow stages execute first. Then:

```bash
python scripts/posterior_mc_shadow.py --date 2026-10-28 \
  --original data/prop_snapshots.jsonl --data-root data \
  --out data/posterior_mc/2026-10-28.jsonl \
  --receipt reports/posterior_mc_receipt.json
```

All MC forecasts are saved into `data/posterior_mc/YYYY-MM-DD.jsonl`,
restored and append-only persisted to `data/shadow-calibration`, and
included in the daily Actions artifacts and receipt. Original forecasts
and previous Monte Carlo rows are never overwritten or re-simulated.
The source-owned game caches and frozen pregame estimates remain immutable.

On the subsequent morning, **after successful settlement**, run:

```bash
python scripts/posterior_mc_audit.py \
  --original data/prop_snapshots.jsonl --mc-dir data/posterior_mc \
  --out reports/posterior_mc_audit.json
```

The audit joins only exact pregame forecast identities with verified
settled outcomes, then compares proper **three-way win/push/loss log loss
and multiclass Brier** for (a) original history/usage baseline, (b)
the parent Bayesian analytic model, and (c) the corresponding MC estimate.
Only sport/stat scopes with at least 30 matched forecasts appear
individually; an unqualified total summary is clearly descriptive.
The audit never fits a coefficient, changes A/B mixture weights, authorizes
tiers or backfills historical MC results after observing outcomes.

**Validation before production promotion:** accumulate prospective
observations per sport and stat, inspect coverage and empirical calibration,
disagreement rates and proper scores by event/date blocks, then approve any
weights or policies only through the existing held-out validation procedure.
MC precision is *not* evidence of forecast accuracy.

Offline verification:
`python -m unittest discover -s tests -p test_posterior_mc.py -q`;
GitHub CI also runs the entire prior multi-sport suite.
