# Phase 0R NFL game-active roster evidence

Governing plan `PA-V25-MASTER-2026-11-09 / v1.1`. This bounded ticket covers
P0R-05 source receipt capture and P0R-07 prospective replay for NFL game-day
status. As inspected on November 23, 2026, Toronto time, main was
`237331c113049326e2d8945f8ea2c17bc5f36486` and draft PR #209 was
`1c13f51dea3a80e7c1a4f770e68ad42846b58f39`. The November 23 Deepnote
afternoon run `242e9bf4-7a1f-4dc0-a801-f8d410ae64b9` used #209's head.
The daily notebook `932674d66d4543c6b10ff2e2c0a4df9c` showed no schedule.
GitHub's daily workflow is dispatch-only and the training pause is set.

## Evidence chain and repair

1. The original PropLine event `726376` identifies CIN at WAS and a scheduled
   start of 8:15 p.m. EST. The NFL Game Center confirms the fixture. The
   nflverse schedule joins the exact oriented teams and start to ESPN
   `401873078`, NFL GSIS `60340`, and nflverse `2026_11_CIN_WAS`.
2. The original archive carries GSIS player IDs. The captured nflverse
   crosswalk agrees by normalized name and one-to-one ESPN/GSIS ID for
   24 distinct players across all 100 rows. For example, Joe Burrow resolves
   from `00-0036442` to ESPN `3915511`. Team membership for this game still
   requires the game roster.
3. The first positive evidence gap is the complete game-specific active
   roster. The NFL published the game's inactive list at 6:48 p.m. EST,
   after all original forecasts. The club flip card contains players later
   declared inactive. Neither document provides a final active roster.
   The raw NFL, Commanders and ESPN requests failed at the transport layer
   (HTTP CONNECT 403). Existing repository evidence separately records the
   ESPN summary without game-active rosters and an ESPN core roster 404.
   The historical lineup importer is a postgame context producer. It has
   no contemporaneous possession receipt for the target event.
4. The new opt-in checker captures raw schedule, crosswalk and ESPN
   game-summary bytes, records completion of each response read, and
   preserves source errors. Replay verifies the pinned report hash and reads
   the same immutable source bytes without any network access. The checker
   uses the earlier applicable decision/freeze/forecast cutoff plus the
   kickoff boundary, validates the game header and both teams' explicit
   active/inactive statuses, rejects incomplete or ambiguous inputs and
   retains the per-contract reasons. The positive ESPN path is fixture-tested.
   A complete live ESPN game-day roster payload remains unobserved.
5. The opt-in report is an evidence sidecar. The existing strict forecast
   gate still requires pre-evaluation input pinning, model cutoff, exact
   contract and original quote evidence. A subsequent production integration
   would require a successful independently replayed prospective roster
   capture and a separate review of how the actual evaluator consumes it.
   #209's research/strict flag separation, the research archive and the
   frozen 60/40 benchmark are available for Phase 1. Publication and Tier
   decisions remain behind their existing approval gates.

