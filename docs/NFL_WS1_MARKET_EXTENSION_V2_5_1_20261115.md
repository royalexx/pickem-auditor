# WS1 V2.5.1 eleven-market immutable extension — November 15, 2026

Status: implemented, tested, source-linked, shadow-only; combined-tackle certification blocked by data. Governing authority: PA-V25-MASTER-2026-11-09 / v1.1. This is Phase 0R source infrastructure, not model promotion. Production forecasting and betting-selection policy are unchanged.

## Executed evidence

Deepnote project `9cc31536-93be-44db-bdeb-06fba3f61410`, notebook `5f9ddef849a745f6a21e7672977ccfa8`, successful run `b541bdbf-bc38-493b-8cbd-6367c10ed3d0` completed 2026-11-15T16:17:58Z on Basic CPU. Feature freeze: 2026-11-15T16:17:30.185351Z (11:17:30 America/Toronto).

3,570 canonical player-stat rows; 1,850 model-input-ready conditional research rows; 1,845 authentic inherited original sportsbook contracts; zero newly collected sportsbook contracts and zero new sportsbook requests. The eight documented provider live request keys remain unchanged. Targets and combined yardage have ORIGINAL_CONTRACT_UNAVAILABLE status unless a future authentic source independently supplies an offer.

52 tests passed (9 extension + 43 original source tests), plus 158,821 separate data audit assertions. This is an automated accounting audit, not independent human or external scientific review. Audit SHA: `38aabd19546ee7b8131ffe6c1f311d0b8444210b7ef68e37eb884f99a3d3f92c`.

## Explicit taxonomy migration

The legacy display labels remain unchanged in frozen original records. Only the new wrapper and player-stat dataset use the canonical v2.5.1 IDs. Inbound provider-key mappings in the pin do not authorize undocumented live requests.

| Legacy/research label | Canonical identifier |
|---|---|
| completions | `pass_completions` |
| pass attempts | `pass_attempts` |
| passing + rushing yards | `passing_rushing_yards` |
| passing yards | `passing_yards` |
| receiving yards | `receiving_yards` |
| receptions | `receptions` |
| rush attempts | `rush_attempts` |
| rushing + receiving yards | `rushing_receiving_yards` |
| rushing yards | `rushing_yards` |
| tackles + assists | `tackles_assists` |
| targets | `receiving_targets` |

Historical source fields: attempts, completions, passing_yards, carries, rushing_yards, targets, receptions and receiving_yards. Composite statistics sum signed observed components in one player-game-period record. Missing fields never become observed zero. Combined tackles are withheld pending independent provider-credit accounting; no solo, assisted, sack, interception or other defensive market is exposed.

## Measured coverage

Ready means enough observed source-linked recent history, resolved identity, allowed position/usage, pregame freeze, and source-backed QB1 where required. It does not mean a model has produced a forecast, confirmed participation, or verified sportsbook settlement terms.

| Market | Stat rows | Ready | Original contracts | Stat rows without contract | Missing features | Not ready (all reasons) |
|---|---:|---:|---:|---:|---:|---:|
| pass_attempts | 24 | 19 | 69 | 1 | 3 | 5 |
| pass_completions | 24 | 19 | 67 | 1 | 3 | 5 |
| passing_yards | 24 | 19 | 96 | 1 | 3 | 5 |
| rush_attempts | 261 | 217 | 98 | 221 | 6 | 44 |
| rushing_yards | 261 | 217 | 249 | 196 | 6 | 44 |
| receiving_targets | 511 | 335 | 0 | 511 | 101 | 176 |
| receptions | 511 | 335 | 568 | 360 | 101 | 176 |
| receiving_yards | 511 | 335 | 584 | 360 | 101 | 176 |
| tackles_assists | 908 | 0 | 114 | 804 | 908 | 908 |
| rushing_receiving_yards | 511 | 335 | 0 | 511 | 101 | 176 |
| passing_rushing_yards | 24 | 19 | 0 | 24 | 3 | 5 |
| TOTAL | 3570 | 1850 | 1845 | 2990 | 1336 | 1720 |

Missing-feature count means fewer than two usable recent observations; all 908 defensive rows are included because their combined accounting is not certified. Missing-contract counts are canonical statistic rows, not invented absent offers. Contract counts include preserved rejected/unresolved originals and are not limited to ready rows. 92 original contracts lack an eligible canonical crosswalk and remain preserved. All 1,845 contracts link to exact raw provider market metadata; zero raw market metadata links are unresolved.

185 historical rows with missing/invalid GSIS namespace were excluded and retained in a source-linked rejection ledger. 20,068 last-ten player-stat historical observations preserve same-game signed component alignment. 7,057 defender histories retain internal tackle components, with combined_total null.

