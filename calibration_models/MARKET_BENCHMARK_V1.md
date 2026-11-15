# WS5 eleven-market source benchmark expansion

Governing authority: PA-V25-MASTER-2026-11-09 / v1.1. Phase 0R / Phase 1 source-reference infrastructure. Implemented and tested; shadow-only. This extends the existing WS5 branch and C2 price-reference semantics, without changing existing frozen C-family outputs. No downstream forecasts, outcomes, source collectors, production settings, training, or schedules are used or changed.

## Source and scope

The eleven approved canonical IDs are explicitly enumerated in `market_benchmark.py`. Standalone solo tackles, assisted tackles, sacks, passes defended, touchdowns, interceptions and field goals are excluded. Combined tackles require independent combined-credit certification. Combined yardage and receiving targets require their own original quoted contracts; neither component sums nor receptions create offers.

Consume WS1 PR #133's v2.5.1 pin, SHA-256 `c3ec93c78fcae413f66afe431f817f4d986f0fd1e884c665caefc5c7a3ed230c`, and expanded manifest `1977685e911b2a9650afde55f5eb7b580d7f8fdc931bf39fad47b1c344c2a46b`. Verify the original November 15 manifest `5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71` and every original source file. Check expanded original_record values against the unchanged original manifest. Metadata catalog and crosswalk have separately pinned exact byte hashes. All bulk input remains in Deepnote, not reconstructed locally.

The source freeze `2026-11-15T16:17:30.185351Z` is an **as-of research audit cutoff**, not a claim that a new forecast was emitted then. Results are generated later. Each consumer must rerun with its actual forecast cutoff and current source evidence; this ledger cannot be used as a newly emitted pregame forecast. Quotes received after the requested cutoff, games started by that cutoff, and receipts older than the prespecified 24-hour ceiling cannot form a benchmark. Later closing evidence must remain separately timestamped. The original provider reported time is unverified and retained separately from the defensible receipt time.

## Probability and comparability contract

For positive American odds A, raw implied weight is 100/(A+100); for negative A it is -A/(100-A). Booleans, missing, infinite and invalid odds are unavailable. Raw weights are quoted-price arithmetic and may sum above one; they are not unconditional statistical forecasts or certified fair probabilities.

`multiplicative-american-v1` removes the margin as w_over/(w_over+w_under), with the corresponding Under ratio. A benchmark requires both genuine prices, certified identity, supported statistical settlement, period evidence and valid chronology. Unverified product settlement terms or missing provider period remain explicit blockers; this expansion does not upgrade the old C2 ledger's research assumptions into certified terms. Raw price conversions remain inspectable even for blocked contracts, and **de-vigged probabilities are null for those rows**. Missing prices never become 0.5.

Every numeric benchmark is conditional on nonpush. `push_probability` and `unconditional` remain null even on integer lines. Quoted binary odds cannot identify P(Push). A future source-backed settlement vocabulary must be explicitly versioned; currently only `FULL_GAME_OFFICIAL_STAT_OVERTIME_INCLUDED_V1` is supported, with separately certified combined-tackle accounting when relevant. No existing WS1 record is retro-certified into this vocabulary.

Direct consensus is an equal-book arithmetic mean of valid same-line conditional probabilities. Keys include player, event, canonical statistic, period, exact line, settlement definition and exact source receipt time. Different thresholds or acquisition windows stay separate. A single book is labeled SINGLE_BOOK_REFERENCE; two or more distinct valid books are DIRECT_SAME_LINE_CONSENSUS. Duplicate quote IDs are withheld; repeated book observations cannot increase weight. No interpolation, fitted implied distribution, cross-line mapping, learned weights, or downstream-model agreement enters this version.

## Immutable tables and WS6 handoff

The linked content-addressed JSONL tables are:

- `market_availability`: one row for each WS1 player_stat_id, including independent statistical readiness, original quote IDs/count, all observed availability states, and null market_probability rather than an arbitrary cross-line player-stat probability.
- `original_quote_benchmarks`: one row per WS1 original quote, including exact original_record, provider metadata/label/description, raw prices, raw implied weights, conditional benchmark or null, original timestamps and hashes, all rejection reasons, and consensus_id.
- `same_line_coverage`: one row per original same-line/timing/settlement group, including individual book and quote IDs, accepted quote IDs, book count, explicit unavailable or single-book status, and conditional probability or null.

Availability states distinguish source-certified offers, uncertified identity/terms, one-sided prices, no offer, unsupported settlement, rejected/stale sources and observation after kickoff. Multiple quote states may apply to a player-stat. `source_certified` is preserved independently from benchmark eligibility. Quotes without an eligible WS1 player-stat crosswalk remain in the quote table and per-line table, with null player_stat_id and an explicit reason. They are not silently joined by name.

