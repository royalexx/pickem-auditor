# WS3 full-market v2 contract and execution

Status: implemented, tested, prospectively executed and arithmetically verified; shadow-only. Final adapter v2.1 results are the current issuance; earlier issuance evidence is retained below. Governing plan: PA-V25-MASTER-2026-11-09 / v1.1. Bounded user-authorized Phase 2/3 shadow extension; no model promotion, training restart or schedules changed.

## Final adapter v2.1 issuance — verified before kickoff

Run `abfe0b90-d718-43b5-b715-d503d5a92589` succeeded, including a new genuine single-player canary, full execution, frozen-input replay and immutable WS6 index. Canary freeze: `2026-11-15T16:43:15.370933Z`; full forecast completed `16:44:15.529088Z`, frozen `16:44:23.438525Z`. Remaining kickoffs begin at 18:00 UTC. DET–NE receives explicit abstentions; no new probabilities were constructed for it.

Final neutral counts: **22 O1 team records; 1,001 O2 stat distributions; 102 O3 QB distributions; 0 O4 distributions; 1,103 O5 distributions**. Total 2,206 player-stat distributions. Weather forecasts: **0**, with `WEATHER_EFFECT_NOT_ESTIMATED`. This operationalizes ten of eleven markets; T+A remains blocked by unauthenticated credit semantics and defensive exposure. The earlier 16 v1 O4 contract forecasts remain preserved, not recertified.

| Market | O1 player | O2 | O3 | O4 | O5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| pass_attempts | 0 | 0 | 17 | 0 | 17 |
| pass_completions | 0 | 0 | 17 | 0 | 17 |
| passing_yards | 0 | 0 | 17 | 0 | 17 |
| rush_attempts | 0 | 111 | 17 | 0 | 128 |
| rushing_yards | 0 | 109 | 17 | 0 | 126 |
| receiving_targets | 0 | 231 | 0 | 0 | 231 |
| receptions | 0 | 226 | 0 | 0 | 226 |
| receiving_yards | 0 | 221 | 0 | 0 | 221 |
| tackles_assists | 0 | 0 | 0 | 0 | 0 |
| rushing_receiving_yards | 0 | 103 | 0 | 0 | 103 |
| passing_rushing_yards | 0 | 0 | 17 | 0 | 17 |

O1 has 22 distributions of each of accounting opportunities, passing attempts, rushing attempts and internal sacks, across eleven games. Seconds-per-play pace remains unestimated; shared game-volume uncertainty is modeled. O1 has zero player forecasts by design.

Eligible stat abstentions: O2 1,715; O3 42; O4 908; O5 1,757. Source-ready rows can still abstain on missing current-team history, stale role, zero historical conversion exposure or missing composite components. Unverified starters remain excluded. Full per-market counts and precise reason combinations are in [the final handoff](FULL_MARKET_V2_1_HANDOFF.json). WR/TE rushing eligibility includes genuine carry evidence and preserves a residual pool.

All 1,845 authentic original observations are retained in 9,225 model-contract evaluations: 2,854 forecasts and 6,371 abstentions. Forecasts cover 1,427 distinct original contracts; 418 receive no player forecast. O2 evaluates 1,191 forecast contracts, O3 236 and O5 1,427; O1 and O4 have zero. Targets and both composite markets have zero authentic original quotes in this source package; their statistical distributions are emitted without lines. No quotes or thresholds are synthesized.

Validation: **45 local tests pass**, 42 earlier full-suite tests passed on Deepnote, and the supplemental arithmetic pass replayed **all 2,206 distributions exactly**. It checked **240 matched composite identities**, exact probability normalization and mass/mean/variance reconstruction, **117 input/source checks**, historical cutoff, real freeze-before-kickoff and zero maximum team conservation error. Five actual-packet corruptions fail closed. The old v1 handoff rehashed unchanged. This is author-performed separate arithmetic verification, not independent human review; prospective accuracy and calibrated participation/weather effects remain unmeasured.

