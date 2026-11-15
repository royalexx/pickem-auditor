import importlib.util
import pathlib
import unittest
import numpy as np

path = pathlib.Path(__file__).with_name('multivariate_scores.py')
spec = importlib.util.spec_from_file_location('ws4_multivariate_scores',path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class TestIndependentJointScores(unittest.TestCase):
    def test_energy_analytic_reference(self):
        self.assertAlmostEqual(mod.energy_score([[0],[2]],[1]),.5,places=12)
        self.assertAlmostEqual(mod.energy_score([[0],[0]],[1]),1,places=12)
    def test_energy_fixed_ensemble_permutation(self):
        x=[[0,2],[2,0],[1,1]]
        self.assertAlmostEqual(mod.energy_score(x,[1,1]),mod.energy_score(x[::-1],[1,1]),places=12)
    def test_variogram_dependence(self):
        self.assertEqual(mod.variogram_score([[0,0],[2,2]],[1,1]),0)
        self.assertAlmostEqual(mod.variogram_score([[0,2],[2,0]],[1,1]),2,places=12)
    def test_rank_shuffling_preserves_exact_marginals(self):
        x=np.array([[1,0,2],[0,2,2],[3,4,0],[1,1,1],[0,0,3]])
        z=mod.independent_marginal_null(x,123)
        np.testing.assert_array_equal(np.sort(x,axis=0),np.sort(z,axis=0))
        np.testing.assert_array_equal(z,mod.independent_marginal_null(x,123))
    def test_event_probability_matches_joint(self):
        v=mod.event_probability([[2,3],[0,3],[2,0],[1,1]],0,1.5,1,2)
        self.assertEqual(v['p_joint'],.25)
        self.assertEqual(v['p_independent_product'],.25)
        self.assertEqual(v['joint_minus_product'],0)
    def test_invalid_dimensions(self):
        with self.assertRaisesRegex(ValueError,'DIMENSIONS'):mod.energy_score([[1,2]],[1])
    def test_nonfinite_values(self):
        with self.assertRaisesRegex(ValueError,'NONFINITE'):mod.energy_score([[np.nan]],[1])
    def test_bad_scales_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'SCALES'):mod.energy_score([[1,2]],[1,2],[1,0])
    def test_invalid_variogram_pair_weights(self):
        with self.assertRaisesRegex(ValueError,'PAIR_WEIGHTS'):mod.variogram_score([[1,2]],[1,2],pair_weights=[[0,2],[0,0]])
    def test_original_offer_line_nonfinite(self):
        with self.assertRaisesRegex(ValueError,'ORIGINAL_LINE'):mod.event_probability([[1,2]],0,float('nan'),1,.5)
    def test_fixed_truth_one_draw_crps_geometry(self):
        x=np.array([[2,4]])
        self.assertAlmostEqual(mod.energy_score(x,[0,0]),np.sqrt(20),places=10)
    def test_no_source_training_or_mutation(self):
        x=np.array([[2,3],[1,5],[0,0]])
        before=x.copy()
        mod.energy_score(x,[1,1]);mod.variogram_score(x,[1,1]);mod.independent_marginal_null(x,1)
        np.testing.assert_array_equal(x,before)

if __name__=='__main__':unittest.main()