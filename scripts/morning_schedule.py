#!/usr/bin/env python3
"""Select schedule-local morning/afternoon work and guard durable morning reruns.

GitHub's schedule events are best-effort; morning backup cron windows must be
idempotent. The authoritative completion marker resides on the separate
data/shadow-calibration branch and is only written after successful settlement
and forecast-identity verification, then persisted alongside the outcomes.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

TORONTO = ZoneInfo("America/Toronto")
STATE_BRANCH = "refs/remotes/origin/data/shadow-calibration"


def phase_for_event(event, trigger, now):
    """Return (phase, scheduled_local_slot, reason); never guess today's UTC hour."""
    if now.tzinfo is None:
        raise ValueError("aware clock required")
    now = now.astimezone(timezone.utc)
    today = now.astimezone(TORONTO).date()
    if trigger == "workflow_dispatch":
        phase = (event.get("inputs") or {}).get("phase")
        return (phase, None, "manual_dispatch") if phase in ("morning", "afternoon") else (
            "skip", None, "invalid_manual_phase")
    local_now = now.astimezone(TORONTO)
    if trigger == "workflow_run":
        source = event.get("workflow_run") or {}
        if (source.get("name") == "NHL Bayesian history warehouse backfill"
                and source.get("conclusion") == "success"
                and source.get("head_branch") == "main"
                and 6 <= local_now.hour < 12):
            return "morning", local_now.isoformat(), "completed_history_workflow_recovery"
        return "skip", None, "workflow_run_not_safe_for_morning"
    if trigger == "push":
        # Only a deliberately dated main-branch recovery commit can settle.
        head = event.get("head_commit") or {}
        expected = ".github/morning-recovery/" + today.isoformat() + ".json"
        changed = list(head.get("added") or []) + list(head.get("modified") or [])
        if (event.get("ref") == "refs/heads/main"
                and head.get("message") == "ops: recover morning " + today.isoformat()
                and expected in changed and 6 <= local_now.hour < 12):
            return "morning", local_now.isoformat(), "authorized_dated_push_recovery"
        return "skip", None, "not_authorized_morning_recovery_push"
    if trigger != "schedule":
        return "skip", None, "unsupported_event"
    fields = str(event.get("schedule") or "").split()
    if len(fields) != 5:
        return "skip", None, "invalid_cron"
    try:
        minute, hour = int(fields[0]), int(fields[1])
    except ValueError:
        return "skip", None, "invalid_cron"
    if not 0 <= hour < 24 or not 0 <= minute < 60:
        return "skip", None, "invalid_cron"
    planned = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if planned > now + timedelta(minutes=2):
        planned -= timedelta(days=1)
    local = planned.astimezone(TORONTO)
    lag = now-planned
    if not timedelta(0) <= lag < timedelta(hours=12) or local.date() != today:
        return "skip", local.isoformat(), "missed_local_day_or_excessive_lag"
    # Primary morning slot 06:13; backups are timezone-aware 06/07/08:41.
    if ((local.hour == 6 and local.minute == 13) or
            (local.hour in (6, 7, 8) and local.minute == 41)):
        return "morning", local.isoformat(), "morning_primary_or_recovery"
    if local.hour == 9 and local.minute == 37:
        return "morning", local.isoformat(), "late_morning_watchdog_schedule"
    if local.hour == 16 and local.minute == 13:
        return "afternoon", local.isoformat(), "afternoon_primary"
    return "skip", local.isoformat(), "inactive_timezone_offset"


def verified_repository_push_recovery(today, now, *, git_run=None):
    """Validate the checked-out commit, not potentially abbreviated push JSON.

    GitHub's contents-API push payload may omit head_commit.added.
    Inspect the checked-out commit and its actual changed paths instead.
    """
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        return False
    local = now.astimezone(TORONTO)
    if not 6 <= local.hour < 12:
        return False
    git_run = git_run or subprocess.run
    expected = ".github/morning-recovery/" + today + ".json"
    try:
        subject = git_run(["git","log","-1","--format=%s","HEAD"],
                          capture_output=True,text=True,timeout=15,check=False)
        changed = git_run(["git","show","--format=","--name-only","--root","HEAD"],
                          capture_output=True,text=True,timeout=15,check=False)
        return (subject.returncode == 0 and changed.returncode == 0
                and subject.stdout.strip() == "ops: recover morning " + today
                and expected in changed.stdout.splitlines())
    except (OSError, subprocess.TimeoutExpired):
        return False


def completed_marker_text(text, expected_date):
    """Do not accept anything except a correctly dated persisted success receipt."""
    try:
        marker = json.loads(text)
        return (isinstance(marker,dict)
                and marker.get("date") == expected_date
                and marker.get("phase") == "morning"
                and marker.get("status") == "completed"
                and isinstance(marker.get("run_id"),str)
                and marker["run_id"].isdigit()
                and isinstance(marker.get("receipt_sha256"),str)
                and len(marker["receipt_sha256"]) == 64
                and marker.get("settle_ok") is True
                and marker.get("identity_ok") is True)
    except (ValueError, TypeError, KeyError):
        return False


