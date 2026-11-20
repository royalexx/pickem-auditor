"""New S4/J zero-mixture research validation. Never changes frozen forecasts."""
import copy
import gzip
from pathlib import Path
import tempfile
import unittest

from tests.nba_joint.test_coherent_predictive_v1 import coherent_fixture
from v2.nba_architecture.p1_subset_handoff_v1 import canonical, digest
from v2.nba_joint.coherent_sensitivity_v1 import (
    SEED, PairedZeroRNG, VARIANTS, _analyze, _cp, _sup_cdf,
    assert_original_fixed_parity, fixed_pair_invariants,
    fixed_paired_scenario, simulate_sensitivity,
)


class PairedS4SensitivityTests(unittest.TestCase):
    def test_full_original_fixed_state_exact_byte_parity_and_shared_parameters(self):
        model,_=coherent_fixture()
        controls=assert_original_fixed_parity(model,seed=SEED,indices=(0,1,2))
        self.assertEqual(len(controls),3)
        a=fixed_paired_scenario(model,SEED,0,None)
        for z in (0.,.005,.01,.02,.05):
            b=fixed_paired_scenario(model,SEED,0,z)
            self.assertTrue(fixed_pair_invariants(a,b))
            self.assertEqual(a['overtime_count'],b['overtime_count'])
            self.assertEqual(a['pace'],b['pace'])
            for team,actors in b['actors'].items():
                self.assertTrue(all(x['identity']['zero_weight_model_draw']==z
                                    for x in actors if x['identity']['player_id']))
        m=copy.deepcopy(a);m['pace']*=2
        with self.assertRaisesRegex(ValueError,'S4_SENS_UNPAIRED_SHARED_G'):
            fixed_pair_invariants(a,m)

    def test_masked_rng_consumes_original_beta_and_only_intervenes_on_z(self):
        import numpy as np
        original=np.random.default_rng(100)
        override=np.random.default_rng(100)
        a=float(original.beta(.5,49.5))
        b=PairedZeroRNG(override,.05)
        self.assertEqual(b.beta(.5,49.5),.05)
        self.assertEqual(b.draw_count,1)
        self.assertEqual(float(original.gamma(2.,1.)),
                         float(override.gamma(2.,1.)))
        self.assertTrue(0<=a<=1)
        with self.assertRaisesRegex(ValueError,'S4_SENS_UNEXPECTED_BETA_CALL'):
            b.beta(1.,2.)
        with self.assertRaises(ValueError):
            PairedZeroRNG(np.random.default_rng(10),1.)

    def test_paired_mean_cdf_and_exact_tail_interval_reference(self):
        self.assertAlmostEqual(_sup_cdf([0,1,2,3],[0,0,2,2]),.25)
        self.assertEqual(_cp(0,10,.05)[0],0)
        self.assertAlmostEqual(_cp(0,10,.05)[1],1-(.025)**(.1))
        self.assertAlmostEqual(_cp(10,10,.05)[0],(.025)**(.1))
        sample={name:{'p':{s:[0,1,2,3] for s in
                        ('points','rebounds','assists','threes','pr','pa','ra','pra')}}
                for name in ('original_beta','fixed_0')}
        with self.assertRaises(ValueError):
            _analyze(sample,4,(('original_beta',None),('fixed_0',0.)))

    def test_missing_model_cohort_fails_before_output_creation(self):
        model,cohort=coherent_fixture()
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(ValueError,'S4_SENS_FROZEN_COHORT'):
                simulate_sensitivity(model,cohort,Path(t)/'out',n=1)
            self.assertFalse((Path(t)/'out').exists())

    def test_actual_pinned_source_smoke_preserves_all_six_variants(self):
        from scripts.nba_coherent_mc_sensitivity import admitted_inputs
        model,cohort=admitted_inputs()
        with tempfile.TemporaryDirectory() as t:
            target=Path(t)/'new'
            receipt=simulate_sensitivity(model,cohort,target,n=1,chunk_size=1,
                                         max_wall_seconds=180)
            self.assertTrue(receipt['completed_variants'])
            self.assertEqual(receipt['chunk_row_denominator'],6)
            self.assertEqual(len(receipt['by_variant']),6)
            self.assertEqual(len(receipt['prefix_scores']['1']['forecasts']),6)
            self.assertEqual((target/'RECEIPT.json').read_bytes()[-1:],b'\n')
            for c in receipt['chunks']:
                packed=(target/c['path']).read_bytes()
                self.assertEqual(digest(packed),c['gzip_raw_sha256'])
                raw=gzip.decompress(packed)
                self.assertEqual(digest(raw),c['raw_sha256'])
                self.assertEqual(len(raw.splitlines()),6)
            with self.assertRaises(FileExistsError):
                simulate_sensitivity(model,cohort,target,n=1)

    def test_event_budget_exhaustion_retains_every_variant_failure(self):
        from scripts.nba_coherent_mc_sensitivity import admitted_inputs
        model,cohort=admitted_inputs()
        with tempfile.TemporaryDirectory() as t:
            result=simulate_sensitivity(model,cohort,Path(t)/'failed',
                                      n=1,event_budget=1,chunk_size=1)
            self.assertFalse(result['completed_variants'])
            self.assertEqual(result['scientific_status'],'FAILED_INCOMPLETE')
            self.assertEqual(result['chunk_row_denominator'],6)
            self.assertTrue(all(x['failed']==1 for x in result['by_variant'].values()))
            self.assertNotIn('prefix_scores',result)


if __name__=='__main__':
    unittest.main()
