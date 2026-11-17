"""P2 mathematical, G0 envelope, timeline and negative-control tests.
All fixtures are explicitly synthetic; none is real pregame source evidence.
"""
import copy
import hashlib
import math
import time
import unittest

from scipy.stats import betabinom, nbinom, poisson
from tests.nba_architecture.golden_v2 import pregame, model
from v2.nba_architecture.v2_contracts import seal, validate_distribution, VERSION
from v2.nba_architecture.families_v2 import validate_forecast
from v2.nba_s_family import SFError, fit, predict, conditional_pmf, predict_conditional, exact_triplet

SRC_HASH='1'*64
RAW_HASH='2'*64
GAME_TIMES=['2022-10-01T00:00:00Z','2022-10-03T00:00:00Z','2022-10-05T00:00:00Z']
REL_TIMES=['2022-10-02T00:00:00Z','2022-10-04T00:00:00Z','2022-10-06T00:00:00Z']
SRC_TIME='2022-10-07T00:00:00Z'
CUTOFF='2022-10-10T00:00:00Z'


def histories(stat='points'):
    ours=[11,14,18] if stat=='points' else [3,5,7] if stat=='threes' else [4,6,8]
    others=[9,11,13] if stat=='points' else [1,2,3] if stat=='threes' else [3,4,5]
    rows=[]
    for pl,values in [('espn:player:10',ours),('espn:player:11',others)]:
        for i,y in enumerate(values):
            rows.append(dict(game_id=f'espn:game:prior:{i}',player_id=pl,team_id='espn:team:1',
                     stat=stat,role='wing',game_start_at=GAME_TIMES[i],
                     outcome_available_at=REL_TIMES[i],source_receipt_sha256=SRC_HASH,
                     source_raw_sha256=RAW_HASH,count=y,minutes=30.0,
                     three_attempts=y+2 if stat=='threes' else None))
    return rows


def manifest():
    return {SRC_HASH:dict(raw_sha256=RAW_HASH,available_at=SRC_TIME,status='P1_VERIFIED',
        games={f'espn:game:prior:{i}':dict(overtime_periods=0,
            game_start_at=t, duration_receipt_sha256=SRC_HASH,
            players={'espn:player:10':'espn:team:1','espn:player:11':'espn:team:1'})
            for i,t in enumerate(GAME_TIMES)})}


def frozen_pregame_with_active():
    p=pregame('original_prospective')
    # A synthetic capture-shape evidence claim, never a real certification.
    t=p['players'][0]
    t['availability']='active_reported'
    t['availability_evidence']=dict(source_receipt_sha256=p['sources'][0]['receipt_sha256'],
                                    player_id=t['player_id'],game_id=p['game_id'],
                                    field='availability',value='active_reported')
    return seal({k:v for k,v in p.items() if k!='content_hash'})


def opportunity_fixture(p):
    gs=seal(dict(schema=VERSION,kind='game_state',game_id=p['game_id'],
                 source_snapshot_sha256=p['content_hash'],model=model('G',p),rng_seed=4,
                 scenarios=[dict(scenario_id='synthetic:o:s0',weight=1.,overtime_periods=0,
                                 pace_regulation=98.,possessions_home=99.,
                                 possessions_away=100.,score_state='home_leading')]))
    persons=[]
    for i,r in enumerate(p['players']):
        played=i%6<5
        persons.append(dict(player_id=r['player_id'],team_id=r['team_id'],
            participation_probability=1. if played else 0.,
            participation_evidence='independently_estimated',
            minutes_law=dict(family='discrete_minutes',conditioning='given_played',
                 units='minutes',parameters={'support':[{'minutes':48. if played else 0.,
                                                         'mass':1.}]})))
    op=seal(dict(schema=VERSION,kind='opportunity',game_id=p['game_id'],
            source_snapshot_sha256=p['content_hash'],game_state_sha256=gs['content_hash'],
            model=model('O',p),players=persons,
            scenarios=[dict(scenario_id='synthetic:o:s0',weight=1.,overtime_periods=0,
                players=[dict(player_id=r['player_id'],team_id=r['team_id'],
                              participation='PLAYED' if i%6<5 else 'DNP',
                              minutes=48. if i%6<5 else 0.)
                         for i,r in enumerate(p['players'])])]))
    return gs,op


