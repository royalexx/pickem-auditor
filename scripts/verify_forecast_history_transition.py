#!/usr/bin/env python3
"""Fail-closed transition check for persistent JSONL forecast history.

Forecasts are immutable. Only settlement fields may be added in-place. A
later correction must be written to a separate append-only correction log,
not by silently overwriting a previously recorded outcome.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

SETTLEMENT_FIELDS = frozenset(("actual_stat", "outcome", "settled_at"))


class ForecastHistoryConflict(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def read(path):
    rows = []
    for lineno, text in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not text.strip():
            raise ForecastHistoryConflict(f"blank_forecast_line:{lineno}")
        try:
            row = json.loads(text)
            if not isinstance(row, dict):
                raise ValueError("forecast must be object")
            canonical(row)  # reject NaN, infinity, invalid values
        except (ValueError, TypeError) as exc:
            raise ForecastHistoryConflict(f"invalid_forecast_json:{lineno}") from exc
        rows.append(row)
    return rows


def forecast_digest(row):
    original = {k: v for k, v in row.items() if k not in SETTLEMENT_FIELDS}
    return hashlib.sha256(canonical(original).encode("utf-8")).hexdigest()


def settlement_key(row):
    return canonical({k: row.get(k) for k in sorted(SETTLEMENT_FIELDS)})


def verify(old_file, new_file):
    previous = read(old_file)
    proposed = read(new_file)
    if not proposed:
        raise ForecastHistoryConflict("EMPTY_FORECAST_HISTORY_REPLACEMENT")
    old_counts = Counter(forecast_digest(row) for row in previous)
    new_counts = Counter(forecast_digest(row) for row in proposed)
    missing = old_counts - new_counts
    if missing:
        raise ForecastHistoryConflict(
            "IMMUTABLE_FORECAST_HISTORY_CONFLICT: prior forecasts missing or changed")
    old_settled = Counter((forecast_digest(row), settlement_key(row))
                          for row in previous
                          if row.get("outcome") is not None or
                             row.get("actual_stat") is not None or
                             row.get("settled_at") is not None)
    new_settled = Counter((forecast_digest(row), settlement_key(row))
                          for row in proposed
                          if row.get("outcome") is not None or
                             row.get("actual_stat") is not None or
                             row.get("settled_at") is not None)
    if old_settled - new_settled:
        raise ForecastHistoryConflict("IMMUTABLE_SETTLEMENT_HISTORY_CONFLICT")
    return {"prior_rows": len(previous), "new_rows": len(proposed),
            "appended_forecasts": len(proposed)-len(previous),
            "preserved_settlements": sum(old_settled.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("previous", type=Path)
    parser.add_argument("proposed", type=Path)
    opts = parser.parse_args()
    try:
        print(canonical(verify(opts.previous, opts.proposed)))
    except ForecastHistoryConflict as exc:
        parser.exit(2, str(exc)+"\n")


if __name__ == "__main__":
    main()
