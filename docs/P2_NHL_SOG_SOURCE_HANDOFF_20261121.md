# P2 — NHL SOG original-source acquisition and P0 handoff

**Document ID:** PA-V25-P2-NHL-SOURCE-20261121  
**Schema:** `PA-P2-NHL-SOG-SOURCE-BUNDLE/1`; P0 `PA-P0/1`.  
**Scope:** NHL skater full-game shots on goal; original input receipt collection and admissibility **only**.  
**Release:** research-only; **no** model fitting, predictions, settlement, production Tier changes or automation mutations.

## Precise dependency and Git state

- Base: `integration/p0-nba-nhl-contract-storage-20261121` @ `c14de84839161f207d6fd7524c18d68b13707365`. This is an integration branch; it is not evidence that P0 has been merged to `main`.
- P2: `research/p2-nhl-sog-original-source-20261121`; stacked draft PR should target the above P0 branch. The PR's actual final head SHA is the authoritative code receipt.
- Reference implementation inspected (not merged or modified): `research/nhl-sog-daily-repair-20261118` @ `4ba7eef27cc2f29dc18ffd5d0b7bbef1e3af4183`, draft PR #183.
- All new P2 code lives in `research/p2_nhl_sog/`; the sole regression test is `tests/test_p2_nhl_source_pipeline.py`. No change to the shared P0 schema, NHL modeling files, NBA/NFL collectors, live automations, or production model/settlement ledgers.

## Root cause diagnosis and owner boundaries

1. The legacy prospective NHL NB2 Deepnote path looks for **both** same-day `live_pool_DATE_afternoon_*.json.gz` and `all_prepared_props_attempts.json`. Their incomplete pair causes `NO_COMPLETE_ORIGINAL_AFTERNOON_SOURCE_YET`. This is not proof that no NHL original archives exist. The November 18 history-repair investigation found 167 two-sided offers but 166 occurrences (54 players) without adequate signed history and one additional native identity gap. Do not replace this legacy admission rule with a new synthetic source format.
2. The registered native NB2 comparison separately searches `reports/v25_sog_source_cert_sprint/<date>/daily_original_gamma_poisson_research_*/daily_research_generation_manifest.json`. The November 20 saved launcher reported `source_batch_count=0`, `native_frozen_count=0`, `NO_ORIGINAL_GAMMA_GENERATOR_YET`. **P4 owns the original frozen Gamma/Poisson artifact.** A P2 source bundle does not replace it.
3. The November 19 signed history preparation retained 495 qualified skaters (321 F, 174 D); its original archived receipts remain independently verifiable but do not constitute a November 21 authenticated sportsbook quote, current game roster, or original Gamma prediction.
4. The first November 21 P2 prospective read-write canary passed P0 storage attestation but exposed a persistent-mount `os.link` restriction. The write path was changed to `O_EXCL` with an independently flushed `.complete` marker and collision detection. A second detached run recovered and verified its persisted failure receipt.
5. The 2026-11-21 21:36:52 UTC one-off exploratory early capture discovered 12 future games for November 21. Attempted original C03 capture for official event `2026020361` was **rejected** with `CohortError:LIVE_SOURCE_FETCH_FAILED:HTTPError`. Rejection attempt SHA: `32dc09130d3d670592ca39e1e652e671c935842f8bf5eb6a08f0b8361973a104`. An unsigned schedule discovery did **not** earn original certification. A narrowly scoped NHL `User-Agent` adapter is now implemented using the **existing C03 canonical archive, signed-field definition, HMAC, and verifier**, not a new signing authority; no successful real capture using that change has yet been independently proven.

## Components and stable callable interfaces

