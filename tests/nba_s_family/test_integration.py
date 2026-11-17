"""Synthetic engineering controls; no historical accuracy claims."""
import copy
import math
import unittest
from unittest.mock import patch
import numpy as np
from tests.nba_s_family.test_statistical import (
    histories, manifest, CUTOFF, SRC_HASH, pregame, opportunity_fixture)
from v2.nba_s_family.model import fit, SFError, _pmf, canonical, digest
from v2.nba_s_family.integration import joint_conditional, full_count_law

class IntegrationTests(unittest.TestCase):
    def test_official_duration_caps_zero_through_three_and_extension(self):
        for ot in range(5):
            for minutes,valid in [(48+5*ot,True),(48+5*ot+.01,False)]:
                with self.subTest(ot=ot,minutes=minutes):
                    rows=histories();rows[0]['minutes']=minutes
                    m=manifest();m[SRC_HASH]['games'][rows[0]['game_id']]['overtime_periods']=ot
                    if valid:
                        f=fit(rows,asof_cutoff_utc=CUTOFF,source_manifest=m,stat='points')
                        self.assertEqual(f.data['training_rows'][0]['minutes'],minutes)
                    else:
                        with self.assertRaisesRegex(SFError,'HISTORICAL_EXPOSURE_PHYSICS'):
                            fit(rows,asof_cutoff_utc=CUTOFF,source_manifest=m,stat='points')

    def test_p6_56_minutes_requires_two_ot_witness(self):
        rows=histories();rows[0]['minutes']=56
        m=manifest();m[SRC_HASH]['games'][rows[0]['game_id']]['overtime_periods']=2
        fit(rows,asof_cutoff_utc=CUTOFF,source_manifest=m,stat='points')
        del m[SRC_HASH]['games'][rows[0]['game_id']]
        with self.assertRaisesRegex(SFError,'HISTORICAL_DURATION_UNRESOLVED'):
            fit(rows,asof_cutoff_utc=CUTOFF,source_manifest=m,stat='points')

    def test_unknown_invalid_duration_evidence(self):
        for value in [None,-1,True,1.5,'2']:
            m=manifest();m[SRC_HASH]['games']['espn:game:prior:0']['overtime_periods']=value
            with self.subTest(value=value), self.assertRaisesRegex(SFError,'DURATION_UNRESOLVED'):
                fit(histories(),asof_cutoff_utc=CUTOFF,source_manifest=m,stat='points')

    def test_duration_late_receipt_and_wrong_identity(self):
        for mutation,reason in [('late','DURATION_SOURCE_LATE'),('player','HISTORICAL_PLAYER_TEAM_MISMATCH'),('team','HISTORICAL_PLAYER_TEAM_MISMATCH')]:
            m=manifest();rows=histories()
            if mutation=='late':
                m['3'*64]=dict(raw_sha256='4'*64,available_at='2022-10-11T00:00:00Z',status='P1_VERIFIED')
                m[SRC_HASH]['games'][rows[0]['game_id']]['duration_receipt_sha256']='3'*64
            elif mutation=='player': rows[0]['player_id']='wrong'
            else: rows[0]['team_id']='wrong'
            with self.subTest(mutation=mutation),self.assertRaisesRegex(SFError,reason):
                fit(rows,asof_cutoff_utc=CUTOFF,source_manifest=m,stat='points')

    def test_negative_and_non_normalized_pmf_rejected(self):
        for masses in [np.array([1.1,-.1]),np.array([.2,.3]),np.array([float('nan')])]:
            with patch('v2.nba_s_family.model.betabinom.pmf',return_value=masses):
                with self.assertRaisesRegex(SFError,'PMF_NUMERICAL_INTEGRITY'):
                    _pmf('S3',dict(alpha=2,beta=3),1)

    def test_joint_identity_cutoff_and_deterministic_scenario_hash(self):
        p=pregame();g,o=opportunity_fixture(p)
        f=fit(histories(),asof_cutoff_utc=CUTOFF,source_manifest=manifest(),stat='points')
        args=dict(pregame=p,game_state=g,opportunity=o,scenario_id=o['scenarios'][0]['scenario_id'],
                  player_id=p['players'][0]['player_id'],team_id=p['players'][0]['team_id'],role='wing')
        a=joint_conditional(f,**args);b=joint_conditional(f,**args)
        self.assertEqual(a,b)
        self.assertEqual(a['scenario_sha256'],digest(canonical(o['scenarios'][0])))
        with self.assertRaisesRegex(SFError,'TARGET_PLAYER_TEAM_MISMATCH'):
            joint_conditional(f,**{**args,'team_id':'wrong'})

    def test_independent_full_count_math(self):
        for family in ['S0','S1','S2','S3']:
            stat='threes' if family=='S3' else 'points'
            f=fit(histories(stat),asof_cutoff_utc=CUTOFF,source_manifest=manifest(),stat=stat,family=family)
            exposure=8 if family=='S3' else 20
            law=full_count_law(f,player_id='espn:player:10',role='wing',projected_exposure=exposure)
            _,_,params=__import__('v2.nba_s_family.model',fromlist=['conditional_pmf']).conditional_pmf(f,player_id='espn:player:10',role='wing',opportunity=exposure)
            if family=='S0':
                mu=params['game_mean'];variance=mu;p0=math.exp(-mu)
            elif family=='S3':
                a,b=params['alpha'],params['beta'];mu=exposure*a/(a+b)
                variance=exposure*a*b*(a+b+exposure)/((a+b)**2*(a+b+1))
                p0=math.prod((b+i)/(a+b+i) for i in range(exposure))
            else:
                a=params['alpha'] if family=='S1' else params['dispersion']
                mu=exposure*params['rate_mean'];variance=mu+mu*mu/a
                p0=math.exp(a*math.log(a/(a+mu)))
            self.assertAlmostEqual(law.mean(),mu,places=10)
            self.assertAlmostEqual(law.var(),variance,places=9)
            self.assertAlmostEqual(law.pmf(0),p0,places=12)
            self.assertAlmostEqual(math.fsum(law.pmf(k) for k in range(100))+law.sf(99),1,places=12)
            self.assertEqual(law.pmf(-1),0)
            if family!='S3': self.assertGreater(law.sf(100),0)

