import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import nfl_context_diagnostics as audit


class Diagnostics(unittest.TestCase):
    def test_redundant_and_constant_columns_are_identified(self):
        result=audit.design_report({"x":[[0.,1.,1.,0.],[0.,2.,2.,1.],[0.,3.,3.,0.]],
                                    "feature_names":["constant","signal","duplicate_mask","other"]})
        self.assertEqual(result["constant_features"],["constant"])
        self.assertEqual(result["duplicate_features"],[{"feature":"duplicate_mask","same_as":"signal"}])
        self.assertEqual(result["rank"],2)

    def test_worst_parameter_coordinates_map_to_features_and_identities(self):
        d={"feature_names":["home","checkdown"],"players":["receiverA","receiverB"],
           "teams":["A","B"],"seasons":["2024","2025"]}
        self.assertEqual(audit.coordinate("beta_rate",1,(2,),d)["feature"],"checkdown")
        r=audit.coordinate("player_z",3,(2,2),d)
        self.assertEqual((r["player_id"],r["effect"]),("receiverB","production"))
        self.assertEqual(audit.coordinate("team_effect",2,(2,2),d)["team"],"B")
        self.assertEqual(audit.coordinate("workload_sigma",0,(),d)["indices"],[])

    def test_invalid_design_does_not_produce_a_clean_report(self):
        with self.assertRaises(ValueError):
            audit.design_report({"x":[[float("nan")]],"feature_names":["bad"]})
