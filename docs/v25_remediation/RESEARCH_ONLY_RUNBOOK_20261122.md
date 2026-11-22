# Pick’em Auditor V2.5 — research-only NBA/NHL SOG runbook (2026-11-22)

**Status: NOT ACTIVATED.** This is an executable source/inventory runbook for the existing integrated owner modules. No forecast or model update is authorized by the commands alone. All observed failures must be retained, not silently retried after tipoff/puck drop.

## Verified environment and initial safety checks

Project: `9cc31536-93be-44db-bdeb-06fba3f61410`. The approved Deepnote alias `/work` resolves to `/datasets/_deepnote_work`; P0's original cross-detached attestation, strict project-ID checks and immutable SHA requirements remain mandatory. Run from a **pinned exact Git checkout** of `integration/v25-p0-p6-remediation-20261122` only for isolated research/QA, with Python import dependencies from that same checkout. Do not use a sparse checkout that omits `scripts/population_normalizers.py` and `scripts/population_history.py`: the native WS1 adapter imports these original dependencies. Do not substitute empty stub modules.

Read-only inventory before any source-capture attempt:

```bash
git rev-parse HEAD
DAY=$(TZ=America/Toronto date +%F)
AS_OF=$(date -u +%Y-%m-%dT%H:%M:%SZ)
python -m scripts.p5_daily_research --as-of "$AS_OF" --root /work --mode inventory
```

The inspected canonical P0 root on November 22 contained eight NBA ExperimentManifest records and **zero** SourceReceipt, PregameFeatureSnapshot, ModelArtifact, ForecastSnapshot, OutcomeRecord, SettlementRecord, TrainingUpdateReceipt, and MarketQuote records. Thus `research-settle` MUST NOT be used as proof of any pregame original or new eligible observation.

## Original NBA rolling source-only invocation

```bash
DAY=$(TZ=America/Toronto date +%F)
python -m research.nba_p1_original.rolling --day "$DAY" --no-wait
```

NBA P1 **reuses** the existing six-file `v2.nba_ws1` producer, does not implement a second network collector, and uses `source_listed_subset`. `--no-wait` captures only when genuinely within a source window; `NOT_DUE`, `MISSED_FREEZE`, `BLOCKED_CAPTURE`, `BLOCKED_DUPLICATE_CAPTURE` and schedule failures must be counted. Do not treat an accepted roster candidate as confirmed participation. Existing P1 windows are early T−70 to T−50 minutes and final T−35 to T−20 minutes, per actual scheduled game. Matinees and simultaneous games require a dispatcher active early enough.

P1's initially discovered same-day immutable manifest collision was repaired without overwriting any prior `daily_manifest.json`: each invocation now writes `runs/YYYY-MM-DD/<policy-run-key>/daily_manifests/<content-sha>.json`. Repeated original claims remain exclusively guarded. New attempt receipts are content-addressed so successive blocked/accepted outcomes cannot collide merely because their observed timestamp is identical. **The P1 development vault is not the canonical shared P0 forecast vault.** Source archive promotion requires verified P0 identity, receipt hashes and independent approval.

## Original NHL source-only invocation

```bash
DAY=$(TZ=America/Toronto date +%F)
python -m research.p2_nhl_sog.cli --root /work rolling --day "$DAY" --max-games 4
```

This command fetches actual schedule-discovery evidence; it signs original official schedule and both team rosters only if called inside P2's authentic event-relative early/final source windows. It never fabricates historical SOG/TOI or sportsbook offers. A successful `SIGNED_GAME_AND_ROSTERS_ONLY` response still requires signed prior-game player observations and, for quote-qualified native NB2, the exact genuine two-sided offer. `source_verified_incomplete` is not a frozen forecast. The observed November 22 probe recorded zero eligible official in-window games and zero frozen predictions. Preserve its append-only run receipt.

## Model generation — gated, not automatically scheduled

NBA P3 is invoked only after an independently source-verified canonical P0 feature/model/source request already exists:

```bash
python -m research.nba_p3_frozen.cli "$P0_ORIGINAL_REQUEST_JSON" --persist --storage-root /work
```

