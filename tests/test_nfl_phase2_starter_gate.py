"""Adversarial pregame QB starter source gate: no backup QB props by inference."""
from __future__ import annotations
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from scripts.nfl_phase2_starter_gate import (
    QBStarterEvidenceError,verify_exact_starter,audit_qb_candidates,
    RECEIPT_SCHEMA,SOURCE_CONFIRMATION,
)
EVENT="2024_01_ARI_BUF"
GAME="2024-09-08T17:00:00Z"
FREEZE="2024-09-08T15:00:00Z"
CAPTURE="2024-09-08T14:50:00Z"
STARTER="00-0034857"
BACKUP="00-0034577"


def make(root,*,status=SOURCE_CONFIRMATION,
         pub="2024-09-08T14:30:00Z",captured=CAPTURE,
         player=STARTER,team="BUF",event=EVENT,post=False):
    raw={
       "game_id":event,"team_id":team,"starting_qb_player_id":player,
       "status":status,"published_at":pub,"is_postgame":post,
    }
    binary=json.dumps(raw,sort_keys=True).encode()
    path=root/"frozen_official_source.json"
    path.write_bytes(binary)
    receipt={"schema":RECEIPT_SCHEMA,
      "source_kind":"original_league_explicit_starting_qb",
      "source_url":"https://www.nfl.com/news/source-identifies-starting-qb",
      "game_id":event,"team_id":team,"starting_qb_player_id":player,
      "published_at":pub,"captured_at":captured,
      "original_raw_archive_path":path.name,
      "original_raw_sha256":hashlib.sha256(binary).hexdigest()}
    return receipt


def candidate(pid=STARTER,stat="pass attempts",line=31.5):
    return {"game_id":EVENT,"team":"BUF","player_id":pid,
            "market":stat,"research_line":line}


