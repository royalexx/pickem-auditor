"""NHL official team membership evidence captured before future model inference."""
from __future__ import annotations
import hashlib,json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from v2.phase15_nhl_roster import (
    roster_members,roster_url,verify_receipt,membership_status,RosterEvidenceError,
)
from scripts.capture_phase15_nhl_roster import capture


def fixture_roster(*,ids=(),other=()):
    skaters=[{"id":i} for i in list(ids)+list(other)]
    needed=[8500000+i for i in range(11-len(skaters))]
    return json.dumps({"forwards":skaters+[{"id":i} for i in needed],
                       "defensemen":[{"id":8600000+i} for i in range(5)],
                       "goalies":[{"id":8700000},{"id":8700001}]},sort_keys=True).encode()


def make_receipt(root,team,pids=(),observed="2026-11-11T17:55:00Z"):
    raw=fixture_roster(ids=pids)
    path=f"roster_{team}.json"
    (root/path).write_bytes(raw)
    return {
        "schema":"nhl_independent_current_roster_receipt_v1",
        "team":team,"source_url":roster_url(team),
        "raw_archive_path":path,"sha256":hashlib.sha256(raw).hexdigest(),
        "bytes":len(raw),"retrieved_at":observed,
    }


class OfficialRosterTests(unittest.TestCase):
    def test_membership_and_opponent_consistency(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            receipts={"COL":make_receipt(root,"COL",pids=(8480069,)),
                      "TOR":make_receipt(root,"TOR",pids=(8470000,))}
            r=membership_status("8480069","COL","TOR",receipts=receipts,
                source_root=root,forecast_at="2026-11-11T18:00:00Z",
                event_start="2026-11-11T23:00:00Z")
            self.assertEqual(r["status"],"pre_event_team_membership_confirmed")
            self.assertFalse(r["is_confirmed_to_play"])

    def test_stale_market_team_goes_to_opponent_quarantine(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            receipts={"COL":make_receipt(root,"COL"),
                      "TOR":make_receipt(root,"TOR",pids=(8480069,))}
            r=membership_status("8480069","COL","TOR",receipts=receipts,
                source_root=root,forecast_at="2026-11-11T18:00:00Z",
                event_start="2026-11-11T23:00:00Z")
            self.assertEqual(r["status"],"blocked_opponent_roster_identity_conflict")

    def test_missing_player_cannot_be_implicitly_marked_active(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            receipts={"COL":make_receipt(root,"COL"),
                      "TOR":make_receipt(root,"TOR")}
            r=membership_status("8480069","COL","TOR",receipts=receipts,
                source_root=root,forecast_at="2026-11-11T18:00:00Z",
                event_start="2026-11-11T23:00:00Z")
            self.assertEqual(r["status"],"blocked_unverified_skaters_team_membership")

    def test_hash_tamper_and_future_retrieval_do_not_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);rec=make_receipt(root,"COL",pids=(8480069,))
            rec["retrieved_at"]="2026-11-11T18:01:00Z"
            with self.assertRaisesRegex(RosterEvidenceError,"not_genuinely_pregame"):
                verify_receipt(rec,source_root=root,
                    forecast_at="2026-11-11T18:00:00Z",
                    event_start="2026-11-11T23:00:00Z")
            rec["retrieved_at"]="2026-11-11T17:55:00Z"
            (root/rec["raw_archive_path"]).write_text("{}")
            with self.assertRaisesRegex(RosterEvidenceError,"sha_or_length"):
                verify_receipt(rec,source_root=root,
                    forecast_at="2026-11-11T18:00:00Z",
                    event_start="2026-11-11T23:00:00Z")

    def test_old_roster_not_pregame_certified(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            rec=make_receipt(root,"COL",observed="2026-11-11T10:00:00Z")
            with self.assertRaisesRegex(RosterEvidenceError,"too_old"):
                verify_receipt(rec,source_root=root,
                    forecast_at="2026-11-11T18:00:00Z",
                    event_start="2026-11-11T23:00:00Z")

    def test_capture_source_bytes_without_real_http_and_clock_is_append_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            phase={"schema":"v25-phase1-nhl-nba-certified-replay-v1",
                   "model_promotion_authorized":False,
                   "contracts":[{"sport":"NHL","team_id":"COL","opponent_id":"TOR",
                       "event_start":"2026-11-11T23:00:00Z"}]}
            clock=lambda:datetime(2026,11,11,18,tzinfo=timezone.utc)
            def fetch(url):
                self.assertIn("/v1/roster/",url)
                return fixture_roster(ids=(8480069,))
            output=capture(phase1=phase,output_dir=root/"out",
                           code_commit="c"*40,source_phase1_sha256="a"*64,
                           fetch=fetch,now=clock)
            self.assertEqual(output["teams_captured"],2)
            self.assertEqual(output["source_phase1_sha256"],"a"*64)
            self.assertTrue((root/"out"/"roster_manifest.json").is_file())
            with self.assertRaises(FileExistsError):
                capture(phase1=phase,output_dir=root/"out",
                        code_commit="c"*40,source_phase1_sha256="a"*64,
                        fetch=fetch,now=clock)


if __name__=="__main__":unittest.main()
