"""Numerical/adversarial extension tests; fabricated fixtures, never forecasts."""
import copy,pathlib,sys,unittest
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'joint_models'))
from all_market_v04.conditional import allocations,covariance,extend_game,verify,MARKETS
from all_market_v04.execute import parameterize,summarize,roles
from test_joint_models import fixture


def event():
    e=fixture()['events'][0];e['all_market_parameters']={}
    for t in e['teams']:
        ps=[]
        for p in t['players']:
            if p['role']=='DEFENDER':continue
            ps.append(dict(player_id=p['player_id'],target_share=0 if p['role']=='QB' else .2,
             rush_share=.1,catch_alpha=7,catch_beta=3,receiving_marks=[-2,8,20],rushing_marks=[-1,3,7]))
        e['all_market_parameters'][t['team_id']]=dict(players=ps,allocation_concentration=28,
          residual=dict(catch_alpha=1,catch_beta=4,receiving_marks=[-1,10],rushing_marks=[-1,5]))
    return e

class AllMarket(unittest.TestCase):
    def test_11_markets_only(self):
        self.assertEqual(len(MARKETS),11)
        self.assertFalse(any('solo' in s or 'td' in s for s in MARKETS))
    def test_games_conserve_and_no_forbidden_outputs(self):
        for model in ('J1','J2'):
            rng=np.random.default_rng(98)
            for _ in range(100):
                s,st=extend_game(event(),rng,model,'neutral');verify(s,st,event())
                self.assertTrue(set(k for p,k in s)<=set(MARKETS))
    def test_no_j3_without_source(self):
        with self.assertRaisesRegex(ValueError,'J3_SOURCE'):extend_game(event(),np.random.default_rng(2),'J3','neutral')
    def test_bad_budget(self):
        for w in ([.8,.8],[-.1,1.1],[float('nan'),1]):
            with self.assertRaises(ValueError):allocations(np.random.default_rng(),30,w,False,28)
    def test_composite_covariance(self):
        x=np.arange(100);y=-x
        r=covariance(x,y);self.assertEqual(r['variance_sum'],0);self.assertAlmostEqual(r['correlation'],-1)
        r=covariance(x,x);self.assertAlmostEqual(r['variance_sum'],4*np.var(x))
    def test_invalid_covariance(self):
        for x,y in [([1,2],[3]),([1,float('nan')],[1,2]),([],[])]:
            with self.assertRaises(ValueError):covariance(x,y)
    def test_tamper_counts(self):
        e=event();s,st=extend_game(e,np.random.default_rng(1),'J2','neutral');st['H']['residual_targets']+=1
        with self.assertRaisesRegex(ValueError,'TARGET_ACCOUNTING'):verify(s,st,e)
    def test_tamper_composite(self):
        e=event();s,st=extend_game(e,np.random.default_rng(1),'J2','neutral');s[('HQ','passing_rushing_yards')]+=1
        with self.assertRaisesRegex(ValueError,'COMPOSITE'):verify(s,st,e)
    def test_exact_contract_and_mc(self):
        r=summarize([0,1,2,3],'rushing_attempts',1)
        self.assertEqual(r['p_over']+r['p_under']+r['p_push'],1)
        self.assertEqual(r['p_push'],.25);self.assertEqual(r['effective_simulation_draws'],4)
    def test_roster_parse(self):
        self.assertEqual(roles({'athletes':[{'items':[{'id':'123','position':{'abbreviation':'QB'}}]}]}),{'123':'QB'})
    def test_wrong_team_join_abstains(self):
        t={'team_id':'H','starter_qb_id':'q'}
        h=[dict(team='A',position='QB',player_id='g')]
        with self.assertRaisesRegex(ValueError,'NO_TEAM'):parameterize(t,{'q':'QB'},{'q':{'g'}},h)
