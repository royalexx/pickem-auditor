"""WS2 temporal, conditioning and adversarial team conservation tests."""
import copy
import importlib.util
from dataclasses import replace
import tempfile
from pathlib import Path
import unittest
import numpy as np
from scipy.integrate import quad
from v2.nba_opportunity import (FEATURES, MinuteLaw, MinutesModel,
    PregameOpportunityInput, capped_allocation, causal_features, freeze_shadow,
    lineup_segments, sample_team)


REPLAY_DEPS = all(importlib.util.find_spec(name) is not None for name in ('pandas','sklearn'))
REPLAY_DEPS_REASON = 'Optional WS2 replay checks require pandas/scikit-learn; full checks run in pinned research environment and Deepnote'

def fixture_model():
    return MinutesModel({'ALL':{'mean':24.,'variance':64.}},
        {m:{r:64. for r in ('low','mid','high')} for m in ('M0','M1','M2')},
        [0.]*len(FEATURES),[1.]*len(FEATURES),[1.]+[0.]*(len(FEATURES)-1),
        0.,.06,.15,'2024-04-15T00:00:00Z','a'*64,'fixture')


def fixture_input(player='1',team='A',p=1.,status='confirmed_active'):
    features=dict(zip(FEATURES,[24,24,24,8,0,2,0,0,0,1,10,0,0]))
    return PregameOpportunityInput('g',player,team,'B' if team=='A' else 'A',
        '2026-11-20T00:00:00Z','2026-11-19T20:00:00Z','2026-11-19T19:59:00Z',
        '2026-11-19T19:58:00Z','2026-11-19T19:58:30Z','2024-04-15T00:00:00Z',
        'b'*64,features,'G',status,p,(p,p) if p is not None else None,True,
        {'product':'fixture','DNP':'void','partial_game':'eligible'})


class OpportunityContractTests(unittest.TestCase):
    def test_states_and_unknown_not_absent(self):
        model=fixture_model()
        for status in ('confirmed_active','probable_participant','questionable_participant','unverified'):
            f=model.forecast('M0',fixture_input(p=None,status=status),17)
            self.assertIsNone(f['participation_probability'])
            self.assertGreater(f['expected_minutes_given_played'],0)
            self.assertIn('UNCONDITIONAL_OPPORTUNITY_UNAVAILABLE',f['abstention_reasons'])
        f=model.forecast('M0',fixture_input(p=None,status='confirmed_inactive'),17)
        self.assertEqual(f['participation_probability'],0)
        self.assertIn('INACTIVE_OR_INELIGIBLE',f['abstention_reasons'])

    def test_active_roster_does_not_imply_participates(self):
        f=fixture_model().forecast('M0',fixture_input(p=.65),1)
        self.assertEqual(f['participation_probability'],.65)
        self.assertEqual(f['product_eligibility']['DNP'],'void')

    def test_temporal_corruption(self):
        item=fixture_input()
        for key,value in [('source_available_at','2026-11-21T00:00:00Z'),
                          ('source_ingested_at','2026-11-21T00:00:00Z'),
                          ('training_cutoff_at','2026-11-21T00:00:00Z'),
                          ('forecast_at','2026-11-20T00:00:00Z'),
                          ('input_freeze_at','2026-11-19T19:59:00')]:
            with self.subTest(key=key),self.assertRaises(ValueError):replace(item,**{key:value}).validate()
        with self.assertRaises(ValueError):
            fixture_model().forecast('M0',replace(item,training_cutoff_at='2023-01-01T00:00:00Z'),1)

    def test_invalid_probabilities_and_identity(self):
        item=fixture_input()
        for change in ({'participation_probability':float('nan')},{'participation_probability':-1},
                       {'participation_probability_interval':(.9,.8)},
                       {'participation_status':'confirmed_inactive'},
                       {'active_roster_eligible':False},{'team_id':'B'},
                       {'source_sha256':'x'*64}):
            with self.subTest(change=change),self.assertRaises(ValueError):replace(item,**change).validate()

    def test_no_postgame_feature_admitted(self):
        item=fixture_input();f={**item.features,'final_margin':20}
        with self.assertRaises(ValueError):replace(item,features=f).validate()

    def test_future_and_current_outcomes_cannot_change_features(self):
        h=[{'game_date':f'2026-11-{i:02d}','game_id':str(i),'team':'A','workload':20+i} for i in range(1,9)]
        a=causal_features(h,game_date='2026-11-06',team='A',home=True)
        for r in h[5:]:r['workload']=100000
        b=causal_features(h,game_date='2026-11-06',team='A',home=True)
        self.assertEqual(a,b)

    def test_dnp_not_conditional_observation(self):
        h=[{'game_date':f'2026-11-{i:02d}','game_id':str(i),'team':'A','workload':0 if i==1 else 30} for i in range(1,6)]
        with self.assertRaisesRegex(ValueError,'DNP_NOT'):causal_features(h,game_date='2026-11-06',team='A',home=True)

    def test_immutable_and_deterministic_forecast(self):
        m=fixture_model();f=m.forecast('M1',fixture_input(),3)
        self.assertEqual(f,m.forecast('M1',fixture_input(),3))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'shadow.jsonl';digest=freeze_shadow(path,[f])
            self.assertEqual(len(digest),64)
            with self.assertRaises(FileExistsError):freeze_shadow(path,[f])
            modelpath=Path(tmp)/'model.json';m.save(modelpath)
            self.assertEqual(f,MinutesModel.load(modelpath).forecast('M1',fixture_input(),3))


