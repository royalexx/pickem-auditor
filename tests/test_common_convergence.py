"""The fair Bayesian sampler benchmark may never score unconverged posteriors."""
import sys
import unittest
from unittest.mock import patch
import numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import convergence_backend_eval as ce

class CommonDiagnosticContracts(unittest.TestCase):
    def test_same_named_variables_and_budget(self):
        self.assertEqual(len(ce.STAGES),3)
        self.assertEqual(list(ce.SEEDS),[19031,29031])
        for a,b in zip(ce.STAGES,ce.STAGES[1:]):
            self.assertGreater(b['draws'],a['draws'])
            self.assertGreater(b['tune'],a['tune'])
            self.assertGreater(b['target_accept'],a['target_accept'])
        self.assertIn('player_effect',ce.CORE_KEYS)
        self.assertIn('opponent_rate',ce.CORE_KEYS)
    def test_source_names_and_season_zero_exclusion(self):
        self.assertNotIn('season_rate',ce.CORE_KEYS)
        self.assertIn('season_rate',ce.MULTI_SEASON_KEYS)
    def test_no_rhat_nan_shortcut_or_missing_diagnostic_keys(self):
        from unittest.mock import patch
        arrays={k:np.tile(np.arange(100.0),8) for k in ce.CORE_KEYS}
        arrays['count_dispersion']=np.arange(800.0)
        del arrays['player_effect']
        with self.assertRaisesRegex(ValueError,'missing_matched_diagnostic_parameters'):
            ce.common_diagnostics({'count':800,'arrays':arrays},
                {'divergences':0,'minimum_bfmi':.4},
                {'family':'count','seasons':['2023']},draws=200,chains=4)
    def test_divergences_are_always_rejected(self):
        import arviz_stats
        # Deterministic fake ArviZ statistics isolate the NUTS diagnostic gate.
        rng=np.random.default_rng(33)
        arrays={k:rng.standard_normal(2000) for k in ce.CORE_KEYS}
        arrays['count_dispersion']=rng.gamma(2,1,size=2000)
        ok=ce.common_diagnostics({'count':2000,'arrays':arrays},
            {'divergences':1,'minimum_bfmi':.8},
            {'family':'count','seasons':['2023']},draws=500,chains=4)
        self.assertFalse(ok['posterior_sampling_ok'])
        self.assertEqual(ok['divergences'],1)

if __name__=='__main__':
    unittest.main()
