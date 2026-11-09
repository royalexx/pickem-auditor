"""Step 8 market-informed logit blend is a read-only unfitted scenario."""
import datetime
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import reform_step8_market_shadow as blend


def item(day, *, model=.7, market=.55):
    return {"date":day,"outcome":"over","game_id":day+"-G",
            "models":{"Consensus":{"over":model,"under":1-model},
                      "Engine_A":{"over":model,"under":1-model},
                      "Engine_B":{"over":model-.03,"under":1-model+.03},
                      "Market":{"over":market,"under":1-market}}}


class MarketLogitShadowTests(unittest.TestCase):
    def test_equal_logit_blend_between_consensus_and_market(self):
        model={"over":.75,"under":.25}
        market={"over":.55,"under":.45}
        p=blend.equal_logit_over(model,market)
        self.assertGreater(p,.55)
        self.assertLess(p,.75)
        self.assertAlmostEqual(blend.sigmoid(.5*(blend.logit(.75)+blend.logit(.55))),p)
        self.assertAlmostEqual(p+(1-p),1.)

    def test_research_scenario_must_not_fit_market_coefficients(self):
        data=[item("2026-11-08") for _ in range(10)]
        scored=blend.same_contract_scenario(data,model="Consensus")
        self.assertEqual(scored["coverage"]["same_contract_compared"],10)
        self.assertFalse(scored["promotion_allowed"])
        self.assertIn("NOT_fitted_M2_M3",scored["scenario"])
        self.assertEqual(scored["same_contract_metrics"]["market"]["n"],10)
        self.assertEqual(scored["same_contract_metrics"]["model"]["n"],10)
        self.assertEqual(scored["same_contract_metrics"]["fixed_equal_logit_market_mix"]["n"],10)

    def test_invalid_noncomplementary_consensus_abstains(self):
        data=[item("2026-11-08")]
        data[0]["models"]["Consensus"]["under"]-=.002
        out=blend.same_contract_scenario(data,model="Consensus")
        self.assertEqual(out["coverage"]["nonunit_two_way_forecast"],1)
        self.assertEqual(out["same_contract_metrics"]["model"]["n"],0)

    def test_original_retrospective_market_nonunit_pair_abstains(self):
        data=[item("2026-11-07")]
        data[0]["models"]["Market"]["under"]-=.011
        out=blend.same_contract_scenario(data,model="Engine_A")
        self.assertEqual(out["coverage"]["nonunit_two_way_forecast"],1)

    def test_missing_market_does_not_get_imputed(self):
        data=[item("2026-11-08")]
        data[0]["models"]["Market"]=None
        out=blend.same_contract_scenario(data,model="Consensus")
        self.assertEqual(out["coverage"]["model_or_market_unavailable"],1)

    def test_tied_blend_direction_abstains(self):
        data=[item("2026-11-08",model=.7,market=.3)]
        out=blend.same_contract_scenario(data,model="Consensus")
        self.assertEqual(out["coverage"]["ties_no_direction"],1)
        self.assertEqual(out["same_contract_metrics"]["model"]["n"],0)

    def test_one_hundred_outcomes_same_day_never_fit(self):
        rows=[item("2026-11-08") for _ in range(700)]
        out=blend.oos_gates(rows,independent_source_archive_verified=True)
        self.assertFalse(out["fitting_authorized"])
        self.assertIn("fewer_than_40_training_plus_evaluation_dates",out["blocking_reasons"])
        self.assertIsNone(out["feasible_chronological_split"])

    def test_forty_dates_but_last_eval_day_underpowered_still_blocks(self):
        base=datetime.date(2026,1,1)
        rows=[]
        for i in range(39):
            rows.extend([item((base+datetime.timedelta(days=i)).isoformat()) for _ in range(9)])
        rows.extend([item((base+datetime.timedelta(days=39)).isoformat()) for _ in range(3)])
        out=blend.oos_gates(rows,independent_source_archive_verified=True)
        self.assertFalse(out["fitting_authorized"])
        self.assertIsNone(out["feasible_chronological_split"])

    def test_sufficient_chronological_split_is_only_authorized_not_fitted(self):
        base=datetime.date(2026,1,1)
        rows=[]
        for i in range(40):
            rows.extend([item((base+datetime.timedelta(days=i)).isoformat()) for _ in range(20)])
        out=blend.oos_gates(rows,independent_source_archive_verified=True)
        self.assertTrue(out["fitting_authorized"])
        self.assertEqual(out["feasible_chronological_split"]["training_dates"],20)
        self.assertEqual(out["feasible_chronological_split"]["evaluation_dates"],20)
        self.assertFalse(out["M2_M3_fitted"])
        self.assertFalse(out["weights_emitted"])
        blocked=blend.oos_gates(rows,independent_source_archive_verified=False)
        self.assertFalse(blocked["fitting_authorized"])
        self.assertIn("original_pregame_feature_source_archive_incomplete",blocked["blocking_reasons"])


if __name__=="__main__":
    unittest.main()
