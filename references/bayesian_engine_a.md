# Phase 1: historical Bayesian Engine A (shadow-only)

`history-bayes-v1` is a *hierarchical empirical-Bayes* alternative to the
production `history-v5` Engine A. It implements Bayesian posterior predictive
inference **conditional on peer-estimated group hyperparameters**. It is **not**
a fully Bayesian joint posterior over group parameters and player abilities,
and its probabilities are **not prospectively calibrated**. Keep the distinction
visible in reports.

## Model and grouping

- Scope: `sport | stat`, with at least five **other, distinct player IDs**
  having at least five verified, dated, earlier observations each. Currently
  position information is not consistently carried by the source-owned usage
  cache, so it is deliberately **not inferred**. There is no cross-stat pooling.
- The reference player never contributes to their own prior. Use one latest
  source snapshot per peer, with a checksum and `retrieved_at <= forecast_at`.
  Disallow future game observations, duplicate IDs, stale source metadata,
  and post-start forecasts. The subject's own log passes existing Engine A
  source verification and `usage_baseline.load` before Bayesian evaluation.
- Estimate group center from the distribution of peer per-game means. Correct
  between-player variance for within-player sampling variance; bound prior
  precision to an equivalent 2–12 games to avoid extreme overconfidence.
  These are initial conservative *regularizers*, not fitted optimal settings.
- Poisson counting stats use a Gamma peer prior on latent expected counts,
  updated exactly to Gamma posterior; the posterior predictive distribution is
  negative binomial, including any whole-line push.
- Overdispersed count stats use the same Gamma prior with the existing verified
  `var_ratio` as a fixed NB observation-dispersion parameter. Posterior over
  mean rate and subsequent win/push/loss are integrated by deterministic
  log-rate quadrature. This path does **not** estimate dispersion uncertainty.
- Normal-valued stats use Normal-inverse-Gamma player-level posterior and an
  analytic Student-t predictive distribution, integrating both mean and
  variance uncertainty. Signed NFL yards are supported. It remains a
  distributional approximation for nonnegative/count-like stat combinations.

## Operational lifecycle

After the **existing** afternoon forecast snapshot, invoke:

```bash
python scripts/bayesian_shadow.py --date 2026-10-28 \
  --snapshots data/prop_snapshots.jsonl --data-root data \
  --out data/bayesian_shadow/2026-10-28.jsonl \
  --receipt reports/bayesian_a_shadow_receipt.json
```

The shadow sidecar is separate from `prop_snapshots.jsonl`, and every row includes
forecast/market identity, posterior parameters, source fingerprint, original
Engine A comparator and explicit `publication_eligible: false`. Previous
sidecar rows are never re-estimated or rewritten; new pregame forecast identities
are appended for repeated afternoon runs. The persistent `data/shadow-calibration`
branch saves and restores sidecars with an append-only conflict check. GitHub
Actions publishes the receipt and sidecars as artifacts. Missing inputs produce
explicit `unavailable` records, not synthetic predictions.

**Nothing changes in production:** probabilities, `probability_blend.py`,
Engine B, shared context, research gates, current Tier 1/2/3 rules, existing
history, and calibration coefficients all remain unchanged. The 6 a.m. job
continues settling existing outcomes without weight modifications. This
phase uses no market quotes to estimate model parameters and incurs no new
PropLine requests.

## Validation and promotion

- Keep predictive results shadow-only until the existing snapshot settlements
  can be joined by unique date/player/stat/side/line/forecast identity.
- Use chronological (not random) out-of-sample comparisons for log loss
  including pushes, Brier score conditional on no push, probability reliability
  by sport/stat, coverage, sharpness, and ranking-threshold robustness.
- Group and calibrate only on forecasts generated with the same model version
  before game start. Never recompute historical forecasts using hindsight.
- Inspect peer sufficiency and reliability separately for NHL, NBA and NFL.
- Future work: source-verified position/subrole cohorts where possible, Bayesian
  group-hyperparameter uncertainty, robust regression and prospective scoring.
  These are not Phase 1 claims.

Offline tests: `python -m unittest discover -s tests -p test_bayesian_engine.py -v`.
