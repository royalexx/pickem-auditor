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
- [x] **Item 6b — position-specific synthetic lines implemented, validated and frozen before holdout.** New `position_training_median_v1` mode derives role-specific half-integer tackle thresholds from only pre-holdout player-game medians (not model Brier or heldout stats), requires independent sample support and abstains on unsupported safety sources. True recorded positions are not mislabeled as verified on-field alignments; holdout roles are chosen from pregame history. In 2025 retrospective research over 4,163 defender-games/59 dates, challenger Brier .220775 vs .224458 simple control; log loss .631440 vs .643497. A later, **non-independent nested** cutoff with more training history supported a 4.5 safety benchmark and gave similar aggregate results on 3,183 defender-games, but did not improve OLB/off-ball-LB performance. **OLB is worse** and off-ball LB has no Brier advantage; high-predicted-snap-share LB subgroup (n=144) has no established improvement. Full report: `docs/REFORM_STEP6_POSITION_SPECIFIC_LINES.md`. No change to sportsbook lines or real rankings.
- [x] **Item 6 source audit — confirmed full tackles + assists, not solo-only.** `population_nfl.normalize_season` calculates `def_tackles_solo + def_tackles_with_assist + def_tackle_assists` and excludes a row if any component is missing/invalid; Step 6 consumes that normalized market. Added full-path regression demonstrating 4 solo + 2 with-assist + 1 assist = 7 combined tackles through the Step 6 normalization (not 4), with missing assist excluded. See `docs/REFORM_STEP9_GAME_LEG_DEPENDENCE.md`.
- [ ] **Item 6 — actual market/production promotion study.** Freeze real pregame tackle lines with immutable snap/availability evidence, evaluate same-contract challenger vs existing 60/40 consensus and market on separate future dates, validate full-time linebackers and uncertainty before allowing ranking changes.
- [x] **Item 7 — uncertainty-proxy ranking shadow implemented and original ranking reproduced.** Fixed λ scenarios subtract at most λ×half the inter-model probability range from the original market-edge priority component, without changing eligibility, other ranking weights, forecasts, or production. Reproduced 160 original eligible candidates / all 30 top-10 placements; λ=1 retained NBA 7/10, NFL 9/10, NHL 8/10. Original Engine B `relative_se` is missing on all 160 eligible records; disagreement is explicitly labeled as a **proxy, not a predictive standard error**. Shuffled-proxy negative control included. See `docs/REFORM_STEP7_8_SHADOW_20261108.md`.
- [ ] **Item 7 — independent prospective validation.** Compare original and shadow top-k rankings on many later, completely graded slates with authentic uncertainty receipts, matched market/stat bands, game/date clusters and negative controls before any production promotion.
- [x] **Item 8 — market-inclusive blending eligibility and logit scenario completed.** Tested fixed, unfitted 50/50 logit-market combination read-only against 50 coherent matched Nov 8 NFL contracts: Brier consensus .267215, logit scenario .260017, market alone .256062; log loss .726957, .713014, .705404. Market remained best. M2/M3 fitting **correctly blocked**: only one production date / 190 complete M3 contracts, legacy 3-day retrospective source lacking coherent original market pairs, missing original source receipts. No fitted weights, no change to 60/40 production. See `docs/REFORM_STEP7_8_SHADOW_20261108.md`.
- [ ] **Item 8 — prospective M2/M3 fitting/evidence gate.** Gather at least 300 original pregame verified matched training contracts over ≥20 dates plus 100 later out-of-fold matches over ≥20 dates, evaluate both proper scores vs frozen market and 60/40, ensure source bytes are authenticated and do not pool earlier research policies.
- [x] **Item 9 — same-game leg dependence diagnostic implemented and run.** Reconciles frozen original probabilities, official outcomes and source game identity; excludes invalid side pairs and repeated same-player/stat lines, compares same-game relationships, and adds cross-game negative control and date-block intervals. Nov 8 market: 220 coherent legs, 4,038 nominal pairs, **only six independent games on one date**; observed both-hit 32.31% vs naive independent 28.72%, but mean residual product -0.00169 and **no valid uncertainty interval**. Historical Engine A: 17,519 nominal pairs from 27 games on just three dates, not pooled. All joint probabilities/entry expected returns blocked. See `docs/REFORM_STEP9_GAME_LEG_DEPENDENCE.md`.
- [ ] **Item 9 — calibrated game-dependent joint probability for entries.** Requires many separately settled prospective game dates, source-matched actual bookmaker lines and conditional opportunities, validation against independence/market and game/date-cluster intervals; current historical archive is insufficient.
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

### Change 6b — frozen position-specific line controls (shadow-only)

To address the unrepresentative fixed-5.5 all-position benchmark, the
2025 walk-forward now supports frozen role-median half-integer lines,
selected using **only** the information available before the holdout.
Results: 4,163 role-scored player-games over 59 dates; overall challenger
Brier .220775 versus simple rate-control .224458 and log loss .631440
versus .643497. OLB and off-ball LB do **not** show improved Brier
with those lines; safety was excluded for source sparsity. Full-time
off-ball LB (predicted ≥75% snaps, n=144) remained unproven.
The original universal 5.5 test is still available for replication, and
the program produces only research evidence, not real market prices.
See `docs/REFORM_STEP6_POSITION_SPECIFIC_LINES.md`.

### Changes 7 and 8 — shadow ranking and market blend

Step 7 added a fixed disagreement-proxy penalty to the original
market-edge *priority* component without modifying prediction probabilities
or eligibility, tested λ=0/.5/1/1.5 and a within-sport shuffled
negative control. For λ=1 original top-10 overlap is NBA 7, NFL 9,
NHL 8. All 160 original candidates remain eligible; 0/160 have actual
archived Engine B `relative_se`. No winner's-curse adjustment is
empirically approved from the two originally graded selected 1 PM picks.

Step 8 added a **fixed, unfitted** same-contract 50/50 logit-market
research scenario. On 50 coherent Nov 8 NFL contracts the scenario
Brier .260017 is between original consensus .267215 and market
.256062; market alone wins, and only six independent games are
available. Date- and provenance-aware M2/M3 fitting correctly abstains
(190 complete Nov8 M3 inputs on one date; three incompatible older
research days). Neither shadow is production eligible.
Detailed archive reproduction is documented in
`docs/REFORM_STEP7_8_SHADOW_20261108.md`.

### Change 9 — same-game leg dependence and tackles+assists verification

Source-level Step 6 check confirms `solo + with_assist + assists` is
used for the NFL credited combined-tackle market. A new end-to-end
regression test protects against solo-only substitution and missing
assistance components.

`reform_step9_game_leg_dependence.py` runs read-only on the pinned
Nov 8 official settlement and separate Nov 5–7 historical research.
The Nov 8 market-side analysis has 220 eligible legs and 4,038 pairs
but only six independent games and one date, therefore **no reliable
joint-hit probability or correlations**. Historical Engine A has
17,519 paired observations spread over 27 pair-bearing games but
only three dates. Correlated pairs are not treated as independent
samples; dates are block-resampled only when enough information is
available. Exact marginal Fréchet bounds are reported instead of
assuming independence. No entry optimizer or production output
was changed.

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
