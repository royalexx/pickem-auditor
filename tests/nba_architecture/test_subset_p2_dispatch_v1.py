from dataclasses import replace
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tests.nba_architecture.test_subset_p3_v1 import CAP,COHORT,HISTORY,MODEL,PACKET
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.subset_p2_dispatch_v1 import (ModelContract,CONDITIONING,
    structural_dispatch_control,run_dispatch,read_dispatch,ADMITTED_MODELS)
from v2.nba_s_family import model as native

UP=PACKET/'p5/actual_full_pipeline'
FIXTURE=Path(__file__).resolve().parents[2]/'research/nba_p4_latest/fixtures_v2'


def real_inputs(model_dir=None):
    raw=(UP/'p3.json').read_bytes()
    return dict(source_raw=(UP/'p1.json').read_bytes(),p3_raw=raw,capture_dir=CAP,
        cohort=COHORT,history_dir=HISTORY,model_path=MODEL,forecast_at=json.loads(raw)['forecast_at'],model_dir=model_dir)


def control_inputs():
    fixture=json.loads((FIXTURE/'inputs.json').read_bytes());p=fixture['pregame']
    a=(FIXTURE/'points.json').read_bytes();m=canonical(fixture['source_manifest']);r=(FIXTURE/'raw_sources.json').read_bytes()
    c=ModelContract(digest(a),digest(m),digest(r),digest(Path(native.__file__).read_bytes()),
        digest(canonical(p)),json.loads(a)['training_cutoff_at'],'points','S1',
        (('F','high','rotation'),),tuple((row['player_id'],row['team_id']) for row in p['players']),'SYNTHETIC_ENGINEERING_ONLY')
    b=dict(game_id=p['game_id'],player_id='espn:player:10',team_id='espn:team:1',opponent_id='espn:team:2',
        statistic='points',cohort_sha256=c.cohort_sha256,conditioning=CONDITIONING,
        participation_probability=None,legal_eligibility=None,p3_variant='M0',p3_forecast_id='synthetic:native:M0',
        projected_exposure=30.,exposure_units='minutes',role_features=dict(position='F',historical_workload_state='high'),
        forecast_at=p['forecast_at'],input_freeze_at=p['input_freeze_at'],event_start_at=p['event_start_at'])
    return b,c,a,m,r


