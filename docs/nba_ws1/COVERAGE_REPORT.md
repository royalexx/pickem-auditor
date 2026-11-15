# NBA WS1 historical coverage and missingness audit

Date: November 15, 2026, America/Toronto. Governing plan: `PA-V25-MASTER-2026-11-09 / v1.1`. This report is a verified archive inventory and bounded source audit, **not full data certification**.

## Verified inputs and actual state

* Main and clean checkout at startup: `912bc7010058092ea735dcda0aa941429194474b`; main was checked again before publication and was unchanged.
* Authoritative population branch: `data/bayesian-history`, SHA `97a8bb566826afe5a3e5a7b8c632043d8a1dca24`, dated November 1. Source files were extracted to an ignored scratch copy; the archive branch was never modified.
* NBA archive cursor: **2023-10-24**, 1,849 checkpointed dates, 5,836 source-game counts. Recent cursor: **2026-11-01**, 1,127 checkpointed dates, 3,789 source-game counts. Streams overlap October 1–23, 2023; their dates are not disjoint independent observations. Shared shard natural keys prevent duplicate insertion.
* Recent population is **not current**: November 1–14 are uncollected cursor dates. The latest row date is October 31. A bounded ESPN November 14 scoreboard probe returned five final games; the missing tail is not merely an offseason gap. Separate daily usage archives and November 10 benchmark evidence exist, but do not fill the warehouse automatically.
* The old HTTP truncation repair is present on main: `population_backfill.fetch_json` catches `HTTPException`, including `IncompleteRead`, retries full responses and fails before a date checkpoint when exhausted. Both retry regression tests passed. The old stream has progressed past its 2018 interruption to October 2023. The archive/recent union spans the intended years, but the archive-only cursor was not advanced across the entire recent stream.
* GitHub workflow cron is commented/paused in the checked main tree; the training pause marker remains true. Deepnote MCP project inventory returned 460 notebooks, 10,766 files, one integration and no notebooks flagged scheduled. Schedule configuration itself is not exposed through this MCP; do not treat its flags as a complete external scheduler audit. No schedule, pause marker or training job was changed.
* Deepnote read-only run found **no local `data/bayesian_warehouse`** in its project mount. Its historical evidence is mainly archived run/source/usage packets. The Git data branch, not an inferred Deepnote warehouse, supplied this full shard audit.

## Row-level season coverage

ESPN labels seasons by ending year. Counts below are from every NBA shard, not partition-name inference. The 11 categories have identical player-game row counts within each season: points, rebounds, assists, threes, steals, blocks, turnovers, PRA, PR, PA and RA.

| Season | Observed row dates | Stored games | Quarantined games | Remaining games | All category rows | Remaining rows |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2018–19 | 2018-10-16 to 2019-04-10 | 1,232 | 2 | 1,230 | 286,891 | 286,385 |
| 2019–20 | 2019-10-22 to 2020-08-14 | 1,061 | 2 | 1,059 | 245,971 | 245,487 |
| 2020–21 | 2020-12-22 to 2021-05-16 | 1,081 | 1 | 1,080 | 252,901 | 252,659 |
| 2021–22 | 2021-10-19 to 2022-04-10 | 1,231 | 1 | 1,230 | 285,758 | 285,505 |
| 2022–23 | 2022-10-18 to 2023-04-09 | 1,231 | 1 | 1,230 | 284,251 | 283,998 |
| 2023–24 | 2023-10-24 to 2024-04-14 | 1,232 | 2 | 1,230 | 289,663 | 289,113 |
| 2024–25 | 2024-10-22 to 2025-04-13 | 1,234 | 4 | 1,230 | 289,025 | 288,266 |
| 2025–26 | 2025-10-21 to 2026-04-12 | 1,235 | 5 | 1,230 | 292,831 | 291,940 |
| 2026–27 | 2026-10-20 to 2026-10-31 | 88 | 0 | 88 | 21,813 | 21,813 |

