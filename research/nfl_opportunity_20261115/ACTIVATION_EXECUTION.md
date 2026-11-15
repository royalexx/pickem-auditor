# WS3 actual prospective activation — November 15, 2026

**Status: implemented, tested, numerically verified, shadow-only.** Genuine forecasts frozen on Deepnote Basic CPU before remaining kickoffs. No production promotion, market-edge claim, NUTS training, baseline rewrite, schedule change or PR merge.

## Actual coverage

All 1,845 original observations are retained in 9,225 model-contract rows. There are 2,711 forecasts covering 1,443 distinct original contracts, and 6,514 model-contract abstentions. All player models abstain on 402 original contracts. The adapter rejects 285 original contracts before model evaluation, including source exclusions and already-started games. Scope exclusions are separate from missing-evidence failures.

| Model | Player-contract forecasts | Contract abstentions | Team distributions |
|---|---:|---:|---:|
| O1-context-volume-v1 | 0 (team model) | 1,845 | 22 |
| O2-position-usage-v1 | 1,191 | 654 | — |
| O3-qb-mean-preserving-v1 | 236 | 1,609 | — |
| O4-defensive-components-v1 | 16 | 1,829 | — |
| O5-role-mixture-v1 | 1,268 | 577 | — |

## Per-game player-contract coverage

Each of the eleven forecast games also has two O1 team distributions. DET–NE had kicked off and receives no new forecasts. Event and original quote identifiers remain available in the JSON handoff.

| Game | ESPN event | O2 | O3 | O4 | O5 |
|---|---|---:|---:|---:|---:|
| BUF at NYJ | 401873054 | 114 | 29 | 4 | 123 |
| CAR at NO | 401873055 | 95 | 32 | 1 | 107 |
| HOU at CLE | 401873056 | 114 | 30 | 0 | 124 |
| JAX at TEN | 401873057 | 131 | 23 | 3 | 139 |
| KC at ATL | 401873058 | 92 | 25 | 2 | 100 |
| MIA at IND | 401873059 | 104 | 14 | 2 | 108 |
| MIN at GB | 401873060 | 80 | 12 | 2 | 84 |
| LAR at ARI | 401873061 | 124 | 13 | 0 | 127 |
| SEA at LV | 401873062 | 128 | 0 | 0 | 128 |
| SF at DAL | 401873063 | 90 | 31 | 1 | 102 |
| PIT at CIN | 401873064 | 119 | 27 | 1 | 126 |

## Per-market coverage

| Original market | Model | Forecasts |
|---|---|---:|
| completions | O3 | 46 |
| pass attempts | O3 | 47 |
| passing yards | O3 | 66 |
| receiving yards | O2 | 501 |
| receiving yards | O5 | 501 |
| receptions | O2 | 489 |
| receptions | O5 | 489 |
| rush attempts | O2 | 67 |
| rush attempts | O3 | 16 |
| rush attempts | O5 | 83 |
| rushing yards | O2 | 134 |
| rushing yards | O3 | 61 |
| rushing yards | O5 | 195 |
| tackles + assists | O4 | 16 |

## Real canary and clocks

Bryce Young / CAR at NO / BetMGM / passing attempts 36.5 / full game. Candidate `d5ff3a2ac803926d3ba98405a4851c3a89f6449802450edb18efba1d4f57b806`; quote `ee7f0b44a30d41f43ce1dcabb19ca3a3f9a666063e4b99ca7f51d734d73d9ea0`. ESPN player `4685720` maps to GSIS `00-0039150`; target event `401873055`, kickoff `2026-11-15T18:00:00Z`. Conditional Over/Under/Push = 0.4215087890625 / 0.5784912109375 / 0. Mean 35.302490234375; variance 58.91850942373276. Maximum binomial Monte Carlo standard error 0.005524271728019903, using 8,192 draws. These are statistical forecasts, not product-certified betting probabilities.

First actual forecast completion: `2026-11-15T15:56:07.974554Z` (10:56:07 Toronto); immutable canary receipt: `15:56:13.403192Z`. Last supplemental forecast completion: `2026-11-15T16:03:14.236233Z` (11:03:14 Toronto); immutable receipt: `16:03:22.159725Z`. Every completion and freeze precedes its target kickoff. Start clocks are separately preserved; no execution is backdated.

## Execution receipts

| Stage | Deepnote run | Result |
|---|---|---|
| Source/schema inspection | d3ac273f-4f3b-4470-949a-9245776c34b5 | Eight feature table hashes and 2024 archive verified |
| Real canary | a21090c4-c025-4a43-8c52-e9b045f9bbca | One O3 contract; two O1 team distributions |
| Initial expansion | 5dcccd0a-5685-4adc-b06a-68258a88a46b | 2,423 forecasts; 20 team distributions |
| Initial frozen-input audit | a12c1f3e-a664-4eaf-936d-fc0b0947de8f | Identical replay; six corruptions rejected; first WS6 export |
| Supplemental expansion | 373e9545-a567-43d5-8971-4644403a9419 | 2,711 forecasts; 22 team distributions; O4 and Toronto night game included |
| Final replay and handoff | 574ea33e-6068-4102-82b2-b23381f224c8 | 37 tests; eight corruptions rejected; 2,711 bit-identical replays |
| Final comparison integrity | 1b642bee-7a4d-4c54-9cb9-f023e6dd6fc9 | Separate original WS6 ledger and handoff checksum check |