class MinuteDistributionTests(unittest.TestCase):
    def test_support_moments_quantiles_and_ot_tail(self):
        law=MinuteLaw(31,49,.08,.2)
        x=np.linspace(0,120,2401);cdf=law.cdf(x)
        self.assertEqual(float(law.cdf(-1)),0)
        self.assertTrue(np.all(np.diff(cdf)>=-1e-12))
        self.assertGreater(float(law.cdf(80)),.999)
        summary=law.summary()
        self.assertAlmostEqual(summary['expected_minutes_given_played'],31,places=7)
        self.assertAlmostEqual(summary['variance_minutes_given_played'],49,places=6)
        self.assertLess(summary['numerical_omitted_ot_mass'],1e-12)
        qs=list(summary['quantiles_given_played'].values());self.assertEqual(qs,sorted(qs))
        self.assertGreater(1-float(law.cdf(48)),0)
        self.assertTrue(any(l>65 for l,w in law.ot_components()))

    @unittest.skipUnless(REPLAY_DEPS, REPLAY_DEPS_REASON)
    def test_crps_integration_independent_reference(self):
        # Test numerical replay score against quadrature with discontinuity split.
        from research.nba_ws2.run_experiment import score
        import pandas as pd
        row={**fixture_input().features,'position':'G','workload':29.}
        m=fixture_model();s=score(m,'M0',pd.DataFrame([row])).iloc[0]
        law=m.law('M0',fixture_input().features,'G')
        reference=quad(lambda x:float(law.cdf(x))**2,0,29)[0]+quad(lambda x:(1-float(law.cdf(x)))**2,29,140)[0]
        self.assertAlmostEqual(s.crps,reference,delta=.002)

    def test_expected_minutes_can_exceed_regulation_with_ot(self):
        law=MinuteLaw(48.1,4.,.1,.2)
        self.assertAlmostEqual(law.summary()['expected_minutes_given_played'],48.1,places=6)
        with self.assertRaises(ValueError):MinuteLaw(50.,4.,.1,.2)

    def test_invalid_law_parameters(self):
        for args in [(0,49,.1,.2),(30,-1,.1,.2),(30,49,1,.2),(30,49,.1,0)]:
            with self.assertRaises(ValueError):MinuteLaw(*args)


