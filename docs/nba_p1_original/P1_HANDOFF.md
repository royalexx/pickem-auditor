# Pick'em Auditor V2.5 — NBA P1 prospective source handoff

**Version:** PA-NBA-P1/1 (research-only, stacked on P0 PA-P0/1)
**Profile:** `source_listed_subset` as approved Nov 19. **No production cutover.**

## Ownership and upstream code

The canonical source and feature producer is the existing WS1 `v2.nba_ws1.capture.capture`, `v2.nba_ws1.store.NBAPregameFeatureSnapshot`, and `v2.nba_ws1.adapters`; the P1 worker calls this existing collector. P0 integrity is the common shared code in draft PR #198; no P0 definitions are edited. The fixed-date Phase 7 registration and Phase 8C runner in draft PR #144 (pinned `ceddb41e8e13029849ec82ba2b537faab0ee0a24`) are not edited, and existing bridge PR #199 is not overwritten. P3 receives P0 feature records and a P1-only read adapter, not a second collector.

The upstream WS1/Phase 7 collector exists in an unmerged history separate from draft P0 PR #198. **Merely merging this stacked research branch does not activate the rolling pipeline.** An integration branch must include the exact original WS1 code and P0 gateway before running a legitimate canary; keep the current task pin unmodified until P6 accepts that integration.

## Root cause (reported Nov 20; verified code and P0 proof)

Original `research/nba_phase8c/daily.py::ensure_authoritative_storage` calls `Path('/work').resolve()` but then compares the resolved `/datasets/_deepnote_work` path with the literal `/work`. On the actual Deepnote project mount this rejects an otherwise durable root with `DURABLE_STORAGE_NOT_ATTESTED`. PR #199 contains the narrowly scoped old-runner bridge; P1 **does not** change the expired pilot. P0 draft #198 has independently verified project writer/reader detached-run receipts; writer 207a1a65-1c3b-4d9f-957f-c4568a863ba1; independent reader d446c692-604d-4c2e-ae14-357dd96278e2; payload SHA256 21084d9cb869c6105a0d286ea268b2b8e5375af01790e6fec79309cc54cc6692. This is cross-run durability evidence, **not** a vendor backup SLA.

## CLI

With accepted P0 and original WS1 in one isolated checkout:

```bash
PYTHONPATH=/path/to/staged/repo python -m research.nba_p1_original.rolling --day 2026-11-21 --no-wait
```

`--no-wait` records NOT_DUE, never claims an early capture. Omit it only when a legitimate current-day window and durable project root are available. This is a worker entry point, not another scheduler. Existing NBA automation must be modified only after separate cutover authorization. Execution outside attested `/work` is rejected before any original write.

## Record flow and data classes

The worker archives original ESPN raw bytes once by SHA256, verifies the original WS1 gzip bytes and original receipt SHA, stores development-only P0-schema SourceReceipt objects, generates immutable P0-schema PregameFeatureSnapshots per retained player for points, rebounds, assists, threes, PRA, PR, PA and RA, and produces a SHA-indexed, read-only consumer manifest. No forecasts, distributions, modeled appearance probabilities, offered sportsbook lines or market probabilities are created. P0 validation and SHA are reused without writing to P0’s shared namespace: dev-only `O_EXCL` SHA and logical-ID claims guard conflicting records. The worker's separate original-capture claim guard uses `O_EXCL` across detached workers. Partial claims are retained for forensic review; a failed claim is not overwritten or silently recaptured.

Two event-relative windows: early opens -70m and closes -50m (target -60m); final opens -35m and closes -20m (target -20m). All early/final windows are globally sorted across the discovered slate, including simultaneous games and late games. An observed completion after a freeze is rejected, even if the automation started earlier. Delayed/postponed/canceled events remain explicit in the attempt ledger; a game changed after original discovery requires separate source verification before promotion. No finalized result is used to reconstruct a missed original. `America/Toronto` determines calendar day; the exact UTC game clock determines each freeze.

The P0 `PregameFeatureSnapshot` fields are exactly `feature_snapshot_id, sport, event_id, team_id, opponent_id, player_id, stat_key, period, input_freeze_at, source_receipt_ids, feature_sha256, reconstruction_class, features` plus `record_type, schema_version`. The P1 `features` payload adds `interface_version, candidate_kind, legal_eligibility, availability_status, participation_probability, source_listed, espn_player_id, official_nba_player_id, espn_event_id, official_nba_event_id, current_name, position, listed_roster_status, listed_roster_uncertainty, identity_source_status, home, roster_record_id, prior_player_history, prior_player_features, current_team_context, opponent_context, missingness, injury_evidence, feature_source_receipt_ids, reconstruction_note`. Historical outcomes exist only in previous-game history with receipt clocks at or before the freeze. These are causal descriptive inputs; P3 owns modeling and distributions.

No legal roster status is inferred from the ESPN source-listed candidate; availability states `UNVERIFIED_AVAILABILITY`, `QUESTIONABLE_SOURCE_REPORTED`, and `RULED_OUT_SOURCE_REPORTED` are **source reports, not proof of DNP or probabilities**. An NBA.com source failure does not remove an ESPN record. Cross-provider official NBA ID remains `null` without a unique source-backed time-valid crosswalk; names are never used for ID matching. The display name, position and listed roster status are extracted only from the exact original ESPN roster receipt, and are explicitly missing when unavailable or ambiguous. Past-team IDs are preserved across trades.

