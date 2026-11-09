# Blind historical slate campaign — NFL 2025 initial pilot

**Execution:** 2026-11-09, Deepnote free CPU, detached read-only run.
**Project:** Pick'em Auditor.
**Run:** `04a39da4-8e78-446f-ae69-afefe934fda0`.
**Notebook:** `578b7aca16d84fe9a6e85af46983bf3a`.

## Objective and deliberate boundaries

Reconstruct historical slates as if viewed pregame, **without exposing
any target-slate result to the prediction process**. Do not retrain
Bayesian NUTS or alter production. The pilot tests the existing Step 6
NFL `tackles + assists` defensive snap-share challenger against its
earlier historical team-play-rate control, using training-derived,
position-specific half-tackle research lines.

The pilot **does not** reconstruct past bookmaker quotes, historical
Engine A/B/Bayesian/NUTS production forecasts, or outcomes of players
with no exact matched weekly defensive-snap/stat row. It is an
offline research validation, not proof of true pregame source
availability or profitable picks.

## Strict three-stage process

1. **Prepare:** read public 2025 NFL player stats, defensive snaps,
   schedules and PBP. Normalize via existing
   `nfl_context_data.normalize` and
   `nfl_tackle_snap_share.normalize_bundles`. For each target slate
   date, assemble prior defender history with
   `available_at < first_game_start - 2h`; derive role-specific lines
   only from prior history; select candidate defenders based on
   prior games and ≤35 days since prior appearance.
   Write *sanitized* pregame packets and a separate outcome vault.
   Packets include historical training outcome counts but **no
   current-slate tackles, snaps, outcomes or settled boxscores**.
2. **Forecast:** execute a separate Python subprocess passed **only
   the immutable packet directory and an output location**, not the
   result vault. Reverify packet SHA-256, prior availability cutoffs,
   and absence of target game IDs from the training history.
   Predict model/control Over probability for the same frozen
   research line and lock the exact forecast file SHA-256.
3. **Settle:** a separate process verifies the forecast's unchanged
   SHA-256 and the preparer's immutable vault hash before opening
   the target outcomes. Match strictly on
   `(date,game_id,team,player_id)`, compute Brier, log loss,
   directional accuracy, participation coverage and abstentions.
   Forecasted players who do not appear in the matched source
   are **not** presumed to have zero tackles or graded as losses.

Both the target slate labels and target-game snap denominators are
absent from the forecaster's packet. This is a *logical source
separation and subprocess boundary*, not proof of operating-system
sandbox isolation from a malicious forecaster.

## Original executed pilot

Source: free public NFL 2025 data.
The original normalizer admitted **272 completed regular-season
games**, **544 team-game records**, **23,395 normalized
player-market records** across the supported stat families.

Research window: starts **October 1, 2025**, scanning up to
December 16, limited to the **first 28 distinct eligible slate
dates**. Benchmarks use a fixed **65-play pregame scenario** and
role-median synthetic tackle lines. These are *not* actual betting lines.

| Quantity | Result |
| --- | ---: |
| Blind slate dates | 28 |
| Distinct officially represented games | 100 |
| Pregame predictions frozen | 2,616 |
| Exactly matched, graded defender-game outcomes | **1,837** |
| Forecasted candidates without a matching observed defender-game | 779 |
| Observed participation-matched coverage | 70.22% |
| Realized Over share in scored cohort | 40.50% |

| Proper score (lower is better) | Snap-share challenger | Original team-play control |
| --- | ---: | ---: |
| Brier | **0.223007** | 0.228671 |
| Binary log loss | **0.636449** | 0.652756 |
| Directional accuracy (higher is better) | **64.725%** | 63.800% |
| Mean forecast Over probability | 44.375% | 42.615% |

The challenger improves Brier by **0.005664** and binary log
loss by **0.016307**, and improves directional accuracy by about
**0.93 percentage points**, on the same observed participants and
same synthetic lines. **No date/game-cluster uncertainty interval
has yet been computed for this sealed-replay pilot**, so these
differences are *descriptive*, not a significance or promotion claim.

### Exact immutable receipts

- Original normalized source digest:
  `5cbe102e983915ca9967711716adc52c7d1b1f6eee3edf2d70085b9c079ad145`
- Sanitized packet manifest SHA-256:
  `cbc248caa5cf0f8f406ec717259781df73392ee847fa7331300c5670498b71f7`
- Restricted outcome vault SHA-256:
  `c73abf6f802952e84278b79c14d535a0a124e93fb6794b47f79115cc5ab73f6d`
- **Locked forecast file SHA-256 (written before settlement):**
  `a70f53bd0a8c48f802c0fededaedf720d3d44b7502d711ffa83b869897dbc8a8`
- Five adversarial regression tests verify the packet contents,
  source/result separation, forecast lock, vault integrity and
  immutable file-writing. The full GitHub offline suite passed on
  the two-source-file branch. The Bayesian NUTS smoke remains
  skipped under the user's training pause.

## Limitations and following campaigns

This is **one real historical pilot** on NFL tackles + assists,
not yet an NFL/NHL/NBA global model evaluation.

The original public nflverse historical dataset does not independently
prove the source provider's publication time for every game; the
`available_at = kickoff + 18h` field is a conservative
**retrospective approximation**, not a contemporaneous archive.
The default candidate selection is based on prior appearances and
therefore includes **779 unmatched cases**. Scoring only matched
participants introduces selection conditioning and may overstate
performance for real pregame available props.

To assess trustworthiness further, rerun the same frozen program on
other untouched years and chronological windows; report role-level
and entire-date-block uncertainty intervals; obtain true archived
bookmaker lines and provider-authenticated timestamp receipts before
comparing against actual 60/40 production/model/market probabilities.
Future NHL/NBA inference should use equivalent sealed per-slate
source packets and independent settlement.

**No NUTS training, production model changes, probability
recalibration, new approved Tiers or entry expected-value claims.**

[Deepnote pilot and recorded raw execution outputs](https://deepnote.com/workspace/stonks-a257-e2858df6-426e-479b-a4f8-0376a602f7bb/project/Pickem-Auditor-Daily-Cloud-Inference-9cc31536-93be-44db-bdeb-06fba3f61410/notebook/Historical-blind-slate-replay-NFL-2025-sealed-outcomes-pilot-578b7aca16d84fe9a6e85af46983bf3a?utm_content=9cc31536-93be-44db-bdeb-06fba3f61410).
