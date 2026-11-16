# NBA V2.5 P1 — source readiness preflight (G0 BLOCKED)
Date: 2026-11-16 (America/Toronto). **Status: read-only prerequisite audit, not P1 execution or G1 acceptance.**

## Authority and gate

- Governing plan: `PA-V25-MASTER-2026-11-09 / v1.1`.
- Frozen candidate contract: `nba-sojc-contract/2.0.0`, branch `research/nba-p0-sojc-architecture-g0-20261116` HEAD `3f38ef9d1f6f2e50623a5623fb5826efc67cf7b2`.
- Owner design acceptance exists, but `G0_P0I_BLOCKED_V2_20261116.json` and issue #149 still require separate, independent adversarial review. PR #147 remains a draft with no submitted reviews. **Do not activate P1–P6 or sign G1 until G0 PASS.**
- This audit-only branch is based on the frozen candidate. It adds no P1 historical adapter, model, source collector, official outcome vault, forecast scoring, trainer or production code.
- The named NBA Parallel Architecture and Monte Carlo Execution Prompts packet was not among available attached/project files. The live contract/plan and source artifacts were inspected instead; do not certify exact-packet compliance.

## Source evidence and exact references

| Source | Exact ref / blob | Evidence level |
|---|---|---|
| GitHub main | `912bc7010058092ea735dcda0aa941429194474b` | verified branch head |
| Frozen G0 candidate branch | `3f38ef9d1f6f2e50623a5623fb5826efc67cf7b2` | verified branch head |
| V2 contract validator | blob `2e99fe2be24198dff407a23e297eececa8ea359a` | Git object identity, not content SHA-256 |
| V2 JSON Schema | blob `3b82cebe7369e94092395f6ecac952e282065383` | Git object identity |
| G0 blocking receipt | blob `03a45116efbb2f2984e94267f2af38a11972418f` | explicit `G0_BLOCKED` |
| Owner design acceptance | blob `20bde0380e9fa2028077e19142333609591c9ca5` | owner approved design only |
| Historical warehouse branch | `data/bayesian-history` at `97a8bb566826afe5a3e5a7b8c632043d8a1dca24` | verified immutable ref, not data-content certification |
| WS1 implementation PR | #137 HEAD `53c01a9eabb9ed09b5c3186eae0d086b07bcc891` | open research draft |
| WS1 coverage manifest | Git blob `77a9e3a2c0a049f1169dccc3f0591ed08d85dac6`; recorded manifest SHA-256 `1cea946b2ea00ecc2ac302b2fb5a5821984be61bd6ef7cd6575e23ff98fd3f9e` | existing WS1 content-SHA claim not independently recomputed from archived bytes here |
| WS1 rejection ledger | blob `af594bf51f4e0dcea8a5c4f5918c5f3e49be7a5a` | prior WS1 audit, not our rerun |

**New independent metadata cross-check:** retrieved all eleven stat directories from the pinned warehouse branch. Exactly 99 compressed objects were listed, with the same 99 relative paths and the same 99 reported compressed byte sizes as the WS1 manifest; zero missing, zero extra and zero size disagreements. The GitHub metadata check **does not** authenticate compressed-byte SHA-256. The original warehouse bytes are not mounted in the connected Deepnote project. Use the added read-only `scripts/nba_p1_source_preflight.py` to actually SHA-256 all bytes on a full local checkout.

## Coverage, with status distinguished

All counts below are **reported from the November 15 WS1 archive audit**, not newly row-parsed in this preflight. Seasons are labeled by their ending year; each count is the sum across eleven stat-category shard rows after reported scope quarantine. They are observations, not verified participation/active-roster denominators.

| Segment | Season(s) | Remaining regular-season candidate games | Eleven-stat rows | Unique player-game appearances (11 categories) |
|---|---|---:|---:|---:|
| Pre-2022 training | 2018–19 to 2021–22 | 4,599 | 1,070,036 | 97,276 |
| Development | 2022–23 | 1,230 | 283,998 | 25,818 |
| Forward validation | 2023–24 | 1,230 | 289,113 | 26,283 |

The 2019–20 and 2020–21 shortened season totals are 1,059 and 1,080 candidate games. Across 2018–19 through 2026–27 the WS1 audit reports **2,249,104 stored rows, 204,464 unique player-games and 9,625 game IDs** before the 18-game / 3,938-row quarantine. The warehouse contains 99 shards: eleven NBA stat categories times nine ending-year partitions (2019–2027). **No independent full official schedule denominator** was obtained; numerically matching familiar game totals is not source certification.

## Scope exclusions and missingness

