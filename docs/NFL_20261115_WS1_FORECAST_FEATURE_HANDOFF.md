# Pick'em Auditor — WS1 Sunday emergency feature-store execution receipt

**Research-only. Do not infer certification, betting release, or a produced model probability from feature readiness.**

- Date: November 15, 2026 (America/Toronto)
- GitHub: `royalexx/pickem-auditor`, branch `chatgpt/nfl-sunday-ws1-source-20261115`, draft PR #133.
- Adapter code commit: `e8edc2dc8d026556ce786d724a17ee724427a8dc`.
- Deepnote project: `9cc31536-93be-44db-bdeb-06fba3f61410`; notebook `c022b82e0e6048bda7f056002578720d`.
- Successful integration run: `c88ec025-4f33-42f5-a666-9926a5c8976f`.
- Successful independent follow-on execution of QA block: `3a9e28e2-ad57-4790-a5e2-034feb19cad2`.
- **Exact immutable feature pin:** `reports/nfl_20261115_prospective/source_control/feature_store/pins/35a1bf7fe16acca1e115c7be7bcad2c2464ec27cdf7e799df4f2b31adba24c2a/FORECAST_FEATURE_PIN.json`
- **Exact feature-pin SHA-256:** `35a1bf7fe16acca1e115c7be7bcad2c2464ec27cdf7e799df4f2b31adba24c2a`
- Root immutable alias: `reports/nfl_20261115_prospective/FORECAST_FEATURE_PIN.json` (same byte hash).
- Original canonical handoff: `reports/nfl_20261115_prospective/source_control/HANDOFF_PIN.json`, untouched.
- Original canonical source-manifest SHA-256: `5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71`
- Historical feature freeze: `2026-11-15T14:29:58.659490Z`; pin generated at `2026-11-15T14:30:05.331698Z`.
- NO actual WS1 predictive probability calculated; all model training cutoffs remain unset for downstream model owners.
- No production policy or NUTS change, paid compute, synthetic quote, duplicate sportsbook collector, altered original source/archive timestamp.

## Working universe and temporal gate

- 1,845 original quotes retained, 1,767 source-certified identities, 1,712 history-feature-ready, 1,686 conditional-on-appearance *permitted at feature freeze*, 159 abstentions, 0 fully certified or product/participation-certified.
- After 09:30 ET NE @ DET kickoff, **126 formerly feature-ready conditional contract rows become ineligible for any NEW pregame forecast**. Prospective working denominator on other 11 games: **1,560 conditional candidate rows**, subject to actual downstream forecast time, training cutoff, lineup and model-specific schema checks.
- The 09:29:58 ET freeze precedes the 09:30 ET kickoff, but the pin was produced at 09:30:05 ET. A downstream forecast produced at or after kickoff MUST exclude NE @ DET.
- Statuses are distinct: SOURCE_IDENTITY_CERTIFIED, PREGAME_FEATURES_AVAILABLE, CONDITIONAL_ON_APPEARANCE_FORECASTABLE, STARTER_ELIGIBLE, PRODUCT_TERMS_VERIFIED, FULLY_CERTIFIED, ABSTAIN.
- Per-game/market entries are measured at the **recorded frozen time**, not updated to represent downstream forecast eligibility after time advances.

## Aggregate per-market counts

| Event / market | Original | ID certified | Feature-ready | Conditional | Fully certified | Abstain |
|---|---:|---:|---:|---:|---:|---:|
| completions | 67 | 65 | 57 | 54 | 0 | 13 |
| pass attempts | 69 | 67 | 58 | 55 | 0 | 14 |
| passing yards | 96 | 94 | 82 | 78 | 0 | 18 |
| receiving yards | 584 | 564 | 557 | 554 | 0 | 30 |
| receptions | 568 | 549 | 542 | 539 | 0 | 29 |
| rush attempts | 98 | 91 | 90 | 88 | 0 | 10 |
| rushing yards | 249 | 233 | 222 | 216 | 0 | 33 |
| tackles + assists | 114 | 104 | 104 | 102 | 0 | 12 |

## Per-game counts