Abort if `P0_ORIGINAL_REQUEST_JSON` is unset or points to reconstructed/postgame data. P3 checks the complete immutable request contract and must reject absent original model artifacts or late source timestamps. Source-listed S0 forecasts need explicit conditional-on-played interpretation; advanced O/J/C native witnesses cannot be bypassed by passing the P3 synthetic suite.

NHL P4's original and quote-free research entry points are separately defined by the existing code:

```bash
python -m scripts.p4_nhl_sog_generate --mode distribution --input "$P2_SOURCE_VERIFIED_DISTRIBUTION_BUNDLE" --source-root /work --artifact-root /work/research/nhl_sog_p4 --code-commit "$(git rev-parse HEAD)"
```

Do not execute without a **genuine, verified pregame** distribution-only P2 bundle and accepted input schema. The quote-qualified `--mode original` path additionally requires the separate original Gamma / exact plugin-Poisson mean and matched genuine two-sided quote; native fixed NB2 shape remains 4 and NHL C10 stays locked to 40 distinct eligible Toronto slate dates. P4 runs only as the forecaster, not as an independent NHL source collector.

## Morning workflow — gated settlement/learning

When eligible genuine original frozen NBA/NHL forecasts eventually exist, the accepted P5 warehouse reader must independently verify source/model/forecast SHAs, chronological cutoffs and official FINAL results before appending any correction-preserving settlement record. Until then, use only:

```bash
AS_OF=$(date -u +%Y-%m-%dT%H:%M:%SZ)
python -m scripts.p5_daily_research --as-of "$AS_OF" --root /work --mode inventory
```

`--mode research-settle --confirm-isolated` is an **explicit, opt-in research write** and is NOT authorized for ordinary automated operation while the genuine original-source, independent official FINAL, and P6 gates remain blocked. An updated model version requires an owner-approved fitting method, changed parameters, training-data SHA, observation availability cutoff, validation, immutable registry transition, and later-only forecast selection. Absent eligible observations return `NO_ELIGIBLE_UPDATE`; absent fitting approval return `PREDICTION_ONLY` or `UPDATE_METHOD_NOT_APPROVED`. Synthetic Alpha/Beta changes in the Deepnote registry canary are not fitted official models.

## Recovery, chronology and resource policy

- Maintain **one original source owner per sport**, independent stage failures, no backdated replacement records and no duplicate work queued merely because a first attempt failed.
- No NUTS campaign, paid data source, paid GitHub Actions training, model promotion, sportsbook edge claim, or trusted Tier publication.
- Fail closed on altered source bytes, missing original availability time, mismatched player/event/line, unknown participation, invalid model training cutoff, unsupported registered model kind or invalid official FINAL.
- Keep the earlier owner SHA, main SHA `912bc7010058092ea735dcda0aa941429194474b`, previously pinned notebook IDs and old exact automation definitions available for **future** rollback if a separately authorized cutover occurs. None was changed on November 22.
- The synthetic P5 Deepnote project-mount stress test used two distinct competing OS processes; a separate detached readonly process independently verified versions 1→2→3→rollback-to-1. The test does **not** promise power-loss durability, external backups, or legitimate state learning.
- Development and unit suites are CPU-only and avoid model refit. Recorded unified detached QA parent-process maximum RSS was approximately 250 MB; that is not a measured ceiling for a future full live collector/model run.
- A later authentic pregame + official FINAL lifecycle is mandatory for operational PASS. Preserve all source failures as specific `BLOCKED`, `MISSED`, `UNRESOLVED` or `ABSTAIN` receipts. Nothing generated retrospectively can be relabeled original.

## Current existing automation owners (unchanged)

| Owner | Existing task ID | Verified activation |
|---|---|---|
| NBA original pilot | `6afa51eeb1488191956f2d672edf6d33` | Disabled, fixed six-day pilot expired; **not re-enabled** |
| NHL SOG shadow | `6af480bda1448191b892f43091479f8d` | Enabled daily 17:30 America/Toronto, prior legacy shadow scope retained |
| Morning settlement | `Automation_12f6ba43eb748191a213917780254329` | Enabled daily 06:00 America/Toronto, NFL and other responsibilities untouched |

A future accepted activation must preserve full existing task prompts/schedules/code pins in a private immutable rollback receipt first, change **only** the authorized existing task, and independently re-inspect the saved definition and subsequent Deepnote execution. Do not add duplicate ChatGPT tasks.
