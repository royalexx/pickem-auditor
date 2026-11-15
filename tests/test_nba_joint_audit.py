import copy
import json
from pathlib import Path
import unittest
import numpy as np
from v2.nba_joint import synthetic_fixture,simulate,audit,extract_forecast
from v2.nba_joint.common import sha
from v2.nba_joint.sources import canary
from v2.nba_joint.markets import original_markets
from v2.nba_joint.state import sample_state
from v2.evaluation import crps_ensemble,energy_score,variogram_score
from research.nba_joint_v01.evaluate import crps,energy,variogram,paired_ci
from research.nba_joint_v01.controls import independent_permutation


class MathAdapterTests(unittest.TestCase):
    def test_crps_reference(self):
        rng=np.random.default_rng(22)
        for n in [1,2,11,40]:
            x=rng.poisson(5,n).tolist()
            for y in [0,4,15]:self.assertAlmostEqual(crps(x,y),crps_ensemble(x,y),places=12)

    def test_energy_reference(self):
        x=np.random.default_rng(12).poisson(5,(20,3));y=[0,5,12]
        self.assertAlmostEqual(energy(x,y),energy_score([tuple(map(float,r)) for r in x],tuple(y)),places=12)

    def test_variogram_reference(self):
        x=np.random.default_rng(12).poisson(5,(20,3));y=[0,5,12]
        self.assertAlmostEqual(variogram(x,y),variogram_score([tuple(map(float,r)) for r in x],tuple(y)),places=12)

    def test_energy_one_sample_is_distance(self):self.assertEqual(energy([[0,0]],[3,4]),5.)

    def test_zero_tail_mc_is_not_zero_uncertainty(self):
        g,m=synthetic_fixture();o=simulate(g,m,n=10,seed=12);f=extract_forecast(o,0,'points',line=100000.)
        self.assertEqual(f['probabilities']['over'],0);self.assertGreater(f['monte_carlo']['over']['ci95'][1],0)

    def test_shuffle_preserves_marginals_but_rederives_combos(self):
        g,m=synthetic_fixture();o=simulate(g,m,n=20,seed=12);s=independent_permutation(o['stats'],g['game_id'],1)
        for k in ('points','rebounds','assists','threes'):np.testing.assert_array_equal(np.sort(s[k],axis=0),np.sort(o['stats'][k],axis=0))
        np.testing.assert_array_equal(s['pra'],s['points']+s['rebounds']+s['assists'])

    def test_date_bootstrap_paired_denominator(self):
        rows=[]
        for j in range(10):
            for model,score in [('a',2.),('b',1.)]:rows.append(dict(game_id=str(j),player_id='p',stat='x',date=str(j//2),model=model,crps=score))
        r=paired_ci(rows,'a','b');self.assertEqual(r['n'],10);self.assertEqual(r['clusters'],5);self.assertEqual(r['ci95'],[-1.,-1.])


class AdversarialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game,cls.model=synthetic_fixture();cls.base=simulate(cls.game,cls.model,n=10,seed=122)

    def broken(self,mutate,reason):
        o=copy.deepcopy(self.base);mutate(o)
        with self.assertRaisesRegex(ValueError,reason):audit(o)

    def test_team_total_corruption(self):self.broken(lambda o:o['minutes'].__setitem__((0,0),-1),'PLAYER_MINUTES')
    def test_count_negative(self):self.broken(lambda o:o['stats']['oreb'].__setitem__((0,0),-1),'COUNT_SUPPORT')
    def test_3pm_attempt_violation(self):self.broken(lambda o:o['stats']['three_pa'].__setitem__((0,0),-1),'COUNT_SUPPORT')
    def test_combo_corruption(self):self.broken(lambda o:o['stats']['pra'].__setitem__((0,0),-1),'COUNT_SUPPORT')
    def test_assist_self_credit(self):self.broken(lambda o:o['event_ledgers'][0]['assist_matrix'][0].__setitem__(0,1),'SELF_ASSIST')
    def test_rebound_excess(self):self.broken(lambda o:o['event_ledgers'][0]['rebounds'][0].__setitem__('available',0),'REBOUND')
    def test_duplicate_scenario(self):self.broken(lambda o:o['scenario_ids'].__setitem__(0,o['scenario_ids'][1]),'SCENARIO_IDENTITY')
    def test_scenario_denominator(self):self.broken(lambda o:o.__setitem__('attempted_scenarios',9),'SCENARIO_DENOMINATOR')
    def test_four_on_court(self):self.broken(lambda o:o['lineup_segments'][0][0][0]['player_indices'].pop(),'FIVE_ON_COURT')
    def test_ot_increment_corruption(self):self.broken(lambda o:o['state']['overtime'].__setitem__(0,99),'OVERTIME')

    def test_infeasible_exit_caps_fail_closed(self):
        g,m=synthetic_fixture()
        for p in g['players'][:9]:p['scenario_exit_cap']=1.
        with self.assertRaisesRegex(ValueError,'INFEASIBLE'):simulate(g,m,n=2,seed=1)

    def test_mixed_team_opponent_identity(self):
        g,m=synthetic_fixture();g['players'][0]['opponent_id']=g['players'][0]['team_id']
        with self.assertRaisesRegex(ValueError,'IDENTITY'):simulate(g,m,n=1,seed=1)

    def test_nan_rate(self):
        g,m=synthetic_fixture();g['players'][0]['rates']['points']=float('nan')
        with self.assertRaisesRegex(ValueError,'RATE'):simulate(g,m,n=1,seed=1)

    def test_negative_participation(self):
        g,m=synthetic_fixture();g['players'][0]['participation_probability']=-.2
        with self.assertRaisesRegex(ValueError,'PARTICIPATION'):simulate(g,m,n=1,seed=1)

    def test_no_synthetic_mode_upgrade(self):
        g,m=synthetic_fixture();g['mode']='prospective'
        with self.assertRaisesRegex(ValueError,'SOURCE'):simulate(g,m,n=1,seed=1)

    def test_ws1_actual_rejection_retained(self):
        p=next(Path('docs/nba_ws1/sample/snapshots').glob('*.json'));r=canary(p)
        self.assertEqual(r['status'],'BLOCKED-BY-DATA');self.assertEqual(r['accepted'],0)
        self.assertIn('ELIGIBILITY_UNCERTAIN',r['reason']);self.assertEqual(r['attempted'],len(r['rejected_players']))

    def test_invalid_line_boolean(self):
        with self.assertRaisesRegex(ValueError,'LINE'):extract_forecast(self.base,0,'points',line=True)

    def test_invalid_line_nan(self):
        with self.assertRaisesRegex(ValueError,'LINE'):extract_forecast(self.base,0,'points',line=float('nan'))

    def test_invalid_state_covariance(self):
        p=copy.deepcopy(self.model['state']);p['log_cov'][0][0]=-100
        with self.assertRaisesRegex(ValueError,'COVARIANCE'):sample_state(p,np.random.default_rng(4))

    def test_g0_has_one_environment(self):
        a=sample_state(self.model['state'],np.random.default_rng(1),kind='G0');b=sample_state(self.model['state'],np.random.default_rng(8),kind='G0')
        self.assertEqual(a,b);self.assertEqual(a['duration'],48.)

    def test_nan_overtime_probability(self):
        p=copy.deepcopy(self.model['state']);p['ot_probability']=float('nan')
        with self.assertRaisesRegex(ValueError,'OVERTIME'):sample_state(p,np.random.default_rng(1))

    def test_unknown_postgame_minute_field(self):
        g,m=synthetic_fixture();g['players'][0]['minute_features']['realized_minutes']=40
        with self.assertRaisesRegex(ValueError,'POSTGAME'):simulate(g,m,n=1,seed=1)

    def test_exact_zero_conversion_fails_closed(self):
        g,m=synthetic_fixture();m['events']['p2']=0
        with self.assertRaisesRegex(ValueError,'ZERO_CONVERSION'):simulate(g,m,n=1,seed=1)

    def test_terminal_free_throw_probability_invalid(self):
        g,m=synthetic_fixture();m['events']['terminal_ft_fraction']=2
        with self.assertRaisesRegex(ValueError,'PROBABILITY'):simulate(g,m,n=1,seed=1)

    def test_future_feature_relative_to_earlier_analysis_cutoff(self):
        g,m=synthetic_fixture();g['analysis_cutoff_at']='2026-11-12T00:00:00Z'
        with self.assertRaisesRegex(ValueError,'FUTURE_FEATURE'):simulate(g,m,n=1,seed=1)


class OriginalContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        g,m=synthetic_fixture();cls.out=simulate(g,m,n=5,seed=11)

    def context(self,contracts):
        from types import SimpleNamespace
        data={'game':{'game_id':self.out['game']['game_id']},'receipts':[{'receipt_id':'r','raw_sha256':'a'*64,'source':'fixture'}],
              'market_context':{'original_contracts':contracts}}
        return SimpleNamespace(require_usable=lambda:data)

    def quote(self):
        p=self.out['players'][0]
        return dict(contract_id='fixture-original',quote_id='q',game_id=self.out['game']['game_id'],player_id=p['player_id'],team_id=p['team_id'],stat='points',period='full_game',line=10.,quoted_at='2026-11-14T23:00:00Z',book='fixture',prices=None,payout_terms={'overtime_included':True,'dnp':'void'},receipt_id='r')

    def test_original_contract_exact_identity_retained(self):
        q=self.quote();r=original_markets(self.out,self.context([q]));f=r['accepted'][0]
        self.assertEqual(f['original_contract'],q);self.assertIsNone(f['original_contract']['prices']);self.assertFalse(f['certified'])

    def test_duplicate_contract_rejection_denominator(self):
        q=self.quote();r=original_markets(self.out,self.context([q,q]));self.assertEqual(r['attempted'],2);self.assertEqual(len(r['accepted']),1);self.assertEqual(r['rejected'][0]['reason'],'DUPLICATE_CONTRACT')

    def test_missing_terms_abstain(self):
        q=self.quote();q['payout_terms']=None;r=original_markets(self.out,self.context([q]));self.assertFalse(r['accepted']);self.assertEqual(r['rejected'][0]['reason'],'SETTLEMENT_TERMS_UNAVAILABLE')

    def test_late_quote_abstain(self):
        q=self.quote();q['quoted_at']='2026-11-17T00:00:00Z';r=original_markets(self.out,self.context([q]));self.assertEqual(r['rejected'][0]['reason'],'LATE_QUOTE')

    def test_wrong_team_contract(self):
        q=self.quote();q['team_id']='wrong';r=original_markets(self.out,self.context([q]));self.assertEqual(r['rejected'][0]['reason'],'CONTRACT_TEAM_IDENTITY')

    def test_period_market_not_reused(self):
        q=self.quote();q['period']='first_half';r=original_markets(self.out,self.context([q]));self.assertEqual(r['rejected'][0]['reason'],'STAT_POLICY_MISMATCH')

    def test_no_quotes_does_not_invent_line(self):
        r=original_markets(self.out,self.context([]));self.assertEqual(r['attempted'],0);self.assertFalse(r['accepted'])


if __name__=='__main__':unittest.main()
