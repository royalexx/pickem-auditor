import copy
import json
from pathlib import Path
import unittest

from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.subset_p4_v1 import run_p4,read_p4,read_native_minute_law
from v2.nba_opportunity import MinuteLaw
from tests.nba_architecture.test_subset_p3_v1 import CAP,COHORT,HISTORY,MODEL,PACKET

UP=PACKET/'p3_accounting_repair/recorded_native_replay'


def inputs():
    p3=(UP/'p3.json').read_bytes()
    return dict(p2_raw=(UP/'p2.json').read_bytes(),p3_raw=p3,
        source_raw=(UP/'p1.json').read_bytes(),capture_dir=CAP,cohort=COHORT,
        history_dir=HISTORY,model_path=MODEL,forecast_at=json.loads(p3)['forecast_at'])


class P4SubsetTests(unittest.TestCase):
    def test_real_native_laws_cross_public_p4_boundary_all_attempts_stay_counted(self):
        kwargs=inputs();x=run_p4(**kwargs)
        self.assertEqual((x['candidate_denominator'],x['attempt_denominator'],x['native_minute_laws_read'],x['minute_stat_references'],x['abstained_rows']),(36,432,36,144,432))
        self.assertEqual(len({(r['player_id'],r['model'],r['statistic']) for r in x['rows']}),432)
        self.assertEqual(sum(r['reason']=='P1_SOURCE_ABSTENTION' for r in x['rows']),132)
        self.assertEqual(sum(r['reason']=='P2_STATISTIC_KERNEL_UNAVAILABLE' for r in x['rows']),144)
        self.assertTrue(all(r['forecast'] is None and r['participation_probability'] is None and not r['actual_joint_model_executed'] for r in x['rows']))
        self.assertEqual(read_p4(canonical(x),**kwargs),x)

    def test_native_reader_rejects_resealed_moments_and_false_q(self):
        p3=json.loads(inputs()['p3_raw']);original=next(r['forecast'] for r in p3['rows'] if r['forecast'])
        self.assertEqual(read_native_minute_law(original)['native_forecast_id'],original['forecast_id'])
        for attack in ('q','moment','team_scenario','distribution'):
            f=copy.deepcopy(original)
            if attack=='q':f['participation_probability']=1.
            if attack=='moment':f['expected_minutes_given_played']+=1.
            if attack=='team_scenario':f['scenario_ids']=['fake']
            if attack=='distribution':f['distribution']['variance']+=1.
            f.pop('forecast_id');f['forecast_id']=digest(json.dumps(f,sort_keys=True).encode())
            with self.subTest(attack=attack),self.assertRaises(ValueError):read_native_minute_law(f)

    def test_upstream_and_resealed_output_mutations_fail(self):
        kwargs=inputs();x=run_p4(**kwargs)
        for attack in ('drop','forecast','q','joint','completeness'):
            v=copy.deepcopy(x)
            if attack=='drop':v['rows'].pop()
            if attack=='forecast':v['rows'][0]['forecast']={'pmf':{'0':1.}}
            if attack=='q':v['rows'][0]['participation_probability']=1.
            if attack=='joint':v['joint_law_status']='ACCEPTED';v['coupling_protocol_admission']='approved'
            if attack=='completeness':v['complete_legal_roster']=True
            v.pop('payload_sha256');v['payload_sha256']=digest(canonical(v))
            with self.subTest(attack=attack),self.assertRaises(ValueError):read_p4(canonical(v),**kwargs)
        p3=json.loads(kwargs['p3_raw']);p3['rows'].pop();kwargs['p3_raw']=canonical(p3)
        with self.assertRaises(ValueError):run_p4(**kwargs)

    def test_duplicate_keys_fail(self):
        kwargs=inputs();raw=canonical(run_p4(**kwargs))
        with self.assertRaises(ValueError):read_p4(b'{"statistic_forecasted_rows":1,'+raw[1:],**kwargs)

    def test_self_consistent_forgery_is_structural_only_and_source_path_rejects(self):
        kwargs=inputs();p3=json.loads(kwargs['p3_raw']);f=next(r['forecast'] for r in p3['rows'] if r['forecast'])
        f['distribution']['mean']+=1.;f.update(MinuteLaw(**f['distribution']).summary())
        f.pop('forecast_id');f['forecast_id']=digest(json.dumps(f,sort_keys=True).encode())
        structural=read_native_minute_law(f)
        self.assertEqual(structural['verification_scope'],'STRUCTURAL_LAW_ONLY_NO_SOURCE_OR_MODEL_ADMISSION')
        p3.pop('payload_sha256');p3['payload_sha256']=digest(canonical(p3));kwargs['p3_raw']=canonical(p3)
        with self.assertRaises(ValueError):run_p4(**kwargs)