| Module | Contract / owner | Source-only behavior |
|---|---|---|
| `source_pipeline.py` | P2 | NHL scoreboard, schedule windows, team rosters, P0 source receipts, immutable attempt/run records; builds `PregameFeatureSnapshot` and standalone source manifest |
| `official_transport.py` | P2 adapter to existing C03 | NHL-only HTTPS `User-Agent`; original bytes, true observed/received UTC, existing C03 signed fields and HMAC; no publisher-time claim |
| `official_player_capture.py` | P2 | Official ID-bound profile/game logs, candidate prior FINAL witnesses, explicit incompleteness until independent gamecenter final receipts |
| `history_bridge.py` | P2 + existing official history producer | Independent revalidation of signed profile/game log/final inputs, SOG and TOI arrays, trade-preserving historical team, and new P0 `SourceReceipt` mappings |
| `market_capture.py` | P2 | Optional genuine Propline native provider response capture with `X-API-Key`, quota preflight, raw SHA-256 and signed collector possession proof |
| `quote_bridge.py` | P2 | Independent two-sided book-price, event/official-player ID, official signed profile name, stat/period/source-HMAC verification; P0 `MarketQuote`, preserving rejects |
| `service.py` | P2 | `prepare_source_bundle`, `prepare_source_batch`, full input/readiness/rejection ledger; no forecasting |
| `fixtures.py` | P2 to P4 | 14 deterministic synthetic P0-compatible source scenarios, **all** `TEST_ONLY_NOT_CERTIFIABLE` |
| `cli.py` | P2 | `storage`, `rolling`, `verify-bundle`, `fixture`; no model endpoints |
| `run_tests.py` | Isolated QA | Retains live NHL test modules and adds P0's frozen `v2.stat_registry` path **only in the test process**, with no shared-package mutation |

Exact use of approved, immutable manifests:

```python
from research.p2_nhl_sog.source_pipeline import verify_bundle
from research.p2_nhl_sog.service import (
    prepare_source_bundle, prepare_source_batch
)

# P2 producer: supply genuine verified game, signed roster sources,
# original history manifest path + exact SHA, original source pool,
# official player IDs, scheduled freeze and optional authentic two-sided offer.
result = prepare_source_bundle(
    "/work", game=game, schedule_source=schedule_source,
    roster_sources=roster_sources,
    signed_history_manifest_path=history_manifest_relative_path,
    signed_history_manifest_sha256=history_manifest_sha256,
    history_pool=original_history_source_pool,
    player_id=official_nhl_player_id,
    freeze=original_input_freeze_at,
    experiment_id=registered_experiment_id,
    peer_player_ids=source_only_peer_ids,
    market_capture=authentic_market_receipt_or_none,
    original_provider_offer=authentic_structured_offer_or_none,
)

# P4/P5 read: verify exact source closure and P0 features.
if result["status"].startswith("SOURCE_READY"):
    manifest_sha = result["source_bundle"]["receipt"]["sha256"]
    source_manifest, p0_feature = verify_bundle("/work", manifest_sha)
    assert source_manifest["model_predictions_present"] is False
    own = p0_feature["features"]["history"]["own"]
    peers = p0_feature["features"]["history"]["peers"]
```

The **P0 feature record** is `PregameFeatureSnapshot` (`PA-P0/1`) with exact official NHL event/team/player identity, source-receipt IDs, UTC `input_freeze_at`, `feature_sha256`, `reconstruction_class="original"`, original historical SOG/TOI, original signed history receipt identifiers, current roster/position, and real market evidence only when independently verified. It includes no target-game outcome, actual target-game TOI, model parameters, forecast or settlement.

The **P2 manifest** is `PA-P2-NHL-SOG-SOURCE-BUNDLE/1`, archived content-addressed under `/work/research/p2_nhl_sog_original/bundles/<sha>.json`. Fields include `official_nhl_player_id`, `event_id`, `input_freeze_at`, `event_start_at`, `official_schedule_source_sha256`, two `official_roster_source_sha256`, `P0_original_historical_source_record_hashes`, `signed_historical_observation_hashes`, historical counts, optional `P0_quote_record_sha256`, `source_admission`, `registered_experiment`, `p0_feature_snapshot_id`, and `p0_feature_record_sha256`.

**P4 must re-check the registered model cohort conditions** before fitting Poisson, Gamma–Poisson or NB2. In `EXP-V25-NHL-SOG-EXPOSURE-EB-001` the registered Gamma challenger requires >=20 distinct leave-one-out F/D peers and >=200 eligible peer-games with up to 20 each, latest <=20 own histories, at most 10 recent own TOIs and genuine same-contract two-sided offers. P2 never changes tau, eta, TOI grid, prior or likelihood. Native NB2 separately requires a freshly frozen original Gamma artifact from P4. P2 source readiness is not Gamma/NB2 model admission or prospective scientific validation.

## Chronology and retention

Every original source is bounded by `source_available_at <= input_freeze_at < event_start_at`; `source_available_at` records the defensible collector **possession** clock unless the upstream publisher release was independently verified. The HMAC is not a publisher publication signature. Results of previous games are eligible only when individually witnessed as finalized before the target event freeze. Missing timing -> reject/abstain; never substitute game start as final publication.

