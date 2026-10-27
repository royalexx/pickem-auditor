#!/usr/bin/env python3
"""Verify collected NBA/NFL/NHL rows and save timestamped source-only snapshots.

Never treats a process exit code as evidence of feed coverage.
"""
from __future__ import annotations
import argparse
import gzip
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

FIELDS = (
    "sport", "game_date", "player", "player_id", "team", "opponent",
    "stat", "baseline_mean", "season_n", "season_mean", "last_5_mean",
    "last_10_mean", "season_n", "season_mean", "sample_size",
    "baseline_window_mean", "baseline_n", "recent_mean", "recent_n",
    "prior_season_mean", "prior_n", "stat_log", "observation_ids",
    "retrieved_at", "event_id", "event_id_namespace",
    "suggested_dist", "sd", "var_ratio", "zero_rate", "role_stable_n",
    "role_stable_mean", "baseline_workload", "snap_share", "target_share",
)
SPORTS = ("NHL", "NBA", "NFL")


def audit(slate: Path, meta_path: Path, output: Path, root: Path, slot: str):
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    date = meta.get("date")
    retrieved = meta.get("retrieved_at")
    result = {
        "date": date, "retrieved_at": retrieved,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_slate": str(slate), "slot": slot, "feed_status": {}, "source_rows": {},
        "status": "blocked", "errors": [],
    }
    if not isinstance(date, str) or len(date) != 10 or not retrieved:
        result["errors"].append("MISSING_SOURCE_DATE_OR_TIMESTAMP")
    try:
        rows = [json.loads(line) for line in slate.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, ValueError) as exc:
        rows = []
        result["errors"].append("NO_VALID_SOURCE_ROWS: " + type(exc).__name__)
    grouped = {sport: [] for sport in SPORTS}
    for row in rows:
        sport = str(row.get("sport", "")).upper()
        if sport in grouped and row.get("game_date") == date:
            grouped[sport].append(row)
    for sport in SPORTS:
        label = sport.lower()
        feed = (meta.get("feeds") or {}).get(label) or {}
        source_status = feed.get("status", "not_reported")
        count = len(grouped[sport])
        result["source_rows"][sport] = count
        result["feed_status"][sport] = {
            "status": source_status, "source_reported_rows": feed.get("rows"),
            "verified_rows": count,
        }
        if count and source_status == "ok" and date and retrieved:
            target = root / "data" / "history_slate" / date / slot / f"{label}.jsonl.gz"
            target.parent.mkdir(parents=True, exist_ok=True)
            # Whitelist public/statistical fields; never archive API-key-bearing
            # request URLs, credentials, odds quotes, or research dossiers.
            clean = [{field: row[field] for field in FIELDS if field in row}
                     for row in grouped[sport]]
            with target.open("wb") as destination:
                with gzip.GzipFile(fileobj=destination, mode="wb", mtime=0) as archive:
                    archive.write("".join(json.dumps(item, sort_keys=True) + "\n" for item in clean).encode("utf-8"))
            result["feed_status"][sport]["archived_path"] = str(target.relative_to(root))
        if not count or source_status != "ok" or feed.get("rows") != count:
            result["errors"].append(f"{sport}_FEED_UNVERIFIED")
    result["status"] = (
        "success" if not result["errors"] else
        "partial" if any(result["source_rows"].values()) else "blocked"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slate", default="data/slate_fetch.jsonl")
    parser.add_argument("--meta", default="data/slate_fetch.meta.json")
    parser.add_argument("--out", default="reports/sport_coverage.json")
    parser.add_argument("--root", default=".")
    parser.add_argument("--slot", default="morning", choices=("morning", "afternoon", "backfill"))
    args = parser.parse_args()
    output = audit(Path(args.slate), Path(args.meta), Path(args.out), Path(args.root), args.slot)
    return 0 if output["status"] == "success" else 2


if __name__ == "__main__":
    sys.exit(main())