## Frozen lineage and new fingerprints

Original canonical source manifest remains byte-identical: `5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71`.
Original feature pin remains byte-identical: `35a1bf7fe16acca1e115c7be7bcad2c2464ec27cdf7e799df4f2b31adba24c2a`.

New expanded source/coverage manifest: `reports/nfl_20261115_prospective/market_extension_v2_5_1/EXPANDED_MANIFEST_1977685e911b2a9650afde55f5eb7b580d7f8fdc931bf39fad47b1c344c2a46b.json`, SHA `1977685e911b2a9650afde55f5eb7b580d7f8fdc931bf39fad47b1c344c2a46b`.
New feature pin: `reports/nfl_20261115_prospective/market_extension_v2_5_1/FEATURE_PIN.json`, SHA `c3ec93c78fcae413f66afe431f817f4d986f0fd1e884c665caefc5c7a3ed230c`.
Implementation SHA: `dc6e69776f5f5b1c0ed2bb2fd65dd850956b426edf5f48702f710b7df2b80bd1`.

| Dataset | Rows | Exact byte SHA-256 | Deepnote project-relative path |
|---|---:|---|---|
| crosswalk | 1845 | `c928cb1c0292ac192423f4a729800496784475dcc3344a173d41be6919f4fab2` | `reports/nfl_20261115_prospective/market_extension_v2_5_1/crosswalk_c928cb1c0292ac192423f4a729800496784475dcc3344a173d41be6919f4fab2.jsonl` |
| historical_identity_rejections | 185 | `8e741a99d2ee79ff453b4e701efdffc14d6d0df80d78a5a01db2ca07ec5d03ae` | `reports/nfl_20261115_prospective/market_extension_v2_5_1/historical_identity_rejections_8e741a99d2ee79ff453b4e701efdffc14d6d0df80d78a5a01db2ca07ec5d03ae.jsonl` |
| internal_tackle_evidence | 7057 | `b518e5c8fade986e8a0390eba7da3afa401a434c7ae365d63af3db91b1146b7d` | `reports/nfl_20261115_prospective/market_extension_v2_5_1/internal_tackle_evidence_b518e5c8fade986e8a0390eba7da3afa401a434c7ae365d63af3db91b1146b7d.jsonl` |
| original_contracts | 1845 | `002312b480ac5cbc281c275d52c9c63e230c7c6c06abb94b03fa714c90810403` | `reports/nfl_20261115_prospective/market_extension_v2_5_1/original_contracts_002312b480ac5cbc281c275d52c9c63e230c7c6c06abb94b03fa714c90810403.jsonl` |
| paired_history | 20068 | `4ff38b3ea3b404aaed5e1e511ca18ecf85f8a2fc5e280636bba6683a9e999210` | `reports/nfl_20261115_prospective/market_extension_v2_5_1/paired_history_4ff38b3ea3b404aaed5e1e511ca18ecf85f8a2fc5e280636bba6683a9e999210.jsonl` |
| player_stats | 3570 | `d3319f57c221badec04bee2d2385b4100b60c6ad8d9d604e70580ab45e7056aa` | `reports/nfl_20261115_prospective/market_extension_v2_5_1/player_stats_d3319f57c221badec04bee2d2385b4100b60c6ad8d9d604e70580ab45e7056aa.jsonl` |
| quote_metadata_crosswalk | 1845 | `71d661422fdc122da398fb713242ba450022f659ab004eeb2268ac6abddd653c` | `reports/nfl_20261115_prospective/market_extension_v2_5_1/quote_metadata_crosswalk_71d661422fdc122da398fb713242ba450022f659ab004eeb2268ac6abddd653c.jsonl` |
| raw_market_catalog | 3296 | `a6dc1df790946d166339694087fd47d6b2d9e695e1cdaa6a0b4c846ca96a4650` | `reports/nfl_20261115_prospective/market_extension_v2_5_1/raw_market_catalog_a6dc1df790946d166339694087fd47d6b2d9e695e1cdaa6a0b4c846ca96a4650.jsonl` |

Bulk raw sources and JSONL datasets reside in the shared Deepnote project. GitHub carries code, credential-free immutable pin/manifest references, the audit copy and handoff descriptors; it does not carry the full source receipts or bulk JSONL copies. A missing local table must be read from that project, not regenerated or assumed present on GitHub.

## Fresh public-source collection

