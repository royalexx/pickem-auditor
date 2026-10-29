#!/usr/bin/env python3
"""Parallel resumable population backfill, research only, with immutable checkpoints.

Four independent sport/stream source readers use nonoverlapping season shards.
Only after all readers finish a bounded batch is history committed to the
independent data/bayesian-history branch. No source date is considered complete
until all its games and player/market rows are verified.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

import population_backfill as population

ROOT = Path(__file__).resolve().parents[1]
SPORTS = ("NHL", "NBA")
STREAMS = ("recent", "archive")
CUTOFF = "2023-10-01"
STATUS_FILE = Path("data/bayesian_warehouse/campaign_complete.json")


def statuses(root: Path, today: date) -> dict:
    return {
        sport + "_" + stream: {
            "cursor": population.read_state(root, sport, stream=stream)["cursor"],
            "target_exclusive": today.isoformat() if stream == "recent" else CUTOFF,
        }
        for sport in SPORTS for stream in STREAMS
    }


def is_complete(rows: dict) -> bool:
    return all(x["cursor"] >= x["target_exclusive"] for x in rows.values())


def batch(root, sport, stream, days, timeout):
    cmd = [sys.executable, "scripts/population_backfill.py",
           "--sport", sport, "--stream", stream,
           "--max-days", str(days), "--max-games", "1800",
           "--request-spacing", ".5" if sport == "NHL" else ".65"]
    if stream == "archive":
        cmd += ["--stop-before", (date.fromisoformat(CUTOFF) - timedelta(days=1)).isoformat()]
    result = {"sport": sport, "stream": stream, "requested_days": days}
    try:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True,
                              check=False, timeout=timeout)
        result["returncode"] = proc.returncode
        result["stdout"] = proc.stdout[-2500:]
        result["stderr"] = proc.stderr[-800:]
    except subprocess.TimeoutExpired as e:
        result["returncode"] = 124
        result["error"] = "source_batch_time_limit"
    return result


def checkpoint(root):
    proc = subprocess.run(["bash", "scripts/history_warehouse_store.sh", "save"],
                          cwd=root, capture_output=True, text=True, timeout=1200)
    if proc.returncode != 0:
        raise RuntimeError("WAREHOUSE_CHECKPOINT_FAILED: " + proc.stderr[-1500:])
    return proc.stdout[-350:]


def report_write(root, obj):
    dest = root / "reports" / "population_campaign.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    tmp.replace(dest)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--max-minutes", type=int, default=315)
    p.add_argument("--batch-days", type=int, default=120)
    p.add_argument("--batch-timeout-minutes", type=int, default=45)
    args = p.parse_args()
    if not 30 <= args.max_minutes <= 330 or not 1 <= args.batch_days <= 300:
        p.error("invalid campaign budget")
    if not 5 <= args.batch_timeout_minutes <= 90:
        p.error("invalid batch timeout")
    root = args.root.resolve()
    today = date.today()
    started = time.monotonic()
    deadline = started + args.max_minutes * 60
    opening = statuses(root, today)
    marker = root / STATUS_FILE
    previous = json.loads(marker.read_text()) if marker.is_file() else {}
    output = {
        "schema": "parallel_resumable_population_campaign_v1",
        "as_of_utc": today.isoformat(),
        "source_data_only": True,
        "no_model_or_production_changes": True,
        "nfl_complete_seasons_through": int(population.read_state(root, "NFL")["cursor"]) - 1,
        "initial": opening, "batches": [], "status": "running",
        "completion_transition": False,
    }
    report_write(root, output)
    blocked = set()
    completed = False
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            while True:
                current = statuses(root, today)
                if is_complete(current):
                    completed = True
                    output["status"] = "complete"
                    break
                if time.monotonic() + (args.batch_timeout_minutes + 18) * 60 > deadline:
                    output["status"] = "runner_budget_exhausted"
                    break
                options = [(sport, stream) for sport in SPORTS for stream in STREAMS
                           if current[sport + "_" + stream]["cursor"] <
                              current[sport + "_" + stream]["target_exclusive"]
                           and (sport, stream) not in blocked]
                if not options:
                    output["status"] = "blocked"
                    break
                print("START_PARALLEL_BATCH " + json.dumps(options), flush=True)
                futures = {
                    executor.submit(batch, root, sport, stream, args.batch_days,
                                    args.batch_timeout_minutes * 60): (sport, stream)
                    for sport, stream in options
                }
                reports = []
                for f in as_completed(futures):
                    item = f.result()
                    reports.append(item)
                    key = (item["sport"], item["stream"])
                    if item["returncode"] != 0:
                        blocked.add(key)
                    print("BATCH_RESULT " + json.dumps(item, sort_keys=True)[-3500:],
                          flush=True)
                # Every worker is finished; no mutable shard is being written.
                print("CHECKPOINT "+checkpoint(root), flush=True)
                for item in reports:
                    item["cursor_after"] = population.read_state(
                        root, item["sport"], stream=item["stream"])["cursor"]
                output["batches"].append(reports)
                output["current"] = statuses(root, today)
                report_write(root, output)
                if all(item["cursor_after"] == current[item["sport"] + "_" +
                                 item["stream"]]["cursor"] for item in reports):
                    output["status"] = "no_progress"
                    break
        if completed and previous.get("completed_through") != today.isoformat():
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps(
                {"schema": "population_campaign_completion_v1",
                 "completed_through": today.isoformat(),
                 "archive_target_exclusive": CUTOFF,
                 "nfl_completed_seasons_through": int(population.read_state(root, "NFL")["cursor"]) - 1},
                indent=2, sort_keys=True) + "\n")
            output["completion_transition"] = True
            print("FINAL_COMPLETION_CHECKPOINT " + checkpoint(root), flush=True)
        output["current"] = statuses(root, today)
        output["finished_after_seconds"] = round(time.monotonic() - started, 1)
        report_write(root, output)
        print("POPULATION_CAMPAIGN_FINAL=" +
              json.dumps({k: v for k, v in output.items() if k != "batches"}, sort_keys=True),
              flush=True)
        return 0 if output["status"] in ("complete", "runner_budget_exhausted") else 2
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        output["status"] = "checkpoint_or_execution_failed"
        output["error"] = str(exc)[-1300:]
        output["current"] = statuses(root, today)
        report_write(root, output)
        print("POPULATION_CAMPAIGN_ERROR="+str(exc)[-1300:], file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