class DispatchTests(unittest.TestCase):
    def test_real_source_to_fixed_m0_exposure_all_144_attempts(self):
        kwargs=real_inputs();x=run_dispatch(**kwargs)
        self.assertEqual((x['candidate_denominator'],x['attempt_denominator'],x['exposure_bound_rows'],x['forecasted_rows'],x['abstained_rows']),(36,144,48,0,144))
        self.assertEqual(sum(r['reason']=='P1_SOURCE_ABSTENTION' for r in x['rows']),44)
        self.assertEqual(sum(str(r['reason']).startswith('P3_MINUTES_UNAVAILABLE:') for r in x['rows']),52)
        self.assertEqual(sum(r['reason']=='SAVED_S_ARTIFACT_UNAVAILABLE' for r in x['rows']),48)
        self.assertEqual(x['model_candidate_denominator'],4);self.assertFalse(ADMITTED_MODELS)
        for row in x['rows']:
            self.assertIsNone(row['trained_role']);self.assertIsNone(row['participation_probability'])
            if row['binding']:self.assertEqual(row['binding']['p3_variant'],'M0')
        self.assertEqual(read_dispatch(canonical(x),**kwargs),x)

    def test_frozen_synthetic_native_numerical_positive_no_new_fit(self):
        args=control_inputs();x=structural_dispatch_control(*args);self.assertFalse(x['admitted'])
        f=x['result'];self.assertTrue(f['actual_native_model_executed']);self.assertFalse(f['minute_uncertainty_integrated'])
        masses=[r['mass'] for r in f['parameters']['support']];self.assertAlmostEqual(sum(masses),1.)
        for line in (10.,10.5):
            triplet=native.exact_triplet(masses,line);self.assertAlmostEqual(sum(triplet.values()),1.)
        self.assertEqual(f['trained_role'],'rotation');self.assertLess(f['uncertainty']['tail_mass_upper_bound'],1e-8)

    def test_wrong_target_exposure_clock_variant_and_q_reject(self):
        b,c,a,m,r=control_inputs()
        for key,value in [('team_id','wrong'),('projected_exposure',-1),('exposure_units','three_attempts'),
            ('p3_variant','M2'),('participation_probability',1.),('forecast_at',b['event_start_at']),('statistic','rebounds')]:
            v=copy.deepcopy(b);v[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):structural_dispatch_control(v,c,a,m,r)
        with self.assertRaises(ValueError):structural_dispatch_control(b,replace(c,family='S3'),a,m,r)

    def test_model_manifest_raw_bytes_code_and_roles_reject(self):
        b,c,a,m,r=control_inputs()
        for args in [(b,c,a+b' ',m,r),(b,c,a,m+b' ',r),(b,c,a,m,r+b' '),
            (b,replace(c,native_code_sha256='0'*64),a,m,r),
            (b,replace(c,role_map=()),a,m,r),
            (b,replace(c,role_map=(('F','high','rotation'),('F','high','rotation'))),a,m,r)]:
            with self.assertRaises(ValueError):structural_dispatch_control(*args)

    def test_rehashed_target_training_wrong_dated_team_future_cutoff_and_duplicates_reject(self):
        b,c,a,m,r=control_inputs()
        for attack in ('target','team','future','duplicate'):
            value=json.loads(a);cc=c
            if attack=='target':value['training_rows'][0]['game_id']=b['game_id']
            if attack=='team':value['training_rows'][0]['team_id']='wrong'
            if attack=='future':value['training_cutoff_at']='2027-01-01T00:00:00Z';cc=replace(cc,training_cutoff_at=value['training_cutoff_at'])
            if attack=='duplicate':value['training_rows'].append(copy.deepcopy(value['training_rows'][0]))
            raw=canonical(value);cc=replace(cc,artifact_sha256=digest(raw))
            with self.subTest(attack=attack),self.assertRaises(ValueError):structural_dispatch_control(b,cc,raw,m,r)

    def test_synthetic_artifact_and_approval_file_do_not_register_real_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'points.json').write_bytes((FIXTURE/'points.json').read_bytes());(p/'approval.json').write_text('{"approved":true,"reviewer":"independent"}')
            kwargs=real_inputs(p);x=run_dispatch(**kwargs)
            self.assertEqual(x['forecasted_rows'],0);self.assertEqual(x['attempt_denominator'],144)
            self.assertEqual(sum(r['reason']=='S_ARTIFACT_NOT_ADMITTED' for r in x['rows']),12)
            self.assertEqual(x['provided_file_denominator'],2);self.assertEqual(x['provided_files']['approval.json']['disposition'],'REJECTED_UNMATCHED_PROVIDED_FILE')

    def test_resealed_output_and_upstream_claims_reject(self):
        kwargs=real_inputs();x=run_dispatch(**kwargs)
        for attack in ('drop','q','forecast','variant','role','model'):
            v=copy.deepcopy(x)
            if attack=='drop':v['rows'].pop()
            if attack=='q':v['rows'][0]['participation_probability']=1.
            if attack=='forecast':v['rows'][0]['forecast']={'mean':10}
            if attack=='variant':v['exposure_variant']='M2'
            if attack=='role':v['rows'][0]['trained_role']='starter'
            if attack=='model':v['admitted_model_count']=1
            v.pop('payload_sha256');v['payload_sha256']=digest(canonical(v))
            with self.subTest(attack=attack),self.assertRaises(ValueError):read_dispatch(canonical(v),**kwargs)
        v=json.loads(kwargs['p3_raw']);v['rows'][0]['team_id']='wrong';v.pop('payload_sha256');v['payload_sha256']=digest(canonical(v));kwargs['p3_raw']=canonical(v)
        with self.assertRaises(ValueError):run_dispatch(**kwargs)

    def test_duplicate_and_nonfinite_wire_reject(self):
        kwargs=real_inputs();raw=canonical(run_dispatch(**kwargs))
        for attack in (b'{"forecasted_rows":999,'+raw[1:],b'{"q":NaN}'):
            with self.assertRaises(ValueError):read_dispatch(attack,**kwargs)
