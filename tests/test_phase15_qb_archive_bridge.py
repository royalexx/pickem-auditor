"""Integrity and conservation tests for source-locked Phase 1.5 QB archive bridge."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import phase15_qb_archive_bridge as m
from phase15_diagnostics import Phase15Error


class QBBridgeTests(unittest.TestCase):
    def write_json(self,path,obj):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(obj,sort_keys=True),encoding="utf-8")

    def fixture(self,root,*,tamper_week=0,mutated_mean_week=0,leak_week=0):
        oracle={"weeks":{}}
        for week in range(1,19):
            pred={"game_id":"G"+str(week),"team":"ABC","player_id":"Q"+str(week),
                  "market":"pass attempts","research_line":4.5,
                  "simulated_mean":4.,"team_xgb_pass_mean":8.,"p_over_hurdle":.5}
            freeze={"week":week,"stage":"before_week_outcomes",
                    "future_2024_week_data_accessed_by_forecaster":False,
                    "research_only":True,"models_input_sha":{"q":"sha123"},
                    "latest_revealed_week":(week if leak_week==week else week-1),
                    "training_label_week_limit":week-1,
                    "forecast_asof":"2024-09-05","predictions":[pred]}
            p=root/"FROZEN"/("week_%02d.json"%week)
            self.write_json(p,freeze)
            revealed=copy.deepcopy(pred)
            revealed["graded"]=True
            revealed["actual_stat"]=6.
            if mutated_mean_week==week:
                revealed["simulated_mean"]=5.
            rv={"week":week,"frozen_sha":hashlib.sha256(p.read_bytes()).hexdigest(),
                "full_research_rows":[revealed]}
            self.write_json(root/"REVEALED"/("week_%02d.json"%week),rv)
            if tamper_week==week:
                p.write_text(p.read_text()+"\n",encoding="utf-8")
            oracle["weeks"][str(week)]={"team_games":[{"game_id":"G"+str(week),
                                            "team":"ABC","pass_attempts":10.}]}
        oracle_path=root.parent/"oracle.json"
        self.write_json(oracle_path,oracle)
        return oracle_path

    def test_full_valid_archive(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"archive"
            oracle=self.fixture(root)
            result=m.process(root,oracle,replicates=40)
            self.assertEqual(result["n"],18)
            self.assertEqual(result["weeks"],18)
            self.assertEqual(result["games"],18)
            self.assertFalse(result["tier_certified"])
            self.assertAlmostEqual(result["mean_predicted_qb_attempts"],4.)
            self.assertAlmostEqual(result["mean_actual_qb_attempts"],6.)
            self.assertAlmostEqual(sum(result["mean_shapley_error_reduction"].values()),4.)
            self.assertEqual(result["clustered_intervals"]["qb_allocation_share"]["week"]["clusters"],18)

    def test_tampered_frozen_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"archive"
            oracle=self.fixture(root,tamper_week=7)
            with self.assertRaisesRegex(Phase15Error,"tampered_frozen_hash"):
                m.process(root,oracle,replicates=0)

    def test_mutated_prediction_in_revealed_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"archive"
            oracle=self.fixture(root,mutated_mean_week=8)
            with self.assertRaisesRegex(Phase15Error,"frozen_qb_prediction_mutated"):
                m.process(root,oracle,replicates=0)

    def test_future_training_week_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"archive"
            oracle=self.fixture(root,leak_week=9)
            with self.assertRaisesRegex(Phase15Error,"training_week_leak"):
                m.process(root,oracle,replicates=0)

    def test_candidate_pool_coverage_reported(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"archive"
            oracle=self.fixture(root)
            result=m.process(root,oracle,replicates=0)
            pool=result["team_game_candidate_pool_diagnostic"]
            self.assertEqual(pool["team_game_groups"],18)
            self.assertEqual(pool["predicted_qb_total_exceeds_team_groups"],0)
            self.assertEqual(pool["multi_candidate_groups"],0)

    def test_nonboolean_grade_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"archive"
            oracle=self.fixture(root)
            path=root/"REVEALED"/"week_01.json"
            data=json.loads(path.read_text())
            data["full_research_rows"][0]["graded"]="false"
            self.write_json(path,data)
            with self.assertRaisesRegex(Phase15Error,"graded_status_not_boolean"):
                m.process(root,oracle,replicates=0)

    def test_multiple_qbs_exceeding_official_team_attempts_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"archive"
            oracle=self.fixture(root)
            fp=root/"FROZEN"/"week_01.json"
            rp=root/"REVEALED"/"week_01.json"
            frozen=json.loads(fp.read_text())
            revealed=json.loads(rp.read_text())
            other=copy.deepcopy(frozen["predictions"][0])
            other["player_id"]="SECOND_QB"
            frozen["predictions"].append(other)
            self.write_json(fp,frozen)
            graded=copy.deepcopy(other)
            graded["graded"]=True
            graded["actual_stat"]=6.
            revealed["full_research_rows"].append(graded)
            revealed["frozen_sha"]=hashlib.sha256(fp.read_bytes()).hexdigest()
            self.write_json(rp,revealed)
            with self.assertRaisesRegex(Phase15Error,"graded_qb_attempt_pool_exceeds_team_total"):
                m.process(root,oracle,replicates=0)

    def test_two_factor_attribution_conservation(self):
        row=m.sh2(8.,.5,10.,.6,6.)
        self.assertAlmostEqual(row["base_squared_error"],4)
        self.assertAlmostEqual(row["oracle_squared_error"],0)
        self.assertAlmostEqual(row["team_volume"]+row["qb_allocation_share"],4)


if __name__ == "__main__":
    unittest.main()
