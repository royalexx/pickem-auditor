"""One Daily Deepnote detached runner for the frozen November 16-20 NBA pilot.

The ONE daily trigger launches a persistent worker. This process, not the
ChatGPT task, waits for each exact original pregame window and starts
same-window slots concurrently. Run from the pinned repository root and
persistent project storage; never from an ephemeral temporary directory.

ESPN WS1 is the primary schedule/roster/history/boxscore source.
NBA.com team pages and official injury PDF are optional supplements.
No NBA.com failure grants legal eligibility, P(appearance), or J2 adoption.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import subprocess
from zoneinfo import ZoneInfo

from research.nba_phase7.pilot import registered_slots, capture_slot, REGISTRY_SHA
from research.nba_phase7.settlement import settle_slot
from research.nba_phase8a.preflight import check as preflight
from v2.nba_ws1.store import digest, instant

TZ = ZoneInfo("America/Toronto")
PILOT_DATES = {"2026-11-16", "2026-11-17", "2026-11-18",
               "2026-11-19", "2026-11-20"}
MAX_SLOTS = 10


def clock():
    return datetime.now(timezone.utc)


def write_once(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as file:
        json.dump(data, file, indent=2, sort_keys=True)
        file.write("\n")


def sha_manifest(directory):
    base = Path(directory)
    rows = []
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if path.is_symlink():
            raise ValueError("PILOT_STORAGE_SYMLINK_NOT_ALLOWED")
        if path.stat().st_size > 1024 * 1024 * 200:
            raise ValueError("PILOT_EVIDENCE_FILE_TOO_LARGE")
        rows.append({"path": path.relative_to(base).as_posix(),
                     "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "bytes": path.stat().st_size})
    return {"schema": "NBADailyEvidenceManifest/1", "files": rows,
            "file_count": len(rows)}


def events_for_day(slots, day):
    """Never derive target games from live scoreboards or model results."""
    selected = [s for s in slots if s["toronto_date"] == day]
    groups = {}
    for slot in selected:
        deadline = instant(slot["scheduled_freeze_at"])
        opened = deadline - timedelta(minutes=10)
        key = opened.isoformat()
        groups.setdefault(key, []).append(slot)
    return [(instant(key), sorted(rows, key=lambda s: s["slot"]))
            for key, rows in sorted(groups.items())]


def ensure_authoritative_storage(root):
    root = Path(root).resolve()
    if root == Path("/tmp") or "/tmp/" in str(root):
        raise ValueError("EPHEMERAL_PILOT_STORAGE_FORBIDDEN")
    root.mkdir(parents=True, exist_ok=True)
    # /work is Deepnote's writable project storage. A Cloud worker can use
    # another explicitly configured durable mount but must attest to it.
    if not (root == Path("/work") or root.is_relative_to(Path("/work")) or
            os.environ.get("NBA_PILOT_DURABLE_STORAGE_ATTESTED") == "1"):
        raise ValueError("DURABLE_STORAGE_NOT_ATTESTED")
    return root


def run_group(slots, output, at):
    if not slots:
        return []
    # Each slot uses a separate FIRST_CAPTURE and ACQUISITION_CLAIM.
    # Do not retry a blocked claim. Futures start without serial delay.
    def attempt(slot):
        now = clock()
        deadline = instant(slot["scheduled_freeze_at"])
        if now > deadline:
            return {"slot": slot["slot"], "status": "MISSED_FREEZE",
                    "observed_at": now.isoformat(),
                    "reason": "Runner did not start within registered deadline"}
        try:
            return capture_slot(slot, output)
        except Exception as exc:
            return {"slot": slot["slot"], "status": "EXECUTION_ERROR",
                    "observed_at": clock().isoformat(),
                    "reason": type(exc).__name__ + ": " + str(exc)}
    with ThreadPoolExecutor(max_workers=len(slots)) as pool:
        futures = {pool.submit(attempt, slot): slot for slot in slots}
        return [f.result() for f in as_completed(futures)]


def settle_prior(slots, capture_root, settlement_root, today):
    result = []
    for slot in slots:
        gameid = slot["game"]["game_id"].split(":")[-1]
        prefix = "slot_%02d_" % slot["slot"] + gameid
        first = capture_root / prefix / "FIRST_CAPTURE.json"
        if not first.exists():
            continue
        if instant(slot["game"]["event_start_at"]) + timedelta(hours=6) >= clock():
            continue
        # Existing FINAL settlement is immutable and never rerun.
        dest = settlement_root / prefix
        if (dest / "settlement.json").exists():
            result.append({"slot": slot["slot"], "status": "ALREADY_SETTLED_OR_ATTEMPTED"})
            continue
        try:
            settlement = settle_slot(first.parent, dest)
            result.append({"slot": slot["slot"], "status": "SETTLEMENT_ATTEMPTED",
                           "settlement": settlement.get("status", settlement.get("schema", "unknown")),
                           "denominator": settlement.get("denominator")})
        except Exception as exc:
            result.append({"slot": slot["slot"], "status": "SETTLEMENT_ERROR",
                           "reason": type(exc).__name__ + ":" + str(exc)})
    return result


def run(day=None, root="/work", dry_run=False, no_wait=False):
    current = clock().astimezone(TZ)
    day = day or current.date().isoformat()
    if day != current.date().isoformat() and not dry_run:
        raise ValueError("NONCURRENT_DAY_LIVE_EXECUTION_FORBIDDEN")
    if day not in PILOT_DATES and day != "2026-11-21":
        raise ValueError("DAY_OUTSIDE_REGISTERED_PILOT_OR_SETTLEMENT")
    slots = registered_slots()
    if len(slots) != MAX_SLOTS:
        raise ValueError("PILOT_REGISTRATION_CHANGED")
    groups = events_for_day(slots, day)
    plan = {"schema": "NBADailyPilotOrchestrator/1", "day": day,
            "checked_at": current.isoformat(), "registration_sha256": REGISTRY_SHA,
            "runner": "one detached Deepnote run; grouped exact windows",
            "sources": {"ESPN": "primary original schedule, roster, historical stats, boxscores, FINAL settlement",
                        "NBA": "optional team identity and official injury evidence, never mandatory for ESPN-only candidate capture"},
            "scheduled": [{"open": start.isoformat(),
                           "deadline": rows[0]["scheduled_freeze_at"],
                           "slots": [s["slot"] for s in rows]} for start, rows in groups]}
    if dry_run:
        plan["mode"] = "DRY_RUN_NO_CAPTURE_NO_CLAIM"
        return plan
    root = ensure_authoritative_storage(root)
    capture_root = root / "reports" / "nba_phase7_pilot"
    settlement_root = root / "reports" / "nba_phase8c_settlement"
    report_root = root / "reports" / "nba_phase8c" / day
    report_root.mkdir(parents=True, exist_ok=False)
    first = {"created_at": clock().isoformat(), "plan": plan, "status": "STARTING"}
    write_once(report_root / "start.json", first)
    records = []
    try:
        try:
            ready = preflight(output=str(capture_root))
        except (ValueError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            if isinstance(exc, ValueError) and str(exc) != "PDF_RUNTIME_UNAVAILABLE":
                raise
            # A failed optional PDF parser must NOT suppress a genuine ESPN
            # game-day candidate/boxscore capture. Verify model manually.
            from research.nba_phase7.participation import MODEL_HASH
            from v2.nba_joint.common import sha
            model = json.loads(Path("research/nba_joint_v01/results/model.json").read_text())
            if sha(model) != MODEL_HASH:
                raise ValueError("FROZEN_MODEL_CHANGED")
            ready = {"status": "ESPN_ONLY_OPTIONAL_PDF_PARSER_UNAVAILABLE",
                     "checked_at": clock().isoformat(),
                     "model_sha256": MODEL_HASH,
                     "registration_sha256": REGISTRY_SHA,
                     "restrictions": "no verified official injuries or legal eligibility",
                     "optional_pdf_failure": type(exc).__name__ + ": " + str(exc)}
        write_once(report_root / "preflight.json", ready)
        # Previous genuine FINAL games are settled independently from pregame capture.
        settlements = settle_prior(slots, capture_root, settlement_root, day)
        write_once(report_root / "settlement_attempts.json", settlements)
        for opened, grouped in groups:
            # Clock governs actual eligibility, not expected time from task scheduler.
            now = clock()
            deadline = instant(grouped[0]["scheduled_freeze_at"])
            if now > deadline:
                records.extend({"slot": x["slot"], "status": "MISSED_FREEZE",
                                "observed_at": now.isoformat()} for x in grouped)
                continue
            while now < opened:
                if no_wait:
                    records.extend({"slot": x["slot"], "status": "NOT_DUE_TEST_ONLY"}
                                   for x in grouped)
                    break
                time.sleep(min(10, max(0.05, (opened - now).total_seconds())))
                now = clock()
            else:
                records.extend(run_group(grouped, capture_root, opened))
            # A future event cannot enter the result as a successful capture.
            write_once(report_root / ("window_" + str(grouped[0]["slot"]) + ".json"),
                       {"recorded_at": clock().isoformat(), "results": records[-len(grouped):]})
        summary = {"status": "COMPLETE_EXECUTION_WITH_EXPLICIT_BLOCKERS",
                   "ended_at": clock().isoformat(), "results": records,
                   "settlements": settlements}
    except Exception as exc:
        summary = {"status": "BLOCKED", "reason": type(exc).__name__ + ":" + str(exc),
                   "ended_at": clock().isoformat(), "results": records}
    # All original game-day receipts remain in the authoritative writable storage.
    try:
        evidence_manifest = sha_manifest(capture_root) if capture_root.exists() else {"files": [], "file_count": 0}
        write_once(report_root / "capture_tree_manifest.json", evidence_manifest)
        summary["captured_tree_file_count"] = evidence_manifest["file_count"]
    except Exception as exc:
        summary["manifest_error"] = type(exc).__name__ + ":" + str(exc)
        summary["status"] = "BLOCKED_MANIFEST"
    write_once(report_root / "finish.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default=None)
    parser.add_argument("--root", default="/work")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-wait", action="store_true",
                        help="test-only: do not sleep and do not claim future slots")
    args = parser.parse_args()
    if args.no_wait and not args.dry_run and os.environ.get("NBA_PILOT_TEST_MODE") != "1":
        parser.error("--no-wait is strictly test-only")
    print(json.dumps(run(day=args.day, root=args.root,
                         dry_run=args.dry_run, no_wait=args.no_wait),
                     indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
