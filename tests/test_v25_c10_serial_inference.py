"""Fixed-horizon C10: deterministic scenario-grid and fail-closed power checks."""
import unittest
from v2.c10_serial_inference import (
    simulate_date_differences,hac_student_stat,calibrate_and_validate,
    candidate_status,SCENARIOS,HORIZONS,
)
import random

class C10Tests(unittest.TestCase):
    def test_grid_coverage(self):
        self.assertEqual(len(SCENARIOS),36)
        self.assertIn((.6,"centered_lognormal",True,"thin"),SCENARIOS)
        self.assertEqual(HORIZONS,(12,20,40))

    def test_seed_fixed_and_direction(self):
        kw=dict(rng=random.Random(17),dates=40,rho=.6,dist="heavy_tail",
                hetero=True,cluster="mixed")
        a=simulate_date_differences(**kw)
        b=simulate_date_differences(**{**kw,"rng":random.Random(17)})
        self.assertEqual(a,b)
        self.assertEqual(len(a),40)
        self.assertEqual(hac_student_stat([x-.002 for x in a])>
                         hac_student_stat(a),True)

    def test_independent_stream_and_power_guard(self):
        cfg=dict(dates=12,calibration_reps=100,validation_reps=100,seed=175)
        a=calibrate_and_validate(**cfg)
        b=calibrate_and_validate(**cfg)
        self.assertEqual(a,b)
        self.assertEqual(len(a["scenarios"]),36)
        self.assertTrue(a["calibration_cutoff"]>0)
        self.assertFalse(a["full_prospective_signoff"])
        self.assertIn(candidate_status(a),
            ("EXPLORATORY_LOW_POWER","BLOCKED_SIMULATED_SIZE",
             "SIMULATION_PASSED_NOT_INDEPENDENTLY_APPROVED"))

    def test_missing_and_underpowered_fail_closed(self):
        self.assertEqual(candidate_status({}),"INVALID_C10_RECEIPT")
        r={"schema":"v25_c10_serial_calibration_v1",
           "worst_null_type1":.01,"min_power_at_minus_0_002":.10}
        self.assertEqual(candidate_status(r),"EXPLORATORY_LOW_POWER")
        r["worst_null_type1"]=.06
        self.assertEqual(candidate_status(r),"BLOCKED_SIMULATED_SIZE")


if __name__=="__main__":
    unittest.main()
