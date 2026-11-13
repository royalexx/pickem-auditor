# SOG shadow prospective producer — current capability and abstention receipt

**Experiment:** EXP-V25-NHL-SOG-EXPOSURE-EB-001.
**Status:** numerical/fixture implementation and fail-closed dry run only.
**Branch:** work/v25-nhl-sog-exposure-eb-shadow, stacked on #120 until approved.

## Executable modules

- v2/nhl_sog_official_history_producer.py imports ORIGINAL signed NHL
  player game-log bytes (regular-season game type 2) and a signed NHL
  gamecenter final-state witness for each historical player game. It derives
  exact SOG and MM:SS TOI, verifies game identity and hashes, and stores an
  independent, content-addressed played-game observation. The field named
  event_ended_at is explicitly an upper bound: **official final first
  observed**, NOT an invented actual final-horn timestamp. The origin
  verifier must recheck both original signed captures and each source row.
- v2/nhl_sog_prospective_runner.py uses the real current UTC process clock,
  accepts only original source-bound, same-contract MarketQuote objects,
  requires both current official team roster receipts and independently
  checked raw origin for all own/peer observations, fits the locked
  exposure-marginal Gamma-Poisson and plug-in Poisson controls, and (if all
  gates pass) writes a complete immutable model, fixed-line shadow snapshot
  and three-way probabilities. All attempts produce content-addressed
  append-only attempt records. No production pathways are invoked.
- tests/test_v25_sog_prospective_runner.py exercises actual fail-closed
  attempt code, including missing real offers and missing original quote
  archive; probability artifacts are NOT produced in such cases.

## Verified dry run

GitHub offline CI run 43445686793 executed:
- tests: 1,535 passed-or-skipped / 9 skipped / 0 failures
- live-clock attempt 2026-11-13T14:45:36.437392Z:
  ABSTAIN — ExperimentBlocked:RAW_REAL_OFFER_RECEIPT_MISSING
- event_id and contract_id unset, **no generated odds/payout/market edge**;
  production_selection_allowed=false; tier_publication_allowed=false.
- the test asserted original attempt-file SHA-256 and content address.

## Blockers preventing an authentic forecast

1. No actual pregame two-sided original offered NHL SOG quote or original
   quote source bytes were provided to the runner in this execution.
2. Signed official player game logs and per-game OFF final-state source
   receipts were not supplied in a jointly verified archive (authentic
   historical possession clocks required; no synthetic replacement).
3. Two-team official pregame roster identity/position source receipts are
   missing for an identified offered player/game.
4. Source producer depends on reviewed C03 signed collector code, which is
   currently a **separate stacked draft branch**; no integration merge yet.
5. No settled prospective contracts are eligible; no legitimate primary
   scoring or actual Brier/edge claim can be made.

Next: following source/identity signoff, freeze one authentic upcoming NHL
full-game SOG offer, its official roster and pregame historical source
captures. Run the same shadow runner **before puck drop**. Do not backdate a
fixture or call this no-source abstention a successful offer forecast.
