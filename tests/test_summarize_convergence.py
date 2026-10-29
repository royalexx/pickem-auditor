"""Fail-closed aggregation tests do not require the scientific stack."""
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from summarize_convergence_backends import reconcile,APPROVED,REJECTED,FROZEN

def fixture(market,backend,converged=False,source=FROZEN):
    x={'schema':'matched-convergence-benchmark-v1','market':market,
       'backend':backend,'status':APPROVED if converged else REJECTED,
       'source_archive':source,'train_digest':'sha-training',
       'holdout_digest':'sha-heldout','seeds':[19031,29031],
       'chain_count':4,'model_changed':False,
       'likelihood_prior_changed':False,'attempts':[]}
    if converged:
        x.update(mean_brier=.12,mean_log_loss=.34,
                 mean_ess_per_second=8.0,total_fit_wall_seconds=200,
                 selected_stage='initial',
                 attempts=[{'seed':z,'common_diagnostics':{'posterior_sampling_ok':True},
                            'holdout':{'brier':.12}} for z in (19031,29031)])
    return x

class SummaryContracts(unittest.TestCase):
    def test_no_winner_when_only_two_backend_posteriors_converge(self):
        rows=[]
        for i in range(4):
            for b in ('pymc','nutpie','cmdstanpy'):
                rows.append((f'{i}-{b}',fixture(f'nhl_test{i}',b,b!='nutpie')))
        result=reconcile(rows,expected=12)
        self.assertEqual(result['status'],'complete')
        self.assertEqual(result['fully_comparable_markets'],0)
        self.assertEqual(result['converged_backend_market_evaluations'],8)
        for m in result['markets'].values():
            self.assertIsNone(m['fastest_reliable_backend'])
    def test_no_score_on_failed_fit(self):
        rows=[]
        for i in range(4):
            for b in ('pymc','nutpie','cmdstanpy'):
                x=fixture(f'nhl_test{i}',b)
                if i==0 and b=='nutpie':x['mean_brier']=.01
                rows.append((f'{i}-{b}',x))
        result=reconcile(rows,expected=12)
        self.assertEqual(result['status'],'invalid_or_incomplete')
        self.assertIn('unconverged_posterior_had_predictive_score',
                      result['invalid'][0]['reason'])
    def test_one_complete_market_can_rank_time_only_if_all_3_converge(self):
        rows=[]
        for i in range(4):
            for b in ('pymc','nutpie','cmdstanpy'):
                x=fixture(f'nba_test{i}',b,i==0)
                if i==0:
                    x['total_fit_wall_seconds']={'pymc':200,'nutpie':300,
                                                  'cmdstanpy':175}[b]
                rows.append((f'{i}-{b}',x))
        result=reconcile(rows,expected=12)
        self.assertEqual(result['status'],'complete')
        self.assertEqual(result['fully_comparable_markets'],1)
        self.assertEqual(result['markets']['nba_test0']['fastest_reliable_backend'],'cmdstanpy')
    def test_source_drift_rejected(self):
        rows=[]
        for i in range(4):
            for b in ('pymc','nutpie','cmdstanpy'):
                rows.append((f'{i}-{b}',fixture(f'nfl_test{i}',b,
                    source='new-history-sha' if i==0 and b=='pymc' else FROZEN)))
        result=reconcile(rows,expected=12)
        self.assertEqual(result['status'],'invalid_or_incomplete')
        self.assertTrue(result['invalid'])

if __name__=='__main__':
    unittest.main()