| Final artifact | SHA-256 |
| --- | --- |
| Full report | `2ee80d736157c32a67a8a4e3c3c4e97c1d7009b0f2d8caa46dfe3d0fcb7ac454` |
| Canary report | `9b04940a141d4b1e1e5e5e68043ac6450bca2b1c252700f2cf67bca096d41a3a` |
| Frozen input packet | `c330b7be4d17b280f4d33b115f5b3e93fb926a74c5bc3dcfe31493f810bf77cd` |
| Player-stat JSONL | `3b34dc439c5822d62c3259ff13a57725069056c4ea7c881c7a6f674b8d748d2f` |
| Original-contract JSONL | `5225c3435c7883e76a3924a982e67f36dda3bbc2bfa26307e2698fa48c66e903` |
| WS6 handoff index (original Deepnote bytes) | `a8bab73d4949a29312e6e169561318764a948931a90927065e6d0e79df036bfe` |
| Source hash index (original Deepnote bytes) | `d8706c540f80c15a927d5978d94606e6a54061c23712a2a9e9b79c2cdc7c6a72` |

Immutable Deepnote directory: `reports/nfl_20261115_prospective/opportunity_models/full_market_v2/2ee80d736157c32a67a8a4e3c3c4e97c1d7009b0f2d8caa46dfe3d0fcb7ac454/`. [Final handoff and audit](FULL_MARKET_V2_1_HANDOFF.json) and [verified source hash/clock index](FULL_MARKET_V2_1_SOURCES.json) are readable repository copies; their JSON is formatted for review, so original-byte hashes refer to Deepnote originals. Report code hashes bind the exact model/adapter sources independently of later documentation commits. Adapter v2.1 source receipt is included in the registry. Preserve every issuance; source/roster changes can change downstream allocation draws and do not amend earlier forecasts.

## Scientific contract

Hypothesis: the existing lower-information opportunity equations can produce quote-independent target/component distributions and coherent matched-component composites using authenticated WS1 histories. This is a non-statistical interface/conservation extension, not a superiority experiment. Primary acceptance criteria are source/cutoff integrity, eligible-market execution, arithmetic constraints and reproducibility. Prospective scoring must use independent subsequent settlement and game-clustered comparisons; no current outcomes are loaded. No predictive calibration, role-transition fitting, participation fitting or weather coefficient fitting is performed.

Original `models.py`, v1 adapter, old model identifiers, seeds and frozen artifacts are untouched. New identifiers end in `full-market-v2`. O1 retains its lower-information accounting volume (attempts + official rushes + sacks suffered). This is not all penalty-inclusive snaps. Shared latent volume uncertainty is propagated; pace in seconds remains unavailable. Missing sacks never imply zero. O2 retains route-free targets per attempt, position priors and a residual pool. WR/TE rushing requires positive verified same-team carry history. A removed unsupported rushing allocation flows back to the residual.

O3 retains the corrected Beta(60s,60(1-s)) starter share with expectation s. Full-game projections condition on the source-backed expected QB1 starting. Official carries include kneels and scrambles where counted by the source; designed runs and scramble decomposition remain unavailable. No backup injury/replacement workload is invented.

O4 publishes only `tackles_assists`. The new WS1 package explicitly labels the official component semantics unverified. V2 abstains rather than assume solo/with-assist/assist fields are disjoint. Compatible snap evidence alone cannot resolve credit overlap. Existing frozen v1 defensive forecasts remain historical artifacts and are not recertified.

O5 uses the unchanged frozen sensitivity weights (.2,.6,.2) and multipliers (.6,1,1.25), with within-team allocation renormalization and residual opportunity conservation. Components share the same player role draw and team environment. Role mixtures are assumptions, not learned transition probabilities. Both yardage composites are sums of matched component arrays; negative yardage is preserved. Missing either component abstains without blocking simpler components.

Participation remains a conditional scenario, not a calibrated appearance probability or confirmed-active claim. Pass yards and receiver yards are separate conditional efficiency marginals; this family does not claim a coherent team passing/receiving yard ledger or multi-leg pricing authority.

## Sources and adapter

`ws1_full_market_adapter_v2.py` invokes the original adapter first, retaining its original-source verification and complete team exposures, then authenticates the WS1 eleven-market extension and original roster/starter evidence. ESPN→GSIS identity is explicit; team alias LAR→LA is preserved. Extended player histories come from authenticated 2026 weekly rows only, joined to complete prior-week team exposures; zero-only rows do not establish appearance. Unavailable routes, designed runs, scrambles and snap observations stay missing. All WS1 stat/rejection denominators and 1,845 original contract observations remain represented.

- Original WS1 feature pin: `35a1bf7fe16acca1e115c7be7bcad2c2464ec27cdf7e799df4f2b31adba24c2a`.
- Original manifest: `5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71`.
- Eleven-market WS1 pin: `c3ec93c78fcae413f66afe431f817f4d986f0fd1e884c665caefc5c7a3ed230c`.
- Expanded manifest: `1977685e911b2a9650afde55f5eb7b580d7f8fdc931bf39fad47b1c344c2a46b`.

