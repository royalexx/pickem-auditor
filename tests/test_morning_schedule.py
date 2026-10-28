"""Recovery schedule is timezone-correct, idempotent and fails closed on receipts."""
import hashlib
import json
from datetime import datetime,timezone,timedelta
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from morning_schedule import (
    phase_for_event, choose, completed_marker_text,
    verified_success_marker,
)

UTC=timezone.utc
def at(s):
    return datetime.fromisoformat(s.replace("Z","+00:00"))

def event(cron):
    return {"schedule":cron}
def runner_return(marker=None, fetch_ok=True):
    commands=[]
    def run(args,**kw):
        commands.append(args)
        if args[1]=="fetch":
            return SimpleNamespace(returncode=0 if fetch_ok else 1,stdout="",stderr="")
        return SimpleNamespace(returncode=0 if marker is not None else 128,
                               stdout=marker or "",stderr="")
    return run,commands

def success_receipt(start="2026-10-28T13:55:17Z"):
    names=("nhl_boxscores","install_dependencies","restore_forecasts",
           "multisport_slate","sport_coverage","settle_forecasts",
           "verify_forecast_identity")
    return {"phase":"morning","started_at_utc":start,
            "persisted_forecasts_loaded":True,
            "sport_coverage":{"status":"success"},
            "stages":{x:{"ok":True,"returncode":0} for x in names}}

