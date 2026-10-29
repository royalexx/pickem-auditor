"""Research-only convergence contracts; importable without scientific extras."""
import ast
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'scripts/convergence_backend_eval.py').read_text()
GRAPH=ast.parse(SOURCE)

class ConvergenceContracts(unittest.TestCase):
    def test_fixed_predeclared_adaptive_budget(self):
        self.assertIn("dict(name='initial',draws=1200,tune=1600,target_accept=.99)",SOURCE)
        self.assertIn("dict(name='extended',draws=2400,tune=3000,target_accept=.995)",SOURCE)
        self.assertIn("dict(name='geometry_warning',draws=3800,tune=4500,target_accept=.997)",SOURCE)
        self.assertIn("SEEDS=(19031,29031)",SOURCE)
        self.assertIn("len(outcomes)==len(SEEDS)",SOURCE)
    def test_identical_diagnostic_gates(self):
        for variable in ("player_effect","opponent_rate","player_chol_stds",
                         "player_correlation","population_rate","count_dispersion"):
            self.assertIn(variable,SOURCE)
        for guard in ("extreme_rhat<=1.01","least_bulk>=400","least_tail>=400",
                      "divergences==0","bfmi>=.30"):
            self.assertIn(guard,SOURCE)
        self.assertIn("if not matched['posterior_sampling_ok']",SOURCE)
    def test_market_scoring_after_both_seeds_pass(self):
        all_scores=[n.lineno for n in ast.walk(GRAPH)
                    if isinstance(n,ast.Attribute) and n.attr=='score']
        self.assertTrue(all_scores)
        self.assertIn("status='not_converged_no_predictive_comparison'",SOURCE)
        self.assertNotIn('payout',SOURCE)
    @unittest.skipUnless(all(importlib.util.find_spec(x) is not None
                             for x in ('numpy','xarray','arviz_stats')),
                         'scientific stack not installed in minimal offline CI')
    def test_divergence_rejection_with_shared_library(self):
        import sys
        import numpy as np
        sys.path.insert(0,str(ROOT/'scripts'))
        from convergence_backend_eval import CORE_KEYS,common_diagnostics
        rng=np.random.default_rng(33)
        arrays={k:rng.standard_normal(2000) for k in CORE_KEYS}
        arrays['count_dispersion']=rng.gamma(2,1,size=2000)
        x=common_diagnostics({'count':2000,'arrays':arrays},
             {'divergences':1,'minimum_bfmi':.8},
             {'family':'count','seasons':['2023']},draws=500,chains=4)
        self.assertFalse(x['posterior_sampling_ok'])
        self.assertEqual(x['divergences'],1)

if __name__=='__main__':
    unittest.main()
