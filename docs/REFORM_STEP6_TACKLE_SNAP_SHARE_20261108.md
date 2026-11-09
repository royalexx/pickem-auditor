# Reform step 6 — NFL tackles defensive snap-share shadow (2026-11-08)

**Release scope:** a research-only NFL tackles + assists challenger and source/validation tooling. It **does not replace** Engine A, Engine B, Bayesian forecasts, the trained NUTS model, production 60/40 consensus, ranking formula or Tier gating. Training remains paused.

## Model

The new `scripts/nfl_tackle_snap_share.py` separates:

\[
\mathrm{E}[T+A] = \mathrm{E}[\text{opponent offensive plays}]
\times \mathrm{E}[\text{defender on-field snap share}]
\times \mathrm{E}[\text{credited tackles per on-field snap}]
\]

Player workload is the weekly **defensive snaps** from `nflreadpy.load_snap_counts`, matched conservatively by the existing `population_nfl.py` name/team/week/game reconciliation (not by merging unrelated GSIS/PFR IDs). Opposing offense's scrimmage plays come from existing `nfl_context_data.normalize` play-by-play records. Invalid denominators and unmatched players are excluded with audit counts. Position partial-pooling, recency weighting, and the negative binomial alpha of 8 are **fixed research assumptions**, not fit to the prospective slate. An alternative adaptive share-prior mode is an **untested challenger**, not an accepted repair.

Teammate conditioning requires source-receipted, archived pregame **active/inactive** status for the exact future and historical games. The archive must contain the identical player, game, team, event time and status. The source publication/retrieval chronology and SHA-256 are verified against original bytes. A missing boxscore, snap count, status, or insufficient contrasting active/inactive games does **not** imply an inactive teammate or generate a bonus. No separate Engine B injury multiplier may be stacked without independent justification.

Future game/availability cutoff is enforced; inference never uses target-game snap count or tackles. The challenger emits `production_eligible: false`, `ranking_allowed: false` and `training_started: false`; its CLI can produce individual research scenarios and a date-blocked chronological fixed-line holdout report.

## Real free 2025 NFL data feasibility

An independent Deepnote run temporarily installed `nflreadpy` outside project storage. It retrieved 19,422 weekly NFL player-stat rows, 26,613 player-snap rows, 285 schedule rows and 48,771 play-by-play rows for 2025. The existing source normalizer retained 23,395 long-format player market records and 544 team-game records (272 completed games). The tackle challenger used **6,732** valid defender-game records for **835** distinct defender IDs across **272** games.

These are historical public free datasets, NOT captured original pregame provider archives. The `available_at=start+18 hours` rule is a documented retrospective approximation and is **not** proof that an outcome was publicly available at precisely that time.

## Chronological fixed-scenario holdout

From 2025-10-01, an unchanged 65-defensive-plays pregame scenario and a **synthetic 5.5 tackles + assists line**, first 4,200 eligible defender-games over 59 dates, using only prior available observations. For comparison, the control predicts 65 plays multiplied by a recency-weighted historical tackle rate **per team play**. Both are scored against the same actual future T+A and use the same uncalibrated fixed-count-family alpha.

| Proper score (smaller is better) | Challenger | Simple team-play-rate control |
| --- | ---: | ---: |
| Brier | **0.09207** | 0.09583 |
| Log loss | **0.31748** | 0.33123 |

Differences (challenger minus control): Brier **-0.00376**, log loss **-0.01375**. Descriptive date-clustered 95% bootstrap intervals: Brier **[-0.00536,-0.00200]**, log loss **[-0.01753,-0.00947]**. These intervals quantify sampling variability in this retrospective fixed-line experiment, not model reliability against a real pick'em bookmaker.

**Adversarial subgroup check:** `LB_all` (1,420 defender-games) improved Brier by 0.00230. `LB_high_snap_share` (estimated ≥75%, **n=40** across 20 dates) was **worse**: its Brier score declined by 0.01370 and log loss by 0.02263 versus the control. This subgroup had a 52.5% actual Over share at the artificial line, versus 44.4% forecast by the challenger, suggesting excess shrinkage toward low-snap-share positional averages. A post-hoc, evidence-adaptive shrinkage alternative has been *implemented only as a frozen research option*: it must be judged on independent seasons/dates before selection. Do not describe aggregate improvement as successful validation of full-time linebackers.

Additional caution: the fixed 5.5 tackle line yields only 12.1% Over outcomes in the all-position 4,200-sample group. Most defensive linemen and many cornerbacks are deep Unders at that threshold; high aggregate directional hit rates are therefore not evidence of an effective real-money selection strategy. This is **not** the existing production A/B/NUTS consensus nor an archived market matched cohort.

## Tests / strict blockers

The offline suite tests actual-snap × per-snap decomposition, unique PBP denominator, coherent Over/Under/Push probabilities, 18-hour historical delay, no future outcomes in history, nonconflation of snap and team play totals, exact teammate fixture/source hashes/identity, missing availability not treated as inactive, insufficient contrast abstention, and date-clustered holdout. The tested code is deliberately isolated from production ranking.

**Promotion blockers:**

1. Independently archived, immutable, pregame-available historical source extracts, especially the defensive snap-share training window and teammate status publication records.
2. A genuine rolling evaluation on **frozen real sportsbook tackle lines** with one contract per player/stat/line, same-contract market and frozen 60/40 production comparator, rather than the synthetic line and simple team-play control.
3. A separate high-snap-share linebacker evaluation, with adequate future dates and no selection of the preferred shrinkage variant using the same holdout.
4. Proof that uncertainty propagation across expected team play volume, snap participation and per-snap conversion is calibrated and does not double count existing Engine B availability adjustments.
5. Independent audit of the shadow output and authorization for a production promotion. No present result satisfies these blockers.

## 4a companion acceptance

Separately, 4a's paired NUTS seed repair was exercised against the actual previously trained NFL receptions posterior through **all 16** original noncomplementary reception contracts, using controlled future-time fixtures. The run made **32** NUTS inference calls, with **zero** NUTS or final 60/40 consensus side-pair errors and **zero** guard rejections for valid pairs. A deliberately tampered pair was correctly withheld by the final paired-probability guard. No retraining occurred.

This proves the **patched NUTS integration logic** works with the trained artifact, but a new genuine pregame batch is still required to verify production operational behavior. Do not rewrite the November 8 archive or confuse a controlled future-time fixture with an actual game forecast.
