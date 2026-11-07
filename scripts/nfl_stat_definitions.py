#!/usr/bin/env python3
"""Strict NFL source-stat challenger; never changes forecasting or settlement.

The combined tackle definition is the sum of nflverse's three distinct credits:
solo tackles, tackles with an assistant, and tackle assists. Missing evidence is
unavailable, rather than a measured zero. This additive audit module is NOT
called by the existing production collector or settler.

Read raw nflverse weekly player-stat JSONL and write a NEW diagnostic file:
    python scripts/nfl_stat_definitions.py --input-jsonl weekly.jsonl \
        --output-jsonl reports/nfl_stat_reconciliation.jsonl

The legacy comparison reconstructs only the old SOURCE COUNT FORMULA. It is not
an original forecast, a historical settlement correction, or a backtest.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Mapping

VERSION = "nfl-source-stat-challenger-v1"
COMPONENTS = {
    "targets": ("targets",),
    "solo tackles": ("def_tackles_solo",),
    "tackles with assist": ("def_tackles_with_assist",),
    "tackle assists": ("def_tackle_assists",),
    "tackles + assists": (
        "def_tackles_solo", "def_tackles_with_assist", "def_tackle_assists",
    ),
}


@dataclass(frozen=True)
class SourceStat:
    stat: str
    status: str
    value: int | None
    required_fields: tuple[str, ...]
    issues: tuple[str, ...]
    definition_version: str = VERSION


def strict_source_stat(row: Mapping, stat: str) -> SourceStat:
    """Resolve a raw source count only when all required counts are known.

    nflreadpy returns integer or floating numeric columns. Integral floats are
    allowed; strings, booleans, fractional/negative/nonfinite and >200 component
    counts are rejected. A true observed zero remains valid. Unsupported labels
    raise instead of guessing what a bookmaker means by a market name.
    """
    if not isinstance(row, Mapping):
        raise TypeError("source row must be a mapping")
    if stat not in COMPONENTS:
        raise ValueError("unsupported_nfl_source_stat:" + str(stat))
    fields = COMPONENTS[stat]
    counts = []
    issues = []
    for field in fields:
        if field not in row:
            issues.append("missing_source_field:" + field)
            continue
        value = row[field]
        if value is None:
            issues.append("missing_source_value:" + field)
            continue
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not 0 <= value <= 200 or not math.isfinite(value)
                or not float(value).is_integer()):
            issues.append("invalid_source_count:" + field)
            continue
        counts.append(int(value))
    if issues:
        return SourceStat(stat, "unavailable", None, fields, tuple(issues))
    total = sum(counts)
    if total > 200:
        return SourceStat(stat, "unavailable", None, fields,
                          ("invalid_combined_count:" + stat,))
    return SourceStat(stat, "available", total, fields, ())


def _legacy_formula(row: Mapping, stat: str) -> float | None:
    """Diagnostic recreation of fetch_slate._game_stat on ONE raw row only."""
    fields = ("def_tackles_solo", "def_tackle_assists") if stat == "tackles + assists" else COMPONENTS[stat]
    if not any(field in row for field in fields):
        return None
    total = 0.0
    for field in fields:
        try:
            value = float(row.get(field))
        except (ValueError, TypeError, OverflowError):
            value = 0.0
        total += value if math.isfinite(value) else 0.0
    return total


def reconcile(row: Mapping, stats=("tackles + assists", "targets")) -> list[dict]:
    """Compare source definitions without generating predictions or outcomes."""
    digest = hashlib.sha256(json.dumps(
        row, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    identity = {key: row.get(key) for key in (
        "season", "week", "game_id", "player_id", "player_display_name",
        "team", "recent_team", "opponent_team",
    ) if key in row}
    results = []
    for stat in stats:
        strict = strict_source_stat(row, stat)
        legacy = _legacy_formula(row, stat)
        results.append({
            **asdict(strict), "identity": identity, "source_row_sha256": digest,
            "legacy_source_formula_value": legacy,
            "strict_minus_legacy": (strict.value - legacy
                                    if strict.value is not None and legacy is not None else None),
            "comparison_kind": "source_count_formula_only",
            "forecast_generated": False, "settlement_written": False,
            "ranking_allowed": False, "production_changed": False,
        })
    return results


def reconcile_file(source: Path, destination: Path, *, stats=("tackles + assists", "targets")) -> dict:
    """Validate the complete input, then exclusively create an audit output.

    Existing output files and input/output aliases are refused. No original
    source, trained artifact, prediction, or settlement file is rewritten.
    """
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError("reconciliation_must_not_replace_source")
    if destination.exists():
        raise FileExistsError("reconciliation_output_already_exists")
    raw = source.read_bytes()
    input_digest = hashlib.sha256(raw).hexdigest()
    results = []
    def reject_constant(value):
        raise ValueError("nonfinite_json_source_constant:" + value)
    for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line, parse_constant=reject_constant)
        if not isinstance(row, dict):
            raise ValueError("nonobject_source_row:" + str(number))
        for item in reconcile(row, stats):
            results.append({**item, "source_line": number,
                            "source_input_sha256": input_digest})
    payload = "".join(json.dumps(item, sort_keys=True, allow_nan=False) + "\n" for item in results)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as handle:
        handle.write(payload)
    return {"schema": VERSION, "diagnostic_rows": len(results),
            "statuses": dict(Counter(item["status"] for item in results)),
            "source_input_sha256": input_digest,
            "production_changed": False, "historical_records_changed": False,
            "ranking_allowed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--output-jsonl", type=Path, required=True)
    parser.add_argument("--stat", action="append", choices=tuple(COMPONENTS))
    args = parser.parse_args(argv)
    result = reconcile_file(args.input_jsonl, args.output_jsonl,
                            stats=tuple(args.stat or ("tackles + assists", "targets")))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