def marker_status(today, *, git_run=None):
    """Return (completed, reason); network failure should never be a fake success."""
    git_run = git_run or subprocess.run
    try:
        fetch = git_run(["git","fetch","--quiet","origin",
            "refs/heads/data/shadow-calibration:"+STATE_BRANCH],
            capture_output=True,text=True,timeout=40,check=False)
        if fetch.returncode:
            return False, "marker_branch_fetch_failed"
        result = git_run(["git","show",f"{STATE_BRANCH}:data/morning_runs/{today}.json"],
            capture_output=True,text=True,timeout=15,check=False)
        if result.returncode:
            return False, "no_completion_marker"
        if completed_marker_text(result.stdout,today):
            return True, "prior_completed_morning_settlement"
        return False, "invalid_completion_marker"
    except (OSError,subprocess.TimeoutExpired):
        return False, "marker_lookup_unavailable"


def choose(event, trigger, now, *, git_run=None):
    phase,slot,reason=phase_for_event(event,trigger,now)
    today=now.astimezone(TORONTO).date().isoformat()
    if (trigger == "push" and phase == "skip"
            and verified_repository_push_recovery(today, now, git_run=git_run)):
        phase,slot,reason="morning",now.astimezone(TORONTO).isoformat(),"validated_repository_recovery_commit"
    result={"phase":phase,"slot":slot,"reason":reason,"toronto_date":today}
    force = (event.get("inputs") or {}).get("force_morning")
    manual_override = trigger=="workflow_dispatch" and force in (True, "true", "True")
    if phase=="morning" and not manual_override:
        completed, state = marker_status(today,git_run=git_run)
        result["marker_check"] = state
        if completed:
            result["phase"]="skip"
            result["reason"]="already_settled"
    elif manual_override and phase=="morning":
        result["marker_check"]="explicit_manual_force"
    return result


def verified_success_marker(receipt, run_id, now):
    """Create a marker only from verified successful stages, never a green-looking skip."""
    if not isinstance(receipt,dict) or receipt.get("phase")!="morning":
        raise ValueError("only morning receipts can be marked")
    stages=receipt.get("stages") or {}
    required={"nhl_boxscores","install_dependencies","restore_forecasts",
              "multisport_slate","sport_coverage","settle_forecasts",
              "verify_forecast_identity"}
    if not required.issubset(stages) or not all(
            isinstance(v,dict) and v.get("ok") is True for v in stages.values()):
        raise ValueError("all required pipeline stages must succeed")
    if receipt.get("persisted_forecasts_loaded") is not True:
        raise ValueError("verified history was not loaded")
    if (receipt.get("sport_coverage") or {}).get("status") != "success":
        raise ValueError("sport coverage was not verified")
    if not str(run_id).isdigit():
        raise ValueError("GitHub run ID missing")
    if now.tzinfo is None:
        raise ValueError("aware clock required")
    day=now.astimezone(TORONTO).date().isoformat()
    started=receipt.get("started_at_utc")
    if not isinstance(started,str):
        raise ValueError("missing timestamped receipt")
    timestamp=datetime.fromisoformat(started.replace("Z","+00:00"))
    if timestamp.tzinfo is None or timestamp.astimezone(TORONTO).date().isoformat()!=day:
        raise ValueError("morning receipt date mismatch")
    payload=json.dumps(receipt,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    return {"date":day,"phase":"morning","status":"completed",
            "run_id":str(run_id),"settle_ok":True,"identity_ok":True,
            "receipt_sha256":hashlib.sha256(payload.encode()).hexdigest(),
            "started_at_utc":started,
            "verified_at_utc":now.astimezone(timezone.utc).isoformat()}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="mode",required=True)
    gate=sub.add_parser("gate")
    gate.add_argument("--event-path",required=True)
    gate.add_argument("--trigger",required=True)
    gate.add_argument("--output",required=True)
    mark=sub.add_parser("mark")
    mark.add_argument("--receipt",required=True)
    mark.add_argument("--run-id",required=True)
    mark.add_argument("--output-dir",default="data/morning_runs")
    args=p.parse_args(argv)
    now=datetime.now(timezone.utc)
    if args.mode=="gate":
        event=json.loads(Path(args.event_path).read_text())
        decision=choose(event,args.trigger,now)
        with Path(args.output).open("a") as f:
            f.write(f"phase={decision['phase']}\n")
            f.write(f"date={decision['toronto_date']}\n")
            f.write(f"reason={decision['reason']}\n")
        print(json.dumps(decision,sort_keys=True))
    else:
        receipt=json.loads(Path(args.receipt).read_text())
        marker=verified_success_marker(receipt,args.run_id,now)
        folder=Path(args.output_dir);folder.mkdir(parents=True,exist_ok=True)
        target=folder/(marker["date"]+".json")
        if target.exists():
            # A force_morning manual rerun may settle additional late-reported
            # outcomes, but must preserve the earlier completed-day identity.
            if not completed_marker_text(target.read_text(),marker["date"]):
                raise ValueError("existing morning settlement marker is invalid")
            status="completed_marker_preserved_after_explicit_rerun"
        else:
            target.write_text(json.dumps(marker,sort_keys=True,indent=2)+"\n")
            status="completed_marker_written"
        print(json.dumps({"status":status,
                          "date":marker["date"],"run_id":marker["run_id"]}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
