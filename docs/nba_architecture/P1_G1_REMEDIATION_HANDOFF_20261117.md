# P1 G1 remediation and source handoff

Recorded November 17 UTC (November 16 in Toronto), 2026. **IMPLEMENTED / AUTHOR-TESTED; G1 BLOCKED.** This supersedes implementation details in the November 16 P1 handoff without altering its receipts. Independent P6 acceptance remains outstanding. PR #167 stays draft; no release or model-work authorization follows from these repairs.

## Authority, baseline and boundaries

Governing authority is `PA-V25-MASTER-2026-11-09 / v1.1`. Frozen G0 is `nba-sojc-contract/2.0.0` at `59d28dc23be97de2a6a82d22be8338151e31f5b6`. Initial P1 HEAD was exactly `e0b8703887d327c8d8ac34807078e75e7b59a540`, matching PR #168's independently tested owner SHA. Work stays on `research/nba-p1-canonical-history-g1-20261116`. G0 implementation/schema, P2/P3/P4, collectors, training, scoring, optimization, production and schedules are unchanged. Actual main was read as `912bc7010058092ea735dcda0aa941429194474b`; no main checkout or write occurred. Historical operational/NUTS/schedule narratives are not live verification; no runtime job was changed or started.

The original 297 G0+P1 tests passed before repair. The unchanged P6 probe at QA commit `31a6ef8e35351e9f8875a759ff474109c7c01418`, raw SHA256 `fa8012e260a21caacb2fcebadc02a2deddaf957bc4425b8128dcae2c83ba9e52`, reproduced all three unsafe acceptances, exit 2. Its exact bytes and before/after outputs are retained in `p1_remediation_20261117/`. Test/source SHA receipts are in the accompanying remediation evidence JSON.

## Accounting policy and failure preservation

| Input | Policy |
|---|---|
| Played zero display with positive statistics, no explanation | Reject whole input with `ZERO_MINUTE_CREDIT_UNRESOLVED`. Preserve the input manifest and raw bytes. Never erase counts or reinterpret as DNP. |
| 900 minutes or any minutes above 48, no official duration evidence | Reject with `GAME_DURATION_EVIDENCE_REQUIRED`; vault uses its explicit vault-prefixed equivalent. No global 53- or 65-minute limit. |
| Completed NBA box with final period `4 + n` | Duration is `48 + 5*n`, for any nonnegative integer `n`. Reject observed or exact minutes above that duration. |
| Zero display, matching official player/team/stat record, exact time strictly between 0 and 30 seconds | `ADJUDICATED_ROUNDED_SUBMINUTE`. Preserve displayed `minutes=0`, positive counts, and separately expose `official_exact_minutes`. No silent replacement of display values. |
| Exact zero time and positive credits, even with a final box | Unresolved. A box alone does not authenticate the specific dead-ball accounting explanation. Preserve and block; no unsupported automatic exemption. |
| Ordinary minutes at most 48 without official evidence | Legacy research-proxy mode only: explicitly `UNRESOLVED_OFFICIAL_DURATION_AND_SOURCE`. These are mathematically possible, not verified exposure. Strict mode blocks them. |
| DNP / unknown / missing result | DNP and unknown require null minutes and empty statistics. Missing official result is `UNRESOLVED`, never played zero. |

