"""No-network reliability, per-position proper-score and workload contracts."""
import sys
import unittest
import importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import joint_population_holdout as audit
import population_history as store


class PopulationAuditGuards(unittest.TestCase):
    def test_reliability_and_position_slices_are_descriptive_only(self):
        observations=[
            {"position":"F","game_date":"2018-10-20","joint_over":.2,
             "control_over":.3,"actual_over":0},
            {"position":"F","game_date":"2018-10-21","joint_over":.8,
             "control_over":.7,"actual_over":1},
            {"position":"D","game_date":"2018-10-20","joint_over":.1,
             "control_over":.2,"actual_over":1},
            {"position":"D","game_date":"2018-10-21","joint_over":.9,
             "control_over":.8,"actual_over":0}
        ]
        report=audit.reliability(observations,probability_key="joint_over")
        self.assertEqual(report["n"],4)
        self.assertGreaterEqual(report["ece"],0)
        self.assertLessEqual(report["ece"],1)
        self.assertEqual(sum(b["n"] for b in report["bins"]),4)
        by=audit.position_slices(observations)
        self.assertEqual(by["F"]["n"],2)
        self.assertEqual(by["D"]["days"],2)
        self.assertAlmostEqual(by["F"]["joint"]["brier"],.04)
        self.assertFalse("approved_for_model_promotion" in report)
        empty=audit.reliability([],probability_key="joint_over")
        self.assertIsNone(empty["ece"])

    def test_cached_control_matches_original_poisson_and_student_t(self):
        if importlib.util.find_spec("scipy") is None:
            self.skipTest("SciPy is installed only in the statistical CI job")
        for family,values,line in (
            ("count",[0,2,3,5,1,7,2,0],2.5),
            ("continuous",[-11.,3.,64.,87.,0.,18.,23.,-2.],49.5)
        ):
            training=[{"player_id":str(i%3),"position":"WR" if i%2 else "RB",
                       "value":value} for i,value in enumerate(values)]
            cache=audit.control_cache(training)
            for player in ("0","1","2","unseen"):
                for position in ("WR","RB"):
                    slow=audit.simple_control(training,player=player,
                        position=position,stat_family=family,line=line)
                    fast=audit.cached_control(cache,player=player,
                        position=position,stat_family=family,line=line)
                    self.assertAlmostEqual(slow,fast,places=12)

    def test_source_workload_and_nhl_goaltending_separation(self):
        base=store.make(sport="NHL",stat="saves",
            game_id="2018020001",game_date="2018-10-03",season="2018",
            player_id="99",position="G",team="BOS",opponent="NYR",
            home=True,value=30,workload=60.,workload_unit="minutes",
            source_url="https://api-web.nhle.com/v1/gamecenter/2018020001/boxscore",
            source_sha256="f"*64)
        with self.assertRaisesRegex(ValueError,"goalie_skater_market_population_mismatch"):
            store.validate(dict(base,position="F"))
        with self.assertRaisesRegex(ValueError,"goalie_skater_market_population_mismatch"):
            store.validate(dict(base,position="G",stat="hits"))
        with self.assertRaisesRegex(ValueError,"sport_workload_measurement_mismatch"):
            store.validate(dict(base,workload_unit="snaps"))
        self.assertEqual(store.validate(base),base)


if __name__=="__main__":
    unittest.main()
