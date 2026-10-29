import sys
import unittest
from datetime import date,datetime,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nba_prior_bridge as bridge
import bayesian_engine as be

def make_record(pid,stat='threes',current=4,prior=20,workload=32.):
    def value(i):
        return float(3+(i%2)) if stat=='threes' else float(23+(i%3))
    record=dict(sport='NBA',stat=stat,player_id=pid,team='DAL',observations=[],
                prior_observations=[])
    for i in range(current):
        record['observations'].append(dict(id=f'{pid}-c-{i}',date=f'2026-10-{20+i:02d}',
                                           value=value(i),workload=workload))
    for i in range(prior):
        record['prior_observations'].append(dict(id=f'{pid}-p-{i}',date=f'2025-01-{i+1:02d}',
                                                 value=value(i),workload=workload))
    return record

class PriorPowerBridgeTests(unittest.TestCase):
    def setUp(self):
        self.record=make_record('subject')
        self.peers=[tuple(bridge.observations(make_record(str(i)),before=date(2026,10,29),stat='threes'))
                    for i in range(6)]
    def test_requires_actual_disjoint_source_gamelogs(self):
        got=bridge.observations(self.record,before=date(2026,10,29),stat='threes')
        self.assertEqual(len(got),24)
        self.assertAlmostEqual(sum(r[-1] for r in got),12.)
        self.assertEqual([r[-1] for r in got[:4]],[1.]*4)
        bad={**self.record,'prior_observations':self.record['prior_observations'][:9]}
        with self.assertRaises(be.ModelUnavailable):
            bridge.observations(bad,before=date(2026,10,29),stat='threes')
        future={**self.record,'observations':[dict(self.record['observations'][0],date='2026-10-30')]+self.record['observations'][1:]}
        with self.assertRaises(be.ModelUnavailable):
            bridge.observations(future,before=date(2026,10,29),stat='threes')
        changed={**self.record,'prior_observations':[dict(v,workload=5.) for v in self.record['prior_observations']]}
        with self.assertRaises(be.ModelUnavailable):
            bridge.observations(changed,before=date(2026,10,29),stat='threes')
    def test_a_and_b_count_probabilities_are_complete(self):
        with patch.object(bridge,'peers',return_value=self.peers):
            args=dict(root='unused',stat='threes',player_id='subject',
                      cutoff=datetime(2026,10,28,20,tzinfo=timezone.utc),
                      before=date(2026,10,29),dist='poisson',line=3.5,side='under')
            a=bridge.model_a(self.record,**args)
            b=bridge.model_b(self.record,**args)
        for v in (a,b):
            self.assertEqual(v['status'],'shadow_only')
            self.assertFalse(v['publication_eligible'])
            self.assertAlmostEqual(v['q_win']+v['q_push']+v['q_loss'],1,places=7)
            self.assertEqual(v['effective_observation_count'] if 'effective_observation_count' in v else v['effective_exposure_games'],12.)
            self.assertEqual(v['peer_count'],6)
            self.assertEqual(v['source_only_prior_power'],.4)
    def test_normal_production_and_workload_path(self):
        record=make_record('subject','points')
        peers=[tuple(bridge.observations(make_record(str(i),'points'),before=date(2026,10,29),stat='points'))
               for i in range(6)]
        with patch.object(bridge,'peers',return_value=peers):
            args=dict(root='unused',stat='points',player_id='subject',
                      cutoff=datetime(2026,10,28,20,tzinfo=timezone.utc),
                      before=date(2026,10,29),dist='normal',line=25.5,side='under')
            a=bridge.model_a(record,**args)
            b=bridge.model_b(record,**args)
        for v in (a,b):
            self.assertAlmostEqual(v['q_win']+v['q_push']+v['q_loss'],1,places=7)
if __name__=='__main__':
    unittest.main()
