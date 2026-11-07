#!/usr/bin/env python3
"""Reject lost or rewritten forecasts before replacing the persistent JSONL.

The forecast payload is immutable, including fields unknown to this helper.
Only the enrichment fields written by settle.py and jobs.run_closing may be
filled later. Once populated, those values also cannot be removed or changed.
This guard reads files only; it never normalizes or rewrites historical rows.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import math
from pathlib import Path
import sys
import uuid


ENRICHMENT_FIELDS = frozenset({
    "actual_stat", "outcome", "settled_at", "closing_line", "closing_q_market",
})
IDENTITY_FIELDS = ("run_id", "game_date", "sport", "player", "stat", "side")


class ForecastHistoryConflict(ValueError):
    """The proposed persisted history is not a safe extension of the old one."""


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ForecastHistoryConflict("duplicate_json_field:" + key)
        result[key] = value
    return result


def _invalid_constant(value):
    raise ForecastHistoryConflict("nonfinite_json_value:" + value)


def _identity(row):
    if not isinstance(row, dict):
        raise ForecastHistoryConflict("forecast_must_be_json_object")
    for key in IDENTITY_FIELDS:
        if not isinstance(row.get(key), str) or not row[key].strip():
            raise ForecastHistoryConflict("missing_or_invalid_identity:" + key)
    try:
        day = date.fromisoformat(row["game_date"])
    except ValueError as exc:
        raise ForecastHistoryConflict("invalid_identity:game_date") from exc
    if day.isoformat() != row["game_date"]:
        raise ForecastHistoryConflict("invalid_identity:game_date")
    if row["sport"] not in ("NBA", "NHL", "NFL"):
        raise ForecastHistoryConflict("invalid_identity:sport")
    if row["side"].strip().lower() not in ("over", "under"):
        raise ForecastHistoryConflict("invalid_identity:side")
    line = row.get("reference_line")
    if isinstance(line, bool) or not isinstance(line, (float, int)) or not math.isfinite(line):
        raise ForecastHistoryConflict("invalid_identity:reference_line")
    # Match the existing snapshot-key run-ID convention without modifying it.
    run = row["run_id"].strip()
    try:
        run = str(uuid.UUID(run))
    except ValueError:
        pass
    return (run, row["game_date"], row["sport"], row["player"].strip(),
            row["stat"].strip(), row["side"].strip().lower())


def _read(path, *, allow_missing=False):
    path = Path(path)
    if allow_missing and not path.exists():
        return {}
    rows = {}
    for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not text.strip():
            continue
        try:
            row = json.loads(text, object_pairs_hook=_object, parse_constant=_invalid_constant)
            key = _identity(row)
            _canonical(row)  # Reject overflowed JSON floats in appended rows too.
        except (ValueError, TypeError, OverflowError) as exc:
            raise ForecastHistoryConflict(f"{path.name}:line_{number}:{exc}") from exc
        if key in rows:
            raise ForecastHistoryConflict(f"{path.name}:line_{number}:duplicate_forecast_identity")
        rows[key] = row
    return rows


def _canonical(value):
    # JSON comparison preserves distinctions such as a Boolean replacing a
    # numerical probability; ordinary Python equality considers True == 1.
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _forecast_payload(row):
    frozen = {key: value for key, value in row.items() if key not in ENRICHMENT_FIELDS}
    if isinstance(frozen.get("market"), dict):
        frozen["market"] = {key: value for key, value in frozen["market"].items()
                            if key != "closing_q_market"}
    return frozen


def _enrichment_values(row):
    values = {key: row.get(key) for key in ENRICHMENT_FIELDS}
    market = row.get("market")
    values["market.closing_q_market"] = (
        market.get("closing_q_market") if isinstance(market, dict) else None)
    return values


def check_history(previous, current):
    """Validate an initial history or a monotone extension without mutating it."""
    old = _read(previous, allow_missing=True)
    new = _read(current)
    if not new:
        raise ForecastHistoryConflict("current_forecast_history_empty")
    for key, before in old.items():
        if key not in new:
            raise ForecastHistoryConflict("existing_forecast_deleted_or_identity_changed")
        after = new[key]
        if _canonical(_forecast_payload(before)) != _canonical(_forecast_payload(after)):
            raise ForecastHistoryConflict("immutable_forecast_payload_changed")
        prior_enrichment = _enrichment_values(before)
        next_enrichment = _enrichment_values(after)
        for field, value in prior_enrichment.items():
            if value is not None and _canonical(value) != _canonical(next_enrichment[field]):
                raise ForecastHistoryConflict("existing_enrichment_changed:" + field)
    return {"status": "verified", "existing_forecasts": len(old),
            "current_forecasts": len(new), "appended_forecasts": len(new) - len(old)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", required=True, type=Path)
    parser.add_argument("--current", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = check_history(args.previous, args.current)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        print("IMMUTABLE_FORECAST_HISTORY_CONFLICT: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