The existing WS1 fetch_public helper acquired four sources in the separate extension receipt namespace. Their observed retrieval times are truthful new observations, including identical-content re-observations. HTTP Last-Modified headers are not publication proof. Original archived 2016–25 acquisition remains November 11, 2026, not reconstructed pregame availability.

| Source | Raw rows | Actual receipt UTC | Raw byte SHA-256 |
|---|---:|---|---|
| games2026 | 7548 | 2026-11-15T16:16:09.167154Z | `ffb6d7379af1f8f5ec3bcb3b73c09509e2710c21fcb4389a02e5e11d9090903a` |
| players | 24869 | 2026-11-15T16:16:06.187629Z | `f82e52fd3d9b0976ad3756dc5ea32a4dbc10650d0a5fed993f9218a850fa944a` |
| snaps2026 | 12785 | 2026-11-15T16:16:10.135200Z | `ba54197d9e1e9a5473153f984f4880e736020c9e20565d1df246bf1e62714866` |
| stats2026 | 9534 | 2026-11-15T16:16:08.127226Z | `a7f51400624ae41f38db1395122115ff653231789ed0a840a3a7fae9e3bc977a` |

All target-day and future game outcomes are excluded from features. Current schedule scores, final game scripts and weather are not model inputs. The fresh players crosswalk supplies identity only, not future personnel usage.

## WS2–WS6 handoff

All consumers use the same fixed feature pin SHA above and their immutable descriptor:

- `reports/nfl_20261115_prospective/market_extension_v2_5_1/handoffs/WS2.json`
- `reports/nfl_20261115_prospective/market_extension_v2_5_1/handoffs/WS3.json`
- `reports/nfl_20261115_prospective/market_extension_v2_5_1/handoffs/WS4.json`
- `reports/nfl_20261115_prospective/market_extension_v2_5_1/handoffs/WS5.json`
- `reports/nfl_20261115_prospective/market_extension_v2_5_1/handoffs/WS6.json`

Dataset A key: `game_id + player_id + normalized_market + period`, with ESPN game namespace and `gsis:00-XXXXXXX` player namespace. Dataset B contains each exact original quote under original_record plus canonical market and player_stat_id. Crosswalk joins by candidate_id/quote_id. Read paired_history by player_stat_id; book and offered line are not required for a statistic forecast. Read original_record for exact book, thresholds, prices, provider quote identity and original timing. Raw catalog/crosswalk from the audit preserve original provider event/market IDs, labels and outcome nodes, explicitly retaining null metadata where absent.

Consumers must verify pin and table byte hashes; select model_input_ready; keep every abstention; recheck actual forecast_at before scheduled kickoff; stamp genuine model-training cutoff/artifact and forecast time. NE–DET is excluded from new pregame forecasts. QB1 means expected starter, not confirmed game-day active. All ready rows are conditional on appearance.

## Remaining limits and bounded next action

- Combined tackle-credit semantics are not independently reconciled. All 114 authentic original tackles_assists contracts remain intact, but zero defensive stat rows are certified ready.
- Raw 2026 defensive snaps are captured; player/game defensive snaps, snap shares, defensive roles and opponent opportunity history are not authenticated joins. Models requiring them must abstain.
- Final inactives, participation probabilities and book-specific payout/void terms remain unavailable.
- The fresh roster/depth source used here is the preserved pregame capture; it is not a fresh lineup confirmation. Historical usage does not make a backup QB eligible.
- Targets and both composite-yardage markets have no authentic original offer in this capture. Their independent features do not imply a book listed them.
- Historical archive receipts support this 2026 prospective freeze, not historical point-in-time backtest certification.
- No predictive distributions, training, NUTS jobs, weights, ranking or betting policy were changed. Phase 0R release certification remains open.

Next bounded source ticket: acquire independent official tackle-credit accounting and reconcile same-game combined totals; authenticate defensive snap identity/game joins before enabling defender model inputs. New offers require a separately timestamped capture through the existing sole collector.

## Reproduce / rollback

Run from the repository root: `python scripts/nfl_sunday_capture.py --expand-markets --code-sha <actual-commit>`. The same source helper is reused; a lease rejects concurrent writers. Completed reruns verify and reuse immutable tables. For independent accounting: `python scripts/nfl_sunday_market_extension_audit.py`.

Rollback is to stop consuming the new descriptors/pin and use the previous exact pin. Preserve both immutable evidence universes; no production rollback is needed.

Automatic approval review rejected GitHub mirroring of full receipt-bearing pin/manifest files because resolved release download URLs contain signed JWT/SAS access parameters. The exact frozen files remain in Deepnote; GitHub publishes FEATURE_PIN_REFERENCE.json with exact hashes and paths instead. No receipt or pin was rewritten to remove metadata.
