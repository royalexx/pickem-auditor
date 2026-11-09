"""Independent receipt/timing audit tests for all-market weekly replay."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import nfl_weekly_blind_multimarket as m
import nfl_weekly_blind_multimarket_audit as a


def make_receipt(root,week,*,previous_sha=None,
                 previous_n=0,update_n=0):
    root=Path(root)
    d=root/f"2024_week_{week:02d}"
    d.mkdir(parents=True)
    market_packets={stat:{"trained_n":previous_n,
                          "candidates":[]} for stat in m.MARKETS}
    packet={"schema":m.SCHEMA,"stage":"pregame","year":2024,"week":week,
            "target_week_results_in_packet":False,
            "markets":list(m.MARKETS),"market_packets":market_packets,
            "previous_week_settlement_sha256":previous_sha}
    packet_sha=m.write_new(d/"pregame_packet.json",packet)
    frozen={"schema":m.SCHEMA,"stage":"all_markets_frozen",
            "year":2024,"week":week,"packet_sha256":packet_sha,
            "markets_order":list(m.MARKETS),
            "market_results":{stat:{"predictions":[]} for stat in m.MARKETS}}
    frozen_sha=m.write_new(d/"frozen_all_markets.json",frozen)
    (d/"encrypted_outcomes.bin").write_bytes(b"cipher_not_plaintext")
    cipher_sha=hashlib.sha256(b"cipher_not_plaintext").hexdigest()
    locked={"schema":m.SCHEMA,"stage":"complete_week_market_lock",
            "year":2024,"week":week,"market_count":len(m.MARKETS),
            "packet_sha256":packet_sha,"forecast_sha256":frozen_sha,
            "encrypted_vault_sha256":cipher_sha}
    lock_sha=m.write_new(d/"lock.json",locked)
    empty={"n":0}
    by_market={
        stat:{"pregame_candidates":0,"forecasted":0,
              "scored_participants":0,
              "unmatched_nonparticipating_or_unverified":0,
              "model":empty,"historical_baseline":empty}
        for stat in m.MARKETS}
    settled={"schema":m.SCHEMA,"stage":"complete_week_settled",
             "year":2024,"week":week,
             "all_markets_frozen_before_any_result":True,
             "trained_only_after_whole_week_revealed":True,
             "forecast_sha256":frozen_sha,"encrypted_vault_sha256":cipher_sha,
             "lock_sha256":lock_sha,"markets_scored":len(m.MARKETS),
             "by_market":by_market,
             "total_forecasts":0,"total_scored":0,
             "prior_train_examples_by_market":{x:previous_n for x in m.MARKETS},
             "next_week_model_update":{x:update_n for x in m.MARKETS}}
    return m.write_new(d/"settlement.json",settled)


class AllMarketReceiptAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_complete_market_lock_and_previous_week_training_chain(self):
        first=make_receipt(self.root,1,previous_n=10,update_n=4)
        make_receipt(self.root,2,previous_sha=first,previous_n=14,update_n=3)
        result=a.audit(self.root,expected_weeks=2)
        self.assertEqual(result["weeks"],2)
        self.assertEqual(result["n_markets"],16)
        self.assertTrue(result["sequential_all_market_reveal_verified"])
        self.assertTrue(result["training_counts_advance_only_after_previous_week_settlement"])
        self.assertFalse(result["calibration_or_tier_promotion_authorized"])

    def test_tampered_pregame_market_receipt_fails_closed(self):
        make_receipt(self.root,1)
        file=self.root/"2024_week_01"/"pregame_packet.json"
        data=json.loads(file.read_text())
        data["market_packets"].pop("tackles + assists")
        file.write_text(json.dumps(data))
        with self.assertRaisesRegex(a.WeeklyAuditError,
                                    "corrupted_frozen_week_receipt"):
            a.audit(self.root,expected_weeks=1)

    def test_broken_forecast_sha_chain_fails_closed(self):
        make_receipt(self.root,1)
        file=self.root/"2024_week_01"/"frozen_all_markets.json"
        data=json.loads(file.read_text())
        data["changed_after_lock"]=True
        file.write_text(json.dumps(data))
        with self.assertRaisesRegex(a.WeeklyAuditError,
                                    "corrupted_frozen_week_receipt"):
            a.audit(self.root,expected_weeks=1)

    def test_failing_to_train_on_revealed_previous_week_is_caught(self):
        first=make_receipt(self.root,1,previous_n=10,update_n=5)
        make_receipt(self.root,2,previous_sha=first,previous_n=10,update_n=3)
        with self.assertRaisesRegex(a.WeeklyAuditError,
                                    "training_counts_did_not_update_after_settlement"):
            a.audit(self.root,expected_weeks=2)

    def test_incomplete_week_market_list_never_certified(self):
        make_receipt(self.root,1)
        file=self.root/"2024_week_01"/"settlement.json"
        data=json.loads(file.read_text())
        data["by_market"].pop("pass attempts")
        file.write_text(json.dumps(data))
        with self.assertRaisesRegex(a.WeeklyAuditError,
                                    "incomplete_required_week_markets"):
            a.audit(self.root,expected_weeks=1)

    def test_weighted_proper_score_calculation_same_cohort(self):
        def summary(n,model,control):
            return {"by_market":{"targets":{
                "model":{"n":n,"brier":model,"log_loss":model+.1,
                         "directional_accuracy":.6},
                "historical_baseline":{"n":n,"brier":control,
                         "log_loss":control+.1,"directional_accuracy":.5}}}}
        res=a.weighted_metrics([summary(2,.2,.3),summary(8,.4,.5)],"targets")
        self.assertEqual(res["n"],10)
        self.assertAlmostEqual(res["model_brier"],.36)
        self.assertAlmostEqual(res["baseline_brier"],.46)
        self.assertAlmostEqual(res["delta_model_minus_baseline_brier"],-.1)
        self.assertAlmostEqual(res["delta_model_minus_baseline_directional_accuracy"],.1)


if __name__=="__main__":
    unittest.main()
