# V2.5 Phase 1.5 — Pregame opportunity factor capture (V25-P1.5-07)

**Status:** shadow-only instrumentation on branch `work/v25-phase15-factor-capture`  
**Governing plan:** PA-V25-MASTER-2026-11-09 / v1.1  
**Promotion:** `production_promotion_allowed` and `tier1_tier2_publication_allowed` are always false in capture artifacts.

## Purpose

Persist genuinely pregame, time-frozen opportunity-factor evidence for later Phase 1.5 error attribution and the Phase 2/3 investment gate. This does **not** build a new forecasting model and does **not** enable four-factor Shapley attribution unless authentic pregame factor predictions exist.

## Schemas

### Frozen input bundle — `v25_phase15_frozen_capture_bundle_v1`

```json
{
  "schema": "v25_phase15_frozen_capture_bundle_v1",
  "experiment_id": "V25-P1.5-07-PREGAME-FACTOR-CAPTURE",
  "run_id": "<uuid-or-run-stamp>",
  "model_version": "shadow-uncertified",
  "contracts": [
    {
      "sport": "NHL",
      "stat": "shots on goal",
      "event_id": "...",
      "player_id": "...",
      "game_date": "YYYY-MM-DD",
      "event_start": "ISO-8601Z",
      "forecast_at": "ISO-8601Z",
      "input_freeze_at": "ISO-8601Z",
      "model_training_cutoff_at": "ISO-8601Z",
      "original_forecast_contract_id": "...",
      "producer_factors": {
        "factors": { },
        "source_receipts": [ ]
      }
    }
  ]
}
```

Omitted `producer_factors` or partial factor dicts yield per-factor **`UNMEASURED`** rows (never imputed). Numeric factors without a **per-factor verified source receipt** (via `factor_names` on a `source_receipts` entry or `factor_source_receipts[factor_name]`) are recorded **`INVALID`**, never `AVAILABLE`. Placeholder digests (`0`*64), inline source ids, and unarchived bytes are rejected.

### Output manifest — `v25_phase15_pregame_factor_capture_v2`

Each contract carries `factor_rows` with:

| Field | Description |
| --- | --- |
| `factor_name` | Canonical factor id |
| `factor_category` | `team_volume`, `player_participation`, `opportunity_share`, `conditional_efficiency` |
| `status` | `AVAILABLE`, `UNMEASURED`, or `INVALID` |
| `predicted_value` | Numeric when `AVAILABLE`; otherwise null |
| `source_*` / timestamps | Required for `AVAILABLE`; chronology checked vs `input_freeze_at` and capture clock |
| `provenance_status` | `shadow_original_runtime_inputs_only` |

Manifest includes `manifest_sha256` over all fields except itself. Artifacts are content-addressed under `reports/phase15_factor_captures/` with an append-only `capture_index.jsonl`.

### Legacy producer receipt — `phase15_pregame_factor_receipt_v1`

Unchanged v1 path for fully specified NHL/NBA producer payloads via `make_shadow_receipt`.

## CLI

```bash
# v1 producer receipt (all factors required)
python scripts/capture_phase15_pregame_factors.py \
  --mode producer \
  --input path/to/producer.json \
  --source-root path/to/archive \
  --output path/to/new_receipt.json

# v2 bundle manifest (missing factors -> UNMEASURED)
python scripts/capture_phase15_pregame_factors.py \
  --mode bundle \
  --input path/to/bundle.json \
  --source-root path/to/archive \
  --output reports/phase15_factor_captures \
  --run-id manual-offline-test-001 \
  --negative-control
```

## Opt-in production hook

`scripts/jobs.run_snapshot` calls factor capture only when `PICKEM_PHASE15_FACTOR_CAPTURE=1`. Default (unset) has **zero effect** on probabilities, certification, or snapshot rows. Scheduled production must not enable this flag without separate approval.

## Live prospective integration (next step)

See `LIVE_INTEGRATION_NOTE` in `v2/phase15_pregame_factors.py`: attach verified `meta['producer_factors']` after Phase 0R pin, enable env flag on an approved shadow runner, verify manifest hashes before oracle consumption.

## Composer executor-governance conflict

Recorded in `docs/architecture_decisions/ADR-2026-11-12-composer-phase15-factor-capture.md`.
