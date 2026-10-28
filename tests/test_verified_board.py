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
      "blend_validated":True,"verified_model_probability":.85,
      "verified_market_probability":.54,"reviewer":"Source reviewer",
      "review_type":"human_attestation",
      "mechanism_evidence":{"version":"mechanism-evidence-v1",
         "tier_ceiling":tier, "quality":"quantified_model_incremental_causal_chain",
         "legacy_count_not_authoritative":True,"no_probability_adjustment":True},
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

    def test_old_numeric_57pct_tiers_are_no_longer_publishable(self):
        rows,_,_=fixture()
        low=receipt(rows[0],tier="Tier 2")
        low["decisions"][0]["verified_model_probability"]=.61
        board=build(rows,[low],DATE,now=NOW)
        self.assertFalse(board["verified_picks"])
        self.assertEqual(board["excluded"]["tier_quality_definition_not_met"],1)
        low=receipt(rows[0],tier="Tier 3")
        low["decisions"][0]["verified_model_probability"]=.62
        board=build(rows,[low],DATE,now=NOW)
        self.assertFalse(board["verified_picks"])

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

    def test_missing_legacy_quality_receipt_cannot_publish(self):
        rows,_,_=fixture()
        old=receipt(rows[0])
        old["decisions"][0].pop("mechanism_evidence")
        board=build(rows,[old],DATE,now=NOW)
        self.assertEqual(board["verified_picks"],[])
        self.assertEqual(board["excluded"]["quality_audit_receipt_missing_or_invalid"],1)

    def test_count_claim_cannot_override_quality_ceiling(self):
        rows,_,_=fixture()
        fabricated=receipt(rows[0],tier="Tier 2")
        fabricated["decisions"][0]["mechanism_evidence"]["tier_ceiling"]="Tier 3"
        board=build(rows,[fabricated],DATE,now=NOW)
        self.assertEqual(board["verified_picks"],[])
        self.assertEqual(board["excluded"]["tier_exceeds_source_quality_ceiling"],1)

    def test_machine_receipt_cannot_claim_tier2_from_embedded_workload(self):
        rows,_,_=fixture()
        fabricated=receipt(rows[0],tier="Tier 2")
        d=fabricated["decisions"][0]
        d["review_type"]="structured_machine_verification"
        d["reviewer"]="machine:deterministic-primary-source-v1"
        d["mechanism_evidence"]["machine_overlap_detected"]=True
        d["mechanism_evidence"]["tier_ceiling"]="Tier 2"
        board=build(rows,[fabricated],DATE,now=NOW)
        self.assertEqual(board["verified_picks"],[])
        self.assertEqual(board["excluded"]["machine_review_quality_identity_invalid"],1)

    def test_missing_reviewer_or_engine_approval_blocks(self):
        rows,_,_=fixture()
        prior=receipt(rows[0])
        prior["decisions"][0]["reviewer"]=None
        board=build(rows,[prior],DATE,now=NOW)
        self.assertEqual(board["verified_picks"],[])
        self.assertEqual(board["excluded"]["latest_decision_not_approved"],1)


if __name__=="__main__":
    unittest.main()