| Event / market | Original | ID certified | Feature-ready | Conditional | Fully certified | Abstain |
|---|---:|---:|---:|---:|---:|---:|
| NE @ DET | 126 | 126 | 126 | 126 | 0 | 0 |
| KC @ ATL | 134 | 134 | 134 | 132 | 0 | 2 |
| HOU @ CLE | 153 | 153 | 153 | 153 | 0 | 0 |
| MIN @ GB | 113 | 113 | 113 | 112 | 0 | 1 |
| MIA @ IND | 142 | 142 | 129 | 128 | 0 | 14 |
| CAR @ NO | 160 | 160 | 152 | 144 | 0 | 16 |
| BUF @ NYJ | 155 | 155 | 155 | 155 | 0 | 0 |
| JAX @ TEN | 162 | 162 | 162 | 162 | 0 | 0 |
| LAR @ ARI | 162 | 162 | 141 | 141 | 0 | 21 |
| SEA @ LV | 162 | 162 | 149 | 135 | 0 | 27 |
| SF @ DAL | 144 | 144 | 144 | 144 | 0 | 0 |
| PIT @ CIN | 154 | 154 | 154 | 154 | 0 | 0 |
| Unresolved event identity | 78 | 0 | 0 | 0 | 0 | 78 |

## Abstention reason counts (non-exclusive)

- `INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY`: 133
- `CROSS_TEAM_ROSTER_IDENTITY_UNVERIFIABLE`: 78
- `ESPN_GSIS_CROSSWALK_UNAVAILABLE`: 78
- `KICKOFF_PASSED_OR_BAD_CAPTURE_CLOCK`: 78
- `PLAYER_ID_UNVERIFIED`: 78
- `QB_STARTER_NOT_SOURCE_BACKED`: 16
- `DEPTH_CHART_NOT_QB1`: 14
- `QB_BACKUP_EXCLUDED`: 14
- `INDEPENDENT_NAME_ID_MISMATCH`: 12

Individual reasons overlap. Do not sum these categories to obtain 159.

## Independently checked execution properties

- Integration preflight: 8 assertions passed.
- 8 immutable table byte-SHA and row-count verifications passed.
- 20 archived historical source-file SHA checks passed; original 2016–25 historical source ingestion date retained as 2026-11-11, not reconstructed pregame.
- 4 newly acquired WS1 raw CSV files verified by raw-byte SHA and true acquisition-before-freeze timestamp.
- 1,845 exact source-identity-to-WS3-adapter contract matches passed.
- 1,686 conditional real-original-quote checks passed; 159 explicit abstentions verified.
- 16,603 retained player-history rows checked for pre-target game dates and source availability.
- 104 game-market rows sum to 1,845 original, 1,686 conditional and 159 abstentions; every fully-certified row count is zero.
- Real original-contract smoke: BetMGM Amon-Ra St. Brown receiving yards 82.5, exact ESPN player ID to GSIS ID, original quote SHA, 09:29:58 ET feature freeze before kickoff, current historical prior, conditional research-only status. A smoke PASS is not a model forecast or prediction of hit probability.
- Additional absent/naive timestamp adversarial rejects passed.
- Subsequent detailed QA verified archived history, new raw acquisitions, statuses and abstention conservation. No independent external human or independent sportsbook settlement review claimed.

## Reusable immutable tables

