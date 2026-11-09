"""No-network Step 10 research calibration/stacking adversarial tests."""
import copy
from datetime import date,timedelta
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import reform_step10_calibration_shadow as c


def record(i,j,*,p=None,market=.55):
    day=(date(2025,1,1)+timedelta(days=i)).isoformat()
    p=.3+.15*((i+j)%4) if p is None else p
    y="over" if (i*3+j)%5<2 else "under"
    return {"date":day,"game_id":f"2025_{i//7}_G{j//5}",
            "contract":("NFL",day,"A","B",f"P{i}_{j}","Test","tackles + assists","5.5"),
            "outcome":y,
            "models":{
                "Consensus":{"over":p,"under":1-p},
                "Market":{"over":market,"under":1-market}}}


class Step10CalibrationTests(unittest.TestCase):
    def test_beta_identity_is_in_family_not_forced_shrink(self):
        for p in (.01,.1,.25,.5,.75,.9,.99):
            self.assertAlmostEqual(
                c.beta_map(p,{"a":1.,"b":1.,"c":0.}),p,places=12)
        self.assertNotEqual(c.beta_map(.7,{"a":.4,"b":.4,"c":0}),.7)

    def test_beta_monotone_nonnegative_parameters_and_abstention(self):
        pars={"a":.7,"b":1.3,"c":.02}
        values=[c.beta_map(i/100,pars) for i in range(1,100)]
        self.assertTrue(all(a<b for a,b in zip(values,values[1:])))
        for bad in (
            {"a":-1.,"b":1.,"c":0.},
            {"a":1.,"b":float("nan"),"c":0.},
        ):
            with self.assertRaisesRegex(c.CalibrationError,"nonmonotone"):
                c.beta_map(.65,bad)

    def test_global_stack_identity_market_if_model_weight_zero(self):
        for p in (.1,.35,.8):
            self.assertAlmostEqual(c.stack_map(.92,p,{
                "intercept":0.,"logit_model":0.,"logit_market":1.}),p,places=9)

    def test_duplicate_and_noncomplementary_source_fail_closed(self):
        good=record(0,0)
        with self.assertRaisesRegex(c.CalibrationError,"duplicate_original_settled_contract"):
            c.normalize([good,copy.deepcopy(good)])
        broken=copy.deepcopy(good)
        broken["models"]["Consensus"]["under"]+=.015
        rows,ex=c.normalize([good,broken])
        self.assertEqual(len(rows),1)
        self.assertEqual(ex["noncomplementary_or_missing_paired_input"],1)

    def test_unverified_80_date_and_1600_contract_data_never_fits(self):
        rows=[record(i,j) for i in range(80) for j in range(20)]
        report=c.research(rows,source_pregame_verified=False)
        self.assertEqual(report["status"],"blocked")
        self.assertEqual(report["block_reason"],
                         "original_point_in_time_source_archives_not_verified")
        self.assertTrue(report["no_fitted_parameters_released"])
        self.assertFalse(report["production_promotion_authorized"])
        self.assertFalse(report["training_started"])

    def test_fewer_than_required_dates_or_rows_blocks_fitting(self):
        data=[record(i,j) for i in range(39) for j in range(21)]
        output=c.research(data,source_pregame_verified=True)
        self.assertEqual(output["status"],"blocked")
        self.assertIn("split",output["block_reason"])
        one_day=[record(0,j) for j in range(900)]
        out=c.research(one_day,source_pregame_verified=True)
        self.assertEqual(out["split"]["available_dates"],1)

    def test_real_chronological_research_no_export_even_if_source_verified(self):
        # Synthetic certified fixture deliberately exercises math only;
        # live CLI NEVER accepts a flag for source certification.
        rows=[record(i,j) for i in range(45) for j in range(18)]
        result=c.research(rows,source_pregame_verified=True,draws=100)
        self.assertEqual(result["status"],"chronological_research_heldout_only")
        self.assertTrue(result["train_and_test_keys_disjoint"])
        self.assertGreaterEqual(result["split"]["train_n"],300)
        self.assertGreaterEqual(result["split"]["holdout_n"],100)
        self.assertGreaterEqual(result["split"]["train_dates"],20)
        self.assertGreaterEqual(result["split"]["holdout_dates"],20)
        self.assertTrue(result["calibration_family_identity_included"])
        self.assertTrue(result["trained_coefficients_not_emitted_to_production"])
        self.assertFalse(result["production_promotion_authorized"])
        self.assertFalse(result["production_modified"])
        m=result["same_contract_holdout_metrics"]
        self.assertEqual(len({v["n"] for v in m.values()}),1)
        self.assertEqual(len(m),4)
        for challenger in c.CANDIDATES:
            for baseline in c.BASELINES:
                score=result["paired_date_block_baseline_improvements"][challenger][baseline]
                for metric in ("brier","log_loss"):
                    self.assertEqual(len(score[metric]["interval_95"]),2)

    def test_holdout_labels_not_used_for_training(self):
        rows=[record(i,j) for i in range(45) for j in range(18)]
        normalized,_=c.normalize(rows)
        training,test,cut=c.split_dates(normalized)
        beta=c.fit_beta(training)
        stack=c.fit_stack(training)
        mutated=copy.deepcopy(rows)
        for row in mutated:
            if row["date"]>=cut["first_holdout_date"]:
                row["outcome"]="under" if row["outcome"]=="over" else "over"
        mutated_normal,_=c.normalize(mutated)
        train2,test2,cut2=c.split_dates(mutated_normal)
        self.assertEqual(beta,c.fit_beta(train2))
        self.assertEqual(stack,c.fit_stack(train2))
        self.assertNotEqual(c.metric(c.evaluate_predictions(test,beta,stack),"market")["brier"],
                            c.metric(c.evaluate_predictions(test2,beta,stack),"market")["brier"])

    def test_push_not_modeled_as_binary_under(self):
        values=[record(0,0),record(0,1)]
        values[1]["outcome"]="push"
        normalized,excluded=c.normalize(values)
        self.assertEqual(len(normalized),1)
        self.assertEqual(excluded["push_unverified_or_other_outcome"],1)

    def test_unsupported_extreme_prob_does_not_produce_nan(self):
        for v in (0.0,1.0):
            p=c.beta_map(v,{"a":1.,"b":1.,"c":0.})
            self.assertTrue(0<p<1)
        with self.assertRaisesRegex(c.CalibrationError,"invalid_calibration_probability"):
            c.betafeatures(float("nan"))


if __name__=="__main__":
    unittest.main()