[NFL Game Center](https://www.nfl.com/games/bengals-at-commanders-2026-reg-11) ·
[NFL game-day inactives](https://fantasy-www.nfl.com/news/week-11-monday-night-inactives-cincinnati-bengals-at-washington-commanders) ·
[Club flip card](https://static.clubs.nfl.com/image/upload/bengals/fmzmdau78liqqlccdnjd) ·
[Existing ESPN source diagnostics](../validation/live-lineup-remainder.json)

## November 23 receipt

| Count | NFL research side rows |
|---|---:|
| Archived | 100 |
| Frozen predictions, verified archive bytes | 100 |
| Authenticated original pre-evaluation input freezes | 0 |
| Roster verified | 0 |
| Integrity certified | 0 |
| Settled from official final stats | 0 |
| Unresolved settlement | 100 |

There are 50 distinct player/stat/line pairs with two archived sides and 24
players. The original archive has a run ID, legacy snapshot keys and
`inputs.id` values. It has no explicit `forecast_id` or `contract_id` values.
The sidecar preserves those source identifiers as supplied and leaves the
explicit ID fields null. The legacy identity is
`(run_id, game_date, player, stat, side)`. Its line, player and event bindings
are retained alongside that key. Assigning replacement IDs would obscure
the source's actual identity contract.

The original forecasts were issued at 12:45:36–12:45:37 p.m. EST. The new
checker possessed the raw schedule at 8:14:47.669108 p.m. EST and the player
crosswalk at 8:14:48.246990 p.m. EST. Both were pre-kickoff and after every
original forecast. The ESPN raw request failed at 8:14:48.274456 p.m. EST.
The source audit reproduced byte-for-byte with these overlapping reasons,
each applying to all 100 rows.

- `NFL_CROSSWALK_POSSESSED_AFTER_CUTOFF`
- `NFL_GAME_ACTIVE_ROSTER_MANIFEST_MISSING`
- `NFL_ORIGINAL_INPUT_FREEZE_MISSING`
- `NFL_ROSTER_SOURCE_MISSING`
- `NFL_SCHEDULE_POSSESSED_AFTER_CUTOFF`

The original archive's independent integrity receipt records
`missing_or_imprecise_timestamp:input_freeze_at` on the entire 1,692-row
multisport batch, including this NFL cohort. All 100 NFL rows also lack a
model cutoff and source receipts. The 231 quote exclusions in the multi-sport
quote archive are a different denominator. The NFL Game Center and club box
score checked during the audit were still showing the scheduled game with
no final player results. Once official results are present, settlement must
verify the event, stable player ID, participation and stat policy, then use
the unaltered sides and lines with the repository's `settlement_outcome`
semantics. Preserve the result as a separate artifact with the original keys.
Leave unexplained absent stat lines and unverified product voids unresolved.
The combined tackles market requires the authorized solo/with-assist/assist
accounting, with a verified equivalent if using a differently labeled source.

## Receipt SHA-256

| Artifact | SHA-256 |
|---|---|
| Original live-pool gzip, run `ce72f72c-a3e2-5b43-8713-c0c44f26a46a` | `e87c58c9267a135043c1dccc3c2032c9994a14c33c0adbd5d6c6eda41178334d` |
| Decompressed live pool JSON | `f85843b5806967d9b31bb74df582be36c9d4043732845e17bb92817764f62cd0` |
| Original forecast JSONL according to the embedded receipt | `bd545f26275286603fda9749275cbf7941ad0849af972e60c437f8a477bf0d09` |
| Schedule source bytes | `6277ae36691416c2390578e918a9ee26f44ab1ac0af6856277fc488a6eaf9489` |
| Player crosswalk source bytes | `6841de1b685d478b4cbe3da2ab533d9e19438e347f4a25e060d5921d7dd2e47b` |
| Earlier pregame transport probe | `ce7b43bdffcbdfcb4a41f8801c8132e8393f43514a8861e4fbba16752c48ae37` |
| Row-level roster evidence sidecar | `5544ae07a7994c864385354ae3428a84f217f2c54ed6b5378e3a121055d56d49` |
| Frozen 60/40 production policy | `955749b0cac3007484d6892a64dc3b9a8bb5027fadfde609c115cb0d7332bb89` |
| November 8 frozen research manifest | `81306a981d933213ba2ce6eb34ce33c00e91cf9ab57ffcf0fa690992de465c21` |

The archive is pinned at `dfd75eda059a4e692255f1b9cb0b601c934547c3` on
`data/live-observations`. Roster and official final evidence hashes are
unavailable. Collector possession timestamps prove local capture chronology
within the collector trust boundary. The replay independently checks the
recorded clocks, hashes and matching logic against the pinned artifacts.

## Phase 1.5 opportunity evidence

These are fields preserved in the original research bytes. None has an
authenticated original input-freeze receipt.

- **Team volume.** `team_pass_attempts_expected` is present in the evaluated
  candidate inputs for all 52 receiving side rows. It carries historical
  team passing averages used as a pregame proxy (33.222222 WAS and
  37.777778 CIN). The source slate also preserves historical pace.
- **Participation and role.** Engine B preserved its historical opportunity
  term, units, observations and per-opportunity conversion for 94 rows.
  The source slate preserves historical snap/workload fields. None of the
  100 rows has a pregame player route/snap or `workload_tonight` forecast.
  Sixty-two rows preserve event context. Ninety record
  `STATUS_NOT_VERIFIED`.
- **Allocation.** The receiving rows preserve 52 team read-bucket throw
  shares, 26 first-read target share values for receiving yards and 26
  checkdown target share values for receptions. These inputs cover those
  charted buckets. A full allocation forecast across all receiving, rushing
  and defensive opportunities remains unavailable.
- **Efficiency.** The 52 receiving rows retain a receiving conversion
  factor (catches per target or yards per target for the respective market).
  These and Engine B's historical conversion terms are stored research
  inputs. No independently frozen, full-market conditional efficiency
  forecasts or matching realized exposure factors were verified.
- **Unmeasured.** Team volume, participation, share, and conditional
  efficiency errors have no paired attribution here. Zero/tail, directional
  calibration and selection errors await official settlement and suitable
  denominators. Engine A has a probability on 100 rows, Engine B on 94,
  and the original blend reports available on 18. The archived original
  model outputs are the Phase 1 inputs. A single game provides one game
  cluster and cannot establish Tier power or rank Phase 2 investments.

## Replay and rollback

With the original `nov23-research.json.gz` and extracted receipt directory
available locally, run:

```bash
python scripts/nfl_pregame_roster.py \
  --archive nov23-research.json.gz \
  --archive-sha256 e87c58c9267a135043c1dccc3c2032c9994a14c33c0adbd5d6c6eda41178334d \
  --provider-event 726376 --espn-event 401873078 \
  --out nov23-roster-audit \
  --replay nov23-roster-audit/5544ae07a7994c864385354ae3428a84f217f2c54ed6b5378e3a121055d56d49.json \
  --replay-sha256 5544ae07a7994c864385354ae3428a84f217f2c54ed6b5378e3a121055d56d49
```

Rollback is a revert of this isolated change, or simply leaving its opt-in
command unused. Preserve its evidence directory and the original forecast
archive. The remaining acceptance gate is a complete authoritative game-day
roster and identity receipt possessed before the freeze of a fresh authorized
original contract, with a second replay of the exact bytes. The November 23
contract cutoff has passed. For this cohort, official final settlement is
the outstanding read-only operation.