if __name__=='__main__': unittest.main()

class JointConversionTests(unittest.TestCase):
    def test_s3_attempt_evidence_is_scenario_bound(self):
        from v2.nba_architecture.v2_contracts import seal
        from v2.nba_s_family.integration import VERSION
        p=pregame();g,o=opportunity_fixture(p)
        f=fit(histories('threes'),asof_cutoff_utc=CUTOFF,source_manifest=manifest(),stat='threes',family='S3')
        args=dict(pregame=p,game_state=g,opportunity=o,scenario_id=o['scenarios'][0]['scenario_id'],player_id='espn:player:10',team_id='espn:team:1',role='wing')
        with self.assertRaisesRegex(SFError,'PROJECTED_ATTEMPT_EVIDENCE_REQUIRED'):
            joint_conditional(f,**args)
        request=dict(schema=VERSION,basis='projected_shared_shot_allocation',source_snapshot_sha256=p['content_hash'],opportunity_sha256=o['content_hash'],scenario_id=args['scenario_id'],player_id=args['player_id'],team_id=args['team_id'],three_pa=8)
        result=joint_conditional(f,**args,projected_attempts=seal(request))
        self.assertEqual(len(result['pmf']),9)
        for key,value in [('basis','target_realized_attempts'),('player_id','wrong'),('three_pa',2.5)]:
            with self.subTest(key=key),self.assertRaises(SFError):
                joint_conditional(f,**args,projected_attempts=seal({**request,key:value}))