Exact original-source hashes, observed receipt clocks, table hashes, row counts and source exceptions are retained in each report's `adapter_audit`. Source hashes establish byte identity, not upstream publication truth. Current source receipts support this prospective freeze only, not historical as-of replay certification.

## WS6 handoff

Outputs live under Deepnote `reports/nfl_20261115_prospective/opportunity_models/full_market_v2/<report SHA>/` with exclusive-create report/receipt/input packet, `player_stat_distributions.jsonl`, `original_contract_evaluations.jsonl`, `SUMMARY.json` and a separate `ARITHMETIC_AUDIT.json`.

Stat keys are `(game_id [ESPN], player_id [GSIS without prefix], model, market, variant)` and period is full game. Quote availability never controls distribution emission. Contract keys are `(contract.contract_id [original candidate_id], model, variant)`. Every forecast contract retains its original source record, quote identifier, book and line. Exact Over/Under/Push probabilities derive from one statistical distribution, conditional on appearance/start; product DNP/settlement rules remain unverified. Missing contracts never acquire synthetic thresholds. Retain explicit abstentions in all comparisons. Keep these new model identities separate from the earlier earliest-forecast v1 handoff. Do not replace earlier v1 probabilities or frozen S2/J1/J2/C2 records.

Neutral outputs have `variant=neutral`; weather forecast count is zero. `WEATHER_EFFECT_NOT_ESTIMATED` is metadata, not an independently fitted weather forecast. No neutral execution waits for weather coefficients.

## Validation and rollback

42 local tests pass, including five new mathematical tests covering quote independence, matched composites, count constraints, missing-component isolation, defensive scope, reproducibility and cutoff/sack rejection. Fixtures are explicitly synthetic tests and never source evidence. Separate arithmetic verification reconstructs mass/mean/variance, replays actual frozen inputs, tests matched identities and corrupts real packet chronology/accounting/identities. This is a sequential audit by the same agent, not independent human review. No production release authority follows from it.

Rollback: stop invoking the new adapter; preserve all artifacts and continue using the untouched v1 research runner. No baseline, schedule, source record or production setting needs restoration.

Operational inspection at task startup: `main` remained `912bc7010058092ea735dcda0aa941429194474b`; research head was `0822c1857c2e61fa8228ad3cd0816993a2805584`, draft PR #134 open. Deepnote project machine was running on Basic CPU (2 vCPUs, 5 GiB); this task uses detached bounded prediction only. Existing workflows retain their pause guards and no schedules were edited.

## Actual prospective execution (November 15)

Deepnote run `6df80c0c-97eb-4dac-80b5-db85076d7ab7` succeeded. Genuine single-QB canary completed at `16:35:57.396514 UTC`, frozen `16:36:01.525792 UTC`; full eligible execution completed `16:36:29.759812 UTC`, frozen `16:36:35.236647 UTC`. Both exclude DET–NE, which had already started. The full population covers 11 remaining games / 22 team opportunity distributions. V2 is operational on ten markets; T+A is explicitly blocked by source semantics, not claimed operational.

| Canonical market | O1 player | O2 stats | O3 stats | O4 stats | O5 stats |
| --- | ---: | ---: | ---: | ---: | ---: |
| pass_attempts | 0 | 0 | 17 | 0 | 17 |
| pass_completions | 0 | 0 | 17 | 0 | 17 |
| passing_yards | 0 | 0 | 17 | 0 | 17 |
| rush_attempts | 0 | 73 | 17 | 0 | 90 |
| rushing_yards | 0 | 73 | 17 | 0 | 90 |
| receiving_targets | 0 | 140 | 0 | 0 | 140 |
| receptions | 0 | 140 | 0 | 0 | 140 |
| receiving_yards | 0 | 139 | 0 | 0 | 139 |
| tackles_assists | 0 | 0 | 0 | 0 | 0 |
| rushing_receiving_yards | 0 | 72 | 0 | 0 | 72 |
| passing_rushing_yards | 0 | 0 | 17 | 0 | 17 |
| Total player-stat distributions | 0 | 637 | 102 | 0 | 739 |

O1 emits 22 team records, each with distributions for accounting opportunities, passing attempts, rushing attempts and sacks; no player distribution is emitted. O1 seconds-per-play pace is unavailable. O5 includes all six eligible QB markets as a separately labeled sensitivity variant; this does not add independent evidence.