- **events**: `reports/nfl_20261115_prospective/source_control/feature_store/events_f8129cf073847ca5b4ec69908647d620531eb3902ca947ae09d74bcd1b6ba705.jsonl` SHA-256 `f8129cf073847ca5b4ec69908647d620531eb3902ca947ae09d74bcd1b6ba705` (12 rows)
- **historical_statistical_priors**: `reports/nfl_20261115_prospective/source_control/feature_store/historical_statistical_priors_7ccc578d146817b4360b5c42066e0c683d3f37a4e2fdb56c53eae99be330b9f5.jsonl` SHA-256 `7ccc578d146817b4360b5c42066e0c683d3f37a4e2fdb56c53eae99be330b9f5` (1712 rows)
- **original_contracts**: `reports/nfl_20261115_prospective/source_control/feature_store/original_contracts_89220d59109d4fe253334ea548bfa845e17229ce725ead2b6aa02ed86482adc4.jsonl` SHA-256 `89220d59109d4fe253334ea548bfa845e17229ce725ead2b6aa02ed86482adc4` (1845 rows)
- **per_game_market**: `reports/nfl_20261115_prospective/source_control/feature_store/per_game_market_dfa8620b83036f9000437b961a14a2a69bfe1f661eb19c922c548c07b8e54d0a.jsonl` SHA-256 `dfa8620b83036f9000437b961a14a2a69bfe1f661eb19c922c548c07b8e54d0a` (104 rows)
- **player_history_last10_by_contract**: `reports/nfl_20261115_prospective/source_control/feature_store/player_history_last10_by_contract_19f40626a6874541196ff5dde49215c5096d23af966922f974c4ece68139c428.jsonl` SHA-256 `19f40626a6874541196ff5dde49215c5096d23af966922f974c4ece68139c428` (16603 rows)
- **pregame_roster_availability**: `reports/nfl_20261115_prospective/source_control/feature_store/pregame_roster_availability_a8401eea1a59e2ff162db560661ba0e06668d22616f54b62a9bf2c0b49011d67.jsonl` SHA-256 `a8401eea1a59e2ff162db560661ba0e06668d22616f54b62a9bf2c0b49011d67` (1845 rows)
- **team_history**: `reports/nfl_20261115_prospective/source_control/feature_store/team_history_ed9d35178462fd95d4087dc1a3bd31644307cd1156fa5920dbd8dc4b969363e1.jsonl` SHA-256 `ed9d35178462fd95d4087dc1a3bd31644307cd1156fa5920dbd8dc4b969363e1` (5552 rows)
- **ws1-nfl-pregame-opportunity-v1**: `reports/nfl_20261115_prospective/source_control/feature_store/ws1-nfl-pregame-opportunity-v1_95f1f79a7c47981923099756ffb4ef57e182c8820199c93cbdc2f48085d2412f.jsonl` SHA-256 `95f1f79a7c47981923099756ffb4ef57e182c8820199c93cbdc2f48085d2412f` (1845 rows)

## New raw sources (WS1-only collection)

- **games2026**: 7548 rows; received 2026-11-15T14:26:51.670585Z; SHA-256 `acdf054288a5c500178ba2022c6e1d9f62214eaca46897412b17130cfc3fa2db`; raw path `reports/nfl_20261115_prospective/source_control/feature_source_receipts/raw/acdf054288a5c500178ba2022c6e1d9f62214eaca46897412b17130cfc3fa2db.csv`
- **players**: 24869 rows; received 2026-11-15T14:26:44.880155Z; SHA-256 `a8a86df9be83cdf88d0dadb47f09fb4a3c5db326e19b46cf20bdade38e3e024d`; raw path `reports/nfl_20261115_prospective/source_control/feature_source_receipts/raw/a8a86df9be83cdf88d0dadb47f09fb4a3c5db326e19b46cf20bdade38e3e024d.csv`
- **snaps2026**: 12785 rows; received 2026-11-15T14:26:53.696892Z; SHA-256 `ba54197d9e1e9a5473153f984f4880e736020c9e20565d1df246bf1e62714866`; raw path `reports/nfl_20261115_prospective/source_control/feature_source_receipts/raw/ba54197d9e1e9a5473153f984f4880e736020c9e20565d1df246bf1e62714866.csv`
- **stats2026**: 9534 rows; received 2026-11-15T14:26:49.153068Z; SHA-256 `a7f51400624ae41f38db1395122115ff653231789ed0a840a3a7fae9e3bc977a`; raw path `reports/nfl_20261115_prospective/source_control/feature_source_receipts/raw/a7f51400624ae41f38db1395122115ff653231789ed0a840a3a7fae9e3bc977a.csv`

## Precise blockers and access policy