class StarterGateTests(unittest.TestCase):
    def _verify(self,rec,root):
        return verify_exact_starter(rec,root=root,game_id=EVENT,
           team_id="BUF",freeze_at=FREEZE,kickoff_at=GAME)

    def test_matching_starter_only_research_not_production(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            r=make(root)
            x=audit_qb_candidates(candidates=[
              candidate(STARTER),candidate(BACKUP,stat="pass attempts",line=2.5),
              candidate(STARTER,stat="qb rushing yards",line=17.5)],
              original_receipts={(EVENT,"BUF"):r},
              source_root=root,freeze_at=FREEZE,kickoff_at=GAME)
            self.assertEqual(x["original_candidates"],3)
            self.assertEqual(x["qualified_candidate_count"],2)
            self.assertEqual(x["abstentions"]["not_the_explicit_pregame_named_starter"],1)
            self.assertEqual(x["individual_candidate_ledger"][1]["status"],"abstain")
            self.assertEqual(x["individual_candidate_ledger"][0]["status"],"source_qualified_candidate_only")
            self.assertFalse(x["tier1_tier2_authorized"])
            self.assertFalse(x["pre_game_source_truth_independently_verified"])

    def test_missing_source_blocks_every_original_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            pool=[candidate(),candidate(BACKUP,line=3.5)]
            before=copy.deepcopy(pool)
            x=audit_qb_candidates(candidates=pool,original_receipts={},
              source_root=Path(folder),freeze_at=FREEZE,kickoff_at=GAME)
            self.assertEqual(x["qualified_candidate_count"],0)
            self.assertEqual(len(x["individual_candidate_ledger"]),2)
            self.assertEqual(x["abstentions"]["qualified_original_starter_receipt_missing"],2)
            self.assertEqual(pool,before)

    def test_depth_chart_and_injury_status_never_count_as_confirmed_starter(self):
        for bad in ("projected_starter","depth_chart_first","active_roster",
                    "was_qb_with_most_pass_attempts"):
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder);rec=make(root,status=bad)
                with self.assertRaisesRegex(QBStarterEvidenceError,"projection_not_confirmation"):
                    self._verify(rec,root)

    def test_postgame_cannot_retro_certify_starter(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);rec=make(root,post=True)
            with self.assertRaisesRegex(QBStarterEvidenceError,"postgame"):
                self._verify(rec,root)

    def test_late_or_stale_collector_clock(self):
        for stamp,error in ((GAME,"source_captured_after_forecast"),
                            ("2024-09-08T15:01:00Z","source_captured_after_forecast"),
                            ("2024-09-07T20:00:00Z","source_stale")):
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder);rec=make(root,captured=stamp)
                with self.assertRaisesRegex(QBStarterEvidenceError,error):
                    self._verify(rec,root)

    def test_unauthenticated_publisher_truth_is_not_certified(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);rec=make(root)
            x=self._verify(rec,root)
            self.assertFalse(x["upstream_publication_independently_verified"])
            self.assertTrue(x["starter_claim_requires_source_adapter_verification"])

    def test_only_approved_league_source_and_valid_https_port(self):
        for bad in ("http://www.nfl.com/news/article",
                    "https://www.nfl.com.evil.com/2024",
                    "https://user@www.nfl.com/news/2024",
                    "https://www.nfl.com:abc/news/2024"):
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder);rec=make(root);rec["source_url"]=bad
                with self.assertRaises(QBStarterEvidenceError):
                    self._verify(rec,root)

    def test_original_source_sha_and_identity_is_immutable(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);rec=make(root)
            (root/rec["original_raw_archive_path"]).write_text("{}")
            with self.assertRaisesRegex(QBStarterEvidenceError,"sha_mismatch"):
                self._verify(rec,root)
            rec=make(root)
            rec["starting_qb_player_id"]=BACKUP
            with self.assertRaisesRegex(QBStarterEvidenceError,"identity_mismatch"):
                self._verify(rec,root)

    def test_wrong_game_team_and_publisher_clock(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);rec=make(root,team="ARI")
            with self.assertRaisesRegex(QBStarterEvidenceError,"receipt_event_or_team_mismatch"):
                self._verify(rec,root)
            rec=make(root)
            rec["published_at"]="2024-09-08T14:55:00Z"
            with self.assertRaisesRegex(QBStarterEvidenceError,"provider_publication_after"):
                self._verify(rec,root)

    def test_unsafe_source_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);rec=make(root)
            for path in ("../escape.json","/etc/passwd","sub\\file.json"):
                mutated={**rec,"original_raw_archive_path":path}
                with self.assertRaisesRegex(QBStarterEvidenceError,"unsafe_original"):
                    self._verify(mutated,root)

    def test_duplicate_or_invalid_original_qb_candidate_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with self.assertRaisesRegex(QBStarterEvidenceError,"duplicate_original"):
                audit_qb_candidates(candidates=[candidate(),candidate()],
                    original_receipts={},source_root=root,freeze_at=FREEZE,kickoff_at=GAME)
            with self.assertRaisesRegex(QBStarterEvidenceError,"invalid_original_line"):
                audit_qb_candidates(candidates=[candidate(line=float("nan"))],
                    original_receipts={},source_root=root,freeze_at=FREEZE,kickoff_at=GAME)

    def test_not_qb_market_or_mixed_game_team_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with self.assertRaisesRegex(QBStarterEvidenceError,"wrong_non_qb_market"):
                audit_qb_candidates(candidates=[candidate(stat="targets")],
                    original_receipts={},source_root=root,freeze_at=FREEZE,kickoff_at=GAME)
            other={**candidate(),"team":"ARI"}
            with self.assertRaisesRegex(QBStarterEvidenceError,"requires_one_game_team"):
                audit_qb_candidates(candidates=[candidate(),other],
                    original_receipts={},source_root=root,freeze_at=FREEZE,kickoff_at=GAME)


if __name__=="__main__":
    unittest.main()