class MorningScheduleTests(unittest.TestCase):
    def test_toronto_morning_primary_in_dst_and_winter(self):
        for utc,cron in [
            ("2026-10-28T10:17:00Z","13 10 * * *"),
            ("2026-11-04T11:17:00Z","13 11 * * *"),
        ]:
            phase,slot,_=phase_for_event(event(cron),"schedule",at(utc))
            self.assertEqual(phase,"morning")
            self.assertIn("06:13:00",slot)

    def test_backup_slots_cover_both_time_offsets(self):
        for utc,cron in [
            ("2026-10-28T11:43:00Z","41 11 * * *"),
            ("2026-10-28T12:43:00Z","41 12 * * *"),
            ("2026-11-04T11:43:00Z","41 11 * * *"),
            ("2026-11-04T12:43:00Z","41 12 * * *"),
        ]:
            phase,slot,_=phase_for_event(event(cron),"schedule",at(utc))
            self.assertEqual(phase,"morning",(utc,cron,slot))
            self.assertIn("41:00",slot)

    def test_wrong_offset_afternoon_and_stale_cron(self):
        self.assertEqual(phase_for_event(event("13 11 * * *"),"schedule",
                         at("2026-10-28T11:14:00Z"))[0],"skip")
        self.assertEqual(phase_for_event(event("13 20 * * *"),"schedule",
                         at("2026-10-28T20:14:00Z"))[0],"afternoon")
        self.assertEqual(phase_for_event(event("13 21 * * *"),"schedule",
                         at("2026-10-28T21:14:00Z"))[0],"skip")
        self.assertEqual(phase_for_event(event("13 10 * * *"),"schedule",
                         at("2026-10-28T23:14:00Z"))[0],"skip")

    def test_no_morning_run_on_inappropriate_trigger(self):
        self.assertEqual(phase_for_event(event("13 10 * * *"),"push",
                         at("2026-10-28T10:14:00Z"))[0],"skip")
        self.assertEqual(phase_for_event({"inputs":{"phase":"morning"}},
                         "workflow_dispatch",at("2026-10-28T13:00:00Z"))[0],"morning")

    def test_completion_marker_is_persisted_and_readable(self):
        receipt=success_receipt()
        marker=verified_success_marker(receipt,"40700885909",
                                        at("2026-10-28T13:57:48Z"))
        self.assertEqual(marker["date"],"2026-10-28")
        self.assertEqual(marker["phase"],"morning")
        self.assertEqual(marker["status"],"completed")
        self.assertTrue(marker["settle_ok"])
        self.assertTrue(marker["identity_ok"])
        self.assertEqual(len(marker["receipt_sha256"]),64)
        self.assertTrue(completed_marker_text(json.dumps(marker),"2026-10-28"))
        self.assertFalse(completed_marker_text(json.dumps(marker),"2026-10-29"))

    def test_backup_skips_only_valid_persisted_completed_marker(self):
        marker=verified_success_marker(success_receipt(),"40700885909",
                                        at("2026-10-28T13:57:48Z"))
        run,commands=runner_return(json.dumps(marker))
        result=choose(event("41 11 * * *"),"schedule",
                      at("2026-10-28T11:43:00Z"),git_run=run)
        self.assertEqual(result["phase"],"skip")
        self.assertEqual(result["reason"],"already_settled")
        self.assertIn("data/morning_runs/2026-10-28.json",commands[1][-1])
        runner,_=runner_return(None)
        result=choose(event("41 11 * * *"),"schedule",
                      at("2026-10-28T11:43:00Z"),git_run=runner)
        self.assertEqual(result["phase"],"morning")
        self.assertEqual(result["marker_check"],"no_completion_marker")

    def test_corrupted_marker_or_fetch_failure_never_claim_success(self):
        runner,_=runner_return('{"status":"completed"}')
        result=choose(event("41 11 * * *"),"schedule",
                      at("2026-10-28T11:43:00Z"),git_run=runner)
        self.assertEqual(result["phase"],"morning")
        self.assertEqual(result["marker_check"],"invalid_completion_marker")
        runner,_=runner_return(None,fetch_ok=False)
        result=choose(event("41 11 * * *"),"schedule",
                      at("2026-10-28T11:43:00Z"),git_run=runner)
        self.assertEqual(result["phase"],"morning")
        self.assertEqual(result["marker_check"],"marker_branch_fetch_failed")

    def test_explicit_manual_force_can_rerun_completed_day(self):
        marker=verified_success_marker(success_receipt(),"40700885909",
                                        at("2026-10-28T13:57:48Z"))
        runner,_=runner_return(json.dumps(marker))
        event_payload={"inputs":{"phase":"morning","force_morning":True}}
        r=choose(event_payload,"workflow_dispatch",at("2026-10-28T14:00:00Z"),
                 git_run=runner)
        self.assertEqual(r["phase"],"morning")
        self.assertEqual(r["marker_check"],"explicit_manual_force")

    def test_no_marker_on_incomplete_settlement_or_identity_error(self):
        invalid=success_receipt()
        invalid["stages"]["settle_forecasts"]["ok"]=False
        with self.assertRaises(ValueError):
            verified_success_marker(invalid,"40700885909",
                                    at("2026-10-28T13:57:48Z"))
        invalid=success_receipt()
        invalid["stages"]["verify_forecast_identity"]["ok"]=False
        with self.assertRaises(ValueError):
            verified_success_marker(invalid,"40700885909",
                                    at("2026-10-28T13:57:48Z"))
        invalid=success_receipt()
        invalid["sport_coverage"]["status"]="failed"
        with self.assertRaises(ValueError):
            verified_success_marker(invalid,"40700885909",
                                    at("2026-10-28T13:57:48Z"))

    def test_manual_force_does_not_replace_prior_success_marker(self):
        # 'mark' reuses the immutable original completion marker, even when
        # force_morning recomputes already-settled historical outcomes.
        import tempfile
        from unittest.mock import patch
        import morning_schedule as scheduler
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);d=root/"data/morning_runs";d.mkdir(parents=True)
            receipt=root/"daily_receipt.json"
            receipt.write_text(json.dumps(success_receipt()))
            old=verified_success_marker(success_receipt(),"40700885909",
                                        at("2026-10-28T13:57:48Z"))
            target=d/"2026-10-28.json"
            target.write_text(json.dumps(old))
            with patch.object(scheduler,"datetime") as dt:
                dt.now.return_value=at("2026-10-28T14:05:00Z")
                self.assertEqual(scheduler.main(["mark","--receipt",str(receipt),
                    "--run-id","40799999999","--output-dir",str(d)]),0)
            self.assertEqual(json.loads(target.read_text())["run_id"],"40700885909")

    def test_scheduler_and_state_branch_wiring(self):
        root=Path(__file__).resolve().parents[1]
        workflow=(root/".github/workflows/pickem-daily.yml").read_text()
        store=(root/"scripts/shadow_store.sh").read_text()
        self.assertIn("cron: '41 11 * * *'",workflow)
        self.assertIn("cron: '41 12 * * *'",workflow)
        self.assertIn("scripts/morning_schedule.py gate",workflow)
        self.assertIn("scripts/morning_schedule.py','mark'",workflow)
        self.assertIn("data/morning_runs",store)
        self.assertIn("IMMUTABLE_MORNING_SETTLEMENT_MARKER_CONFLICT",store)
        self.assertNotIn("one-shot missed morning settlement",workflow)

if __name__=="__main__":
    unittest.main()
