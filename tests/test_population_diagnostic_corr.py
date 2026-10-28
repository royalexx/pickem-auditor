"""Regression: a constant LKJ correlation diagonal must not veto a good fit."""
from __future__ import annotations
import importlib.util
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import joint_population_bayes as model


class LKJCorrelationDiagnostics(unittest.TestCase):
    def test_constant_correlation_diagonal_and_stochastic_offdiagonal(self):
        if importlib.util.find_spec("arviz") is None:
            self.skipTest("ArviZ available in isolated numerical CI")
        import arviz as az
        import numpy as np
        rng=np.random.default_rng(761)
        shape=(4,800)
        rho=np.clip(rng.normal(.3,.1,shape),-.9,.9)
        corr=np.zeros((*shape,2,2),dtype=float)
        corr[...,0,0]=1.
        corr[...,1,1]=1.
        corr[...,0,1]=rho
        corr[...,1,0]=rho
        posterior={
            "population_workload":rng.normal(3.,.2,(*shape,2)),
            "population_rate":rng.normal(-1.,.2,(*shape,2)),
            "player_chol_stds":rng.uniform(.05,.5,(*shape,2)),
            "player_chol_corr":corr,
            "workload_sigma":rng.uniform(.15,.5,shape),
            "opponent_rate_sd":rng.uniform(.1,.3,shape),
            "home_effect":rng.normal(0.,.1,shape),
            "count_dispersion":rng.gamma(4,.5,shape)
        }
        stats={"diverging":np.zeros(shape,dtype=int),
               "energy":rng.normal(0.,1.,shape)}
        draws=az.from_dict(posterior=posterior,sample_stats=stats)
        d=model.diagnostics(draws)
        self.assertEqual(d["status"],"sampling_diagnostics_pass",d)
        self.assertTrue(d["posterior_sampling_ok"])
        self.assertGreater(d["min_bulk_ess"],400)
        self.assertFalse(d["publication_eligible"])

    def test_actual_variable_stuck_must_still_fail(self):
        if importlib.util.find_spec("arviz") is None:
            self.skipTest("ArviZ available in isolated numerical CI")
        import numpy as np
        import arviz as az
        rng=np.random.default_rng(761)
        shape=(4,700)
        corr=np.broadcast_to(np.eye(2),(*shape,2,2)).copy()
        posterior={
            "population_workload":rng.normal(3.,.2,(*shape,2)),
            "population_rate":rng.normal(-1.,.2,(*shape,2)),
            "player_chol_stds":rng.uniform(.05,.5,(*shape,2)),
            "player_chol_corr":corr,
            "workload_sigma":rng.uniform(.15,.5,shape),
            "opponent_rate_sd":rng.uniform(.1,.3,shape),
            "home_effect":rng.normal(0.,.1,shape)
        }
        draws=az.from_dict(posterior=posterior,
            sample_stats={"diverging":np.zeros(shape,dtype=int),
                          "energy":rng.normal(size=shape)})
        d=model.diagnostics(draws)
        self.assertFalse(d["posterior_sampling_ok"])
        self.assertFalse(d["publication_eligible"])

if __name__=="__main__":
    unittest.main()