**Totals:** 99 compressed shards, 2,249,104 rows, 204,464 unique player-games and 9,625 game IDs. No structural validation failures, duplicate player/game/stat keys, cross-stat team/date/minutes collisions, or combo/component arithmetic discrepancies were found. Every game had two observed teams and at least ten observed players. These checks do not establish complete game rosters, source truth, or identity correctness across providers. Source byte hashes are recorded per shard; the manifest content hash is `1cea946b2ea00ecc2ac302b2fb5a5821984be61bd6ef7cd6575e23ff98fd3f9e`.

## Material contamination and remaining completeness limits

**18 games / 3,938 rows are quarantined without altering stored data.** Fifteen games involve exhibition team codes such as WORLD, USA, LEB, GIA, DUR, EAST/WEST and the later STARS/STRIPES format. Three are NBA Cup championship games: ESPN `401607495`, `401734908`, `401809839`. These finals do not count toward regular-season records. Their retrieved summaries identify championship articles and are preserved under `source_audit/`, with raw hashes. All eighteen still passed the old `season.type == 2` gate. The quarantine is in `coverage.json`; the legacy WS1 adapter now requires explicit approved game scopes and rejects exhibition franchises.

After quarantine, the completed-season counts are 1,230; 1,059; 1,080; then five seasons of 1,230. These agree with familiar season totals, including the pandemic-shortened seasons, but **count agreement does not prove game-ID completeness**. A bounded attempt to obtain an all-season ESPN range scoreboard returned HTTP 400. No complete independent league schedule denominator was retrieved, so missing/replaced IDs, original postponement dates and all official corrections remain incompletely independently reconciled. Do not label all older seasons certified from these totals.

The 2026 All-Star format also produced two different event IDs for STARS versus STRIPES on the same date. This is a real exhibition-format warning, not proof of a duplicated regular-season game. Both remain quarantined. There were 2,292 observed changes in a player’s successive team labels, including exhibition participation; these are **not 2,292 independently verified trades**. The audit found no cross-stat collisions, but future cross-provider identity and transaction reconciliation need dated mapping evidence.

## What the existing sources actually contain

`scripts/population_normalizers.py` uses ESPN completed-game summaries and daily scoreboards. It preserves stable ESPN player IDs, original per-game team/opponent abbreviations, actual positive minutes and 11 category values with canonicalized source hashes. Its postponement/cancellation gate explicitly excludes unplayed events rather than inventing zeros. Its date checkpoint occurs after all required source games normalize. Those safeguards and their tests are preserved.

The v1 population schema has no original capture/publication/availability clock, no raw-byte archive path and no provider-independent ID mapping. It is a **retrospectively retrieved population**, not proof those values were available at an old pregame freeze. A canonicalized source digest cannot independently recover original response bytes. Existing source-owned immutable writes reject changed corrections with `IMMUTABLE_POPULATION_SOURCE_CONFLICT`; they do not version official corrections. WS1 adds explicit revision/supersession handling without rewriting that warehouse.

The old normalizer requires positive minutes and accepts at most 65 minutes. Consequently all observed zero-minute appearances, DNP rows and some potential long-overtime workloads are absent or ambiguous. Zero **stat** values are retained; zero **minutes** are not. Absence is not inactivity. The new ESPN WS1 adapter preserves DNP/unknown/played-zero distinctions and long historical OT minutes, but cannot recover omitted old observations without new source evidence.

`scripts/fetch_slate.py` already retrieves ESPN current/prior player gamelogs, ESPN counting stats and optional official NBA `LeagueDashTeamStats` advanced pace. The official NBA pace client is a season aggregate, with no historical as-of date filter in that call; replaying it now is not evidence of its old pregame value. No new official-pace request was made and no independently frozen historical team-possession series was found. Authentic existing pregame receipts, when present, remain usable under their original clocks. No second collector was created.

## Missingness and provenance boundaries

