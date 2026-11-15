"""WS5 adversarial contract tests; actual workstreams remain independently pinned."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from v2.nba_joint import synthetic_fixture, simulate, audit, extract_forecast, freeze


class JointTests(unittest.TestCase):
    def setUp(self): self.game, self.model = synthetic_fixture()

    def test_physical_and_composite_identities(self):
        out=simulate(self.game,self.model,n=40,seed=12)
        self.assertEqual(audit(out)['violations'],0)
        for k,columns in {'pr':['points','rebounds'],'pa':['points','assists'],'ra':['rebounds','assists'],'pra':['points','rebounds','assists']}.items():
            np.testing.assert_array_equal(out['stats'][k],sum(out['stats'][c] for c in columns))

    def test_deterministic_scenario_prefix(self):
        a=simulate(self.game,self.model,n=4,seed=3);b=simulate(self.game,self.model,n=8,seed=3)
        for k in a['stats']: np.testing.assert_array_equal(a['stats'][k],b['stats'][k][:4])
        self.assertEqual(a['scenario_ids'],b['scenario_ids'][:4])

    def test_hash_changes_with_inputs(self):
        a=simulate(self.game,self.model,n=3,seed=4); g=copy.deepcopy(self.game);g['players'][0]['rates']['points']*=2
        b=simulate(g,self.model,n=3,seed=4);self.assertNotEqual(a['input_sha256'],b['input_sha256'])

    def test_overtime_and_cap(self):
        self.model['state']['ot_probability']=.95
        out=simulate(self.game,self.model,n=35,seed=91)
        self.assertTrue(np.any(out['state']['overtime']>0));self.assertEqual(audit(out)['violations'],0)

    def test_inactive_exposure_zero(self):
        p=self.game['players'][0];p['eligible']=False;p['participation_probability']=0
        o=simulate(self.game,self.model,n=8,seed=1)
        self.assertTrue(np.all(o['minutes'][:,0]==0));self.assertTrue(np.all(o['stats']['points'][:,0]==0))

    def test_unknown_participation_prospective_rejected(self):
        self.game['mode']='prospective';self.game['players'][0]['participation_probability']=None
        with self.assertRaisesRegex(ValueError,'SOURCE|PARTICIPATION'):simulate(self.game,self.model,n=2,seed=1)

    def test_conditional_unknown_remains_unknown(self):
        self.game['players'][0]['participation_probability']=None
        out=simulate(self.game,self.model,n=2,seed=1)
        f=extract_forecast(out,0,'points',line=10)
        self.assertIsNone(f['participation_probability']);self.assertFalse(f['certified'])

    def test_fewer_than_five_not_repaired(self):
        self.game['players']=[p for p in self.game['players'] if p['team_id']!=self.game['teams'][0] or int(p['player_id'].split(':')[-1])<4]
        with self.assertRaisesRegex(ValueError,'FEWER_THAN_FIVE'):simulate(self.game,self.model,n=2,seed=1)

    def test_duplicate_identity(self):
        self.game['players'][1]['player_id']=self.game['players'][0]['player_id']
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):simulate(self.game,self.model,n=2,seed=1)

    def test_future_training_cutoff(self):
        self.model['training_cutoff_at']='2030-01-01T00:00:00Z'
        with self.assertRaisesRegex(ValueError,'CUTOFF'):simulate(self.game,self.model,n=2,seed=1)

    def test_future_feature_date(self):
        self.game['players'][0]['last_observation_date']=self.game['game_date']
        with self.assertRaisesRegex(ValueError,'FUTURE'):simulate(self.game,self.model,n=2,seed=1)

    def test_target_game_history_rejected(self):
        self.game['players'][0]['history_game_ids'].append(self.game['game_id'])
        with self.assertRaisesRegex(ValueError,'SAME_GAME'):simulate(self.game,self.model,n=2,seed=1)

    def test_invalid_conversion(self):
        self.model['events']['p3']=1.1
        with self.assertRaisesRegex(ValueError,'PROBABILITY'):simulate(self.game,self.model,n=2,seed=1)

    def test_no_silent_scenario_drop(self):
        for p in self.game['players']:p['participation_probability']=1.
        for p in self.game['players'][:6]:p['participation_probability']=0
        self.game['conditional_on_roster']=False
        with self.assertRaisesRegex(ValueError,'FEWER_THAN_FIVE'):simulate(self.game,self.model,n=5,seed=1)

    def test_exact_push_semantics(self):
        out=simulate(self.game,self.model,n=20,seed=1)
        for line in (0,1,10,10.5):
            f=extract_forecast(out,0,'points',line=line)
            self.assertAlmostEqual(sum(f['probabilities'].values()),1)
            if line%1:self.assertEqual(f['probabilities']['push'],0)
            self.assertEqual(f['probabilities']['push'],np.mean(out['stats']['points'][:,0]==line))

    def test_empirical_pmf_and_quantiles(self):
        out=simulate(self.game,self.model,n=15,seed=1);f=extract_forecast(out,0,'pra')
        self.assertAlmostEqual(sum(f['pmf'].values()),1);self.assertIsNone(f['probabilities'])
        self.assertEqual(f['mean'],np.mean(out['stats']['pra'][:,0]))

    def test_integer_counts_and_nonnegative(self):
        o=simulate(self.game,self.model,n=10,seed=991)
        for v in o['stats'].values():self.assertTrue(np.issubdtype(v.dtype,np.integer));self.assertTrue(np.all(v>=0))

    def test_audit_detects_corruption(self):
        o=simulate(self.game,self.model,n=3,seed=4);o['stats']['points'][0,0]+=1
        with self.assertRaisesRegex(ValueError,'POINTS'):audit(o)

    def test_secondary_markets_disabled(self):
        o=simulate(self.game,self.model,n=2,seed=1)
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED'):extract_forecast(o,0,'steals',line=.5)

    def test_immutable_writes(self):
        o=simulate(self.game,self.model,n=2,seed=1);f=extract_forecast(o,0,'points')
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'f.json';freeze(p,f)
            with self.assertRaises(FileExistsError):freeze(p,f)

    def test_synthetic_cannot_be_certified(self):
        o=simulate(self.game,self.model,n=2,seed=1);f=extract_forecast(o,0,'points')
        self.assertFalse(f['certified']);self.assertEqual(f['mode'],'synthetic')

    def test_property_sweep(self):
        for seed in range(12):self.assertEqual(audit(simulate(self.game,self.model,n=6,seed=seed))['violations'],0)


if __name__=='__main__':unittest.main()
