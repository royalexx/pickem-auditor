# Sunday WS2 real forecast execution

Authority: PA-V25-MASTER-2026-11-09 / v1.1 and explicit WS2 execution instruction. Research-only prospective marginal pilot. Original mathematical library, frozen parameters, production 60/40 and NUTS artifacts are unchanged.

## Actual pre-kickoff freeze

Deepnote run `4f039061-5d96-4e97-b36b-e8065dbef9f3` created 1,635 S2 forecasts at **2026-11-15 14:29:18.370098 UTC**, completing at 14:29:25.109 UTC, before the earliest 14:30 kickoff. All 1,845 original contracts were retained. S2 abstained on 210; all other versions abstained because legitimate role peers or original controls were unavailable.

These are 1,635 original book/stat/line contracts, not independent players or games. S2 counts: receptions 518, receiving yards 533, rushing yards 210, rush attempts 85, passing yards 78, pass attempts 55, completions 54, tackles + assists 102. Window counts: 14:30 UTC 126; 18:00 956; 21:05 255; 21:25 144; 01:20 next UTC day (Sunday Toronto) 154.

First numerical contract: Amon-Ra St. Brown / BetMGM / receiving yards 82.5, original quote ID `c17463d28c3e364ec125afb405341180d68e5a631ce913b3bcf234818e7ac159`. Eight historical appearances; Over 0.43714456036542126, Under 0.5628554396345787, Push 0; mean 82.62960554168716, variance 1655.0783227372945. This is an observed-support empirical benchmark, not extrapolated tails, verified availability, a pick, or an accuracy/edge claim.

WS1's first feature-store run failed on a source-rejected row's absent kickoff. WS2 therefore used a read-only adapter of **already captured WS1** players/stats/schedule CSV bytes, with exact ESPN–GSIS IDs and name corroboration. No sportsbook or historical source was collected by WS2. That run has its own actual WS2 feature freeze (14:29:15.089813 UTC), explicitly **no WS1 feature pin**, and source receipts proving history availability by 14:26:51.670585 UTC. It does not pretend to be a WS1-generated pin. Nonzero official statistics in another recorded category can prove an appearance; all-zero rows without joined snaps remain unknown and are excluded. DNP/unknown never become zeros.

## Canonical WS1 feature-pin execution

WS1 subsequently froze its canonical feature pin at 14:29:58.659490 UTC, SHA-256 `35a1bf7fe16acca1e115c7be7bcad2c2464ec27cdf7e799df4f2b31adba24c2a`. Run `a047666e-c881-45cb-bb9a-8717edae2b75` consumed it and created 1,546 S2 forecasts at **14:32:41.529073 UTC** for remaining games. It abstained for the already-started game. The earlier 126 genuine pre-kickoff forecasts for that game remain untouched.

The native adapter reads `original_contracts` and `player_history_last10_by_contract`, checks table hashes and exact book/player/event/stat/line/source identities, and applies the original S2 law. Native v1 does not supply source-bound historical role peers, so S1/S3/S4/S5 remain explicit abstentions. S6 and both S7 intensities require exact originally frozen production controls; none were supplied.

The first-forecast Sunday index selects each contract's earliest actual prediction while retaining every later version and original abstention. Assembly time is separately labeled and never substitutes for forecast creation time.

## Artifacts and reproduction

Complete populations live in the supplied Deepnote project under `reports/nfl_20261115_prospective/simple_models/live/` (each run has immutable `INDEX.json` and `forecast_rows.json`). `EARLY_REAL_EXECUTION_RECEIPT.json` binds the first numerical index and output hashes without copying temporary signed download URLs. The complete cross-version population is written separately under `simple_models/sunday_first_forecasts_v1/` by `scripts/nfl_ws2_ledger_audit.py`.

```
python scripts/nfl_ws2_live.py --source-root /datasets/_deepnote_work/reports/nfl_20261115_prospective --out-root /datasets/_deepnote_work/reports/nfl_20261115_prospective/simple_models/live
```

The canonical source manifest SHA-256 must be `5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71`. Every invocation creates an exclusive directory and writes its index last. Original dictionaries, source hashes, quote time semantics, history cutoff, feature freeze, creation time, code hashes, model parameters and output hashes are retained. A late invocation abstains for started games; later unstarted windows can still execute. For pinned code archives without `.git`, pass the verified archive SHA using `--code-commit`.

`--ws1-archived-only-fallback` is an explicit read-only fallback if the WS1 feature pin is absent. It verifies already archived CSV hashes and joins completed pre-today games; it never fetches data or manufactures a WS1 pin. The final canonical path takes precedence once present.

Validation: 61 targeted mathematical/adversarial/adapter tests passed locally, including full CLI handling of malformed rejected rows. An additional 22 discrete-contract checks passed. Deepnote numerical runs repeated the targeted tests before inference. Frozen outputs undergo an independent mass/probability/moment and timestamp audit. These checks establish engineering integrity only. No outcomes were inspected or performance claimed.

Rollback removes the standalone executors; immutable forecasts remain historical evidence. PR #132 remains draft, with no Tier, calibrator, weight, ranking or production release.