The official NBA [Rule 5](https://official.nba.com/rule-no-5-scoring-and-timing/) was actually retrieved; exact HTML bytes are preserved. Section II states 12-minute regulation periods and five-minute overtime. Section I permits scoring from free throws; Section VIII describes clock restart after an unsuccessful free throw that remains in play. Therefore positive statistics with no elapsed clock time cannot be categorically forbidden. Rule 5 does **not** establish a universal minute-display rounding convention or authenticate a particular player's credit. The adapter's conservative subminute reconciliation requires exact official time plus matching counts and identities. Dead-ball explanations beyond that remain blocked pending authenticated official adjudication/play-by-play and a reviewed semantic adapter. No NBA statistical scoring manual or real dead-ball exception was independently authenticated here.

The CLI rejects an entire bad manifest before writing output, emits its input SHA, attempted-entry denominator and rejection scope, and leaves source/manifest bytes untouched. This is fail-closed rejection, not silent row filtering. API callers must preserve their input and caught integrity code. Existing suspect legacy vault files remain immutable and fail read validation; do not delete or rewrite them to make a directory pass. An independently reviewed migration/quarantine is required if any such real legacy records are discovered; no such real vault population was supplied.

## Versioned P2 prior-game interface

`v2.nba_architecture.p1_evidence` owns `nba-p1-prior-game-evidence/1.0.0`:

- `duration(bundle, game_id=..., game_date=...)` derives completed-game periods directly from supplied NBA live-data box-score bytes. It validates the exact NBA HTTPS URL/game ID, final status/clock, Toronto game date, numeric team identity, raw SHA256, receipt parent hashes, contiguous revisions and strictly increasing actual retrieval timestamps. It accepts 0, 1, 2, 3 and additional OTs.
- `prior_game_exposure(data, bundle)` additionally binds the unique player, team/opponent, participation, every retained stat and exact minutes. It returns displayed/exact minutes separately, OT count, duration, accounting status, raw/receipt SHA, actual retrieval time, null original pregame availability, source status and permanent uncertified classification.
- Bundle shape is `{capture, raw, prior}`. Raw is exact bytes; each prior item has an empty `prior` list. The current capture plus all prior captures must form a complete revision chain. Capture schema: `p1-official-capture-1.0.0.schema.json`.
- Official source status is `OFFICIAL_BYTES_CONSISTENT_AUTHENTICITY_REVIEW_REQUIRED`. URL/hash consistency is not a signature or independent collector attestation. An independently reviewed source admission process remains necessary. No authenticated historical duration population is claimed.
- The builder accepts `official_game_evidence` keyed by **prior** canonical NBA game ID and `require_official_evidence=True`. It rejects target/same-day/future evidence, unused evidence and evidence retrieved after ingestion. Normalized ESPN IDs cannot be silently joined to NBA IDs: absent a dated source-backed crosswalk it fails `OFFICIAL_GAME_CROSSWALK_REQUIRED`.
- CLI `--require-official-evidence` is the strict exposure gate. Optional manifest key `official_game_evidence` maps game IDs to `{capture, source_path, prior}` descriptors under `--source-root`; absolute/path/symlink escapes are rejected. Missing official evidence does not become regulation evidence.

**P2 action:** consume the versioned prior-game interface, preserve source/accounting states, and replace its own hard 53-minute rule only in the P2 owner branch. Do not infer target OT from realized target outcomes. No P2 implementation was modified and no owner acknowledgment is claimed by this author.

## P3/P4 eligibility and availability interface

`v2.nba_architecture.p1_context` owns `nba-p1-dated-context/1.0.0`; its closed assertion schema is `p1-context-1.0.0.schema.json`.

- `resolve_dated_identity(provider_id, kind, at, bundles, input_freeze_at=...)` requires exact namespaced identities, nonoverlapping effective `[from,to)` evidence, original capture/availability at or before freeze, raw bytes/hash and recognized source identity. Missing/ambiguous mappings block. Dated membership changes are not inferred from a player's next game.
- `pregame_candidates(...)` requires source-bound, pre-freeze, effective pregame-roster assertions for the exact target and its teams. It separates nullable eligibility from availability. Missing bundles return `BLOCKED_NO_AUTHENTICATED_PREGAME_CONTEXT`, an empty candidate list and no fabricated eligibility. Postgame captures, target outcome fields, duplicate players, wrong teams and future-effective trades fail.
- This is a **reviewed adapter-export interface**, not a claim that native NBA HTTP responses contain this custom assertion schema. No authenticated historical export exists in the supplied archive. End-to-end native-source adapters and independent authentication remain blocked. Source-bound output explicitly requires independent review.
- The G0 historical generator remains candidate-only from prior rows: legal eligibility is null and availability unknown. It never imports this interface's assertions into certified history or obtains candidates from target-game final rosters. Current role/trade truth cannot be recovered from archive participation alone.

**P3/P4 action:** consume these versioned context/source-status interfaces only after authentic source adapters and independent admission are available. Preserve unknowns and report blocked coverage. No consumer implementation changes or acknowledgment are claimed.

## Outcome-vault separation and revisions

`p1_vault.py` remains a separate filesystem-root consumer. Pregame modules do not import it, open its directories or use `latest` outcomes. Append-only content-addressed outcome records and exact raw sources remain isolated. `nba-p1-official-outcome-vault/1.1.0` adds optional official accounting evidence; prior v1.0 bytes are never rewritten. New structural schema: `p1-vault-1.1.0.schema.json`; Python validators also enforce semantic arithmetic and chains.

Positive zero-display and multi-OT vault records require matching official bytes and explicit accounting evidence. All referenced source revisions are stored in the vault's own `sources/`. Every read now checks **all** outcome chains for gaps, conflicting team/clock and broken parents, not only the key requested by `latest`. Appends require monotonic correction clocks and explicit prior hashes. `outcome_status(game_id, player_id)` returns `UNRESOLVED / MISSING_OFFICIAL_RESULT` when absent, with null minutes and no stats. This does not fabricate an official result or a timestamp. Caller-supplied official labels/ordinary legacy records are not independently authenticated by hashes alone.

## Exact archive reconciliation and remaining source gaps

WS1 source is pinned at `53c01a9eabb9ed09b5c3186eae0d086b07bcc891`. Warehouse is read-only at `97a8bb566826afe5a3e5a7b8c632043d8a1dca24`. The newly executed `nba_p1_reconcile_archive.py` checks all 99 exact compressed shards, **39,916,715 bytes**: 99 verified, 0 missing, 0 modified. It then scans actual rows, checks duplicates, cross-stat identities/minutes and combination arithmetic, and reconciles WS1 exclusions. No accounting issues were detected in this population scan; this does not prove source truth.

| Cohort | Games | Player-games | Category rows | Excluded rows | Player-games >48 min |
|---|---:|---:|---:|---:|---:|
| Season-ending 2019–2022 training | 4,599 | 97,276 | 1,070,036 | 1,485 | 46 |
| 2022–23 development | 1,230 | 25,818 | 283,998 | 253 | 14 |
| 2023–24 validation | 1,230 | 26,283 | 289,113 | 550 | 12 |

The earlier handoff's training population includes the **entire 2021–22 season**. It is not a strict calendar-before-2022 split. For an exclusive `2022-01-01` calendar cutoff, exact observed coverage is **3,896 games / 82,624 player-games / 908,864 category rows**. No training or validation split was fitted or optimized here.

For each listed cohort: authenticated official-duration player-games **0**, authenticated original pregame-context games **0**, complete official correction chains **0**. Zero-minute rows in this archive are 0 because the legacy population validator requires positive workload; this is **selection loss**, not evidence that zero-minute appearances/DNPs did not occur. Missing official results, roster candidates, DNP, played-zero and unknown-participation denominators are not identifiable without an independent official schedule/roster/result population. Report them as unavailable, not zero missing games. Nonstandard games remain excluded under the pinned WS1 ledger (18 across all nine archive seasons). Team abbreviations remain a separate namespace; a correct shard digest does not verify numeric identity or a dated trade.

`archive_reconciliation.json` preserves the full 99-shard proof, cohort counts, strict-calendar count and one **real archive row**. Archive `source_sha256` hashes canonical parsed provider JSON, unlike a raw HTTP SHA256. The original provider bytes for that hash are absent. No archive shard is treated as historically available merely because its SHA is correct.

## Real source-backed demonstration, with explicit limits

The sample preserves actual ESPN response bytes for `401070213` (Boston–Philadelphia, October 16, 2018 Toronto date) and an October 19 scoreboard. The unmodified pinned WS1 adapter exported 26 prior player records. Target identity/start is taken only from the scoreboard's scheduling fields for `401070219` (Toronto–Boston); final scores and target participants never enter the manifest or generator. Analyst-chosen historical freeze/forecast/training-cutoff clocks are **simulated replay inputs**, not original captures. The modern capture clock is retained as modern.

The CLI reconstructs 13 Boston prior-game candidates, 338 features, 13 verified supplied raw-source references and 13 unresolved exposures. Two runs are byte-identical. Snapshot content hash is `39ef73ff53832aca7e569e641f6201c8b15c5888e863a6cc7a3db744f2f0b369`. Strict official-evidence mode correctly blocks this same real sample. It is an actual source-backed **uncertified partial reconstruction**, not a complete authenticated P1 source population, official duration test, original pregame snapshot, or real S/O/J integration.

The archive example's canonical source hash is `648933bf7f12d02c09313fbcfccd120deb103477fb8b0f05e5aaa4df85003fef`; today's retrieved parsed response hashes to `077729f88d66762350d199f66d4dbe220370b362e357b0e27e9e58a6c68be93a`, and today's raw response hashes to `2b3c8715bdd7de72a7e8e06b4f163b856c84ca41c525a8936a2655a7e93e360c`. These are different objects/revisions. Their correction chain is unresolved; the new response cannot authenticate the archive's missing old source bytes.

The NBA CDN historical box endpoint `https://cdn.nba.com/static/json/liveData/boxscore/boxscore_0022300713.json` returned HTTP 403 on both attempted requests. Accordingly, actual official historical-duration sample verification is **BLOCKED**, not substituted with ESPN or inferred from maximum observed minutes. All official-shaped positive/negative duration, overtime and rounded-display fixtures are **synthetic**, explicitly labeled in permanent tests.

## Reproduction and independent retest

```bash
python -m unittest discover -s tests/nba_architecture -p 'test_*.py' -v
python -m unittest discover -s tests -p 'test_nba_p1_source_preflight.py' -v
PYTHONPATH=. python docs/nba_architecture/p1_remediation_20261117/p6_exact_probe.py P1
python scripts/nba_p1_build_pregame.py --input docs/nba_architecture/p1_remediation_20261117/real_ws1_manifest.json --output /tmp/p1-real-replay.json --source-root docs/nba_architecture/p1_remediation_20261117
python scripts/nba_p1_reconcile_archive.py --manifest /path/to/pinned/ws1/coverage.json --warehouse-root /path/to/pinned/warehouse --output /tmp/p1-archive-reconciliation.json
```

The five original P6 controls are exported without alteration from the QA commit into a temporary directory and run with `PYTHONPATH=.:tests/nba_architecture`; they are not reauthored as independent evidence. They contain 83 additional controls. A first isolated invocation lacked the golden-fixture import path and failed imports; the corrected command passes. The exact P6 negative probe remains unmodified and permanent; source receipt hashes distinguish it from author-written tests.

Permanent adversarial tests cover the exact three failures; 0/1/2/3/additional OT; zero display with source-confirmed subminute credit; unresolved true-zero credit; malformed shooting arithmetic; corrupt hashes; incomplete official and vault revision chains; wrong teams/player IDs; ambiguous DNP; strict source absence; missing official results; dated trades and overlapping identity intervals; postgame rosters; target outcome/evidence injection; source observation clocks; raw-source corruption; explicit source status; and deterministic real-source CLI replay. Existing G0+P1 controls remain in place. The changed P1 golden hash reflects the new explicit unresolved source-status feature, not a changed G0 contract.

**G1 remains NO-GO / BLOCKED** for original source authenticity/availability, dated identity/trades, authentic schedule/roster/DNP coverage, complete official results/corrections, native context adapters, real consumer integration and independent P6 retest. Author tests are not G1 acceptance. P6 must rerun the new exact head, inspect the source policies and challenge the real/synthetic distinction. P2/P3/P4 owners must independently accept their interface handoffs. Rollback: close draft PR #167 or revert only the P1 remediation commits; preserve all old source and outcome versions.

## Executed author verification receipt

Exact tested code commit: `1da5dfd7172414f33ebbd70a49a93e1a35b4ea59`. Python 3.12.14; package versions and every source/test/raw-capture SHA are recorded in [engineering_receipt.json](p1_remediation_20261117/engineering_receipt.json). Logs are retained beside it. Results: **331/331 G0+P1**, **83/83 unchanged P6 regression controls**, **9/9 P1 preflight**, zero failures/errors/skips. The **34/34 new remediation controls are included in the 331**, not an extra count. Total distinct invoked controls across these suites: 423. These are author executions, not independent acceptance.

The unchanged P6 probe moved from exit 2 / three suspect acceptances to exit 0 / three explicit rejections. The real-source CLI ran twice with identical output; strict mode returned exit 2 and blocked the entire 26-entry manifest. Full-suite stdout SHA256: `6820401ce3e66acd1dfccf9eceb74638612512499bd56f49d5679c12f9abb021`; P6 control stdout SHA256: `96f5f71c669302e5c0ce13740810ee1b8339b5d98ca9abec7dd98a737decdeb3`. The following receipt-only commit does not change executable sources, schemas, fixtures or G0.