class SFamilyTests(unittest.TestCase):
    def fitter(self,stat='points',family='S1',rows=None,**kwargs):
        return fit(histories(stat) if rows is None else rows,asof_cutoff_utc=CUTOFF,
                   source_manifest=manifest(),stat=stat,family=family,**kwargs)

    def test_s0_control_matches_poisson(self):
        f=self.fitter(family='S0')
        mass,tail,params=conditional_pmf(f,player_id='espn:player:10',role='wing',opportunity=0)
        self.assertAlmostEqual(params['game_mean'],(11+14+18)/3)
        self.assertAlmostEqual(mass[0],poisson.pmf(0,params['game_mean']),places=9)
        self.assertLess(tail,1e-8)

    def test_s1_gamma_poisson_math_moments(self):
        f=self.fitter(family='S1')
        mass,tail,p=conditional_pmf(f,player_id='espn:player:10',role='wing',opportunity=31.)
        mu=31*p['alpha']/p['beta']
        variance=mu+mu*mu/p['alpha']
        self.assertAlmostEqual(sum(i*z for i,z in enumerate(mass)),mu,places=7)
        self.assertAlmostEqual(sum((i-mu)**2*z for i,z in enumerate(mass)),variance,places=6)
        self.assertAlmostEqual(mass[0],nbinom.pmf(0,p['alpha'],p['beta']/(p['beta']+31)),places=10)
        self.assertLess(tail,1e-8)

    def test_s2_nb2_dispersion_and_tail(self):
        f=self.fitter(family='S2',hyperparameters={'dispersion':9.})
        m,tail,p=conditional_pmf(f,player_id='espn:player:10',role='wing',opportunity=27.)
        mu=27*p['rate_mean'];variance=mu+mu*mu/9.
        self.assertAlmostEqual(sum((i-mu)**2*z for i,z in enumerate(m)),variance,places=6)
        self.assertLess(tail,1e-8)

    def test_s3_beta_binomial_physical_cap(self):
        f=self.fitter(stat='threes',family='S3')
        m,tail,p=conditional_pmf(f,player_id='espn:player:10',role='wing',opportunity=8)
        self.assertEqual(len(m),9)
        self.assertAlmostEqual(sum(m),1.,places=12)
        for i,v in enumerate(m):
            self.assertAlmostEqual(v,betabinom.pmf(i,8,p['alpha'],p['beta']),places=10)
        self.assertEqual(tail,0.)
        self.assertEqual(conditional_pmf(f,player_id='espn:player:10',role='wing',opportunity=0)[0],[1.])
        with self.assertRaises(SFError):
            conditional_pmf(f,player_id='espn:player:10',role='wing',opportunity=8.5)

    def test_all_four_stats_integer_complete(self):
        for stat in ('points','rebounds','assists','threes'):
            for family in ('S0','S1','S2'):
                f=self.fitter(stat=stat,family=family)
                m,tail,_=conditional_pmf(f,player_id='espn:player:10',role='wing',opportunity=28)
                self.assertAlmostEqual(sum(m),1.,places=10)
                self.assertTrue(all(0<=z<=1 and math.isfinite(z) for z in m))
                self.assertGreater(m[0],0)
                self.assertLessEqual(tail,1e-8)

    def test_unchanged_g0_s_only_envelope(self):
        p=frozen_pregame_with_active()
        f=self.fitter(family='S0')
        result=predict(f,frozen_pregame=p,target_player_id=p['players'][0]['player_id'],role='wing')
        self.assertIsNone(result.abstain_reason,result.abstain_reason)
        self.assertTrue(validate_distribution(result.distribution,p))
        self.assertEqual(result.distribution['pipeline_mode'],'S_ONLY')
        self.assertIsNone(result.distribution['lineage']['O'])

    def test_unchanged_g0_s_o_conservation(self):
        p=pregame()
        g,o=opportunity_fixture(p)
        f=self.fitter()
        result=predict(f,frozen_pregame=p,target_player_id=p['players'][0]['player_id'],
                       role='wing',opportunity=o,game_state=g)
        self.assertIsNone(result.abstain_reason,result.abstain_reason)
        self.assertEqual(result.distribution['opportunity_output_sha256'],o['content_hash'])
        self.assertTrue(validate_forecast(result.distribution,p,g=g,o=o))
        self.assertEqual(result.distribution['pipeline_mode'],'S_O')

    def test_dnp_remains_distinct_and_no_target_actual_minutes(self):
        p=pregame();g,o=opportunity_fixture(p)
        f=self.fitter()
        o['players'][0]['participation_probability']=0.
        # Invalid O self-hash/participation discrepancy cannot be silently used.
        x=predict(f,frozen_pregame=p,target_player_id=p['players'][0]['player_id'],role='wing',
                  opportunity=o,game_state=g)
        self.assertIsNotNone(x.abstain_reason)
        self.assertIsNone(x.distribution)

    def test_future_source_and_game_rejected(self):
        rows=histories()
        rows[0]['outcome_available_at']='2022-10-30T00:00:00Z'
        with self.assertRaisesRegex(SFError,'FUTURE_OR_UNRELEASED_OUTCOME'):
            self.fitter(rows=rows)
        rows=histories();rows[0]['game_start_at']='2022-10-15T00:00:00Z'
        with self.assertRaises(SFError):self.fitter(rows=rows)
        rows=histories();rows[0]['source_raw_sha256']='f'*64
        with self.assertRaisesRegex(SFError,'RAW_SOURCE_SHA_MISMATCH'):
            self.fitter(rows=rows)

    def test_duplicate_identity_and_actual_target_input(self):
        rows=histories()+[histories()[0]]
        with self.assertRaisesRegex(SFError,'DUPLICATE_GAME_PLAYER_STAT'):
            self.fitter(rows=rows)
        rows=histories();rows[0]['target_actual_minutes']=31
        with self.assertRaisesRegex(SFError,'UNSAFE_OR_INCOMPLETE_HISTORY_ROW'):
            self.fitter(rows=rows)
        rows=histories();rows[0]['count']=-1
        with self.assertRaises(SFError):self.fitter(rows=rows)

    def test_reproducible_content_bytes_and_seed(self):
        first=self.fitter(rows=histories(),family='S0')
        second=self.fitter(rows=list(reversed(histories())),family='S0')
        self.assertEqual(first.payload,second.payload)
        self.assertEqual(first.artifact_sha256,second.artifact_sha256)
        p=frozen_pregame_with_active()
        a=predict(first,frozen_pregame=p,target_player_id=p['players'][0]['player_id'],role='wing',seed=42)
        b=predict(first,frozen_pregame=p,target_player_id=p['players'][0]['player_id'],role='wing',seed=42)
        self.assertEqual(a.distribution,b.distribution)
        c=predict(first,frozen_pregame=p,target_player_id=p['players'][0]['player_id'],role='wing',seed=13)
        self.assertNotEqual(a.distribution['content_hash'],c.distribution['content_hash'])
        self.assertEqual(a.distribution['pmf'],c.distribution['pmf'])

    def test_training_target_game_cross_player_leakage(self):
        f=self.fitter()
        p=pregame();fdata=f.data
        for row in fdata['training_rows']:
            row['game_id']=p['game_id']
        from v2.nba_s_family.model import FittedS,canonical
        corrupted=FittedS(canonical(fdata))
        x=predict(corrupted,frozen_pregame=p,target_player_id=p['players'][0]['player_id'],
                  role='wing')
        self.assertEqual(x.abstain_reason,'TARGET_GAME_USED_IN_TRAINING')

    def test_missing_opportunity_and_unknown_participation_abstain(self):
        f=self.fitter();p=pregame()
        x=predict(f,frozen_pregame=p,target_player_id=p['players'][0]['player_id'],role='wing')
        self.assertEqual(x.abstain_reason,'PREGAME_G_O_OPPORTUNITY_REQUIRED')
        f0=self.fitter(family='S0')
        x=predict(f0,frozen_pregame=p,target_player_id=p['players'][0]['player_id'],role='wing')
        self.assertEqual(x.abstain_reason,'PARTICIPATION_UNRESOLVED_S_ONLY')

    def test_threshold_triplet_push(self):
        mass=[.2,.3,.5]
        p=exact_triplet(mass,1)
        # Threshold contract returns a tuple or dict depending on G0 implementation.
        self.assertAlmostEqual(sum(p.values()) if isinstance(p,dict) else sum(p),1.)
        q=exact_triplet(mass,1.5)
        self.assertAlmostEqual(sum(q.values()) if isinstance(q,dict) else sum(q),1.)

    def test_independent_gamma_poisson_probability_recurrence(self):
        f=self.fitter(family='S1')
        mass,_,p=conditional_pmf(f,player_id='espn:player:10',role='wing',opportunity=20.)
        a,b=p['alpha'],p['beta']
        p0=(b/(b+20.))**a
        self.assertAlmostEqual(mass[0],p0,places=10)
        for k in range(5):
            recurrence=mass[k]*(k+a)/(k+1)*20./(b+20.)
            self.assertAlmostEqual(mass[k+1],recurrence,places=10)

    def test_verified_source_manifest_missing_naive_or_late(self):
        for bad in [dict(raw_sha256=RAW_HASH,available_at='2022-10-11T00:00:00Z',status='P1_VERIFIED'),
                    dict(raw_sha256=RAW_HASH,available_at='2022-10-07T00:00:00',status='P1_VERIFIED'),
                    dict(raw_sha256=RAW_HASH,available_at=SRC_TIME,status='UNVERIFIED')]:
            with self.subTest(bad=bad):
                with self.assertRaises(SFError):
                    fit(histories(),asof_cutoff_utc=CUTOFF,source_manifest={SRC_HASH:bad},stat='points')

    def test_impossible_three_makes_and_bad_attempts(self):
        rows=histories('threes');rows[0]['three_attempts']=0
        with self.assertRaisesRegex(SFError,'THREES_EXCEED_ATTEMPTS'):
            self.fitter(stat='threes',family='S3',rows=rows)
        p=self.fitter(stat='threes',family='S3')
        r=predict_conditional(p,player_id='espn:player:10',role='wing',projected_exposure=4097)
        self.assertEqual(r.abstain_reason,'PROJECTED_3PA_OUT_OF_RANGE')

    def test_zero_minutes_count_degenerate(self):
        for family in ('S1','S2'):
            f=self.fitter(family=family)
            m,tail,_=conditional_pmf(f,player_id='espn:player:10',role='wing',opportunity=0.)
            self.assertEqual(m,[1.]);self.assertEqual(tail,0.)

    def test_s_only_rejects_future_model_training_and_game_mutation(self):
        p=frozen_pregame_with_active();f=self.fitter(family='S0')
        mutated=copy.deepcopy(p)
        if mutated['features']:
            mutated['features'][0]['name']='actual_minutes'
        else:
            mutated['features'].append({'name':'actual_minutes'})
        r=predict(f,frozen_pregame=mutated,target_player_id=p['players'][0]['player_id'],role='wing')
        self.assertIsNotNone(r.abstain_reason)
        from v2.nba_s_family.model import FittedS,canonical
        modified=f.data;modified['training_cutoff_at']='2026-11-17T00:00:00Z'
        bad=FittedS(canonical(modified))
        r=predict(bad,frozen_pregame=p,target_player_id=p['players'][0]['player_id'],role='wing')
        self.assertEqual(r.abstain_reason,'MODEL_FIT_AFTER_FREEZE')

    def test_unchanged_g0_shas_and_supplementary_lineage(self):
        p=pregame();g,o=opportunity_fixture(p);f=self.fitter()
        a=predict(f,frozen_pregame=p,target_player_id=p['players'][0]['player_id'],
                  role='wing',opportunity=o,game_state=g)
        self.assertEqual(a.distribution['lineage']['S']['artifact_sha256'],f.artifact_sha256)
        self.assertEqual(a.distribution['lineage']['O'],o['model'])
        self.assertEqual(a.distribution['lineage']['G'],g['model'])
        self.assertIsNone(a.distribution['lineage']['J'])
        self.assertAlmostEqual(sum(x['mass'] for x in a.distribution['pmf']),1.,places=12)

    def test_s3_predict_requires_predeclared_attempt_scenarios(self):
        f=self.fitter(stat='threes',family='S3');p=pregame()
        r=predict(f,frozen_pregame=p,target_player_id=p['players'][0]['player_id'],role='wing')
        self.assertEqual(r.abstain_reason,'S3_REQUIRES_PREDECLARED_3PA_J_OPPORTUNITIES')

    def test_runtime_receipt_nonbinding(self):
        start=time.perf_counter();f=self.fitter()
        for _ in range(16):
            conditional_pmf(f,player_id='espn:player:10',role='wing',opportunity=30.)
        seconds=time.perf_counter()-start
        self.assertTrue(math.isfinite(seconds))
        self.assertLess(seconds,30.)  # safety bound only, not performance claim


if __name__=='__main__':
    unittest.main()