A P3 consumer imports only `research.nba_p1_original.feature_store.load_handoff` or reads exact `PregameFeatureSnapshot` P0 files. The P1 adapter calls P0 `validate_record`, requires the cross-detached P0 project-storage attestation, reopens immutable DEV P0-schema receipt bytes/logical-ID claims, checks archived source hashes, source availability and freeze, game and player identity and reconstruction class. `load_handoff(root,manifest_relpath)` verifies the stored SHA before returning game and feature records. A P3 model must also run P0 `admit_forecast(...)` with its own authentic model artifact, source bytes and training cutoff; source P1 certification is **not** model certification.

```python
from research.nba_p1_original.feature_store import load_handoff, verify_handoff
source = load_handoff('/work', 'research/nba_p1_original/dev_v1/handoffs/<observed_sha_name>.json')
# source['features'] is a list of P0-compatible feature records.
# Reject records with reconstruction_class != 'original' for original forecast A/B.
# Authenticate each source receipt, training cutoff, and model artifact via P0 before P3 predicts.
```

## Real quotes and official outcomes

Authentic two-sided NBA prop prices are **not** generated or inferred. The existing authorized market collector is the sole market owner; accepted P0 MarketQuote records may be joined later with exact source, event, player, period, line and two-sided terms. Until independently reverified, `accepted_market_quotes=[]`, `market_status=NO_ORIGINAL_TWO_SIDED_QUOTE_REUSED`, and feature output is distribution-only research (class A eligibility is not a forecast claim). Official outcomes, DNP and stat corrections stay entirely in the P0 OutcomeRecord vault and morning independent settlement workflow; the feature adapter does not read them.

## Test and acceptance gates

Unit/adversarial test path: `python -m unittest discover -s tests/nba_p1_original -v`. Local tests use a restricted P0 stub only if P0 isn't installed; **these results are not P0 integration tests**. A P0-conformant detached Deepnote test requires staging the precise draft #198 files with main `v2/stat_registry.py` and `v2/contracts.py` into a private dev checkout and running the same suite. No genuine prospective game certification, historical simulation score, market profitability or P3 probability result is claimed by these tests.

**Gate checklist:** P0 common contract and project storage pass; dev-only records pass P0 schema; P6-authorized adoption into the shared P0 namespace is independently checked; P1 full source + native WS1 integration tests pass; original forward event source and final snapshot with authenticated pregame clock pass; P3 reads full frozen snapshot; independent P6 tamper/cross-detached review passes; original forecast/official result cross-verification passes before operational acceptance. If any missing, research-only.

## Known limitations and requested adjustments

1. The original WS1 call (`capture`) exists on a different unmerged branch; no automatic merger into P0 is permitted here. Native collector integration is a **BLOCKED** dependency.
2. Historical ESPN backfill gives class C reconstructed source features, never original future pregame status.
3. Source-listed candidate is not proven legally active, and the P3 layer must abstain when availability evidence is inadequate.
4. WS1 often has unavailable historical possessions/pace, injuries, actual final historical publication clocks, and incomplete component stats. Missingness is preserved, never imputed from final target game.
5. The development worker does not write to the shared P0 record store; only `research/nba_p1_original/dev_v1` receives bytes and P0-compatible dev receipt claims. A separately authorized P6 cutover must import/reverify originals into the shared P0 store. This worker does not duplicate the market collector; source-certified two-sided market records are currently **BLOCKED_BY_DATA**.
6. Source discovery occurs at worker start; a subsequent reschedule, game delay or cancellation requires original revalidation before live certification. Capture's `expected_game` comparison rejects changed original event identity/tipoff, but no authoritative reschedule event watcher is introduced.
7. A crash after exclusive capture claim leaves a permanent claim requiring independent review. The design **fails closed** instead of trying to reconstruct or recapture after deadline; optional authorized retry semantics are a future change-control ticket.
8. P0's tested storage has cross-detached persistence but not an established indefinite backup SLA; no live scheduler pin has been changed.
9. Source-first archival paths are immutable, but the `daily_manifest` first invocation is write-once, not a continuously mutable daily ledger. Interrupted-worker finalization needs an explicit revision/append-only policy approved by P0/P6.
10. P0 `admit_forecast` remains downstream P3's authority; all current source exports are RESEARCH_ONLY.

## Deployment and rollback

Integration (after P6): stage P0 draft PR #198 + original WS1/P7 exact hashes + this P1 branch in one validated checkout. Run targeted tests and detached dev canary first; confirm `/work` alias with P0 proof (never env bypass); verify independent second execution can read SHA bundles. Ask automation owner for controlled update of the **existing** NBA task only. Do not create another task. Keep old Nov16–20 ten-slot registration, original SHA, settlement receipts, and old automation prompt immutable. Rollback is to restore the old pinned task commit *only under explicit owner control*, stop calling the new research CLI and preserve every failed/source/feature receipt; no destructive cleanup.

## Handoff decision

- Engineering implementation: `IMPLEMENTED` once code pushed; test status depends on measured execution receipts.
- Operational source certification: `BLOCKED_BY_DATA` until a genuinely original future pregame freeze survives independent validation.
- P3 forecast readiness: interface exists, but native integration and original live proof remain **BLOCKED**.
- Production: `RESEARCH_ONLY`, no cutover/no betting recommendations.