- WS1 quarantined fifteen exhibition games (3,179 rows) and three NBA Cup championship games (759 rows). They remain in immutable source bytes and are excluded *on read*.
- The legacy population schema stores observed strictly positive minutes and eleven stat values, but lacks DNP rows, played-zero-minute roster witnesses, reliable game-day legal active lists, starting role, shot/FT attempt breakdowns, explicit official pace/possessions, original point-in-time source publication clocks and original sportsbook offers.
- Historical completed ESPN summary retrieval in 2026 is `historical_reconstruction`. It may support a date-only prior-game model experiment with explicit limitations; it **cannot** become `original_prospective`, even if a reconstructed cutoff is before the 2022–24 games.
- Trades are not verified from changes in abbreviations alone. Preserve original team-by-game membership, use source-backed dated crosswalks, and fail closed on collisions.
- Made threes may appear as `3PT='3-8'`; parse as 3 makes with 8 attempts only under explicit nonnegative integer and makes<=attempts checks. The existing `population_normalizers.py` and `population_repair_nba_threes.py` already address this; reuse and test, do not invent a second authoritative collector.
- The WS1 report found recent warehouse collection behind the November 15 date; the current 2026 tail is not the user-requested historical 2022–24 replay, but this is evidence that collector state must never be inferred from reporting schedules.
- Independent league/game-id reconciliation, official stat corrections, dated player↔team crosswalk, roster eligibility, DNP coverage, first-known information clocks and canonical official-result vault are open G1 prerequisites.

## Contract-bound P1 implementation plan — **not authorized at this gate**

On an accepted G0 v2.0.0 contract, **one** WS1-owned adapter should consume the pinned source warehouse, preserve each raw original receipt (or explicit historic lack thereof), and build immutable `pregame` objects with `source_profile='historical_reconstruction'`, `certification='HISTORICAL_RECONSTRUCTION_UNCERTIFIED'`, UTC clocks, stable `espn:game`, `espn:player`, `espn:team` identities and explicit null eligibility. For a target game, enforce `prior_game_date < decision_local_date`, exclude all same-game outcomes, and never populate target minutes, score, overtime, team totals or DNP from that game's boxscore. A genuinely original pregame capture uses separate `original_prospective` receipts and actual observed/retrieval/ingestion timestamps.

An isolated append-only official outcome vault should hold final/void/DNP and correction versions, preserve official raw bytes and exact source identity and never be importable by the pregame builder. Existing `v2/official_nba_nhl_capture.py` and WS1 ESPN adapters should be reused; game/result status, made threes, combined stats and missing official results should be validated before an outcome is available for evaluation. No historical forecast scoring belongs to P1.

One canonical API for S/O/G/J consumers is the frozen `v2.nba_architecture.v2_contracts.validate_pregame(p)` plus its schema-2.0.0 JSON envelope. Do **not** invent a competing market-feature schema; original offered contracts use the separate original-offer path. P1 may add a deterministic generator/adapter only after G0 PASS and an explicit v2 ownership conformance handoff. All current WS1 schemas are v1 research interfaces and need a documented v2 transformation, not silent widening of fields.

## Executed checks and exact limitations

- **Executed live:** GitHub ref/PR/issue inspection; 99-of-99 path and compressed-size metadata comparison; Deepnote project file inventory (no authoritative local NBA warehouse). No source collector or historical model run.
- **Executed offline on synthetic data:** `python -m unittest discover -s tests -p 'test_nba_p1_source_preflight.py' -v` — **9/9 pass**: hash verification, tampered bytes, missing shard, missing stat-season, duplicate, path traversal, fake SHA, invalid schema and unexpected stat. This is **not** an independent G0 review or a test of real NBA data.
- **Not executed:** actual 99 compressed-byte SHA-256 pass, historical feature generation, dated roster reconciliation, official result vault, consumer v2 adapter fixture integration, complete source schedule parity, G1 signoff.

To run the preflight when the pinned warehouse has been checked out locally:

```bash
git fetch origin data/bayesian-history research/v25-nba-ws1-feature-store-20261115
git worktree add --detach /tmp/nba-warehouse 97a8bb566826afe5a3e5a7b8c632043d8a1dca24
git show 53c01a9eabb9ed09b5c3186eae0d086b07bcc891:docs/nba_ws1/coverage.json > /tmp/nba-ws1-coverage.json
python scripts/nba_p1_source_preflight.py --manifest /tmp/nba-ws1-coverage.json --warehouse-root /tmp/nba-warehouse
python -m unittest discover -s tests -p 'test_nba_p1_source_preflight.py' -v
```

## Handoff decision

**G1: BLOCKED / not attempted. P1 production/research implementation: not authorized until G0 PASS.** Next action is an independent auditor-authored G0 review of PR #147 at its exact final SHA, followed by documented owner-adapter conformance. Then P1 can implement the one canonical historical input pipeline on its own isolated branch, run the actual pinned-warehouse source-byte verification, construct date-ordered fixtures, and request the six-team G1 checks. No retrospective capture is certified, no outcome vault is assumed complete, and no forecast was scored.

Rollback: close this audit-only draft PR or revert its additions. No production collector, forecast, source archive, NUTS state, automation or existing G0 receipt is changed.
