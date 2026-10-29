"""Benchmark source integrity and Stan/PyMC model parity assumptions."""
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from benchmark_bayes_backends import FIXTURES,stan_data

class BenchmarkContracts(unittest.TestCase):
    def test_stan_uses_same_nuts_model_families(self):
        text=(ROOT/'benchmarks/stan/identical_joint.stan').read_text()
        for required in ['lkj_corr_cholesky(2)','diag_pre_multiply','neg_binomial_2(',
                         'student_t(4,','normal(0,0.45)','gamma(3,0.35)',
                         'season_workload','opponent_rate','player_effect']:
            self.assertIn(required,text)
        self.assertEqual(set(FIXTURES),{'nhl_hits','nba_points','nfl_rec_yards'})
    def test_stan_data_uses_one_indexed_individual_ids_and_source_values(self):
        d=dict(sport='NHL',family='count',rows=2,
            players=['a','b'],positions=['C','D'],seasons=['2023'],
            opponents=['BOS','NYR'],player_idx=[0,1],position_idx=[1,0],
            season_idx=[0,0],opponent_idx=[0,1],home=[0,1],
            workload=[18.,22.],value=[2.,3.])
        got=stan_data(d)
        self.assertEqual(got['p'],[1,2])
        self.assertEqual(got['group'],[2,1])
        self.assertEqual(got['season_on'],0)
        self.assertEqual(got['y_count'],[2,3])
        self.assertEqual(got['base_work'],2.9)
        self.assertEqual(got['is_count'],1)
    def test_research_only_and_event_frozen(self):
        text=(ROOT/'.github/workflows/benchmark-bayes-backends.yml').read_text()
        self.assertIn('research only',text)
        self.assertNotIn('PROPLINE_API_KEY',text)
        self.assertIn('history_warehouse_store.sh load',text)
        for fixture in FIXTURES.values():
            self.assertLess(fixture['train_from'],fixture['cutoff'])
            self.assertLess(fixture['cutoff'],fixture['until'])
            self.assertFalse(float(fixture['line']).is_integer())

if __name__=='__main__':
    unittest.main()
