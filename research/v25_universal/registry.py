"""Discover new frozen model snapshots by original-source manifest, never by engine whitelist.

A researcher publishes a create-once manifest under /work/reports/v25_model_registry.
A filename, mtime or later annotation NEVER proves forecast pregame chronology.
All candidate engines, including O1-O5, J3, new NHL/NBA models, share the same
explicit immutable registration contract. Missing/invalid forecasts are abstentions.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
import hashlib, json, math, re
from v2.nba_ws1.store import instant

SCHEMA = "V25FrozenResearchManifest/1"
ROW_SCHEMA = "V25FrozenResearchForecast/1"
ROOT = "reports/v25_model_registry"
_SHA = re.compile(r"^[a-f0-9]{64}$")
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,79}$")
_ALLOWED_CONDITIONING = {"given_played", "conditional_nonpush", "unconditional"}
_ALLOWED_SPORTS = {"NFL", "NBA", "NHL"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _num(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("NONFINITE_OR_INVALID_NUMBER")
    return float(value)


def _path(base, relative):
    if not isinstance(relative, str) or relative.startswith("/") or "\\" in relative:
        raise ValueError("UNSAFE_RELATIVE_PATH")
    p = base / relative
    if p.is_symlink() or not p.resolve().is_relative_to(base.resolve()):
        raise ValueError("REGISTRY_PATH_ESCAPE")
    return p


def _chronology(row):
    keys = ("source_received_at", "input_freeze_at", "forecast_at",
            "event_start_at", "model_training_cutoff_at")
    values = [instant(row[k]) for k in keys]
    if not (values[0] <= values[1] <= values[2] < values[3] and values[4] <= values[1]):
        raise ValueError("MODEL_SAME_GAME_OR_POST_FREEZE_LEAKAGE")


def _normalize_distribution(row):
    data = row.get("distribution")
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("DISTRIBUTION_NOT_OBJECT")
    if data.get("kind") == "discrete":
        points = data.get("masses")
        if not isinstance(points, list) or not points or len(points) > 10000:
            raise ValueError("INVALID_DISCRETE_SUPPORT")
        values = [(_num(pair[0]), _num(pair[1])) for pair in points
                  if isinstance(pair, list) and len(pair) == 2]
        if len(values) != len(points) or any(p < 0 for _, p in values):
            raise ValueError("INVALID_DISCRETE_MASSES")
        if abs(math.fsum(p for _, p in values)-1) > 1e-6:
            raise ValueError("DISCRETE_MASS_NONUNIT")
        return {"kind": "discrete", "masses": values}
    if data.get("kind") == "nba_minutes_law":
        # Native NBA WS2 M0/M1/M2 law: positive played-only exposure,
        # not an unconditional distribution or DNP probability.
        from v2.nba_opportunity import MinuteLaw
        law=MinuteLaw(**data["parameters"])
        if row["sport"] != "NBA" or row["stat"] != "minutes" or row["conditioning"] != "given_played":
            raise ValueError("MINUTE_LAW_WRONG_CONDITIONING")
        return {"kind": "nba_minutes_law", "parameters": data["parameters"],
                "expected_given_played": law.summary()["expected_minutes_given_played"]}
    raise ValueError("UNREGISTERED_DISTRIBUTION_TYPE")


def validate_row(row, manifest):
    if row.get("schema") != ROW_SCHEMA or row.get("sport") != manifest["sport"] or row.get("engine") != manifest["engine"]:
        raise ValueError("MODEL_ROW_SCHEMA_OR_IDENTITY")
    for k in ("event_id", "player_id", "stat", "source_sha256", "forecast_at",
              "input_freeze_at", "source_received_at", "event_start_at",
              "model_training_cutoff_at", "conditioning"):
        if row.get(k) in (None, ""):
            raise ValueError("ROW_FIELD_MISSING:" + k)
    if row["conditioning"] not in _ALLOWED_CONDITIONING:
        raise ValueError("UNSPECIFIED_MODEL_CONDITIONING")
    if row.get("retrospective") or row.get("fixture") or row.get("synthetic"):
        raise ValueError("RETROSPECTIVE_OR_SYNTHETIC_NOT_FORECAST")
    if not _SHA.fullmatch(row["source_sha256"]):
        raise ValueError("UNHASHED_ORIGINAL_SOURCE")
    _chronology(row)
    dist = _normalize_distribution(row)
    p = row.get("p_over_given_no_push")
    if p is not None and not 0 <= _num(p) <= 1:
        raise ValueError("MODEL_PROBABILITY_OUT_OF_RANGE")
    if p is None and dist is None and row.get("status") == "forecast":
        raise ValueError("NO_FROZEN_PROBABILITY_OR_DISTRIBUTION")
    if row["sport"] == "NFL" and row.get("status") == "forecast":
        if not row.get("original_contract_id") or row.get("line") is None or not row.get("original_quote_id"):
            raise ValueError("NFL_CONTRACT_IDENTITY_MISSING")
        _num(row["line"])
    if row["sport"] == "NBA" and row.get("status") == "forecast":
        if not row.get("team_id") or not row.get("game_id"):
            raise ValueError("NBA_TEAM_GAME_IDENTITY_MISSING")
    return {**row, "validated_distribution": dist}


def discover(root, *, max_manifests=150):
    directory = Path(root) / ROOT
    valid, rejected, manifests = [], [], []
    if not directory.is_dir():
        return {"schema": "V25Discovery/1", "status": "REGISTRY_ABSENT",
                "forecasts": [], "manifests": [], "rejected": []}
    paths = sorted(directory.glob("*/manifest.json"))
    if len(paths) > max_manifests:
        raise ValueError("MANIFEST_COUNT_BOUND")
    seen = set()
    for path in paths:
        entry = {"manifest": str(path.relative_to(root))}
        try:
            if path.is_symlink():
                raise ValueError("SYMLINKED_MANIFEST")
            document = json.loads(path.read_bytes())
            if document.get("schema") != SCHEMA:
                raise ValueError("UNKNOWN_MANIFEST_SCHEMA")
            sport, engine = document.get("sport"), document.get("engine")
            if sport not in _ALLOWED_SPORTS or not isinstance(engine, str) or not _NAME.fullmatch(engine):
                raise ValueError("INVALID_SPORT_OR_ENGINE")
            expected = document.get("forecast_rows_sha256")
            if not isinstance(expected, str) or not _SHA.fullmatch(expected):
                raise ValueError("MISSING_OR_MALFORMED_FORECAST_SHA")
            src = _path(path.parent, document.get("forecast_rows_path"))
            raw = src.read_bytes()
            if len(raw) > 30 * 1024 * 1024:
                raise ValueError("FORECAST_ARCHIVE_TOO_LARGE")
            if digest(raw) != expected:
                raise ValueError("FROZEN_FORECAST_BYTES_CHANGED")
            lines = [json.loads(line) for line in raw.splitlines() if line.strip()]
            if len(lines) != document.get("expected_rows") or not isinstance(document.get("expected_rows"), int):
                raise ValueError("FORECAST_DENOMINATOR_MISMATCH")
            if len(lines) > 20000:
                raise ValueError("FORECAST_ROWS_EXCEED_BOUND")
            registered_at = instant(document["first_archived_at"])
            accepted = 0
            for index, row in enumerate(lines):
                identity = (sport, engine, str(row.get("event_id")), str(row.get("player_id")),
                            str(row.get("stat")), str(row.get("original_contract_id") or ""),
                            str(row.get("game_id") or ""), str(row.get("forecast_at")))
                if identity in seen:
                    rejected.append({"manifest": entry["manifest"], "index": index,
                                     "reason": "DUPLICATE_ENGINE_ORIGINAL_FORECAST"})
                    continue
                seen.add(identity)
                try:
                    normalized = validate_row(row, document)
                    if registered_at >= instant(row["event_start_at"]):
                        raise ValueError("FIRST_ARCHIVE_AFTER_EVENT_STARTED")
                    valid.append({**normalized, "registry_manifest": entry["manifest"],
                                  "registry_manifest_forecast_sha256": expected})
                    accepted += 1
                except Exception as exc:
                    rejected.append({"manifest": entry["manifest"], "index": index,
                                     "engine": engine, "reason": type(exc).__name__+":"+str(exc)})
            manifests.append({**entry, "sport": sport, "engine": engine, "expected_rows": len(lines),
                              "valid_rows": accepted, "rejected_rows": len(lines)-accepted,
                              "frozen_rows_sha256": expected})
        except Exception as exc:
            rejected.append({**entry, "reason": type(exc).__name__+":"+str(exc)})
    return {"schema": "V25Discovery/1", "status": "DISCOVERED_WITH_QUARANTINE",
            "forecasts": valid, "manifests": manifests, "rejected": rejected,
            "unregistered_engine_policy": "unknown engines auto-admitted ONLY under the strict immutable manifest contract"}


def create_manifest(root, batch, sport, engine, rows):
    """Create exactly once while every game is still future; no retrospective backfill."""
    root=Path(root)
    if not isinstance(batch,str) or not _NAME.fullmatch(batch):
        raise ValueError("BAD_MANIFEST_BATCH")
    if not isinstance(engine,str) or not _NAME.fullmatch(engine) or sport not in _ALLOWED_SPORTS:
        raise ValueError("BAD_MANIFEST_ID")
    if not rows or len(rows)>20000:
        raise ValueError("EMPTY_OR_OVERSIZED_PROSPECTIVE_SUBMISSION")
    now=datetime.now(timezone.utc)
    document={"schema":SCHEMA,"sport":sport,"engine":engine,
              "first_archived_at":now.isoformat(),
              "forecast_rows_path":"forecasts.jsonl","expected_rows":len(rows)}
    for row in rows:
        validate_row(row,document)
        if now>=instant(row["event_start_at"]):
            raise ValueError("FIRST_MANIFEST_ARCHIVE_AFTER_GAME_STARTED")
    raw=b"".join((json.dumps(r,sort_keys=True,allow_nan=False)+"\n").encode() for r in rows)
    document["forecast_rows_sha256"]=digest(raw)
    dest=root/ROOT/batch
    dest.mkdir(parents=True,exist_ok=False)
    with (dest/"forecasts.jsonl").open("xb") as f:f.write(raw)
    with (dest/"manifest.json").open("x") as f:
        json.dump(document,f,sort_keys=True,indent=2);f.write("\n")
    return document
