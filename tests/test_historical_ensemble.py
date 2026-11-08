"""Regression tests for user-authorized 60/40 post-shadow ensemble."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from historical_ensemble import calculate


def m(win, push=0, **extra):
    return {"status": "forecast", "q_win": win, "q_push": push, **extra}


class HistoricalEnsembleTests(unittest.TestCase):
    def test_equal_historical_families_mix_unconditional_masses_first(self):
        models={"Engine_A":m(.60,.10),"Bayesian_A":m(.80,.05),
                "Bayesian_B":m(.40,.15),"NUTS":m(.70,.10),
                "Engine_B":m(.50,.20)}
        p=calculate(models)
        self.assertEqual(p["status"],"forecast")
        self.assertEqual(set(p["historical_families"]),
                         {"Engine_A","Bayesian_A","Bayesian_B","NUTS"})
        self.assertAlmostEqual(p["q_win"], .60*((.60+.80+.40+.70)/4)+.40*.50)
        self.assertAlmostEqual(p["q_push"], .60*((.10+.05+.15+.10)/4)+.40*.20)
        self.assertAlmostEqual(p["probability"],p["q_win"]/(1-p["q_push"]))
        self.assertAlmostEqual(sum(p["historical_family_weights"].values()),.60)
        self.assertAlmostEqual(p["q_win"]+p["q_push"]+p["q_loss"],1)
        self.assertFalse(p["empirically_calibrated"])

    def test_available_pool_renormalizes_with_provenance_not_nuts_substitution(self):
        models={"Engine_A":m(.60),"Bayesian_A":m(.40),
                "Bayesian_B":{"status":"unavailable","reason":"missing_history"},
                "Engine_B":m(.55),
                "NUTS":{"status":"unavailable","reason":"strict_sampling_failed"}}
        p=calculate(models)
        self.assertEqual(p["status"],"forecast")
        self.assertEqual(p["historical_families"],["Engine_A","Bayesian_A"])
        self.assertEqual(p["historical_unavailable"]["NUTS"],"strict_sampling_failed")
        self.assertAlmostEqual(p["q_win"],.6*.5+.4*.55)

    def test_one_historical_model_is_not_a_fake_ensemble(self):
        p=calculate({"Engine_A":m(.8),"Engine_B":m(.5)})
        self.assertEqual(p["status"],"unavailable")
        self.assertEqual(p["reason"],"insufficient_historical_model_coverage")

    def test_missing_core_engine_abstains(self):
        p=calculate({"Bayesian_A":m(.8),"Bayesian_B":m(.75),"Engine_B":m(.5)})
        self.assertEqual(p["reason"],"required_historical_model_missing")
        p=calculate({"Engine_A":m(.8),"Bayesian_A":m(.7)})
        self.assertEqual(p["reason"],"engine_b_missing_or_invalid")

    def test_provisional_nuts_is_excluded(self):
        p=calculate({"Engine_A":m(.6),"Bayesian_A":m(.7),"Engine_B":m(.5),
                     "NUTS":m(.99,provisional=True)})
        self.assertEqual(p["historical_families"],["Engine_A","Bayesian_A"])
        self.assertEqual(p["historical_unavailable"]["NUTS"],
                         "non_strict_nuts_not_production_eligible")

    def test_invalid_masses_cannot_enter_ensemble(self):
        for bad in [m(.9,.2),m(float("nan")),m(True),m(-.01)]:
            p=calculate({"Engine_A":m(.8),"Bayesian_A":bad,"Engine_B":m(.5)})
            self.assertEqual(p["status"],"unavailable")
            self.assertEqual(p["reason"],"insufficient_historical_model_coverage")

    def test_policy_weights_are_strictly_validated(self):
        with self.assertRaisesRegex(ValueError,"invalid_historical_ensemble_policy"):
            calculate({"Engine_A":m(.8),"Bayesian_A":m(.7),"Engine_B":m(.6)},
                      weight_historical=.61,weight_b=.4)


if __name__ == "__main__":
    unittest.main()
