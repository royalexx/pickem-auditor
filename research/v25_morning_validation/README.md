# V2.5 NFL WS6 and NBA Phase 8C morning research audit

This is an **additive, non-production** validation stage for the already scheduled
Deepnote notebook `932674d66d4543c6b10ff2e2c0a4df9c`. It runs only in
`RUN_PHASE == "morning"`, **after** the pre-existing morning blocks. The
6:00 a.m. Eastern schedule and the production settlement pipeline are preserved.

## Frozen research sources

1. NFL: original connected Deepnote ledger at
   `/work/reports/nfl_20261115_ws6_real_comparison/canonical_s2_c2_j1_j2_original_forecast_comparison_v1/comparison_ledger_1845.jsonl`,
   SHA-256 `242c4404a6b1505844528ee7096f86060f459df6517f0420f618deef8888fbba`.
   The old draft PR #135 is **not** a production release. This source has
   1,845 original contract observations, 1,672 S2 forecasts, 1,767 C2 market
   nonpush references, 58 J1 and 58 J2 distributions, and 49 exact four-way
   original-quote intersections. Only originally timestamped model quantities
   are evaluated; the ledger is never recalculated or overwritten.

2. NBA: original locked `FIRST_CAPTURE.json` and frozen per-game
   `game_day_ledger.json` from the ten slots in
   `/work/reports/nba_phase7_pilot/`; the original slot registry and SHA
   remain unchanged. If no first capture exists, report
   `NO_GENUINE_PREGAME_CAPTURE`. When FINAL is established, perform a
   separate independent source outcome retrieval and call the Phase 7
   `settle_original` pure function. No eligibility or positive appearance
   probabilities are fabricated. Phase 8C's evening collector is separate.

## Outcome semantics

For NFL, ESPN NFL summary is fetched only after event start and only scored
when header IDs, kickoff, teams and `STATUS_FINAL` agree with the original
ledger. ESPN category-specific player stats can independently support passing
attempts, completions, passing yards, rushing attempts/yards, receptions and
receiving yards. An unlisted player/category is **unknown**, not a zero or
confirmed DNP. ESPN defensive `TOT` is not accepted as a certified original
`tackles + assists` contract without independent stat parity validation.

Models S2, J1, J2 are **conditional on appearance**, never an unconditional
pick win probability; C2 is a no-vig market reference **conditional on
nonpush**, not a three-way player distribution. Where the matching original
contract and observed player statistic are available, compute binary Brier,
log loss and exact discrete CRPS for models supplying a frozen PMF, with push
excluded from conditional binary scores. Paired results use identical
outcomes/contracts. Bookmaker quotes share the underlying player-stat result,
so the resulting contract rows are dependent and do not justify naive IID
confidence intervals or edge claims. Provisional ESPN outcomes are not
independent official stat-provider reconciliation or product-specific
payout/void settlement certification. No production promotion.

For NBA, preserve all ten pre-registered original slots. Report per-slot
original candidates, confirmed FINAL appearances, explicit ESPN DNP
classification, missing/unlisted outcome counts, missed actual participants,
accepted F forecast count, and immutable ledger identity/source receipts. J2
remains blocked until real pregame eligibility, participation probabilities
and original unconditional forecast artifacts exist. No synthetic scores.

## Outputs and idempotency

`/work/reports/v25_morning_research_validation/YYYY-MM-DD/`

- `start.json`: true execution timestamp, reference date
- `nfl_sources/*.json.gz`, `nba_sources/*.json.gz`: separate postgame
  ESPN outcome raw bytes, source hashes
- `nfl_contract_audit.json`: all 1,845 contract rows with scored/abstained
  states, model-specific metrics, no original input overwrites
- `nba_participation_audit.json`: all ten registered slots and denominators
- `manifest.json`, `final.json`: append-only research publication

A second invocation on the same morning returns the pre-existing final
receipt and never overwrites either research or production files. A partial
first invocation is explicitly blocked for forensic review. No new schedule,
paid compute, GitHub Actions, heavy NUTS training or production changes.

## Tests

`python -B -m unittest discover -s tests/v25_morning_validation -v`

Tests explicitly cover exact CRPS, sum-to-one, original eligibility,
nonpush/push semantics, game FINAL, original SHA, no missing-as-zero,
tackle-stat parity quarantine, duplicate-file preservation and nonexistent
NBA frozen-ledger abstentions. The integration is a distinct Deepnote code
block, so its failure is separately reported rather than silently marking a
production settlement as a research success.
