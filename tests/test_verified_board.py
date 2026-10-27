"""A latest valid verification can approve current picks; old/blocked cannot."""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from pick_verification import forecast_digest
from verified_board import build
from test_pick_verification import build as fixture, DATE, ID
NOW=datetime(2026,10,27,20,30,tzinfo=timezone.utc)


def decision(row, status="verified", at="2026-10-27T20:20:00Z", tier="Tier 2"):
    return {"candidate_id":ID,"checked_at":at,"forecast_sha256":forecast_digest(row),
      "forecast_at":row["forecast_at"],"event_start":row["event_start"],
      "team":row["team"],"stat":row["stat"],"side":row["side"],
      "reference_line":row["reference_line"],
      "decision":status,"publication_eligible":status=="verified",
      "verified_rank":tier,"engine_a_reliable":True,"engine_b_reliable":True,
      "blend_validated":True,"verified_model_probability":.65,
      "verified_market_probability":.54,"reviewer":"Source reviewer",
      "blockers":[] if status=="verified" else ["NEW_STATUS_CONFLICT"]}


def receipt(row,status="verified",at="2026-10-27T20:20:00Z",tier="Tier 2"):
    return {"schema":"pick-verification-v1","date":DATE,
      "source_forecast_run_id":"daily-1",
      "decisions":[decision(row,status,at,tier)]}


class BoardTests(unittest.TestCase):
    def test_accepts_only_prestart_timely_source_linked_decisions(self):
        rows,_,_=fixture()
        board=build(rows,[receipt(rows[0])],DATE,now=NOW)
        self.assertEqual(board["status"],"verified_picks_available")
        self.assertEqual(board["rank_counts"]["Tier 2"],1)
        self.assertEqual(board["verified_picks"][0]["candidate_id"],ID)

    def test_latest_negative_recheck_vetoes_prior_verification(self):
        rows,_,_=fixture()
        board=build(rows,[receipt(rows[0]),receipt(rows[0],"blocked",
                         "2026-10-27T20:25:00Z")],DATE,now=NOW)
        self.assertEqual(board["verified_picks"],[])
        self.assertEqual(board["excluded"]["latest_decision_not_approved"],1)

    def test_past_kickoff_excludes_even_prior_verified(self):
        rows,_,_=fixture()
        after=datetime(2026,10,27,23,20,tzinfo=timezone.utc)
        board=build(rows,[receipt(rows[0])],DATE,now=after)
        self.assertEqual(board["verified_picks"],[])
        self.assertEqual(board["excluded"]["game_started"],1)

    def test_expired_verification_is_not_a_current_pick(self):
        rows,_,_=fixture()
        after=datetime(2026,10,27,22,0,tzinfo=timezone.utc)
        board=build(rows,[receipt(rows[0])],DATE,now=after)
        self.assertEqual(board["verified_picks"],[])
        self.assertEqual(board["excluded"]["verification_stale"],1)

    def test_forecast_change_invalidates_verified_receipt(self):
        rows,_,_=fixture()
        receipt_before=receipt(rows[0])
        rows[0]["reference_line"]=3.5
        board=build(rows,[receipt_before],DATE,now=NOW)
        self.assertEqual(board["verified_picks"],[])
        self.assertEqual(board["invalid_receipts"]["forecast_receipt_identity_mismatch"],1)

    def test_morning_settlement_preserves_decision_identity(self):
        rows,_,_=fixture()
        previous=receipt(rows[0])
        rows[0].update(actual_stat=4,outcome="win",settled_at="2026-10-28T10:00:00Z")
        board=build(rows,[previous],DATE,now=NOW)
        self.assertEqual(len(board["verified_picks"]),1)

    def test_tier1_requires_validated_blend(self):
        rows,_,_=fixture()
        prior=receipt(rows[0],tier="Tier 1")
        prior["decisions"][0]["blend_validated"]=False
        board=build(rows,[prior],DATE,now=NOW)
        self.assertEqual(board["verified_picks"],[])
        self.assertEqual(board["excluded"]["tier1_blend_unvalidated"],1)

    def test_missing_reviewer_or_engine_approval_blocks(self):
        rows,_,_=fixture()
        prior=receipt(rows[0])
        prior["decisions"][0]["reviewer"]=None
        board=build(rows,[prior],DATE,now=NOW)
        self.assertEqual(board["verified_picks"],[])
        self.assertEqual(board["excluded"]["latest_decision_not_approved"],1)


if __name__=="__main__":
    unittest.main()
