"""Research review gates never authorize production or modify frozen receipts."""
import copy
import importlib.util
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import review_frozen_posterior as review


def entry(name="population_workload",rhat=1.005,bulk=600.,tail=550.):
    return {"variable":name,"parameter":name,"rhat":rhat,"bulk_ess":bulk,"tail_ess":tail}


class ReviewComparisonTests(unittest.TestCase):
    def compare(self,entries,**kwargs):
        return review.compare_thresholds(entries,**{"divergences":0,"bfmi":.6,"chains":4,
            "expected_variables":{e["variable"] for e in entries},**kwargs})

    def test_borderline_ess_is_hypothesis_not_strict_pass(self):
        original=[entry(bulk=389.414906)]
        saved=copy.deepcopy(original);result=self.compare(original)
        self.assertFalse(result["current_operational_strict"]["comparison_pass"])
        self.assertTrue(result["operational_relaxed_hypothesis"]["comparison_pass"])
        self.assertFalse(result["critical_parameter_strict_review"]["comparison_pass"])
        self.assertEqual(original,saved)
        status=review.review_status(result,[{"numerical_review_pass":True}])
        self.assertEqual(status["review_status"],"restricted_pending_review")
        self.assertFalse(status["ranking_allowed"])

    def test_local_noncritical_difficulty_can_only_request_manual_shadow_review(self):
        result=self.compare([entry(),entry("player_effect",rhat=1.015,bulk=350.,tail=350.)])
        self.assertFalse(result["all_parameter_strict_review"]["comparison_pass"])
        self.assertTrue(result["critical_parameter_strict_review"]["comparison_pass"])
        self.assertTrue(result["all_parameter_relaxed_hypothesis"]["comparison_pass"])
        status=review.review_status(result,[{"numerical_review_pass":True}])
        self.assertEqual(status["review_status"],"limited_provisional_shadow_candidate_requires_manual_review")
        for key in ("ranking_allowed","publication_eligible","automatic_promotion",
                    "production_gate_changed","provisional_shadow_execution_authorized"):
            self.assertIs(status[key],False)
        self.assertEqual(review.review_status(result,[])["review_status"],"restricted_pending_review")
        self.assertEqual(review.review_status(result,[{"numerical_review_pass":False}])["review_status"],
                         "restricted_pending_review")

    def test_bad_energy_divergences_or_chain_count_fail_every_comparison(self):
        for kwargs in ({"bfmi":.2},{"divergences":1},{"chains":2}):
            with self.subTest(kwargs=kwargs):
                self.assertTrue(all(not v["comparison_pass"] for v in self.compare([entry()],**kwargs).values()))

    def test_tail_is_a_separate_stronger_review(self):
        for tail in (50.,None,math.inf):
            result=self.compare([entry(tail=tail)])
            self.assertTrue(result["current_operational_strict"]["comparison_pass"])
            self.assertFalse(result["all_parameter_strict_review"]["comparison_pass"])
            self.assertFalse(result["all_parameter_relaxed_hypothesis"]["comparison_pass"])

    def test_missing_required_variable_or_missing_inventory_fails_closed(self):
        for expected in ({"population_workload","workload_sigma"},None):
            result=review.compare_thresholds([entry()],divergences=0,bfmi=.6,chains=4,
                                             expected_variables=expected)
            self.assertTrue(all(not x["comparison_pass"] for x in result.values()))

    def test_missing_empty_and_nonfinite_diagnostics_fail_closed(self):
        for entries in ([],[entry(rhat=math.nan)],[entry(bulk=None)]):
            with self.subTest(entries=entries):
                self.assertTrue(all(not v["comparison_pass"] for v in self.compare(entries).values()))


@unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("arviz_stats"),
                     "functional MCMC checks require audit statistical dependencies")
class PredictivePrecisionTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("xarray"),"coordinate checks require xarray")
    def test_only_known_structural_constants_are_exempt(self):
        import numpy as np
        import xarray as xr
        import arviz_stats as stats
        rng=np.random.default_rng(8)
        player=rng.normal(size=(4,200,2,2));player[:,:,0,1]=.3
        corr=np.zeros((4,200,2,2));corr[:,:,0,0]=1.;corr[:,:,1,1]=1.
        corr[:,:,0,1]=rng.uniform(-.5,.5,size=(4,200));corr[:,:,1,0]=corr[:,:,0,1]
        posterior=xr.Dataset({"player_z":(("chain","draw","players","effect"),player),
            "workload_sigma":(("chain","draw"),np.full((4,200),.3)),
            "player_chol_corr":(("chain","draw","a","b"),corr),
            "season_rate":(("chain","draw","season"),np.zeros((4,200,1)))})
        entries,excluded=review.parameter_entries(posterior,{"players":["p1","p2"],"seasons":["2025"]},stats)
        bad={e["parameter"] for e in entries if e.get("diagnostic_failure")=="unexpected_constant_coordinate"}
        self.assertEqual(bad,{"player_z(0, 1)","workload_sigma"})
        self.assertEqual(set(excluded),{"player_chol_corr(0, 0)","player_chol_corr(1, 1)","season_rate(0,)"})

    def test_chain_ordered_mcse_detects_between_chain_probability_disagreement(self):
        import numpy as np
        import arviz_stats as stats
        rng=np.random.default_rng(51)
        q=.8+rng.normal(0,.002,size=(4,1500))
        good=review.prediction_summary(q,quadrature_delta=0.,stats=stats)
        self.assertTrue(good["numerical_review_pass"])
        self.assertLess(good["mcmc_mcse"],.001)
        q[0]-=.07;q[1]+=.07
        bad=review.prediction_summary(q,quadrature_delta=0.,stats=stats)
        self.assertFalse(bad["numerical_review_pass"])
        self.assertGreater(bad["functional_rhat"],1.01)
        self.assertGreater(bad["chain_mean_range"],.1)

    def test_constant_function_and_invalid_inputs_and_quadrature_error(self):
        import numpy as np
        import arviz_stats as stats
        result=review.prediction_summary(np.full((4,100),.8),quadrature_delta=0.,stats=stats)
        self.assertEqual(result["mcmc_mcse"],0.)
        self.assertTrue(result["numerical_review_pass"])
        self.assertFalse(review.prediction_summary(np.full((4,100),.8),quadrature_delta=.01,stats=stats)["numerical_review_pass"])
        for invalid in (np.array([.8,.9]),np.full((4,100),math.nan),np.full((4,100),1.1)):
            with self.assertRaisesRegex(ValueError,"invalid_chain_ordered_probability_functional"):
                review.prediction_summary(invalid,quadrature_delta=0.,stats=stats)


if __name__=="__main__":unittest.main()
