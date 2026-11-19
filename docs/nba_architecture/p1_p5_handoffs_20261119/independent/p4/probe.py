"""Independent P4 real minute-law transport, abstentions and forgery controls."""
import copy,collections,json,pathlib,subprocess,unittest
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.subset_p2_v1 import run_p2
from v2.nba_architecture.subset_p4_v1 import run_p4,read_p4,read_native_minute_law,MinuteLaw
ROOT=pathlib.Path(__file__).resolve().parents[5];PACK=ROOT/'docs/nba_architecture/p1_p5_handoffs_20261119';OUT=pathlib.Path(__file__).resolve().parent;CAP=ROOT/'docs/nba_architecture/p1_subset_acceptance_20261119/initial_tonight_capture';C=json.loads((PACK/'PROSPECTIVE_COHORT.json').read_bytes());P3=PACK/'independent/p3/final_05b44764';S=(P3/'p1.json').read_bytes();P3RAW=(P3/'p3.json').read_bytes();CLOCK=(P3/'forecast_at.txt').read_text().strip();P2=canonical(run_p2(S,CAP,C));KW=dict(p2_raw=P2,p3_raw=P3RAW,source_raw=S,capture_dir=CAP,cohort=C,history_dir=PACK/'prospective_inputs',model_path=ROOT/'research/nba_ws2/results/model.json',forecast_at=CLOCK)
class IndependentP4(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.actual=run_p4(**KW)
 def test_real_native_law_transport_and_all_stat_attempts(self):
  x=self.actual;self.assertEqual((x['candidate_denominator'],x['attempt_denominator'],x['native_minute_laws_read'],x['minute_stat_references']),(36,432,36,144));self.assertEqual(x['statistic_forecasted_rows'],0);self.assertEqual(x['abstained_rows'],432);self.assertFalse(x['team_normalization_performed']);self.assertFalse(x['production_release']);self.assertTrue(all(r['forecast'] is None and r['participation_probability'] is None and r['legal_eligibility'] is None and not r['actual_joint_model_executed'] for r in x['rows']));self.assertEqual(len({(r['player_id'],r['model'],r['statistic']) for r in x['rows']}),432);self.assertEqual(sum(r['reason']=='P1_SOURCE_ABSTENTION' for r in x['rows']),132);self.assertEqual(sum(r['reason']=='P2_STATISTIC_KERNEL_UNAVAILABLE' for r in x['rows']),144);self.assertEqual(read_p4(canonical(x),**KW),x);(OUT/'p2.json').write_bytes(P2);(OUT/'p4.json').write_bytes(canonical(x));print(json.dumps({'candidate_rows':36,'native_minute_laws':36,'stat_references':144,'stat_attempts':432,'stat_forecasts':0,'reason_counts':dict(collections.Counter(r['reason'] for r in x['rows']))},indent=2))
 def test_fully_resealed_legal_law_cannot_replace_source(self):
  p=json.loads(P3RAW);row=next(r for r in p['rows'] if r['forecast']);f=row['forecast'];f['distribution']['mean']=20.;law=MinuteLaw(**f['distribution']);f.update(law.summary());f.pop('forecast_id');f['forecast_id']=digest(json.dumps(f,sort_keys=True).encode());parsed=read_native_minute_law(f);self.assertEqual(parsed['verification_scope'],'STRUCTURAL_LAW_ONLY_NO_SOURCE_OR_MODEL_ADMISSION');p.pop('payload_sha256');p['payload_sha256']=digest(canonical(p));kw=dict(KW,p3_raw=canonical(p))
  with self.assertRaises(ValueError):run_p4(**kw)
 def test_self_resealed_false_q_joint_moment_output_and_duplicates(self):
  original=next(r['forecast'] for r in json.loads(P3RAW)['rows'] if r['forecast'])
  for kind in ['q','moment','scenario']:
   f=copy.deepcopy(original)
   if kind=='q':f['participation_probability']=1
   if kind=='moment':f['expected_minutes_given_played']+=1
   if kind=='scenario':f['scenario_ids']=['invented']
   f.pop('forecast_id');f['forecast_id']=digest(json.dumps(f,sort_keys=True).encode())
   with self.subTest(kind=kind),self.assertRaises(ValueError):read_native_minute_law(f)
  x=copy.deepcopy(self.actual);x['rows'][0]['forecast']={'pmf':{'0':1}};x['joint_law_status']='ACCEPTED';x['rows'][0]['participation_probability']=1;x.pop('payload_sha256');x['payload_sha256']=digest(canonical(x))
  with self.assertRaises(ValueError):read_p4(canonical(x),**KW)
  with self.assertRaises(ValueError):read_p4(b'{"statistic_forecasted_rows":1,'+canonical(self.actual)[1:],**KW)
 def test_original_physical_and_budget_contract_preserved(self):
  for path in ['v2/nba_opportunity.py','v2/nba_architecture/exposure_v2.py','docs/nba_architecture/substantive_remediation_20261117/PHYSICAL_LAW_REJECTION.md']:
   self.assertEqual((ROOT/path).read_bytes(),subprocess.check_output(['git','show','33842b96:'+path],cwd=ROOT))
  self.assertEqual(subprocess.check_output(['git','diff','33842b96','--','docs/nba_architecture/substantive_remediation_20261117'],cwd=ROOT),b'')
if __name__=='__main__':unittest.main(verbosity=2)