Original contract forecasts: O2 1,191; O3 236; O4 0; O5 1,427; O1 0. There are 2,854 model-contract forecasts, covering 1,427 distinct original quotes. All 1,845 original observations remain in 9,225 model-contract rows; 6,371 are abstentions and 418 originals have no player forecast. Neutral player-stat forecast count is 1,478; independently fitted weather forecast count is zero.

Model-specific stat abstentions are preserved: O2 1,893, O3 42, O4 908, O5 1,935. Scope exclusions are not counted as eligible player-stat forecasts. O4's 908 WS1 defensive rows lack input-ready authenticated combined accounting; current raw tackle evidence explicitly says `UNVERIFIED_COMPONENT_SEMANTICS`. Other abstentions include started games, insufficient/current-team histories, stale roles, missing legitimate rushing exposure/yardage, unverified starter identity and WS1 input readiness. Exact per-row reasons and complete per-market forecast/abstention counts are in the JSONL and `FULL_MARKET_V2_RESULTS.json`. Additional WR/TE rush candidates emitted from actual carry histories can enlarge a market's denominator beyond WS1's initial position filter; no rows are removed from the WS1 eligible universe.

| Immutable artifact | SHA-256 |
| --- | --- |
| Canary report | `d27bda4e8bce57eefc7d3551dcc744dec66d294fa25d759e3e496ef8c7a658b0` |
| Full report | `ee8f497169684f4f00844a8e42c9628449461908169e283738d5b6b57e11d699` |
| Full player-stat handoff | `2de14164e7346edb024a86d8824212e52e75019ba95a5b848a5d239fed87bbb3` |
| Full original-contract handoff | `56d067306d224ff88dd6a8ab8a591abbf31289b3f6631ffac07327c771e57fe1` |

The receipt uses the existing v1 freeze-envelope schema; the report itself is `nfl-opportunity-full-market-v2`, and every output model has an explicit `full-market-v2` identity. Reusing that envelope does not relabel any neutral v1 model. The actual source/code receipts are stored with the report.

The real canary is Bryce Young / CAR–NO / BetMGM / passing attempts 36.5, original candidate `d5ff3a2ac803926d3ba98405a4851c3a89f6449802450edb18efba1d4f57b806`, quote `ee7f0b44a30d41f43ce1dcabb19ca3a3f9a666063e4b99ca7f51d734d73d9ea0`. O3 conditional Over/Under/Push = 0.4215087890625 / 0.5784912109375 / 0. The original quote source hash is `6993a07ebce5001a55729ff556765bff388bc91cb5235416af9cd26401ede14a`, received `2026-11-15T04:32:39.016077Z`; kickoff is `18:00 UTC`. This reproduces the old O3 canary arithmetic without changing its earlier frozen forecast.

## Adapter v2.1 — quote-independent roster repair

The original `pregame_roster_availability` table is quote-indexed. Adapter v2 initially required every player to appear there, which incorrectly restricted nonquoted players despite authenticated roster identities in WS1's expanded package. `ws1_full_market_adapter_v2_1.py` accepts a non-QB identity only when its `identity_source_sha256` belongs to the already-authenticated original source hash set and the independent ESPN→GSIS bridge matches, with WS1 input-readiness and event gates intact. It does not reinterpret historical participation as confirmed game-day activity. QBs still require the original explicit expected-starter evidence. No new source collector or model equation is introduced.

The repaired adapter is version `ws1-full-market-adapter-v2.1`; v2 code and both frozen v2 reports remain preserved. Three additional synthetic adapter regression tests verify quote independence, rejection of an unauthenticated identity receipt, and QB1 gating. All 45 local tests pass. This repair changes the roster input population, so downstream allocations may change under the same model equations; keep report hash and adapter version in the issuance identity. Do not mix draws from different roster issuances or sum duplicate forecasts.

Initial issuance arithmetic audit: Deepnote run `2f510b56-85cb-4afd-9c2b-876764a09952`, PASS. All 1,478 stat distributions replayed exactly, 178 matched composite identities passed, 117 source/input byte checks, zero maximum team conservation error. Five actual-packet corruptions were rejected (missing sacks, changed accounting, passed kickoff, future history, duplicate roster identity). Earlier v1 earliest-forecast handoff independently rehashed unchanged. Initial packet SHA-256: `519cb7cc49a67f459efe1715fbbfa5cf9d249e48292d05a8a30d9e3af4ece999`. Audit method is a separate sequential arithmetic pass by the author, not an independent reviewer or evidence of empirical calibration.
