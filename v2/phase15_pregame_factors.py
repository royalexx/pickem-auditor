"""Opt-in Phase 1.5 PRE-EVENT opportunity-factor capture (shadow only).

Never converts postgame box-score values into purported pregame factors.
v1 receipt API remains for producer-supplied NHL/NBA factor bundles.
v2 row manifest records AVAILABLE / UNMEASURED / INVALID per factor with
immutable content-addressed artifacts.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any

from .official_nba_nhl_capture import SettlementCaptureError, instant

SCHEMA_RECEIPT_V1 = "phase15_pregame_factor_receipt_v1"
SCHEMA_MANIFEST_V2 = "v25_phase15_pregame_factor_capture_v2"
SCHEMA_BUNDLE_V1 = "v25_phase15_frozen_capture_bundle_v1"
SCHEMA_VERSION = "2.0.0"
DEFAULT_EXPERIMENT = "V25-P1.5-07-PREGAME-FACTOR-CAPTURE"

STATUS_AVAILABLE = "AVAILABLE"
STATUS_UNMEASURED = "UNMEASURED"
STATUS_INVALID = "INVALID"

POSTGAME_FORBIDDEN = re.compile(
    r"^(actual_|postgame_|realized_|boxscore_)", re.IGNORECASE)

NBA_STATS = {"points", "assists", "rebounds", "threes", "pa", "pr", "ra", "pra"}

FIELDS_REQUIRED_V1 = {
    "NHL": (
        "team_unblocked_attempts",
        "probability_active",
        "individual_share_if_active",
        "on_target_probability",
    ),
    "NBA": (
        "projected_minutes",
        "projected_team_possessions",
        "player_usage_or_opportunity_rate",
        "conditional_stat_rate_per_minute",
    ),
}

FACTOR_SPECS: dict[tuple[str, str], tuple[tuple[str, str, str], ...]] = {
    ("NHL", "shots on goal"): (
        ("team_unblocked_attempts", "team_volume", "unblocked_shot_attempts"),
        ("probability_active", "player_participation", "probability"),
        ("individual_share_if_active", "opportunity_share", "share_of_team_attempts"),
        ("on_target_probability", "conditional_efficiency", "on_goal_per_attempt"),
    ),
}

for _stat in NBA_STATS:
    FACTOR_SPECS[("NBA", _stat)] = (
        ("projected_team_possessions", "team_volume", "possessions"),
        ("projected_minutes", "player_participation", "minutes"),
        ("player_usage_or_opportunity_rate", "opportunity_share", "usage_rate"),
        ("conditional_stat_rate_per_minute", "conditional_efficiency", "stat_per_minute"),
    )

del _stat


def _digest_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _digest_obj(obj: Any) -> str:
    return _digest_bytes(
        json.dumps(obj, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False, allow_nan=False).encode("utf-8"))


def _canonical_manifest_body(manifest: dict) -> bytes:
    body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _num(v: Any, name: str) -> float:
    if isinstance(v, bool):
        raise SettlementCaptureError("factor_boolean:" + name)
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError) as exc:
        raise SettlementCaptureError("factor_non_numeric:" + name) from exc
    if not math.isfinite(f):
        raise SettlementCaptureError("factor_nonfinite:" + name)
    return f


def _reject_postgame_keys(obj: dict | None, label: str) -> None:
    if not isinstance(obj, dict):
        return
    for key in obj:
        if POSTGAME_FORBIDDEN.match(str(key)):
            raise SettlementCaptureError("postgame_factor_forbidden:" + label + ":" + key)


def factor_specs(sport: str, stat: str) -> tuple[tuple[str, str, str], ...]:
    key = (sport, stat)
    if key not in FACTOR_SPECS:
        raise SettlementCaptureError("factor_stat_unsupported")
    return FACTOR_SPECS[key]


def validate_factor_row(
    row: dict,
    *,
    sport: str,
    stat: str,
    event_id: str,
    player_id: str,
    event_start: datetime,
    possession_clock: datetime,
) -> dict:
    """Return validated row copy; raise on hard contract violations."""
    if not isinstance(row, dict):
        raise SettlementCaptureError("factor_row_not_object")
    name = row.get("factor_name")
    if not isinstance(name, str) or not name:
        raise SettlementCaptureError("factor_row_name_missing")
    allowed = {t[0] for t in factor_specs(sport, stat)}
    if name not in allowed:
        raise SettlementCaptureError("factor_row_name_unknown:" + name)
    status = row.get("status")
    if status not in (STATUS_AVAILABLE, STATUS_UNMEASURED, STATUS_INVALID):
        raise SettlementCaptureError("factor_row_status_invalid:" + str(status))
    out = dict(row)
    out["factor_name"] = name
    out["status"] = status
    out.setdefault("units", next(u for n, _c, u in factor_specs(sport, stat) if n == name))
    out.setdefault(
        "factor_category",
        next(c for n, c, _u in factor_specs(sport, stat) if n == name),
    )
    out.setdefault("conditioning", "full_game")
    out.setdefault("provenance_status", "shadow_original_runtime_inputs_only")
    if str(row.get("event_id", event_id)) != str(event_id):
        raise SettlementCaptureError("factor_row_event_mismatch")
    if str(row.get("player_id", player_id)) != str(player_id):
        raise SettlementCaptureError("factor_row_player_mismatch")
    out["event_id"] = str(event_id)
    out["player_id"] = str(player_id)
    freeze_at = instant(row.get("input_freeze_at") or row.get("forecast_at") or "")
    forecast_at = instant(row.get("forecast_at") or row.get("input_freeze_at") or "")
    if forecast_at >= event_start:
        status = STATUS_INVALID
        out["status"] = status
        out["invalid_reason"] = "forecast_at_not_before_event_start"
    if status == STATUS_AVAILABLE:
        if row.get("predicted_value") is None:
            raise SettlementCaptureError("factor_available_missing_value:" + name)
        _reject_postgame_keys({"predicted_value": row.get("predicted_value")}, name)
        val = _num(row["predicted_value"], name)
        out["predicted_value"] = val
        src_id = row.get("source_identifier")
        src_hash = row.get("source_content_sha256")
        retrieved = row.get("source_retrieved_at")
        if not src_id or not src_hash or not retrieved:
            raise SettlementCaptureError("factor_available_missing_source:" + name)
        ret = instant(retrieved)
        if ret > possession_clock:
            status = STATUS_INVALID
            out["status"] = status
            out["invalid_reason"] = "source_retrieved_after_capture_clock"
        if ret > freeze_at:
            status = STATUS_INVALID
            out["status"] = status
            out["invalid_reason"] = "source_retrieved_after_input_freeze"
        out["source_identifier"] = str(src_id)
        out["source_content_sha256"] = str(src_hash)
        out["source_retrieved_at"] = ret.isoformat().replace("+00:00", "Z")
        if row.get("source_available_at"):
            out["source_available_at"] = instant(row["source_available_at"]).isoformat().replace(
                "+00:00", "Z"
            )
    elif status == STATUS_UNMEASURED:
        if row.get("predicted_value") is not None:
            raise SettlementCaptureError("factor_unmeasured_must_not_have_value:" + name)
        out["predicted_value"] = None
    else:
        out["predicted_value"] = None
        out.setdefault("invalid_reason", "unspecified")
    out["input_freeze_at"] = freeze_at.isoformat().replace("+00:00", "Z")
    out["forecast_at"] = forecast_at.isoformat().replace("+00:00", "Z")
    if row.get("model_training_cutoff_at"):
        out["model_training_cutoff_at"] = instant(row["model_training_cutoff_at"]).isoformat().replace(
            "+00:00", "Z"
        )
    return out


def _validate_v1_numeric_ranges(sport: str, values: dict[str, float]) -> None:
    if sport == "NHL":
        if values["team_unblocked_attempts"] < 0 or any(
            not 0 <= values[k] <= 1
            for k in (
                "probability_active",
                "individual_share_if_active",
                "on_target_probability",
            )
        ):
            raise SettlementCaptureError("factor_nhl_support_violation")
    else:
        if (
            values["projected_minutes"] < 0
            or values["projected_minutes"] > 80
            or values["projected_team_possessions"] < 0
            or values["player_usage_or_opportunity_rate"] < 0
            or values["conditional_stat_rate_per_minute"] < 0
        ):
            raise SettlementCaptureError("factor_nba_support_violation")


def _rows_from_producer(
    producer: dict,
    *,
    sport: str,
    stat: str,
    event_id: str,
    player_id: str,
    event_start: datetime,
    possession_clock: datetime,
    input_freeze_at: str,
    forecast_at: str,
    model_training_cutoff_at: str | None,
    source_root: Path | None,
) -> list[dict]:
    _reject_postgame_keys(producer.get("factors"), "producer_factors")
    _reject_postgame_keys(producer, "producer_payload")
    factors = producer.get("factors")
    if factors is not None and not isinstance(factors, dict):
        raise SettlementCaptureError("producer_factors_not_object")
    sources = producer.get("source_receipts") or []
    if factors and not isinstance(sources, list):
        raise SettlementCaptureError("factor_original_sources_missing")
    source_by_path: dict[str, dict] = {}
    if source_root is not None and sources:
        root = source_root.resolve()
        for sr in sources:
            if not isinstance(sr, dict):
                raise SettlementCaptureError("factor_source_invalid")
            relative = sr.get("archive_path")
            hash_ = sr.get("sha256")
            if not isinstance(relative, str) or not relative or relative.startswith("/"):
                raise SettlementCaptureError("factor_unsafe_source")
            path = (root / relative).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise SettlementCaptureError("factor_source_missing")
            if not isinstance(hash_, str) or _digest_bytes(path.read_bytes()) != hash_:
                raise SettlementCaptureError("factor_source_hash_mismatch")
            source_by_path[relative] = sr
    rows: list[dict] = []
    for fname, _cat, units in factor_specs(sport, stat):
        base = {
            "factor_name": fname,
            "units": units,
            "conditioning": "full_game",
            "event_id": str(event_id),
            "player_id": str(player_id),
            "input_freeze_at": input_freeze_at,
            "forecast_at": forecast_at,
            "provenance_status": "shadow_original_runtime_inputs_only",
        }
        if model_training_cutoff_at:
            base["model_training_cutoff_at"] = model_training_cutoff_at
        if isinstance(factors, dict) and fname in factors:
            sr = sources[0] if len(sources) == 1 else None
            if sr is None and sources:
                sr = sources[0]
            row = {
                **base,
                "status": STATUS_AVAILABLE,
                "predicted_value": factors[fname],
                "source_identifier": (sr or {}).get("archive_path", producer.get("source_identifier", "producer_inline")),
                "source_content_sha256": (sr or {}).get("sha256", producer.get("source_content_sha256", "0" * 64)),
                "source_retrieved_at": (sr or {}).get("retrieved_at", producer.get("source_retrieved_at", forecast_at)),
            }
            if sr and sr.get("source_available_at"):
                row["source_available_at"] = sr["source_available_at"]
        else:
            row = {**base, "status": STATUS_UNMEASURED, "predicted_value": None}
        rows.append(
            validate_factor_row(
                row,
                sport=sport,
                stat=stat,
                event_id=event_id,
                player_id=player_id,
                event_start=event_start,
                possession_clock=possession_clock,
            )
        )
    if isinstance(factors, dict) and factors:
        values = {k: _num(factors[k], k) for k in FIELDS_REQUIRED_V1[sport] if k in factors}
        if set(values) == set(FIELDS_REQUIRED_V1[sport]):
            _validate_v1_numeric_ranges(sport, values)
    return rows


def build_contract_capture(
    contract: dict,
    *,
    possession_clock: datetime,
    source_root: Path | None = None,
) -> dict:
    sport = contract.get("sport")
    stat = contract.get("stat")
    if sport not in ("NHL", "NBA"):
        raise SettlementCaptureError("factor_sport_unsupported")
    try:
        factor_specs(sport, str(stat))
    except SettlementCaptureError:
        raise
    for key in ("event_id", "player_id", "event_start"):
        if not contract.get(key):
            raise SettlementCaptureError("factor_identity_missing:" + key)
    event_start = instant(contract["event_start"])
    input_freeze = contract.get("input_freeze_at") or contract.get("forecast_at")
    forecast = contract.get("forecast_at") or input_freeze
    if not input_freeze or not forecast:
        raise SettlementCaptureError("factor_timing_missing")
    producer = contract.get("producer_factors") or {}
    rows = _rows_from_producer(
        producer,
        sport=sport,
        stat=str(stat),
        event_id=str(contract["event_id"]),
        player_id=str(contract["player_id"]),
        event_start=event_start,
        possession_clock=possession_clock,
        input_freeze_at=input_freeze,
        forecast_at=forecast,
        model_training_cutoff_at=contract.get("model_training_cutoff_at"),
        source_root=source_root,
    )
    return {
        "sport": sport,
        "stat": stat,
        "market_stat_definition": stat,
        "event_id": str(contract["event_id"]),
        "player_id": str(contract["player_id"]),
        "game_date": contract.get("game_date") or contract["event_start"][:10],
        "event_start": instant(contract["event_start"]).isoformat().replace("+00:00", "Z"),
        "forecast_at": instant(forecast).isoformat().replace("+00:00", "Z"),
        "input_freeze_at": instant(input_freeze).isoformat().replace("+00:00", "Z"),
        "original_forecast_contract_id": contract.get("original_forecast_contract_id")
        or contract.get("contract_id"),
        "model_version": contract.get("model_version"),
        "factor_rows": rows,
    }


def build_capture_manifest(
    bundle: dict,
    *,
    source_root: Path | None,
    observed_clock: str,
    include_negative_control: bool = False,
) -> dict:
    bundle_schema = bundle.get("schema")
    if bundle_schema is not None and bundle_schema != SCHEMA_BUNDLE_V1:
        raise SettlementCaptureError("capture_bundle_schema_invalid")
    contracts_in = bundle.get("contracts")
    if not isinstance(contracts_in, list) or not contracts_in:
        raise SettlementCaptureError("capture_bundle_empty")
    possession = instant(observed_clock)
    experiment_id = bundle.get("experiment_id") or DEFAULT_EXPERIMENT
    run_id = bundle.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise SettlementCaptureError("capture_run_id_missing")
    model_version = bundle.get("model_version") or "shadow-uncertified"
    captures = [
        build_contract_capture(c, possession_clock=possession, source_root=source_root)
        for c in contracts_in
    ]
    manifest: dict[str, Any] = {
        "schema": SCHEMA_MANIFEST_V2,
        "schema_version": SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "run_id": run_id,
        "capture_run_at": possession.isoformat().replace("+00:00", "Z"),
        "model_version": model_version,
        "original_forecast_model_version": bundle.get("original_forecast_model_version")
        or model_version,
        "production_promotion_allowed": False,
        "tier1_tier2_publication_allowed": False,
        "source_status": "shadow_original_runtime_inputs_only",
        "contracts": captures,
        "row_count": sum(len(c["factor_rows"]) for c in captures),
        "contract_count": len(captures),
        "four_factor_attribution_possible": False,
        "four_factor_attribution_note": (
            "Set true only when every contract has all four categories AVAILABLE "
            "from authentic pregame sources; never from postgame boxes."
        ),
    }
    available_by_cat: dict[str, int] = {}
    for cap in captures:
        for row in cap["factor_rows"]:
            if row["status"] == STATUS_AVAILABLE:
                available_by_cat[row["factor_category"]] = (
                    available_by_cat.get(row["factor_category"], 0) + 1
                )
    required_cats = {"team_volume", "player_participation", "opportunity_share", "conditional_efficiency"}
    if (
        captures
        and all(
            required_cats <= {r["factor_category"] for r in c["factor_rows"] if r["status"] == STATUS_AVAILABLE}
            for c in captures
        )
        and manifest["row_count"] == len(captures) * 4
    ):
        manifest["four_factor_attribution_possible"] = True
        manifest["four_factor_attribution_note"] = (
            "All contracts report four AVAILABLE pregame factors; oracle attribution "
            "may proceed only under Phase 1.5 preregistered diagnostics."
        )
    manifest["available_factor_rows_by_category"] = available_by_cat
    if include_negative_control:
        manifest["negative_control_receipt"] = synthetic_negative_control_receipt(possession)
    digest = _digest_bytes(_canonical_manifest_body(manifest))
    manifest["manifest_sha256"] = digest
    return manifest


def synthetic_negative_control_receipt(possession_clock: datetime) -> dict:
    """Explicit INVALID row: source retrieved after freeze (test fixture)."""
    event = datetime(2099, 1, 2, 0, 0, tzinfo=timezone.utc)
    freeze = datetime(2099, 1, 1, 12, 0, tzinfo=timezone.utc)
    row = {
        "factor_name": "team_unblocked_attempts",
        "status": STATUS_INVALID,
        "predicted_value": None,
        "event_id": "negative-control-event",
        "player_id": "negative-control-player",
        "input_freeze_at": freeze.isoformat().replace("+00:00", "Z"),
        "forecast_at": freeze.isoformat().replace("+00:00", "Z"),
        "source_retrieved_at": "2099-01-01T13:00:00Z",
        "invalid_reason": "negative_control_source_after_freeze",
    }
    validated = validate_factor_row(
        row,
        sport="NHL",
        stat="shots on goal",
        event_id="negative-control-event",
        player_id="negative-control-player",
        event_start=event,
        possession_clock=possession_clock,
    )
    return {
        "control_id": "V25-P1.5-07-NC-001",
        "expected_status": STATUS_INVALID,
        "factor_row": validated,
        "receipt_sha256": _digest_obj(validated),
    }


def capture_artifact_paths(output_dir: Path, manifest: dict) -> tuple[Path, Path]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    digest = manifest["manifest_sha256"]
    manifest_path = output_dir / f"phase15_factor_capture_{digest[:16]}.json"
    index_path = output_dir / "capture_index.jsonl"
    return manifest_path, index_path


def write_capture_manifest(
    manifest: dict,
    output_dir: Path,
    *,
    allow_supersession: bool = False,
) -> dict:
    manifest_path, index_path = capture_artifact_paths(output_dir, manifest)
    if manifest_path.exists() and not allow_supersession:
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("manifest_sha256") == manifest["manifest_sha256"]:
            return {
                "written": False,
                "reason": "identical_capture_exists",
                "path": str(manifest_path),
                "manifest_sha256": manifest["manifest_sha256"],
            }
        raise SettlementCaptureError("duplicate_capture_path_hash_collision")
    key = {
        "experiment_id": manifest["experiment_id"],
        "run_id": manifest["run_id"],
        "manifest_sha256": manifest["manifest_sha256"],
    }
    if index_path.exists():
        for line in index_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            prior = json.loads(line)
            if (
                prior.get("experiment_id") == key["experiment_id"]
                and prior.get("run_id") == key["run_id"]
                and prior.get("manifest_sha256") != key["manifest_sha256"]
                and not allow_supersession
            ):
                raise SettlementCaptureError("duplicate_capture_key_run_id")
    payload = json.dumps(manifest, sort_keys=True, indent=2, allow_nan=False) + "\n"
    tmp = manifest_path.with_suffix(".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, manifest_path)
    with index_path.open("a", encoding="utf-8") as index:
        index.write(
            json.dumps(
                {
                    **key,
                    "path": manifest_path.name,
                    "capture_run_at": manifest["capture_run_at"],
                    "contract_count": manifest["contract_count"],
                },
                sort_keys=True,
            )
            + "\n"
        )
    return {
        "written": True,
        "path": str(manifest_path),
        "manifest_sha256": manifest["manifest_sha256"],
        "index_path": str(index_path),
    }


def manifest_canonical_hash(manifest: dict) -> str:
    return _digest_bytes(_canonical_manifest_body(manifest))


def shadow_capture_from_evaluated(
    evaluated_contracts: list[dict],
    *,
    run_id: str,
    experiment_id: str,
    observed_clock: datetime,
    source_root: Path | None = None,
) -> dict | None:
    """Build manifest from pipeline attempt receipts; never mutates inputs."""
    forecasts = [r for r in evaluated_contracts if r.get("status") == "forecast"]
    if not forecasts:
        return None
    bundle_contracts = []
    for item in forecasts:
        meta = item.get("meta") or {}
        parsed = item.get("sport"), item.get("stat")
        if not item.get("sport") or not item.get("stat"):
            continue
        bundle_contracts.append(
            {
                "sport": item["sport"],
                "stat": item["stat"],
                "event_id": meta.get("event_id") or item.get("event_id"),
                "player_id": meta.get("player_id") or item.get("player_id"),
                "game_date": meta.get("game_date") or item.get("game_date"),
                "event_start": meta.get("event_start") or item.get("event_start"),
                "forecast_at": meta.get("forecast_at") or item.get("forecast_at"),
                "input_freeze_at": meta.get("input_freeze_at") or meta.get("forecast_at"),
                "original_forecast_contract_id": item.get("id"),
                "model_version": meta.get("model_version") or "pipeline_shadow",
                "producer_factors": meta.get("producer_factors") or {},
            }
        )
    if not bundle_contracts:
        return None
    bundle = {
        "schema": SCHEMA_BUNDLE_V1,
        "experiment_id": experiment_id,
        "run_id": run_id,
        "model_version": "pipeline_shadow_uncertified",
        "contracts": bundle_contracts,
    }
    return build_capture_manifest(
        bundle,
        source_root=source_root,
        observed_clock=observed_clock.isoformat().replace("+00:00", "Z"),
    )


def integrate_shadow_factor_capture(
    evaluated_contracts: list[dict],
    *,
    run_id: str,
    output_root: Path,
    observed_clock: datetime,
    data_root: Path | None = None,
) -> dict:
    """Opt-in hook: no-op unless caller invoked from jobs with env gate."""
    manifest = shadow_capture_from_evaluated(
        evaluated_contracts,
        run_id=run_id,
        experiment_id=DEFAULT_EXPERIMENT,
        observed_clock=observed_clock,
        source_root=data_root,
    )
    if manifest is None:
        return {"captured": False, "reason": "no_forecast_contracts"}
    out_dir = output_root / "phase15_factor_captures"
    receipt = write_capture_manifest(manifest, out_dir)
    return {"captured": True, "receipt": receipt, "contract_count": manifest["contract_count"]}


# --- v1 producer receipt API (backward compatible) ---


def validate_pregame_factor_receipt(receipt, *, source_root, possession_clock):
    """Validate origin, timing, support. Never assert empirical skill."""
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA_RECEIPT_V1:
        raise SettlementCaptureError("factor_schema_missing")
    sport = receipt.get("sport")
    stat = receipt.get("stat")
    if sport not in ("NHL", "NBA") or (sport == "NHL" and stat != "shots on goal") or (
        sport == "NBA" and stat not in NBA_STATS
    ):
        raise SettlementCaptureError("factor_stat_unsupported")
    for key in ("event_id", "player_id", "model_version", "period"):
        if not isinstance(receipt.get(key), str) or not receipt[key]:
            raise SettlementCaptureError("factor_identity_missing:" + key)
    if receipt["period"] != "full":
        raise SettlementCaptureError("factor_period_invalid")
    now = instant(possession_clock)
    cap = instant(receipt.get("captured_at"))
    event = instant(receipt.get("event_start"))
    cutoff = instant(receipt.get("model_training_cutoff_at"))
    if cap != now:
        raise SettlementCaptureError("factor_capture_clock_not_runtime")
    if cap >= event or cutoff > cap:
        raise SettlementCaptureError("factor_not_genuinely_pregame")
    sources = receipt.get("source_receipts")
    if not isinstance(sources, list) or not sources:
        raise SettlementCaptureError("factor_original_sources_missing")
    root = Path(source_root).resolve()
    refs = set()
    for sr in sources:
        if not isinstance(sr, dict):
            raise SettlementCaptureError("factor_source_invalid")
        relative = sr.get("archive_path")
        hash_ = sr.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or relative.startswith("/")
            or ("\\" in relative or ".." in relative.split("/"))
        ):
            raise SettlementCaptureError("factor_unsafe_source")
        if relative in refs:
            raise SettlementCaptureError("factor_duplicate_source")
        refs.add(relative)
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise SettlementCaptureError("factor_source_missing")
        if not isinstance(hash_, str) or _digest_bytes(path.read_bytes()) != hash_:
            raise SettlementCaptureError("factor_source_hash_mismatch")
        if instant(sr.get("retrieved_at")) > cap:
            raise SettlementCaptureError("factor_future_source")
    values = receipt.get("factors")
    if not isinstance(values, dict) or set(values) != set(FIELDS_REQUIRED_V1[sport]):
        raise SettlementCaptureError("factor_fields_missing_or_unrecognized")
    _reject_postgame_keys(values, "v1_factors")
    val = {key: _num(values[key], key) for key in FIELDS_REQUIRED_V1[sport]}
    if sport == "NHL":
        if val["team_unblocked_attempts"] < 0 or any(
            not 0 <= val[k] <= 1
            for k in (
                "probability_active",
                "individual_share_if_active",
                "on_target_probability",
            )
        ):
            raise SettlementCaptureError("factor_nhl_support_violation")
        exp = (
            val["team_unblocked_attempts"]
            * val["probability_active"]
            * val["individual_share_if_active"]
            * val["on_target_probability"]
        )
        if receipt.get("factorization") != "nhl_SOG_unblocked_team_attempt_product_v1":
            raise SettlementCaptureError("factor_nhl_model_definition_missing")
        provided = _num(receipt.get("implied_mean"), "nhl_implied_mean")
        if abs(provided - exp) > max(1e-8, 1e-6 * max(1, exp)):
            raise SettlementCaptureError("factor_nhl_product_not_coherent")
    else:
        if (
            val["projected_minutes"] < 0
            or val["projected_minutes"] > 80
            or val["projected_team_possessions"] < 0
            or val["player_usage_or_opportunity_rate"] < 0
            or val["conditional_stat_rate_per_minute"] < 0
        ):
            raise SettlementCaptureError("factor_nba_support_violation")
        if receipt.get("factorization") != "nba_diagnostic_nonmultiplicative_v1":
            raise SettlementCaptureError("factor_nba_invalid_multiplicative_claim")
        if receipt.get("implied_mean") is not None:
            raise SettlementCaptureError("factor_nba_combo_mean_not_identified_from_fields")
    if receipt.get("production_promotion_allowed") is not False:
        raise SettlementCaptureError("factor_promotion_guard_missing")
    if receipt.get("source_status") != "shadow_original_runtime_inputs_only":
        raise SettlementCaptureError("factor_status_not_shadow")
    return {
        "valid_structure": True,
        "source_count": len(sources),
        "factor_field_count": len(val),
        "original_pregame_receipt_verified": True,
        "empirical_forecast_skill_verified": False,
        "released_to_production": False,
    }


def make_shadow_receipt(raw, *, source_root, observed_clock):
    """Stamp runtime first, reject post-event claims, then append only by caller."""
    if not isinstance(raw, dict):
        raise SettlementCaptureError("factor_raw_payload_not_dict")
    _reject_postgame_keys(raw.get("factors"), "v1_raw")
    candidate = dict(raw)
    candidate["schema"] = SCHEMA_RECEIPT_V1
    candidate["captured_at"] = observed_clock
    candidate["source_status"] = "shadow_original_runtime_inputs_only"
    candidate["production_promotion_allowed"] = False
    validated = validate_pregame_factor_receipt(
        candidate, source_root=source_root, possession_clock=observed_clock
    )
    candidate["validation_receipt"] = validated
    candidate["receipt_sha256"] = _digest_obj(candidate)
    return candidate


def producer_payload_to_v2_bundle(raw: dict, *, run_id: str, experiment_id: str | None = None) -> dict:
    """Wrap a single v1 producer dict as a one-contract frozen bundle."""
    sport = raw.get("sport")
    stat = raw.get("stat")
    if sport not in ("NHL", "NBA"):
        raise SettlementCaptureError("factor_sport_unsupported")
    return {
        "schema": SCHEMA_BUNDLE_V1,
        "experiment_id": experiment_id or DEFAULT_EXPERIMENT,
        "run_id": run_id,
        "model_version": raw.get("model_version"),
        "contracts": [
            {
                "sport": sport,
                "stat": stat,
                "event_id": raw["event_id"],
                "player_id": raw["player_id"],
                "event_start": raw["event_start"],
                "game_date": raw.get("game_date") or raw["event_start"][:10],
                "forecast_at": raw.get("forecast_at") or raw.get("captured_at"),
                "input_freeze_at": raw.get("input_freeze_at") or raw.get("forecast_at"),
                "model_training_cutoff_at": raw.get("model_training_cutoff_at"),
                "model_version": raw.get("model_version"),
                "producer_factors": {
                    "factors": raw.get("factors"),
                    "source_receipts": raw.get("source_receipts"),
                },
            }
        ],
    }


LIVE_INTEGRATION_NOTE = """
Subsequent live prospective capture (not enabled in this ticket):
1. After phase0_pre_eval pin succeeds in scripts/jobs.run_pipeline_batch, attach
   producer-supplied factor payloads to meta['producer_factors'] from the engine
   that actually emits them (never from postgame settlement).
2. Set PICKEM_PHASE15_FACTOR_CAPTURE=1 on an approved shadow runner only.
3. integrate_shadow_factor_capture() appends under reports/phase15_factor_captures/
   without modifying snapshot rows or certification flags.
4. Independently verify manifest_sha256 and capture_index.jsonl before Phase 1.5
   oracle attribution consumes rows.
"""
