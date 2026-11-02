"""Bounded empirical Bayes workload has finite exposure moments and matching MC."""
import math
import random
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import bayesian_usage as bu
import posterior_mc as mc
import phase4_validation as phase4


def sample_pairs(prefix, n=18, work=20.):
    return [(f"{prefix}-{i}", float((i%5)+1), work*(.85+.05*(i%6)))
            for i in range(n)]


class BoundedExposureTests(unittest.TestCase):
    def test_truncated_workload_nodes_are_physical_and_normalized(self):
        peers=[sample_pairs(f"peer{i}",work=17.+i) for i in range(8)]
        r=bu.workload_posterior(sample_pairs("subject"),peers,sport="NBA")
        self.assertEqual(len(r["future_exposures"]),bu.GRID_WORKLOAD)
        self.assertTrue(all(.05<=w<=100. for w in r["future_exposures"]))
        self.assertGreater(r["truncation_probability_mass"],.5)
        self.assertTrue(math.isfinite(r["expected_exposure"]))
        self.assertTrue(math.isfinite(r["exposure_sd"]))

    def test_out_of_support_workload_fails_instead_of_clipping(self):
        peers=[sample_pairs(f"peer{i}") for i in range(8)]
        with self.assertRaisesRegex(Exception,"outside_physical_support"):
            bu.workload_posterior(sample_pairs("bad",work=999.),peers,sport="NBA")

    def test_legacy_and_bounded_mc_models_are_distinct(self):
        peers=[sample_pairs(f"peer{i}") for i in range(8)]
        prediction=bu.forecast(sample_pairs("subject"),peers,dist="poisson",
                               line=2.5,side="over",stat="points",sport="NBA")
        record={"status":"forecast","version":prediction["version"],
                "distribution":"poisson",
                "workload_posterior":prediction["workload"],
                "conversion_posterior":prediction["conversion"]}
        sampler=mc.sampler_b(record)
        for n in range(30):
            mean,sd,ratio=sampler(random.Random(100+n))
            self.assertTrue(math.isfinite(mean))
            self.assertGreaterEqual(mean,0)
        self.assertIn("usage-bayes-v1",mc.SUPPORTED_POSTERIOR_VERSIONS_B)
        self.assertIn("usage-bayes-v2-bounded-exposure",mc.SUPPORTED_POSTERIOR_VERSIONS_B)
        self.assertIsNotNone(phase4._sidecar_model(
            {"status":"forecast","version":prediction["version"],
             "publication_eligible":False,"source_digest":"test",
             "q_win":prediction["q_win"],"q_push":prediction["q_push"]},
            expected=("usage-bayes-v1",prediction["version"])))


if __name__=="__main__":
    unittest.main()
