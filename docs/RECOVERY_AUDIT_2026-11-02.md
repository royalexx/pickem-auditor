# November 2 recovery: audit and integration checklist

This document records changes on **draft PR #55**, not a production deployment.
The previous six Work agents' uncommitted workspace could not be recovered.
Source reference: main commit `d1ce75d4bd3fe25bad1abdb5e9621610c6976316`.

## Verified by source inspection and targeted numerical reproduction

- Corrected `bayesian_engine._betacf`: the second continued-fraction factor
  was multiplied twice. New shadow version `history-bayes-v2-cdf-fixed`.
  An independent reproduction matched SciPy's Student-t CDF with maximum
  absolute error approximately `8.91e-15` on df .5–100 / x -50–50.
  **This was not a full repository test run.**
- `bayesian_usage` now uses a normalized truncated Student-t log-workload
  predictive law with explicit bounds by collector unit and a new
  `usage-bayes-v2-bounded-exposure` version. The corresponding MC sampler
  uses rejection sampling from the same truncated law. Historic v1 sidecars
  remain readable, but mixed-version holdout cohorts cannot certify new models.
- The generic NFL yardage Student-t shadow output is discretized into integer
  yards with whole-line push mass. The frozen count-model version remains
  unchanged; only the revised yardage forecast has a new model version.
- Bayesian diagnostics flatten each xarray variable independently, check
  local effects, bulk/tail ESS, R-hat, divergences, BFMI and depth evidence.
  PyMC backends using `tree_depth` are supported with a documented
  default-max-depth-10 fallback; non-default samplers need separate review.
- Market estimates are normalized and anchored to a matched two-way quote.
  The reference edge is not monetary EV, and large positive gaps require
  research rather than automatic publication or automatic rejection.
- Direct ranking, verification and the final board require high-conviction
  tier floors; 56–58% internal screens do not authorize approved Tier 1–3.
  This is a policy change that requires prospective selection replay.
- Calendared model calibration fits now generate review-only proposals.
  Canonical event/player IDs and postgame settlement timestamps are required;
  one player-game-stat contributes at most one observation. Legacy calibration
  certificates fail the revised cohort-version contract.
- Frozen NHL saves forecasts and settlement sidecars have durable load/save
  paths with immutable checks. The source snapshot history transition rejects
  changed or missing forecasts and changed settled outcomes. No historical
  forecast was modified on this PR.
- Reports include same-cohort timestamp-verified model/market Brier/log loss
  and explicitly count excluded rows.

## Not yet validated (merge-blocking)

1. **Full offline suite on an actual checkout.** GitHub Actions allowance was
   exhausted; prior CI jobs failed before test steps. `[skip ci]` was used on
   follow-up commits. Do not report test success based on code inspection.
2. **Clean-runner round trip:** source snapshot → frozen shadow → persist →
   fresh clone → restore → postgame settle → immutable sidecar → evaluation.
3. **Replay of historical selections:** compare old/new market anchoring and
   tier-policy changes on a fixed, pregame-only quote cohort; quantify coverage
   and false exclusions.
4. **Four-chain numerical fit review:** check all stochastic effects and
   posterior-predictive calibration by sport/stat. Synthetic smoke is not
   convergence certification. No training jobs were launched.
5. **Production release controls:** confirm versioned registration and rollback
   for calibration and model binaries; no candidate certificate is activated.
6. **Research branches:** selectively review #48, #49, #50 and #53 before
   merging training workflows into main. No blind branch merge.
7. **Further research:** read-feature ablation, goalie/new-player support,
   count dispersion sensitivity, distinct offered-market coverage and
   multiple-selection/ROI evaluation remain open scientific tasks.
8. **Corrected outcomes:** existing frozen settlements cannot be silently
   revised; an append-only official correction event format and explicit
   as-of evaluation policy are still needed.

## No-GitHub-minutes local validation

From a fresh branch checkout with required Python dependencies installed:

```bash
python -m compileall -q scripts tests
bash -n scripts/shadow_store.sh
bash -n scripts/history_warehouse_store.sh
python -m unittest discover -s tests -p 'test_nov2_*.py' -v
python -m unittest discover -s tests -v
```

Keep the PR draft and do not restart expensive GitHub workflows or promote
Tier 1/2 recommendations until those results are reviewed. The old Odds API
fallback remains disabled in the daily workflow; missing market quotes are
reported as missing, not invented.