1. No independently certified final inactive/participation probabilities; all 1,686 candidate distributions must be labeled conditional on actually appearing and remain research-only. QB-only markets may be explored only for source-backed pregame QB1 identities.
2. Original product-specific payout/void/DNP rules not verified; no unconditional, decision-grade or financially certified forecasts.
3. The reduced historical player-stats source contains team pass/rush attempt aggregates but not full team scrimmage plays or sacks; these fields remain null, not invented.
4. Defensive snap share history and route participation are not independently joined, even though raw 2026 snap receipts exist; WS3 variants requiring them must abstain.
5. A prior historical player-event name/ID mismatch or thin history blocks individual contracts. All 159 abstentions are explicit, with reason codes.
6. Original frozen V1 / 60–40 model forecasts and Sunday model artifact training cutoffs are not present in this WS1 package. Downstream model owners must truthfully stamp their own genuine training/model artifact and forecast times; never backdate.
7. No historical pregame first-seen verification for reconstructed 2016–2025 backtests; those records support 2026 prospective priors but do not retroactively certify old replay windows.
8. No NFL 2026-11-15 completed-game outcome, in-game snap count or final score was used in pregame features. Later settlements require separate timestamped artifacts.

## Full per-game × market reason ledger (104 rows)

| Game | Market | Original | ID | Features | Conditional | Fully | Abstain | Abstention reason counts (overlap allowed) |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Unresolved identity | completions | 2 | 0 | 0 | 0 | 0 | 2 | CROSS_TEAM_ROSTER_IDENTITY_UNVERIFIABLE:2, ESPN_GSIS_CROSSWALK_UNAVAILABLE:2, INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:2, KICKOFF_PASSED_OR_BAD_CAPTURE_CLOCK:2, PLAYER_ID_UNVERIFIED:2, QB_STARTER_NOT_SOURCE_BACKED:2 |
| Unresolved identity | pass attempts | 2 | 0 | 0 | 0 | 0 | 2 | CROSS_TEAM_ROSTER_IDENTITY_UNVERIFIABLE:2, ESPN_GSIS_CROSSWALK_UNAVAILABLE:2, INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:2, KICKOFF_PASSED_OR_BAD_CAPTURE_CLOCK:2, PLAYER_ID_UNVERIFIED:2, QB_STARTER_NOT_SOURCE_BACKED:2 |
| Unresolved identity | passing yards | 2 | 0 | 0 | 0 | 0 | 2 | CROSS_TEAM_ROSTER_IDENTITY_UNVERIFIABLE:2, ESPN_GSIS_CROSSWALK_UNAVAILABLE:2, INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:2, KICKOFF_PASSED_OR_BAD_CAPTURE_CLOCK:2, PLAYER_ID_UNVERIFIED:2, QB_STARTER_NOT_SOURCE_BACKED:2 |
| Unresolved identity | receiving yards | 20 | 0 | 0 | 0 | 0 | 20 | CROSS_TEAM_ROSTER_IDENTITY_UNVERIFIABLE:20, ESPN_GSIS_CROSSWALK_UNAVAILABLE:20, INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:20, KICKOFF_PASSED_OR_BAD_CAPTURE_CLOCK:20, PLAYER_ID_UNVERIFIED:20 |
| Unresolved identity | receptions | 19 | 0 | 0 | 0 | 0 | 19 | CROSS_TEAM_ROSTER_IDENTITY_UNVERIFIABLE:19, ESPN_GSIS_CROSSWALK_UNAVAILABLE:19, INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:19, KICKOFF_PASSED_OR_BAD_CAPTURE_CLOCK:19, PLAYER_ID_UNVERIFIED:19 |
| Unresolved identity | rush attempts | 7 | 0 | 0 | 0 | 0 | 7 | CROSS_TEAM_ROSTER_IDENTITY_UNVERIFIABLE:7, ESPN_GSIS_CROSSWALK_UNAVAILABLE:7, INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:7, KICKOFF_PASSED_OR_BAD_CAPTURE_CLOCK:7, PLAYER_ID_UNVERIFIED:7 |
| Unresolved identity | rushing yards | 16 | 0 | 0 | 0 | 0 | 16 | CROSS_TEAM_ROSTER_IDENTITY_UNVERIFIABLE:16, ESPN_GSIS_CROSSWALK_UNAVAILABLE:16, INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:16, KICKOFF_PASSED_OR_BAD_CAPTURE_CLOCK:16, PLAYER_ID_UNVERIFIED:16 |
| Unresolved identity | tackles + assists | 10 | 0 | 0 | 0 | 0 | 10 | CROSS_TEAM_ROSTER_IDENTITY_UNVERIFIABLE:10, ESPN_GSIS_CROSSWALK_UNAVAILABLE:10, INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:10, KICKOFF_PASSED_OR_BAD_CAPTURE_CLOCK:10, PLAYER_ID_UNVERIFIED:10 |
| NE @ DET | completions | 5 | 5 | 5 | 5 | 0 | 0 | — |
| NE @ DET | pass attempts | 6 | 6 | 6 | 6 | 0 | 0 | — |
| NE @ DET | passing yards | 8 | 8 | 8 | 8 | 0 | 0 | — |
| NE @ DET | receiving yards | 38 | 38 | 38 | 38 | 0 | 0 | — |
| NE @ DET | receptions | 36 | 36 | 36 | 36 | 0 | 0 | — |
| NE @ DET | rush attempts | 5 | 5 | 5 | 5 | 0 | 0 | — |
| NE @ DET | rushing yards | 17 | 17 | 17 | 17 | 0 | 0 | — |
| NE @ DET | tackles + assists | 11 | 11 | 11 | 11 | 0 | 0 | — |
| BUF @ NYJ | completions | 6 | 6 | 6 | 6 | 0 | 0 | — |
| BUF @ NYJ | pass attempts | 6 | 6 | 6 | 6 | 0 | 0 | — |
| BUF @ NYJ | passing yards | 8 | 8 | 8 | 8 | 0 | 0 | — |
| BUF @ NYJ | receiving yards | 52 | 52 | 52 | 52 | 0 | 0 | — |
| BUF @ NYJ | receptions | 51 | 51 | 51 | 51 | 0 | 0 | — |
| BUF @ NYJ | rush attempts | 5 | 5 | 5 | 5 | 0 | 0 | — |
| BUF @ NYJ | rushing yards | 15 | 15 | 15 | 15 | 0 | 0 | — |
| BUF @ NYJ | tackles + assists | 12 | 12 | 12 | 12 | 0 | 0 | — |
| CAR @ NO | completions | 6 | 6 | 6 | 6 | 0 | 0 | — |
| CAR @ NO | pass attempts | 6 | 6 | 6 | 6 | 0 | 0 | — |
| CAR @ NO | passing yards | 8 | 8 | 8 | 8 | 0 | 0 | — |
| CAR @ NO | receiving yards | 52 | 52 | 48 | 46 | 0 | 6 | INDEPENDENT_NAME_ID_MISMATCH:2, INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:4 |
| CAR @ NO | receptions | 50 | 50 | 46 | 44 | 0 | 6 | INDEPENDENT_NAME_ID_MISMATCH:2, INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:4 |
| CAR @ NO | rush attempts | 9 | 9 | 9 | 7 | 0 | 2 | INDEPENDENT_NAME_ID_MISMATCH:2 |
| CAR @ NO | rushing yards | 18 | 18 | 18 | 16 | 0 | 2 | INDEPENDENT_NAME_ID_MISMATCH:2 |
| CAR @ NO | tackles + assists | 11 | 11 | 11 | 11 | 0 | 0 | — |
| HOU @ CLE | completions | 6 | 6 | 6 | 6 | 0 | 0 | — |
| HOU @ CLE | pass attempts | 6 | 6 | 6 | 6 | 0 | 0 | — |
| HOU @ CLE | passing yards | 8 | 8 | 8 | 8 | 0 | 0 | — |
| HOU @ CLE | receiving yards | 48 | 48 | 48 | 48 | 0 | 0 | — |
| HOU @ CLE | receptions | 48 | 48 | 48 | 48 | 0 | 0 | — |
| HOU @ CLE | rush attempts | 8 | 8 | 8 | 8 | 0 | 0 | — |
| HOU @ CLE | rushing yards | 20 | 20 | 20 | 20 | 0 | 0 | — |
| HOU @ CLE | tackles + assists | 9 | 9 | 9 | 9 | 0 | 0 | — |
| JAX @ TEN | completions | 4 | 4 | 4 | 4 | 0 | 0 | — |
| JAX @ TEN | pass attempts | 4 | 4 | 4 | 4 | 0 | 0 | — |
| JAX @ TEN | passing yards | 7 | 7 | 7 | 7 | 0 | 0 | — |
| JAX @ TEN | receiving yards | 56 | 56 | 56 | 56 | 0 | 0 | — |
| JAX @ TEN | receptions | 55 | 55 | 55 | 55 | 0 | 0 | — |
| JAX @ TEN | rush attempts | 8 | 8 | 8 | 8 | 0 | 0 | — |
| JAX @ TEN | rushing yards | 20 | 20 | 20 | 20 | 0 | 0 | — |
| JAX @ TEN | tackles + assists | 8 | 8 | 8 | 8 | 0 | 0 | — |
| KC @ ATL | completions | 5 | 5 | 5 | 5 | 0 | 0 | — |
| KC @ ATL | pass attempts | 5 | 5 | 5 | 5 | 0 | 0 | — |
| KC @ ATL | passing yards | 7 | 7 | 7 | 7 | 0 | 0 | — |
| KC @ ATL | receiving yards | 44 | 44 | 44 | 43 | 0 | 1 | INDEPENDENT_NAME_ID_MISMATCH:1 |
| KC @ ATL | receptions | 43 | 43 | 43 | 42 | 0 | 1 | INDEPENDENT_NAME_ID_MISMATCH:1 |
| KC @ ATL | rush attempts | 6 | 6 | 6 | 6 | 0 | 0 | — |
| KC @ ATL | rushing yards | 16 | 16 | 16 | 16 | 0 | 0 | — |
| KC @ ATL | tackles + assists | 8 | 8 | 8 | 8 | 0 | 0 | — |
| MIA @ IND | completions | 6 | 6 | 3 | 3 | 0 | 3 | INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:3 |
| MIA @ IND | pass attempts | 6 | 6 | 3 | 3 | 0 | 3 | INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:3 |
| MIA @ IND | passing yards | 8 | 8 | 4 | 4 | 0 | 4 | INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:4 |
| MIA @ IND | receiving yards | 43 | 43 | 43 | 43 | 0 | 0 | — |
| MIA @ IND | receptions | 40 | 40 | 40 | 40 | 0 | 0 | — |
| MIA @ IND | rush attempts | 5 | 5 | 5 | 5 | 0 | 0 | — |
| MIA @ IND | rushing yards | 23 | 23 | 20 | 20 | 0 | 3 | INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:3 |
| MIA @ IND | tackles + assists | 11 | 11 | 11 | 10 | 0 | 1 | INDEPENDENT_NAME_ID_MISMATCH:1 |
| MIN @ GB | completions | 5 | 5 | 5 | 5 | 0 | 0 | — |
| MIN @ GB | pass attempts | 4 | 4 | 4 | 4 | 0 | 0 | — |
| MIN @ GB | passing yards | 8 | 8 | 8 | 8 | 0 | 0 | — |
| MIN @ GB | receiving yards | 33 | 33 | 33 | 33 | 0 | 0 | — |
| MIN @ GB | receptions | 33 | 33 | 33 | 33 | 0 | 0 | — |
| MIN @ GB | rush attempts | 4 | 4 | 4 | 4 | 0 | 0 | — |
| MIN @ GB | rushing yards | 17 | 17 | 17 | 17 | 0 | 0 | — |
| MIN @ GB | tackles + assists | 9 | 9 | 9 | 8 | 0 | 1 | INDEPENDENT_NAME_ID_MISMATCH:1 |
| LAR @ ARI | completions | 6 | 6 | 3 | 3 | 0 | 3 | INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:3 |
| LAR @ ARI | pass attempts | 6 | 6 | 3 | 3 | 0 | 3 | INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:3 |
| LAR @ ARI | passing yards | 8 | 8 | 4 | 4 | 0 | 4 | INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:4 |
| LAR @ ARI | receiving yards | 55 | 55 | 52 | 52 | 0 | 3 | INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:3 |
| LAR @ ARI | receptions | 54 | 54 | 51 | 51 | 0 | 3 | INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:3 |
| LAR @ ARI | rush attempts | 8 | 8 | 7 | 7 | 0 | 1 | INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:1 |
| LAR @ ARI | rushing yards | 21 | 21 | 17 | 17 | 0 | 4 | INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:4 |
| LAR @ ARI | tackles + assists | 4 | 4 | 4 | 4 | 0 | 0 | — |
| SEA @ LV | completions | 5 | 5 | 3 | 0 | 0 | 5 | DEPTH_CHART_NOT_QB1:3, INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:2, QB_BACKUP_EXCLUDED:3, QB_STARTER_NOT_SOURCE_BACKED:3 |
| SEA @ LV | pass attempts | 6 | 6 | 3 | 0 | 0 | 6 | DEPTH_CHART_NOT_QB1:3, INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:3, QB_BACKUP_EXCLUDED:3, QB_STARTER_NOT_SOURCE_BACKED:3 |
| SEA @ LV | passing yards | 8 | 8 | 4 | 0 | 0 | 8 | DEPTH_CHART_NOT_QB1:4, INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:4, QB_BACKUP_EXCLUDED:4, QB_STARTER_NOT_SOURCE_BACKED:4 |
| SEA @ LV | receiving yards | 52 | 52 | 52 | 52 | 0 | 0 | — |
| SEA @ LV | receptions | 50 | 50 | 50 | 50 | 0 | 0 | — |
| SEA @ LV | rush attempts | 11 | 11 | 11 | 11 | 0 | 0 | — |
| SEA @ LV | rushing yards | 23 | 23 | 19 | 15 | 0 | 8 | DEPTH_CHART_NOT_QB1:4, INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY:4, QB_BACKUP_EXCLUDED:4 |
| SEA @ LV | tackles + assists | 7 | 7 | 7 | 7 | 0 | 0 | — |
| SF @ DAL | completions | 5 | 5 | 5 | 5 | 0 | 0 | — |
| SF @ DAL | pass attempts | 6 | 6 | 6 | 6 | 0 | 0 | — |
| SF @ DAL | passing yards | 8 | 8 | 8 | 8 | 0 | 0 | — |
| SF @ DAL | receiving yards | 44 | 44 | 44 | 44 | 0 | 0 | — |
| SF @ DAL | receptions | 42 | 42 | 42 | 42 | 0 | 0 | — |
| SF @ DAL | rush attempts | 12 | 12 | 12 | 12 | 0 | 0 | — |
| SF @ DAL | rushing yards | 21 | 21 | 21 | 21 | 0 | 0 | — |
| SF @ DAL | tackles + assists | 6 | 6 | 6 | 6 | 0 | 0 | — |
| PIT @ CIN | completions | 6 | 6 | 6 | 6 | 0 | 0 | — |
| PIT @ CIN | pass attempts | 6 | 6 | 6 | 6 | 0 | 0 | — |
| PIT @ CIN | passing yards | 8 | 8 | 8 | 8 | 0 | 0 | — |
| PIT @ CIN | receiving yards | 47 | 47 | 47 | 47 | 0 | 0 | — |
| PIT @ CIN | receptions | 47 | 47 | 47 | 47 | 0 | 0 | — |
| PIT @ CIN | rush attempts | 10 | 10 | 10 | 10 | 0 | 0 | — |
| PIT @ CIN | rushing yards | 22 | 22 | 22 | 22 | 0 | 0 | — |
| PIT @ CIN | tackles + assists | 8 | 8 | 8 | 8 | 0 | 0 | — |

---

WS1 handed the exact path and SHA to WS2 PR #132, WS3 PR #134, WS4 PR #130, WS5 PR #131 and WS6 PR #135 via repository comments. Research remains independent and release disabled.