- P2 raw/research namespace: `/work/research/p2_nhl_sog_original/`; P0 immutable ledger: the **unmodified** attested P0 source/feature/market records.
- `put_once`: collision-safe SHA content IDs, `O_EXCL` initial byte reservation, fsync, separately flushed `.complete` marker, verified read-back. A crashed writer leaves incomplete bytes **untrusted** and they cannot be overwritten or admitted. Attempt records preserve negative evidence.
- `verify_bundle`: rereads manifest SHA, verifies P0 immutable record SHA, verifies every referenced original source body, source time and feature/source closure. It does not validate or recreate model forecasts.
- No sports directory overlap and no modification of NFL, NBA, canonical model-forecast or settlement records.
- NHL roster membership is *not* evidence the player will play; preserve `participation_status=UNKNOWN`. A prior historical team differing from current signed roster raises role-transition uncertainty. Never infer DNP from an absence of a game-log row.

## Authentic quote policy

`market_capture.capture_original_provider` is **optional** and never invoked by the ordinary official-only `rolling` runner, avoiding an unapproved duplicate sportsbook request. It uses native endpoint `https://api.prop-line.com/v1/sports/icehockey_nhl/odds?markets=player_shots_on_goal&bookmakers=...`, `X-API-Key`, `X-Daily-Remaining` preflight, collector timestamp and original body SHA. Missing credentials, quota, signed proof, provider/official crosswalk, official signed player name, original team/event, exact full-game stat/period, line or either original side's price -> source rejection ledger. Never make up -110 prices or admit synthetic fixture quotes as genuine.

Market-dependent registered cohorts **ABSTAIN** without original quotes. Quote-free skaters may enter only a separately designated **line-independent distribution-research** input cohort. They cannot silently enter `EXP-V25-NHL-SOG-EXPOSURE-EB-001`, registered P15 NB2 or native NB2 matched-quote comparisons.

## Synthetic fixture interface

```python
from research.p2_nhl_sog.fixtures import CASES, make_case, all_cases
fixture = make_case("traded_player")
assert fixture["source_admission"] == "TEST_ONLY_NOT_CERTIFIABLE"
feature = fixture["p0_feature"]
```

Available cases: ordinary future game; two-sided synthetic-format quote; sufficient own and peer observations; insufficient history; trade; missing roster; unsupported goalie; quote-free eligible source; role-change uncertainty; late historical final; stale roster receipt; missing/corrupt raw source; wrong player/event crosswalk; duplicate historical game. They are solely for S/O/J or legacy P4 parser integration; they do not establish live API availability, genuine odds, empirical prediction quality or financial edge.

## Exact current Deepnote receipts and independent status

Deepnote project: `9cc31536-93be-44db-bdeb-06fba3f61410`.

1. `eb2e9d0a-2d99-42ca-bc53-719593afcb45`: initial 41-test execution **FAILED** 5 checks (atomic-write race and missing local P0 stat-registry dependency), recorded rather than hidden.
2. `bfe96834-eb11-45b4-afe2-6783af512a68`: corrected previous-revision 41/41 **PASS** with frozen P0 isolated checkout. **Not** evidence the subsequently expanded 49-test revision passed.
3. `a145dc66-2ede-4e4f-a251-372277883faa`: first real storage-attested canary **FAILED** on unsupported hard link; no original NHL receipt.
4. `42bc5407-062b-40da-bce7-02af89550065`: corrected storage-attested source-only rolling check **SUCCESS**, 0 matching standard 60-minute capture windows, 0 signed games/quotes/forecasts; prior failure recorded as receipt SHA `3e3a898756e51629ee28e19a0b61bc58d74ac142b6349370f35a822191fbe55c`.
5. `35773628-3407-4c6e-a293-b87e7bb3e70e`: separate detached read-only Deepnote run **PASS** verifying that exact previous failure-attempt raw 273-byte content, completion marker and SHA persisted between runs. **This is a storage-persistence proof for a P2 attempt, not for original NHL HTTP data.**
6. `d2224aad-c6e4-4839-a9b7-01c55667f87d`: prospective discovery **SUCCESS**, signed official capture **REJECTED** with HTTPError, official event `2026020361`, fail receipt SHA `32dc09130d3d670592ca39e1e652e671c935842f8bf5eb6a08f0b8361973a104`. No originally signed official NHL response was certified.
7. `8088b89e-c7ae-4de7-a5cd-1c2c5c2588bb`: expanded 49-case source QA **FAILED** 4 synthetic P0 history-reference fixture metadata checks; corrected afterwards, full current-head rerun pending. Do not report 49/49 until a new receipt proves it.

