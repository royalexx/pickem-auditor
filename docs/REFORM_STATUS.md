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
- [x] **Item 4 — canonical read-only scorecard completed.** Matched original frozen November 8 NFL 1 PM forecasts to 253 verified official contracts (67 with production consensus); kept the separate November 5–7 retrospective backtest at 645 officially settled contracts. Rejected 1,379 historical unverified/missing contracts. See `docs/REFORM_PHASE4_RESULTS_20261108.md`.
- [x] **Item 4 — per-engine directional and calibration diagnostics.** Published one-contract-not-two-sides Brier/log loss, Over/Under direction bias, confidence-versus-hit gaps, per-market/sport/day breakdown, exact consensus–market common-contract comparisons, reliability cohorts and game/date-cluster **insufficiency** reports. Reusable code: `scripts/reform_phase4_scorecard.py`.
- [x] **Item 4a — paired NUTS numerical bug found and fixed.** The original 2026-11-08 NFL sidecar used `forecast_at` in the supposed shared-contract integration seed: 16 original noncomplementary NUTS reception pairs, all from different Over/Under Monte Carlo seeds. Updated `nuts_slate_shadow.shared_contract_seed` to exclude side-specific forecast times, retaining exact game/fixture/player/line identity, and added `slate_model_report.enforce_paired_probability_integrity` to withhold incompatible pairs from future consensus and rankings, preserving raw diagnostics. The original archived forecasts remain untouched.
- [x] **Item 4a — authentic posterior numerical acceptance.** Read the original 336 MB, four-chain NFL receptions NUTS artifact in Deepnote (no refit), and forecast the same frozen player/stat/line twice with corrected shared seed: exactly identical Over/Under/Push masses, summing to 1.000000; original paired archive summed to 0.989756. This closes the identified code/numerical defect.
- [x] **Item 4a — controlled full 16-pair actual-posterior integration.** Generated all 32 original paired NFL receptions NUTS sidecar inference calls against the authentic 336 MB trained posterior, then the complete historical-family 60/40 consensus and publication-pair numerical guard: zero invalid paired sums; tampered negative control was withheld. No NUTS training or historical archive edits. Controlled fixtures only; not a genuine new pregame game.
- [ ] **Item 4a — prospective integration acceptance.** Confirm the first fresh paired pregame NUTS sidecar/report produced by the patched code stays complementary and no invalid sidecar becomes production eligible. This requires the next frozen run, not user-provided data or training. The November 8 archive remains untouched.
- [x] **Item 5 — original top-k replay and descriptive audit.** Replayed all 2,436 frozen side rows, exactly reproduced 160 original eligible research candidates and all 30 original top-10 ranks. Only 10 eligible candidates fell in the independently settled NFL 1 PM window; 2 original selected picks won 2/2, with 4/8 unselected winning. No comparable matched stat/confidence/edge strata exist, so an optimizer's-curse hypothesis is **not yet identified**. See `docs/REFORM_4A_5_RESULTS_20261108.md`.
- [ ] **Item 5 — prospective statistical conclusion.** Require independently graded full-day top-k selections across enough games/dates and comparable eligible-unselected candidates before fitting edge shrinkage or changing rankings.
- [x] **Item 6 — NFL tackle snap-share research challenger built and tested.** Added `scripts/nfl_tackle_snap_share.py` and 18+ adversarial tests: separate opponent offensive plays × verified defender snap share × per-snap tackle conversion; source-hashed, timestamp-checked explicit teammate status; strictly prior-only context; date-clustered research backtest. Public 2025 NFL data: 6,732 valid defender-games, 835 players, 272 games. Synthetic fixed 5.5 tackle threshold, 4,200 matched holdout rows, 59 dates: Brier .09207 challenger vs .09583 simple team-play control, log loss .31748 vs .33123. High-snap-share LBs (n=40) were worse; **no production promotion**. See `docs/REFORM_STEP6_TACKLE_SNAP_SHARE_20261108.md`.
- [ ] **Item 6 — actual market/production promotion study.** Freeze real pregame tackle lines with immutable snap/availability evidence, evaluate same-contract challenger vs existing 60/40 consensus and market on separate future dates, validate full-time linebackers and uncertainty before allowing ranking changes.
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

### Change 3 — item 4 contract-level multi-slate diagnostics

Original frozen 2026-11-08 NFL 1 PM: 253 official matches, 67 production
consensus forecasts, 25 correct directions (37.3%). On 65 exactly shared
consensus/market contracts, consensus is 24/65 (36.9%) and market is 36/65
(55.4%); their Brier scores are .2658 and .2568, respectively. **Only six
independent NFL games:** no robust confidence interval or production promotion.

Earlier November 5–7 archives: 645 verified contracts from 2,024 original
records, including 348 flagged historically reliable; 297 false/missing.
Within 273 historically reliable Engine A/market matched cases, Engine A
Brier .2801 versus market .2464. Only three independent dates. Older
production is not the frozen 60/40 baseline.

No training, ranking, market adjustment or numerical probability update
was made. The audit *did not* recover missing archived pregame sources.
Detailed limitations and reproduction commands are in
`docs/REFORM_PHASE4_RESULTS_20261108.md`.

### Change 4 — source-side NUTS numerical consistency repair (4a)

The population NUTS integration is now seeded by the immutable
game/player/stat/line/fixture/run, not the per-side timestamp. All 16
inconsistent original reception pairs had different old side-specific seeds;
the new seed agrees for all 16. Maximum original consensus pair discrepancy:
0.339 percentage points. New paired numeric gate rejects incompatible NUTS
and consensus pairs prospectively without rewriting historic probabilities.
The corrected seed was exercised twice against the actual cached, converged
336 MB NFL receptions NUTS posterior (4 chains × 2,000 draws, no retraining);
both forecasts shared exact masses 0.4983248289428103 Over and
0.5016751710571896 Under, versus 0.9897555945128014 paired original
archive sum. A fresh integrated pregame batch remains the final deployment
acceptance check. No NUTS training was run.

### Change 5 — exact top-10 selection replay and bias pilot

`scripts/reform_phase5_selection_audit.py` reproduces all 30 original
full-slate top-10 research ranks from 160 eligible candidates out of 2,436
frozen forecast sides, then joins only the 1 PM independently settled NFL
contracts. Two of the original top-ten entries were in that 1 PM window:
2/2 correct, compared with 4/8 correct among equally eligible but unselected
candidates. No exact stat/confidence/market-edge matched strata or reliable
winner's-curse inference are available from so few selected outcomes.
Ranking, Tier logic and 60/40 weights are unchanged.

### Change 6 — NFL tackle snap share challenger (shadow-only)

The first full research rollout is implemented and tested with original
free 2025 NFL public data: 6,732 valid defender-game records, 272 regular-season
games, and a 4,200-observation chronological fixed-5.5 holdout across 59 dates.
The challenger improves Brier .09583 to .09207 and log loss .33123 to .31748
against a simple historical team-play control. High-snap-share linebackers
(n=40) are notably worse, and the threshold is not a real archived pick'em
quote. No production substitution or model-selection certificate is justified.
For source limitations, subgroup breakdown, CI and guarded roommate/teammate
availability see `docs/REFORM_STEP6_TACKLE_SNAP_SHARE_20261108.md`.

Step 4a also passed the controlled full-batch trained-posterior test on all
16 formerly invalid receptions contracts (32 sidecar calls) plus the paired
60/40 publication guard; first true future pregame operational confirmation
remains a separate incomplete check.

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