* Legacy warehouse: missing FGA/FGM/FTA/FTM/three-point attempts, offensive/defensive rebound splits, foul counts, starting flags, DNPs, zero-minute appearances, exact starts/venues, original roster/eligibility, injury/rotation reports, team possessions/pace, usage percentage, touches, lineup stints and original quotes. It contains 11 market outcomes but not all box-score components needed for an opportunity simulator.
* Existing gamelog/source packets may add some fields, but were not silently promoted to a complete warehouse. Current raw boxscore adapters expose attempts, splits, starts and explicit team totals when the source supplies them. No unavailable field is synthesized.
* Historical team abbreviations and numeric team IDs stay in separate namespaces. Trades retain original row membership. A current roster never backfills an old game’s team.
* Same-source hashes are not independent NBA-versus-ESPN stat corroboration. Full official correction reconciliation, raw original publication clocks, game-active lists and cross-provider identity certification remain open.
* Original compatible prop quotes, game spread/total quotation clocks and payout terms were not available in the new sample. ESPN summary odds were deliberately not promoted into original sportsbook contracts without their quotation evidence. All 11 existing NBA market categories are schema-supported; this is not an assertion of 11-category offer coverage.

## Actual pregame package and regression benchmark

The real upcoming event was **Lakers at Suns**, ESPN `401909986`, November 15 at **4:00 p.m. America/Toronto**. Ten retained responses supplied 36 season roster members, reported injuries, four recent game boxscores and explicit team totals. Input freeze: **2:02:12.757146 p.m.**; final feature-package serialization: **2:09:58.797255 p.m.**. Both precede the scheduled start. The sample contains 55 historical player-game rows associated with current roster members, plus retained source observations for their opponents; it does not pretend to have twenty recent games for each player.

The sample content hash is `a0532e8c6f26ea47102a9a6867f7c030c9914a79999d6124481066d779a4cf13`. Offline replay verifies all retained source bytes and rebuilds exactly the same serialized package. Status: **blocked / shadow-only evidence** because eligibility is not game-confirmed and original contracts are absent. Retrospective historical retrieval is explicitly flagged. Historical possessions and pace remain null. The sample training cutoff is an explicit consumer upper bound, not a claim a model was trained.

The original November 10 benchmark was reproduced with the existing evaluator in Deepnote read-only run `c4ca630e-64d3-47e5-bed4-cc00ac333f93`, twice with byte-identical outputs: 712 original sides, 1,314 prepared attempts, NBA 250 / NHL 106 retained contracts; 160 Over, 194 Under, two unresolved NHL settlements. Output byte hash: `b438345979353e9c421c440c9bd39f0202994a3e94925a5416b904279b0c617d`. Exact original input and report hashes are in `benchmark_replay.json`. The first failed attempt used the parent settlement directory; the corrected invocation uses the existing `official_source_raw` directory. No source or evaluator was changed.

## Validation and status

25 dedicated WS1 tests passed, including actual raw-source replay, same-game player/team leakage, future and same-day history, late source clocks, changed/rehashed feature vectors, identity and roster collisions, trades, postponed games, played-zero versus DNP, stale and duplicate quotes, supersession, post-freeze corrections, immutable writes and deterministic serialization. Existing regression suites: 24 population tests (21 passed, three optional numerical tests skipped), 11 Phase 1 evaluator tests passed, 13 official-capture tests passed. The three skips require ArviZ/PyMC and concern numerical model diagnostics, not this source store; no training was launched. Pytest was absent, so these unittest suites were used.

Implemented and tested: isolated source package, immutable interface, scope rejection, source/temporal checks, sample capture/replay and coverage/quarantine ledger. Verified by executed checks: source hashes, shard counts/components, pinned Git state and original evaluator replay in a separate runtime. **Independent reviewer approval was not performed.** Sequential self-audit and a separate runtime are not independent code certification. Full regular-season source certification, missing recent history, game-active eligibility, original availability clocks, actual model manifests and complete market/payout evidence remain blocked-by-data or review.

All original data, forecast archives, legacy engines, weights/ranking, evaluator, NUTS pause and schedules are unchanged. Rollback and per-workstream instructions are in `HANDOFF.md`; serialization semantics are in `INTERFACE.md`.
