"""Strictly frozen NHL population posterior is not refit to heldout game results."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import historical_nhl_warehouse as wh
import joint_nhl_bayes as joint
import joint_nhl_holdout as hold


def sample_rows(day,gid):
    rows=[]
    for i in range(16):
        rows.append({"version":wh.VERSION,"game_id":str(gid),
           "game_date":day,"season":"2018","player_id":str(100+i),
           "position":"F" if i<12 else "D","team":"BOS" if i<8 else "NYR",
           "opponent":"NYR" if i<8 else "BOS","home":i>=8,
           "shots":i%5,"toi_minutes":14.5+i/10,
           "source_url":"https://api-web.nhle.com/v1/gamecenter/x/boxscore",
           "source_sha256":"f"*64})
    return rows


class FrozenHoldout(unittest.TestCase):
    def test_same_train_design_on_unseen_actuals(self):
        train=sample_rows("2018-10-01",2018020001)
        later=sample_rows("2018-10-02",2018020002)
        frozen=joint.prepare(train,min_rows=8)
        visited=[]
        def forecast(_idata,data,**kw):
            self.assertIs(data,frozen)
            self.assertEqual(data["last_game"],"2018-10-01")
            visited.append(kw["player_id"])
            return {"q_over":.6}
        with patch.object(hold.joint,"predictive_cache",return_value={"count":100,"arrays":{}}), \
             patch.object(hold.joint,"forecast",side_effect=forecast):
            report=hold.evaluate(None,train,frozen,train+later,
                cutoff="2018-10-02",until="2018-10-03",
                diagnostics={"status":"sampling_diagnostics_pass","posterior_sampling_ok":True},
                draws=500)
        self.assertEqual(report["model_covered_rows"],16)
        self.assertEqual(len(report["scored_observations"]),16)
        self.assertEqual(report["paired_by_game_date"]["n_dates"],1)
        self.assertEqual(report["paired_by_game_date"]["status"],"exploratory_insufficient_dates")
        self.assertIn("F",report["by_position"])
        self.assertIn("D",report["by_position"])
        self.assertEqual(len(visited),16)
        self.assertFalse(report["calibrated_for_production"])
        self.assertFalse(report["publication_eligible"])
        self.assertEqual(report["status"],"underpowered_holdout")
        self.assertIsNotNone(report["gamma_poisson_control"]["log_loss"])
        self.assertFalse(report["historical_sportsbook_line_claim"])

    def test_date_cluster_resampling_deterministic_and_never_promotes(self):
        pairs=[(.8,.6,1,"2018-10-02"),(.25,.45,0,"2018-10-02"),
               (.3,.4,1,"2018-10-03"),(.55,.5,0,"2018-10-03")]
        first=hold.paired_date_bootstrap(pairs,repeats=250,seed=22)
        second=hold.paired_date_bootstrap(pairs,repeats=250,seed=22)
        self.assertEqual(first,second)
        self.assertEqual(first["n_dates"],2)
        self.assertEqual(first["n_observations"],4)
        self.assertFalse(first["approved_for_model_promotion"])
        self.assertEqual(first["status"],"exploratory_insufficient_dates")
        self.assertEqual(len(first["brier_delta_ci95"]),2)
        with self.assertRaisesRegex(ValueError,"insufficient_cluster_bootstrap_replicates"):
            hold.paired_date_bootstrap(pairs,repeats=5)

    def test_overlapping_duplicate_or_bad_dates_rejected(self):
        train=sample_rows("2018-10-01",2018020001)
        frozen=joint.prepare(train,min_rows=8)
        with self.assertRaisesRegex(ValueError,"invalid_holdout_period"):
            hold.evaluate(None,train,frozen,train,
                cutoff="2018-10-03",until="2018-10-02",
                diagnostics={"posterior_sampling_ok":True})
        with self.assertRaisesRegex(ValueError,"posterior_diagnostics_failed"):
            hold.evaluate(None,train,frozen,train,
                cutoff="2018-10-01",until="2018-10-02",diagnostics={})
        mixed=[dict(r,game_date="2018-10-02") for r in train]
        with self.assertRaisesRegex(ValueError,"training_holdout_data_overlap"):
            hold.evaluate(None,train,frozen,mixed,
                cutoff="2018-10-02",until="2018-10-03",
                diagnostics={"posterior_sampling_ok":True})


if __name__=="__main__":
    unittest.main()