P0 storage proof from the November 21 21:33:30 UTC run: `status=STORAGE_ATTESTED_FOR_PROJECT_PATH`, writer receipt SHA `e5fe4929c23f8b7aac9680d59e30083ee891ed46755322fb3e8a4220e7140c13`, reader receipt SHA `2ab6fa006b1c18d4c626986d54d089cebf4bf537c887e212318a1b19434bc185`.

No original P2 game/player/quote source bundle was certified in the recorded canary. No P4 original Gamma model artifact or P5 settlement was created.

## Deployment, verification and rollback

1. Merge/rebase P2 only **after P0 contracts/storage are accepted**, and independent review confirms no P4/NBA/NFL drift. Keep all live schedules unchanged.
2. On isolated Deepnote source execution, preflight `python -m research.p2_nhl_sog.cli storage --root /work` **with** `--root` before the subcommand (see CLI parser); record P0 writer/reader evidence. Ensure existing C03 secret is available without exposing it.
3. Run `python -m research.p2_nhl_sog.cli --root /work rolling --day YYYY-MM-DD --early-minutes 60 --final-minutes 20 --tolerance-minutes 5` in a detached, source-only read-write run. The scheduler intent does not prove a source was actually acquired. If no valid window exists, record an explicit no-capture/missed-window artifact, not a simulated live success.
4. For each player/event, invoke `prepare_source_bundle` with actual validated schedule/roster receipts, source-hashed signed history manifest, explicit peer history IDs and optional original provider offer. Preserve every reject; never silently drop a candidate.
5. Have P4 call `verify_bundle`, apply the **unchanged** registered source/model rules, generate a new original frozen Gamma model artifact and only then run the native NB2 verifier. P4 appends the approved frozen forecast ledger, not P2.
6. P5 independently reads the approved frozen forecast, official final/participation evidence, market/settlement policy and original quote; appends settlement and learning artifacts. It must not write back into P2 evidence.
7. Before any promotion, rerun P2 adversarial tests with a runnable P0 checkout, reproduce source SHA and HMAC, verify a genuine signed source **across two separate persisted runs**, prove accepted quote hashes/prices and identity, and obtain independent audit/review. Code-only PASS is not prospective certification.
8. **Rollback** by disabling only the P2 source invocation or reverting the P2 branch/release commit, leaving existing P0 source records, P2 raw archives, failure attempts, prior NB2/Gamma/Poisson models, original forecasts, settlements, 60/40 benchmark and live automations immutable. Never delete, backdate or replace stored evidence to erase an unsuccessful canary.

## P4/P5 requested gate statuses

| Gate | P2 status | Exact next dependency |
|---|---|---|
| Isolated NHL source branch | **IMPLEMENTED** | Independent PR review and final test rerun |
| Deterministic P0 source/manifest adapters | **IMPLEMENTED; TEST RE-RUN PENDING** | Pass expanded 49-case QA and P0 stable merge |
| Synthetic P4 ingestion fixtures | **IMPLEMENTED** | P4 parser/negative-fixture integration |
| Genuine official schedule/roster capture | **BLOCKED operational certification** | Re-run NHL UA-aware C03 adapter and verify original HMAC/bytes before the freeze |
| Original historical SOG/TOI source proof | **PARTIALLY IMPLEMENTED** | Execute signed-history bridge against persistent originals and reconcile complete skater/peer source population |
| Genuine provider two-sided SOG quotes | **BLOCKED** | Real matched provider response, signed profile/player ID and raw prices; no imputation |
| Complete NHL eligible source bundles | **BLOCKED** | Signed schedule+both rosters+historical P0 receipts, authentic quote for market cohorts, intact source closure |
| Original Gamma model | **BLOCKED / P4 OWNED** | P4 must generate and freeze actual original artifact |
| Native NB2 matched experiment | **BLOCKED / P4 OWNED** | Original Gamma + complete registered original inputs |
| Independent morning settlement | **BLOCKED / P5 OWNED** | Frozen P4 forecast + original official outcome and settlement |
| Production Tier/promotion | **NOT AUTHORIZED** | Separate preregistered prospective validation and independent release approval |

**Conclusion:** Implementation is a research-only, isolated NHL upstream source candidate. It is **not** operationally source-certified until the P2 signed NHL original acquisition, real quote linkage and complete replayable source-manifest conditions pass on a legitimate future event. No synthetic fixture or 41-case earlier test receipt can override that gate.
