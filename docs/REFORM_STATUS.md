# Pick'em Auditor — model reform status

**Started:** 2026-11-08. **Phase:** 1 — point-in-time validation and trustworthy out-of-sample comparisons.

This document is an implementation log, not evidence of improved prop accuracy.
Production continues to use the frozen 60% historical / 40% Engine B policy.
Training is deliberately paused, and existing checkpoints/posteriors are preserved.

## Release checklist

- [x] Stop self-hosted training run #42518781212; recorded GitHub conclusion: cancelled.
- [x] Disable hourly frozen-training recovery automation.
- [x] Add `.training-control/PAUSED.json` and an early GitHub Actions guard to reject successor 31-market starts.
- [x] Preserve the original 60/40 model, source manifest, and archived pregame forecasts.
- [x] **Code**: replace IID row bootstrap in `fit_blend.py` with matched date-block resampling and reject sparse chronological promotion comparisons.
- [x] **Code**: reject NFL season profiles retrieved after the historical evaluation time; block missing/naive provenance timestamps.
- [x] **Tests written**: four blend-bootstrap tests (same-day pseudo-replication, misaligned contracts, correlated slates, insufficient independent dates); two NFL retrieval-integrity tests.
- [ ] Full repository CI green; the 2026-11-08 reform-branch workflow found two failures outside the changed code, including `test_automated_scouting_review` and `test_provisional_nuts_shadow`. The separate joint-Bayesian smoke check passed.
- [ ] Expand the immutable historical timing/source audit to additional inputs, including lineups and injury features; preserve missing-retrieval evidence as unavailable.
- [ ] Compile a **single canonical** matched pregame settlement cohort across sports and dates, with original model/market quotes and non-push/push status.
- [ ] Run aggregate Brier/log loss, directional and Over/Under bias, full-universe vs selected top-k calibration, with game/date clustering.
- [ ] Build and validate NFL tackle snap-share / on-field conversion challenger, including teammate availability.
- [ ] Evaluate uncertainty-adjusted rankings vs frozen original rank, without editing the original forecasts.
- [ ] Validate M2/M3 market-inclusive blends against the frozen 60/40 and market-only baselines on adequate independent chronological folds.
- [ ] Quantify game-level leg dependence before making multi-leg expected-hit claims.
- [ ] Defer Beta calibration, hierarchical stacking, and richer simulations until prospective data and simple challengers justify them.
- [ ] Independent adversarial audit; require explicit approval for any production/Tier promotion.

## Phase 1 statistical and provenance gates

1. Use **only** frozen pregame model forecasts; never reconstruct a historical
   prediction after its outcome was known.
2. Reconcile identical sport, event, player, statistic, line, side, and pregame
   timestamps; leave unobserved or postgame data unavailable.
3. Treat pushes, voids, DNPs, and missing official outcomes separately.
4. Score the same paired contracts for all compared forecast systems.
5. For selection bias, compare selected top-k to equally eligible unselected
   contracts conditional on comparable confidence and market ranges, not
   merely their unconditional Brier-score difference.
6. Bootstrap game/day blocks (never individual correlated prop rows). The
   blend fitter requires at least 20 distinct game dates before the
   selected confidence interval may support promotion.
7. Preserve Engine A, Engine B, Bayesian A, Bayesian B, NUTS, Market and
   Consensus side by side, including coverage and model-source timestamps.
8. Do not automatically promote a model because it trained, converged, or
   won a single slate.

## Change log

### Change 1 — paired/date-block blend-validation bootstrap

File: `scripts/fit_blend.py`. Out-of-fold pairs now carry their original
contract identity and game date. Bootstrapped intervals sample *whole dates*.
Mismatched contracts and fewer than 20 independent dates return no interval.
Promotion logic fails closed when the chronological test cohort is too small.

### Change 2 — NFL source-timing guard

File: `scripts/nfl_season_store.py`. Historical profile reads check both
the source snapshot's as-of and its source retrieval timestamps against
evaluation time, rejecting future or timezone-naive retrieval metadata.

### CI note

The 2026-11-08 reform branch's full offline test job finished with 1,085
tests and two failures in unrelated modules. This is **not** a green build;
CI must be reconciled before release. The independent Bayesian smoke-test
job was successful. The six newly added reform regression tests did not
appear among the reported failures. No production blend was promoted.

## Important operational note

The GitHub workflow guard only applies to fresh runs using a revision
containing the marker and guard. The cancelled already-running job cannot be
retrofitted. Removing the pause marker or re-enabling model training
requires the user's explicit authorization. The routine morning settlement
is not itself Bayesian training and may continue to collect validation data.
