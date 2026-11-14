"""Research-only C10 inference stress tests; no claims about observed score."""
import unittest
import numpy as np
from v2.c10_sog_fixed_horizon import (hac_t,run,scenarios,generate_slate_date_differences)

class C10FixedHorizonTests(unittest.TestCase):
    def test_predeclared_grid_and_determinism(self):
        self.assertEqual(len(list(scenarios())),96)
        a=run(calibrate_reps=20,audit_reps=30)
        b=run(calibrate_reps=20,audit_reps=30)
        self.assertEqual(a,b)
        self.assertEqual(a["horizon"],40)
        self.assertFalse(a["prospective_outcomes_used"])
        self.assertEqual(len(a["canonical_sha256"]),64)

    def test_signed_effect_and_date_statistic(self):
        base=dict(repeats=100,seed=5,rho=.3,innovation="gaussian",
                  hetero=True,cluster_pattern="sparse",date_sd=.04)
        null=generate_slate_date_differences(effect=0.0,**base)
        alt=generate_slate_date_differences(effect=-.002,**base)
        self.assertTrue(np.allclose(alt-null,-.002))
        self.assertEqual(hac_t(null).shape,(100,))
        self.assertTrue(np.isfinite(hac_t(alt)).all())

if __name__=="__main__":unittest.main()
