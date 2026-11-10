#!/usr/bin/env python3
"""Read-only Phase 0 pregame feature/source audit; never modifies forecasts.

When historical provider bytes or training cutoffs are absent, the output is
UNCERTIFIED rather than inventing a reconstructed pregame feature history.
The afternoon and settlement jobs are not blocked by missing source archives.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

from point_in_time_provenance import pregame_snapshot_status
from phase0r_contract import strict_snapshot_status
from market_odds_archive import atomic_json

SCHEMA = "pickem_phase0_pregame_provenance_v1"


def audit(path: Path, *, slate_date: str, archive_root: Path, strict: bool = True) -> dict:
    date.fromisoformat(slate_date)
    path = Path(path)
    report = {
        "schema": SCHEMA,
        "game_date": slate_date,
        "source_forecasts": str(path),
        "original_forecast_bytes_sha256": None,
        "selected_run_id": None,
        "contract_rows_in_batch": 0,
        "certified_rows": 0,
        "metadata_verified_rows": 0,
        "certification_level": ("strict_pre_evaluation_input_binding_v1" if strict else
                                "legacy_metadata_only_diagnostic"),
        "uncertified_rows": 0,
        "distinct_games_in_batch": 0,
        "uncertified_reasons": {},
        "status": "source_forecasts_unavailable",
        "publication_eligible": False,
        "tier1_tier2_publication_allowed": False,
        "legacy_predictions_preserved": True,
        "retrospective_backfill_allowed": False,
        "training_resumed": False,
        "market_api_requests_added": 0,
        "source_archive_complete": False,
        "limits": (
            "Receipt/digest verification cannot establish independent provider "
            "publication truth or prove unarchived upstream feature transforms. "
            "Original unarchived historical inputs never become certifiable."
        ),
    }
    if not path.is_file():
        return report
    raw = path.read_bytes()
    report["original_forecast_bytes_sha256"] = hashlib.sha256(raw).hexdigest()
    rows = []
    for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"non_object_forecast_row:{number}")
        if row.get("game_date") == slate_date:
            rows.append(row)
    if not rows:
        report["status"] = "no_forecasts_on_requested_date"
        return report
    # Only the newest *original* batch for this slate is assessed. Each side
    # is included once by immutable contract identity; collisions fail closed.
    run_ids = {}
    for row in rows:
        ident = str(row.get("run_id") or "")
        if ident:
            run_ids[ident] = max(str(row.get("forecast_at") or ""),
                                 run_ids.get(ident, ""))
    if not run_ids:
        report["status"] = "missing_original_run_identity"
        return report
    newest = max(run_ids, key=lambda rid: (run_ids[rid], rid))
    selected = [row for row in rows if row.get("run_id") == newest]
    report["selected_run_id"] = newest
    report["contract_rows_in_batch"] = len(selected)
    report["distinct_games_in_batch"] = len({
        (row.get("sport"), row.get("event_id")) for row in selected
    })
    identity_counts = Counter(
        (row.get("sport"), row.get("event_id"), row.get("player_id"),
         row.get("stat"), row.get("side"), str(row.get("reference_line")))
        for row in selected)
    reasons = Counter()
    certified = 0
    metadata_accepted = 0
    for row in selected:
        identity = (
            row.get("sport"), row.get("event_id"), row.get("player_id"),
            row.get("stat"), row.get("side"), str(row.get("reference_line")))
        if identity_counts[identity] > 1:
            reasons["duplicate_original_contract_identity"] += 1
            continue
        old_accepted, old_reason = pregame_snapshot_status(
            row, archive_root=Path(archive_root))
        if old_accepted:
            metadata_accepted += 1
        accepted, reason = (
            strict_snapshot_status(row, archive_root=Path(archive_root))
            if strict else (old_accepted, old_reason))
        if accepted:
            certified += 1
        else:
            reasons[reason] += 1
    report["metadata_verified_rows"] = metadata_accepted
    report["certified_rows"] = certified
    report["uncertified_rows"] = len(selected) - certified
    report["uncertified_reasons"] = dict(sorted(reasons.items()))
    report["source_archive_complete"] = certified == len(selected) and bool(selected)
    report["status"] = (
        ("all_rows_have_strict_pre_eval_input_bindings" if strict
         else "all_rows_have_metadata_receipts_diagnostic_only")
        if report["source_archive_complete"]
        else "uncertified_research_only")
    # Source certification is necessary but never enough to release Tiers.
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--snapshots", default="data/prop_snapshots.jsonl")
    parser.add_argument("--archive-root", default="data/source_archives")
    parser.add_argument("--out", default="reports/phase0_pregame_provenance.json")
    args = parser.parse_args(argv)
    report = audit(Path(args.snapshots), slate_date=args.date,
                   archive_root=Path(args.archive_root))
    atomic_json(Path(args.out), report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
