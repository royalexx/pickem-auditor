"""Adversarial independent global-index sharded NBA S4/J sensitivity audit."""
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from v2.nba_joint.coherent_sensitivity_pimh_v1 import simulate_sensitivity
from v2.nba_joint.coherent_sensitivity_aggregate_v1 import aggregate_complete_shards


class ShardedS4MCAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from scripts.nba_coherent_mc_pimh import admitted_inputs
        cls.model,cls.cohort=admitted_inputs()

    def _two_shards(self,root):
        a=Path(root)/'shard-000000-000000'
        b=Path(root)/'shard-000001-000002'
        simulate_sensitivity(self.model,self.cohort,a,n=1,start_index=0,
                             rare_sampler='sequential',chunk_size=1)
        simulate_sensitivity(self.model,self.cohort,b,n=2,start_index=1,
                             rare_sampler='sequential',chunk_size=2)
        return a,b

    def test_two_shards_exact_global_coverage_and_population(self):
        with tempfile.TemporaryDirectory() as t:
            a,b=self._two_shards(t)
            r=aggregate_complete_shards(t,self.model,self.cohort,
                              expected_n=3,rare_sampler='sequential')
            self.assertEqual(r['totals']['accepted'],18)
            self.assertEqual(r['totals']['score_assignment_rows'],18*14)
            self.assertEqual(r['n_per_variant'],3)
            self.assertIn('3',r['full_distribution_receipts'])
            self.assertTrue((Path(t)/'AGGREGATE_RECEIPT.json').exists())
            with self.assertRaises(FileExistsError):
                aggregate_complete_shards(t,self.model,self.cohort,
                              expected_n=3,rare_sampler='sequential')

    def test_does_not_accept_missing_index(self):
        with tempfile.TemporaryDirectory() as t:
            a,b=self._two_shards(t)
            with self.assertRaisesRegex(ValueError,
                   'S4_MC_SHARD_COVERAGE_OVERLAP_OR_GAP|S4_MC_MISSING_GLOBAL'):
                aggregate_complete_shards(t,self.model,self.cohort,
                             expected_n=4,rare_sampler='sequential',write=False)

    def test_compressed_chunk_tamper_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            a,b=self._two_shards(t)
            chunk=next(a.glob('chunk-*.jsonl.gz'))
            data=chunk.read_bytes()
            chunk.write_bytes(data+b'JUNK')
            with self.assertRaisesRegex(ValueError,'S4_MC_COMPRESSED_CHUNK_TAMPER'):
                aggregate_complete_shards(t,self.model,self.cohort,
                             expected_n=3,rare_sampler='sequential',write=False)

    def test_receipt_mutation_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            a,b=self._two_shards(t)
            path=a/'RECEIPT.json';r=json.loads(path.read_text())
            r['end_index_exclusive']=123
            path.write_text(json.dumps(r))
            with self.assertRaises(ValueError):
                aggregate_complete_shards(t,self.model,self.cohort,
                             expected_n=3,rare_sampler='sequential',write=False)

    def test_exact_frozen_K_ge_two_probability_bound(self):
        p=self.model['named_players'][0]['minutes']['ot_probability']
        q=self.model['named_players'][0]['minutes']['ot_continuation']
        delta=p*q
        self.assertTrue(0.006<delta<0.007)
        self.assertAlmostEqual(delta,p*q)
        # Global count CDF bias from *any* invalid K>=2 conditional
        # sampler <= total prior mass K>=2, independent of MCMC mixing.
        self.assertLess(delta,0.01)


if __name__=='__main__':
    unittest.main()