An immutable `LEDGER_<sha256>.json` binds all three table paths, exact byte hashes, row counts, input hashes, implementation hash, cutoff, per-market coverage, source receipt time/hash and overlapping rejection-reason counts. Files use exclusive creation; conflicting bytes cannot replace a ledger or table. WS6 joins availability to quotes by player_stat_id and quote_id, then quotes to line groups by consensus_id; it must verify all hashes before consumption. Null probabilities are mandatory abstentions. Rollback: stop consuming this separate version; preserve every existing source and benchmark ledger.

## Validation

`python -m unittest discover -s calibration_models -t . -q`: 47 tests pass, including 16 expansion tests. Exact rational expectations cover odds conversion and margin removal. Adversarial fixtures cover all eleven IDs, exclusions, pushes, differing lines, duplicates, identity/period/settlement conflicts, incomplete prices, hashes, chronology, false composite reconstruction, missing offers and immutability. Fixtures are synthetic engineering checks, not source coverage.

`audit_market_benchmark.py` separately recomputes rational raw price conversions and verifies output hashes, row accounting, joins, threshold isolation and null probability requirements on actual source outputs. Automated audit is not independent human/scientific approval. No profitability, market edge, Tier, or production promotion is claimed.

## Executed source audit and WS6 receipt

Successful live Basic CPU run `3300732b-b1aa-411e-9595-acca13b6a4b7` completed 2026-11-15T16:40:57.240Z. No shared machine restart, stop or reconfiguration occurred. The initial detached failure and rate/trial-limit request failures remain visible in the execution history. The missing kickoff defect was fixed before the successful run.

New immutable ledger SHA-256: `7b584f9190861f4b799c0fe1af725e7d0b0a07617e8d10a42ba8456c48dca2ca`. Its exact-byte copy and `WS6_MARKET_HANDOFF_V1.json` are included here; bulk output tables remain in Deepnote under `calibration_models/market_benchmarks_v1/`. The receipt pins all three exact byte hashes. A separate rational arithmetic and accounting audit passed **15,913 assertions**. Original quote receipt: `2026-11-15T04:32:39.016077Z`, raw source SHA-256 `6993a07ebce5001a55729ff556765bff388bc91cb5235416af9cd26401ede14a`.

| Market | Original quotes | Player-stat rows without contract | Original line groups | Eligible numerical benchmarks |
|---|---:|---:|---:|---:|
| pass_attempts | 69 | 1 | 38 | 0 |
| pass_completions | 67 | 1 | 36 | 0 |
| passing_yards | 96 | 1 | 74 | 0 |
| rush_attempts | 98 | 221 | 54 | 0 |
| rushing_yards | 249 | 196 | 143 | 0 |
| receiving_targets | 0 | 511 | 0 | 0 |
| receptions | 568 | 360 | 171 | 0 |
| receiving_yards | 584 | 360 | 356 | 0 |
| tackles_assists | 114 | 804 | 110 | 0 |
| rushing_receiving_yards | 0 | 511 | 0 | 0 |
| passing_rushing_yards | 0 | 24 | 0 | 0 |
| Total | 1845 | 2990 | 982 | 0 |

All 1,845 original quote records contain convertible price pairs; raw implied weights were verified independently with Fraction arithmetic. **Zero benchmark probabilities are eligible.** All 1,845 have uncertified settlement terms and null raw provider period. 1,767 preserve source_certified=true from WS1; 78 retain original source rejection and invalid chronology. Source certification does not certify the new benchmark.

Critically, **1,599 WS1 quote-to-metadata links do not reproduce the original player/line/price pair**. For example, first original quote `c17463d28c3e364ec125afb405341180d68e5a631ce913b3bcf234818e7ac159` is Amon-Ra St. Brown receiving yards 82.5, but the supplied metadata crosswalk points to Rhamondre Stevenson receiving-yard milestones. That linked provider description is preserved as unverified *claimed* metadata, not a certified label for the original quote. This is a source metadata join failure, not evidence that the preserved original quote was fabricated. WS5 neither repairs WS1 records nor substitutes another offer. WS1 must issue a corrected immutable crosswalk before these links can be accepted.

Other overlapping blockers: 114 combined-tackle accounting failures, 92 absent eligible player-stat crosswalks, and 126 quotes for a game already started at the research cutoff. Mutually exclusive primary quote states: 1,626 SOURCE_REJECTED_OR_STALE, 209 ORIGINAL_OFFER_UNCERTIFIED, 10 UNSUPPORTED_SETTLEMENT_DEFINITION. None of these states is silently counted as certified numerical coverage. No claim of stale quotes specifically is made from the aggregate state name; detailed reason arrays are authoritative.