class TeamConservationTests(unittest.TestCase):
    def forecasts(self,n=10,team='A',p=1.):
        return [fixture_model().forecast('M0',fixture_input(str(i),team,p),31) for i in range(n)]

    def test_randomized_projection_and_five_on_court(self):
        rng=np.random.default_rng(29)
        for _ in range(300):
            length=48+5*int(rng.integers(0,10));n=int(rng.integers(5,19))
            desired=rng.exponential(25,n);cap=np.full(n,length,dtype=float)
            if n>5:cap[rng.integers(n)]=rng.random()*length  # early exit limit
            if cap.sum()<5*length:continue
            m=capped_allocation(desired,cap,5*length)
            self.assertAlmostEqual(m.sum(),5*length,places=7)
            self.assertTrue(np.all(m<=cap+1e-8));self.assertTrue(np.all(m>=0))
            segments=lineup_segments(m,length)
            self.assertTrue(all(len(s['player_indices'])==5 for s in segments))
            reconstructed=np.zeros(n)
            for s in segments:reconstructed[s['player_indices']]+=s['end']-s['start']
            np.testing.assert_allclose(m,reconstructed,atol=1e-7)

    def test_overtime_shared_by_both_teams_and_reproducible(self):
        a=sample_team(self.forecasts(),seed=4,n=100,ot_probability=.5,ot_continuation=.3)
        b=sample_team(self.forecasts(team='B'),seed=4,n=100,ot_probability=.5,ot_continuation=.3)
        self.assertEqual([s['overtime_periods'] for s in a],[s['overtime_periods'] for s in b])
        self.assertEqual(a,sample_team(self.forecasts(),seed=4,n=100,ot_probability=.5,ot_continuation=.3))
        for s in a:self.assertAlmostEqual(s['team_total'],240+25*s['overtime_periods'],places=7)

    def test_underfilled_roster_retained_not_forced(self):
        s=sample_team(self.forecasts(4),seed=4,n=10,ot_probability=.1,ot_continuation=.2)
        self.assertEqual(len(s),10)
        self.assertTrue(all(not x['valid'] and x['reason']=='FEWER_THAN_FIVE_PARTICIPANTS' for x in s))
        uncertain=self.forecasts(10,p=.1)
        s=sample_team(uncertain,seed=4,n=50,ot_probability=.1,ot_continuation=.2)
        self.assertTrue(any(not x['valid'] for x in s))

    def test_inactive_unverified_duplicates_mixed_teams(self):
        f=self.forecasts();f[0]=fixture_model().forecast('M0',fixture_input('0',p=None,status='confirmed_inactive'),1)
        scenarios=sample_team(f,seed=1,n=10,ot_probability=.1,ot_continuation=.2)
        self.assertTrue(all(s['minutes'][0]==0 for s in scenarios))
        for bad in ([*f,f[0]], [*f[:-1],self.forecasts(team='B')[-1]]):
            with self.assertRaises(ValueError):sample_team(bad,seed=1,ot_probability=.1,ot_continuation=.2)
        f[1]['participation_probability']=None
        with self.assertRaises(ValueError):sample_team(f,seed=1,ot_probability=.1,ot_continuation=.2)

    def test_raw_sampler_payload_probability_validation(self):
        for p in (float('nan'), -1., 2.):
            f=self.forecasts();f[0]['participation_probability']=p
            with self.assertRaises(ValueError):sample_team(f,seed=1,ot_probability=.1,ot_continuation=.2)

    def test_unusual_independent_draws_still_respect_game_length(self):
        scenarios=sample_team(self.forecasts(),seed=41,n=100,ot_probability=.2,
                              ot_continuation=.2,unusual_rotation_probability=1.)
        for s in scenarios:
            self.assertTrue(all(0 <= m <= s['game_length'] for m in s['independent_minutes']))

    def test_latent_early_exit_caps_are_honored_or_retained_as_invalid(self):
        scenarios=sample_team(self.forecasts(),seed=41,n=2,ot_probability=0,
            ot_continuation=.2,scenario_player_caps={0:{'0':3.},1:{str(i):10. for i in range(10)}})
        self.assertTrue(scenarios[0]['valid'])
        self.assertLessEqual(scenarios[0]['minutes'][0],3.)
        self.assertFalse(scenarios[1]['valid'])
        self.assertEqual(scenarios[1]['reason'],'INFEASIBLE_TEAM_ROTATION')

    def test_selected_participants_keep_positive_exposure(self):
        scenarios=sample_team(self.forecasts(),seed=57,n=100,ot_probability=0,
                             ot_continuation=.2,unusual_rotation_probability=1.)
        self.assertTrue(all(all(m>0 for m in s['minutes']) for s in scenarios))
        invalid=sample_team(self.forecasts(),seed=57,n=1,ot_probability=0,
                           ot_continuation=.2,scenario_player_caps={0:{'0':0.}})[0]
        self.assertFalse(invalid['valid'])
        self.assertEqual(invalid['reason'],'PARTICIPANT_HAS_ZERO_EXPOSURE_CAP')

    def test_impossible_early_exit_caps_rejected(self):
        with self.assertRaises(ValueError):capped_allocation([20]*5,[40]*5,240)
        with self.assertRaises(ValueError):capped_allocation([np.nan]*6,[48]*6,240)
        with self.assertRaises(ValueError):lineup_segments([40]*6,53)

    def test_exact_five_all_play_full_game(self):
        s=sample_team(self.forecasts(5),seed=1,ot_probability=0,ot_continuation=.2)[0]
        np.testing.assert_allclose(s['minutes'],[48]*5)


@unittest.skipUnless(REPLAY_DEPS, REPLAY_DEPS_REASON)
class ReplayAdapterTests(unittest.TestCase):
    def test_positions_use_prior_appearance_only(self):
        from research.nba_ws2.run_experiment import build_table
        rows=[{'game_id':str(i),'game_date':f'2024-01-{i:02d}',
            'player_id':'p','team':'A','home':True,'season':'2024',
            'workload':20.,'position':'G' if i<6 else 'C'} for i in range(1,7)]
        table,rejects=build_table(rows)
        self.assertEqual(len(rejects),5)
        self.assertEqual(table.iloc[0]['position'],'G')
        self.assertEqual(table.iloc[0]['observed_position'],'C')

    def test_exhibition_rows_excluded_before_histories(self):
        from research.nba_ws2.run_experiment import franchise_population
        rows=[{'team':'BOS','opponent':'NY'}, {'team':'EAST','opponent':'WEST'},
              {'team':'BOS','opponent':'CHK'}]
        kept,rejected=franchise_population(rows)
        self.assertEqual(kept,[rows[0]])
        self.assertEqual(len(rejected),2)
        self.assertTrue(all(r['reason']=='NON_FRANCHISE_COMPETITION_IDENTITY' for r in rejected))

    def test_duplicate_population_never_silently_deduplicated(self):
        import gzip,json
        from research.nba_ws2.run_experiment import load_population
        row={'game_id':'g','player_id':'p','sport':'NBA','stat':'points',
            'workload_unit':'minutes','workload':20,'source_sha256':'a'*64,
            'source_url':'https://example.com','game_date':'2024-01-01'}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'2024.jsonl.gz'
            with gzip.open(path,'wt') as handle:handle.write(json.dumps(row)+'\n'+json.dumps(row)+'\n')
            with self.assertRaisesRegex(ValueError,'DUPLICATE'):load_population(tmp)

if __name__=='__main__':unittest.main()