Failed integration attempts are retained as Deepnote snapshots: `9f060e20-13ad-4c43-9cc6-1050f910e9b7` (wrong native archive root), `26b58360-e1dc-4316-b45c-11394ab69709` (LAR/LA namespace gate), `eda63591-f21b-46d3-90fa-004a8049022f` (current-week training gate), and `a21491a7-2208-44bc-b49b-b7f7ac0154fa` (cached pre-fix UTC validator). None produced a frozen forecast. Rate-limit and detached parallel-machine-limit refusals returned no run IDs.

## Exact fingerprints

| Artifact | SHA-256 |
|---|---|
| Original manifest | `5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71` |
| WS1 feature pin | `35a1bf7fe16acca1e115c7be7bcad2c2464ec27cdf7e799df4f2b31adba24c2a` |
| Canary report | `b15d211b3b13ae4503197622b413804f5cf58b7707ce2fc58d7e12ea6dea4ba7` |
| Initial expansion report | `067e70ec285f6492df9afdad7836cdbc3be5dc876775272864190b29f0a89ff6` |
| Final expansion report | `0ee15529f1e8ad3fcf5dc39b4d0e2a10c74d05d29f917932a9d0bdd3d6852cd3` |
| Final frozen input packet | `f63e8ae8b67cce76f3be901ea37bd773f36b4c2659e3e159d7a5f9517544fae7` |
| Earliest forecast WS6 JSONL | `752e72afa7423f560298b1eeff68623a809a522b8433a22b0726b5416befaa2e` |
| Summary original bytes | `cf1eedc2cdf87930198331f4948a4654657592c9a1ff8b422f0fa7820a93d255` |
| Final models.py | `2d7c5cb16ae8164cb9fa8fc6fa6ca768fb1a9af9cf3798eb52fafd3281befdd0` |
| Final adapter | `a3717aa7ce5eec9417e0597775f79fb7facd112bf4235e1ada7c62539c2eed9e` |

All other executed code fingerprints are in `ACTIVATION_RESULTS.json` under `source_reports`. Every authenticated source-table fingerprint is in the unchanged WS1 pin and the report’s adapter audit (82 source checks). Schema mappings and provenance semantics are in `ACTIVATION.md`.

## WS6 handoff

Deepnote project `9cc31536-93be-44db-bdeb-06fba3f61410`, path `reports/nfl_20261115_prospective/opportunity_models/activation_v1/0ee15529f1e8ad3fcf5dc39b4d0e2a10c74d05d29f917932a9d0bdd3d6852cd3/first_forecasts.jsonl`. The sibling `FIRST_FORECAST_INDEX.json` lists source runs and hashes. `report.json`, `adapter_packet.json`, `receipt.json`, `SUMMARY.json`, `NUMERICAL_AUDIT.json` and `INTEGRITY_RECEIPT.json` are create-once artifacts. Assembly selects each model-contract’s earliest actual frozen forecast, including the canary; it does not replace those forecasts with the later run. The already-frozen S2/C2/J1/J2 ledger is unchanged.

## Validation and remaining limitations

Independent arithmetic pass by the same agent: mass normalization, exact integer pushes, mean and variance reconstruction, reproducibility from frozen inputs and seeds, and zero maximum team-conservation error. Eight actual-packet corruptions were rejected: missing sacks, broken team accounting, wrong player/game namespace, future history, passed kickoff, duplicate roster identity, completions exceeding attempts and tackle components exceeding snaps. All 2,423 shared early/supplemental distributions were unchanged. This is not independent human review or evidence of predictive superiority.

Participation and starter certainty remain unmeasured. Forecasts condition on modeled players appearing and expected QB1 starting; no final inactive certification or calibrated DNP probability is claimed. O5 weights remain frozen sensitivity assumptions. Routes, pace tracking, and designed-run/scramble histories are unavailable. Defensive exposure incompatibility remains explicit: 284 pre-dedup feature-history references retain missing snaps, while 366 exact compatible references are retained; these are feature-store reference counts, not unique player-games. Of 16,603 historical contract references, 3,906 lack usable complete team accounting; 179 lack confirmed appearance evidence. Seventy same-week raw player rows are excluded by the frozen prior-week gate. No historical records were silently removed to improve model coverage.

The superseded blockers were absent team/player interchange and absent usable starter workload history. Remaining blockers are model-specific missing history, stale same-team roles, unverified/backup starters, defensive exposure incompatibility and source identity exclusions. O4 now has a genuine 16-contract subset. The UTC/Toronto validation bug is repaired. No weather estimate was required for neutral activation. Source integrity does not establish statistical calibration, market edge or production release authority.
