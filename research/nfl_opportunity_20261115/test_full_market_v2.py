"""Synthetic mathematical tests, never forecast substitutes."""
import copy
import unittest
import numpy as np
from .test_models import fixture
from . import models as m
from .full_market_v2 import FullMarketModel, MARKETS, MODELS

class FullMarketTests(unittest.TestCase):
    def packet(self):
        p=fixture();p['contracts']=[c for c in p['contracts'] if c['stat'] not in {'solo tackles','tackle assists'}]
        return p
    def test_quote_independent_and_reproducible(self):
        p=self.packet(); p['contracts']=[]
        a=FullMarketModel(p,1024).run();b=FullMarketModel(p,1024).run()
        self.assertEqual(a,b)
        self.assertTrue(any(r['market']=='receiving_targets' and r['status']=='forecast' for r in a['player_stat_rows']))
        self.assertEqual(a['contract_rows'],[])
        self.assertTrue(all(r['market'] in MARKETS for r in a['player_stat_rows']))
        self.assertTrue(all(r['model'] in MODELS for r in a['player_stat_rows']))
    def test_matched_composites_and_constraints(self):
        p=self.packet();model=FullMarketModel(p,8192);e=p['events'][0];env=model.environment(e)
        for mixture in (False,True):
            v,a,d,f=model.offense(e,'A',env['A'],mixture)
            for pid,x in v.items():
                for total,left,right in [('rushing + receiving yards','rushing yards','receiving yards'),('passing + rushing yards','passing yards','rushing yards')]:
                    if left in x and right in x: np.testing.assert_array_equal(x[total],x[left]+x[right])
                if 'receptions' in x:self.assertTrue((x['receptions']<=x['targets']).all())
                if 'completions' in x:self.assertTrue((x['completions']<=x['pass attempts']).all())
            self.assertTrue((sum(x.get('targets',0) for x in v.values())<=env['A']['pass_attempts']).all())
            self.assertTrue((sum(x.get('carries',0) for x in v.values())<=env['A']['rush_attempts']).all())
    def test_defense_fails_closed_and_no_components_published(self):
        r=FullMarketModel(self.packet(),1024).run()
        defense=[x for x in r['player_stat_rows'] if x['model']==MODELS[3]]
        self.assertTrue(defense);self.assertTrue(all(x['status']=='abstain' for x in defense))
        self.assertEqual({x['market'] for x in defense},{'tackles_assists'})
    def test_missing_component_abstains_without_blocking_targets(self):
        p=self.packet()
        for h in p['player_history']: h.pop('rushing_yards',None)
        rows=FullMarketModel(p,1024).run()['player_stat_rows']
        self.assertTrue(any(x['market']=='receiving_targets' and x['status']=='forecast' for x in rows))
        self.assertTrue(all(x['status']=='abstain' for x in rows if x['market'].endswith('_receiving_yards') or x['market']=='passing_rushing_yards'))
    def test_kickoff_and_missing_sacks_rejected(self):
        for mutate in [lambda p:p.update(forecast_at='2026-11-15T18:00:00Z'),lambda p:p['team_history'][0].update(sacks=None)]:
            p=self.packet();mutate(p)
            with self.assertRaises(m.GateError):FullMarketModel(p,1024)
