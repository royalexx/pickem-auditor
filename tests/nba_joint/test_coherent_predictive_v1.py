import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from tests.nba_joint.test_residual_events_v1 import fixture
from v2.nba_joint.coherent_components_v1 import posterior,fit
from v2.nba_joint.coherent_predictive_v1 import draw_parameters,generate,rows,query,validate_bank


def coherent_fixture():
    model=fixture();cohort=dict(game_id=model['target'],frozen_candidates=[])
    for p in model['named_players']+list(model['residual_groups'].values()):
        p['rates']={s:p['rates'][s] for s in ('assists','rebounds')}
        p.pop('ft_non3_point_share',None)
        p['attempt_posteriors']={s:dict(alpha=20.,beta=b) for s,b in dict(twoPA=50.,threePA=120.,FTA=100.,TO=300.).items()}
    cohort['frozen_candidates']=[dict(player_id=p['player_id'],team_id=p['team_id']) for p in model['named_players']]
    cohort['frozen_candidates'] += [dict(player_id='unsupported:'+str(i),team_id='A') for i in range(21)]
    return model,cohort


class CoherentTests(unittest.TestCase):
    def test_attempt_conversion_algebra_no_independent_pts_threes(self):
        model,_=coherent_fixture();p=model['named_players'][0]
        for seed in range(40):
            v=draw_parameters(p,np.random.default_rng(seed));a=v['attempt_rates']
            self.assertAlmostEqual(v['rates']['threes']/v['p3'],a['threePA'])
            self.assertAlmostEqual((v['rates']['points']-3*v['rates']['threes'])*(1-v['ft_share'])/(2*v['p2']),a['twoPA'])
            self.assertGreaterEqual(v['rates']['points'],3*v['rates']['threes'])
        p['rates']['points']=dict(alpha=1,beta=1)
        with self.assertRaises(ValueError):draw_parameters(p,np.random.default_rng(1))

    def test_actual_same_kernel_projections_and_complete_denominators(self):
        model,c=coherent_fixture()
        with tempfile.TemporaryDirectory() as temp:
            bank=generate(model,c,Path(temp)/'trace',seed=5,n=3)
            self.assertEqual(validate_bank(bank,Path(temp)/'trace',model)['scenarios'],3)
            out=rows(bank);self.assertEqual((len(out),sum(r['samples'] is not None for r in out)),(280,112))
            for kind,value in (('pmf',4),('cdf',8),('oup',7.5)):
                kw=dict(player_id='A0',statistic='points',kind=kind,value=value)
                self.assertEqual(query(bank,channel='S4',**kw),query(bank,channel='J',**kw))
            q=query(bank,player_id='A0',statistic='points',kind='pmf',value=100000)
            self.assertEqual(q['estimate'],[0.]);self.assertGreater(q['componentwise_MC_95_family_intervals'][0]['upper'],0)
            self.assertFalse(q['population_exact_zero_claim'])
            first=next((Path(temp)/'trace').glob('*'));first.write_bytes(first.read_bytes()+b'bad')
            with self.assertRaises(ValueError):validate_bank(bank,Path(temp)/'trace',model)

    def test_exhaustion_cannot_expose_successful_subset(self):
        model,c=coherent_fixture()
        with tempfile.TemporaryDirectory() as temp:
            bank=generate(model,c,Path(temp)/'trace',n=3,event_budget=5)
            self.assertEqual((bank['status'],len(bank['scenarios']),len(bank['failed'])),('FAILED_WHOLE_RUN',3,3))
            self.assertTrue(all(s['proposals'] for s in bank['scenarios']))
            with self.assertRaises(ValueError):rows(bank)

    def test_conjugate_working_likelihood_update(self):
        def row(a,m,sec):
            return dict(exact_seconds=sec,official_counts=dict(fieldGoalsAttempted=a+2,threePointersAttempted=2,
                fieldGoalsMade=m+1,threePointersMade=1,freeThrowsAttempted=4,freeThrowsMade=3,turnovers=1))
        own=[row(5,2,600)];peers=[row(10,5,1200)];p=posterior(own,peers)
        self.assertEqual(p['attempt_posteriors']['twoPA']['alpha'],.5+180*.5+5)
        self.assertEqual(p['attempt_posteriors']['twoPA']['beta'],191.)
        self.assertEqual(p['conversion2']['alpha'],.5+40*.5+2)
        self.assertEqual(p['conversion2']['beta'],.5+40*.5+3)
        with patch('v2.nba_joint.coherent_components_v1.PREFIT_SHA',None),self.assertRaises(ValueError):fit(approval_path='missing',protocol_path='missing',old_model_path='missing',
            old_admission_path='missing',source_inputs={},original_raw_dir='missing',spec_path='missing',policy_path='missing',output='missing')


if __name__=='__main__':unittest.main()
