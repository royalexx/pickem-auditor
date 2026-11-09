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
- [x] **Item 2 completed — point-in-time code enforcement.** The original Phase 1 validator now requires archived pregame source files and verifies their SHA-256 bytes, explicit publication/observation/retrieval chronology, original contract identity, and unique feature receipts across NFL/NBA/NHL. Later or absent provider inputs are rejected, never reconstructed.
- [x] **Item 2 completed — NFL live/replay safety.** `nfl_season_store.py` rejects timezone-naive cutoffs and future retrievals, distinguishes actual captured retrieval times from user-supplied `as_of`, and the live NFL opportunity projection refuses profiles without captured source provenance.
- [x] **Item 3 completed — clustered blend statistics.** `fit_blend.py` preserves earliest frozen forecasts and distinct exact lines, excludes fold predictions before 300 prior rows on at least 20 dates, resamples matched game dates, rejects duplicated/mismatched contracts and fewer than 100 OOF rows / 20 test dates, and requires positive 95% paired-block improvement for BOTH log loss and Brier vs M0 and M2.
- [x] **Item 3 completed — promotion source gate.** The market-augmented blend cannot emit weights without verified source archive bytes, explicit same-line market quote and all included engine provenance; unverified historical snapshots are research-only.
- [x] **Adversarial tests.** Expanded regression suites for hash tampering, future lineup/news/market inputs, clock drift, duplicate receipts, source path traversal, missing player-line identity, pseudo-replication and underpowered/blended results.
- [x] **Full offline CI green.** PR #67 run #42540922477 completed **1,104 tests** (nine expected skips) with no failures on the final reform code revision. The Bayesian sampling job was deliberately skipped during the training pause. The old scouting-review/NUTS test fixtures were corrected without weakening safety gates.
- [ ] **Historical evidence limitation:** The original November 8 market/lineup/injury provider bundle was incomplete. Integrity checks cannot retrospectively establish a missing original publication time or create evidence that was not archived. Collect/source-pin those payloads prospectively in item 4's validation cohort.
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

### CI and audit note

The full **offline** test suite passed **1,104 tests** (nine skipped)
on the final PR #67 revision (`27d9aba4b2c74548a5e5471c0ec79b1661ec3710`).
PR #67 was squash-merged into `main` as
`66484d1782f15a301f531a6939c189ccd8da6b78`.
The separate Bayesian NUTS smoke job is deliberately **skipped**, not passed,
while model training remains paused. CI on the merged revision is separately recorded by GitHub Actions.
No production ensemble weight, trained posterior, frozen forecast,
selection Tier or ranking algorithm was modified.

The requirements behind items 2 and 3 are implemented and tested.
They do not retroactively authenticate unavailable historical sources, nor
prove predictive skill. Item 4 must still assemble an adequate prospective
matched archive and publish aggregate performance.


## Important operational note

The GitHub workflow guard only applies to fresh runs using a revision
containing the marker and guard. The cancelled already-running job cannot be
retrofitted. Removing the pause marker or re-enabling model training
requires the user's explicit authorization. The routine morning settlement
is not itself Bayesian training and may continue to collect validation data.
