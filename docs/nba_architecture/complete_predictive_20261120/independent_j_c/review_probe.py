"""Independent exact J-to-C engineering transport controls; no generation or score."""
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone
import copy,json,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from scripts.nba_genuine_s import frozen_inputs
from v2.nba_architecture import conditional_j_c_v1 as C
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
P=ROOT/'docs/nba_architecture/complete_predictive_20261120';H=Path(__file__).resolve().parent;OLD=ROOT/'docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive';RESULT={}
parent=(OLD/'forecast.json').read_bytes();original=dict(frozen_inputs(OLD),forecast_at=json.loads(parent)['forecast_at'])
full_inputs=dict(law_snapshot_path=P/'FULL_S_CANDIDATE.json',cohort=json.loads((P/'FULL_FORECAST_COHORT.json').read_bytes()),admission_path=P/'independent_full_law/ADMISSION.json',original_inputs=original,pbp_raw_dir=P/'raw',pbp_population_path=P/'PBP_POPULATION.json',model_card_path=P/'FULL_PLAYED_MODEL_CARD.json',protocol_path=P/'independent_protocol/DECISION.json')
outcome_inputs=dict(raw_dir=P/'raw',population_path=P/'PBP_POPULATION.json',original_raw_dir=original['raw_dir'],spec_path=original['spec_path'],profile_path=P/'independent_c_profile/DECISION.json')
ARGS=dict(run_raw=(P/'actual_j_candidate/RUN.json').read_bytes(),receipt_raw=(P/'actual_j_candidate/EXECUTION_RECEIPT.json').read_bytes(),model_raw=(P/'fitted_j/event_model.json').read_bytes(),model_admission_raw=(P/'independent_j_artifact/ARTIFACT_ADMISSION.json').read_bytes(),full_raw=(P/'actual_full_forecast/forecast.json').read_bytes(),parent_raw=parent,full_inputs=full_inputs,outcome_inputs=outcome_inputs)
RUN=json.loads(ARGS['run_raw']);FULL=json.loads(ARGS['full_raw'])
class Review(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  with patch.object(C,'fixed_scenario',wraps=C.fixed_scenario) as regenerate,patch.object(C,'audit_run',wraps=C.audit_run) as audit:
   cls.value=C.read_J_for_C(**ARGS)
  assert regenerate.call_count==32;assert audit.call_count==1
  RESULT.update(fixed_scenarios_recomputed=regenerate.call_count,public_full_run_audits=audit.call_count,result_payload_sha256=cls.value['payload_sha256'])
 def test_01_public_read_positive_and_public_cli_match(self):
  x=self.value;self.assertEqual((x['source_candidate_denominator'],x['primitive_attempts'],x['primitive_supported'],x['primitive_abstained'],x['all_market_attempts'],x['all_market_supported'],x['all_market_abstained'],x['scenario_denominator']),(35,140,56,84,280,112,168,32))
  self.assertEqual(x['actual_scores'],0);self.assertEqual(x['pending_outcomes'],280);self.assertFalse(x['J_family_admitted']);self.assertFalse(x['marginal_fidelity_accepted']);self.assertFalse(x['historical_predictive_validation']);self.assertFalse(x['release'])
  self.assertEqual(digest(canonical({k:v for k,v in x.items() if k!='payload_sha256'})),x['payload_sha256'])
  self.assertEqual(canonical(x),(H/'public_cli/RESULT.json').read_bytes());self.assertEqual(x['physics']['scenarios'],32);self.assertTrue(all(r['violations']==0 for r in x['physics']['results']))
  RESULT['source_execution']=dict(scenarios=len(RUN['scenarios']),proposals=sum(len(s['proposals']) for s in RUN['scenarios']),rejections=sum(len(s['proposals'])-1 for s in RUN['scenarios']),OT_scenarios=[s['fixed']['index'] for s in RUN['scenarios'] if s['fixed']['overtime_count']])
 def test_02_all280_same_draw_values_and_combinations_independent(self):
  expected={};combo_checks=0
  for i,s in enumerate(RUN['scenarios']):
   path=s['proposals'][-1]
   for tid,actors in s['fixed']['actors'].items():
    for actor in actors:
     pid=actor['identity']['player_id']
     if not pid:continue
     count=path['counts'][tid][actor['index']];p,r,a=count['points'],count['rebounds'],count['assists']
     for stat,value in dict(points=p,rebounds=r,assists=a,threes=count['threes'],pr=p+r,pa=p+a,ra=r+a,pra=p+r+a).items():expected.setdefault((pid,stat),[]).append(value)
  self.assertEqual(len(expected),112)
  candidates={r['player_id']:r for r in FULL['cohort']['frozen_candidates']};self.assertEqual(len(candidates),35)
  rows=self.value['rows'];self.assertEqual(len({(r['player_id'],r['statistic']) for r in rows}),280)
  for row in rows:
   self.assertEqual(row['team_id'],candidates[row['player_id']]['team_id']);self.assertIsNone(row['outcome']);self.assertIsNone(row['score']);self.assertIsNone(row['participation_probability']);self.assertIsNone(row['legal_eligibility'])
   if (row['player_id'],row['statistic']) in expected:
    self.assertEqual(row['samples'],expected[row['player_id'],row['statistic']]);self.assertEqual(row['scenario_ids'],list(range(32)));self.assertTrue(all(type(k) is int and k>=0 for k in row['samples']))
    if row['statistic'] in ('pr','pa','ra','pra'):combo_checks+=32
   else:self.assertIsNone(row['samples']);self.assertIsNone(row['scenario_ids']);self.assertEqual(row['status'],'FORECAST_ABSTAINED')
  RESULT['same_draw_checks']=dict(supported_arrays=112,individual_values=112*32,combo_values_independently_readded=combo_checks,abstained_rows=168)
 def test_03_frozen_raw_input_mutations_reject(self):
  controls=[]
  for key in ('run_raw','receipt_raw','model_raw','model_admission_raw','full_raw'):
   args=dict(ARGS);args[key]=args[key]+b' '
   with self.subTest(key=key),self.assertRaises(ValueError) as error:C.read_J_for_C(**args)
   controls.append(dict(input=key,rejected=str(error.exception)))
  RESULT['raw_byte_mutations']=controls
 def test_04_all_direct_dependency_byte_mutations_reject(self):
  targets=[ROOT/'v2/nba_joint'/name for name in C.J_CODE_SHA]+[ROOT/'v2/nba_architecture'/name for name in C.TRANSPORT_CODE_SHA];read=Path.read_bytes;controls=[]
  for target in targets:
   def changed(path):return read(path)+b'\n# REVIEW_ONLY_SIMULATED_UNREVIEWED_BYTES\n' if path.resolve()==target.resolve() else read(path)
   with self.subTest(target=str(target)),patch.object(Path,'read_bytes',new=changed),self.assertRaises(ValueError) as error:C.read_J_for_C(**ARGS)
   self.assertIn('J_C_REVIEWED_',str(error.exception));controls.append(dict(helper=str(target.relative_to(ROOT)),rejected=str(error.exception)))
  RESULT['dependency_mutations']=controls
 def test_05_resealed_receipt_lineage_and_clock_controls(self):
  controls=[]
  for field,value in [('input_model_receipt_raw_sha256','0'*64),('freeze_at','2026-11-20T03:00:00+00:00'),('event_start_at','2026-11-23T01:00Z')]:
   receipt=json.loads(ARGS['receipt_raw']);receipt[field]=value;raw=canonical(receipt);args=dict(ARGS,receipt_raw=raw)
   # Deliberately mocked root pin tests deeper invariants; these are NOT
   # authorized alternate inputs. Original actual raw pins remain immutable.
   with self.subTest(field=field),patch.object(C,'RECEIPT_SHA',digest(raw)),patch.object(C,'read_issued_forecast',return_value={}),patch.object(C,'read_native_outcomes',return_value={}),self.assertRaises(ValueError) as error:C.read_J_for_C(**args)
   controls.append(dict(field=field,rejected=str(error.exception)))
  RESULT['resealed_receipt_controls']=controls
 def test_06_resealed_run_physics_population_and_fixed_handoff_controls(self):
  controls=[]
  for mutation in ('dropped_scenario','failed_final_proposal','count_tamper','fixed_rate_tamper'):
   run=copy.deepcopy(RUN)
   if mutation=='dropped_scenario':run['scenarios'].pop()
   elif mutation=='failed_final_proposal':run['scenarios'][0]['proposals'][-1]['status']='REJECT_OT_PATTERN'
   elif mutation=='count_tamper':next(iter(run['scenarios'][0]['proposals'][-1]['counts'].values()))[0]['points']+=1
   else:next(iter(run['scenarios'][0]['fixed']['actors'].values()))[0]['rates']['points']+=.1
   run['payload_sha256']=digest(canonical({k:v for k,v in run.items() if k!='payload_sha256'}));raw=canonical(run);receipt=json.loads(ARGS['receipt_raw']);receipt['run_raw_sha256']=digest(raw);rr=canonical(receipt);args=dict(ARGS,run_raw=raw,receipt_raw=rr)
   with self.subTest(mutation=mutation),patch.object(C,'RUN_SHA',digest(raw)),patch.object(C,'RECEIPT_SHA',digest(rr)),patch.object(C,'read_issued_forecast',return_value={}),patch.object(C,'read_native_outcomes',return_value={}),self.assertRaises(ValueError) as error:C.read_J_for_C(**args)
   controls.append(dict(mutation=mutation,rejected=str(error.exception)))
  RESULT['resealed_run_controls']=controls
 def test_07_cli_output_is_create_only(self):
  output=H/'public_cli';before={p.name:p.read_bytes() for p in output.iterdir()};command=[sys.executable,'scripts/nba_complete_predictive.py','read-j','--output',str(output)]
  process=subprocess.run(command,cwd=ROOT,capture_output=True);(H/'cli_reuse.stdout').write_bytes(process.stdout);(H/'cli_reuse.stderr').write_bytes(process.stderr);self.assertNotEqual(process.returncode,0);self.assertIn(b'CREATE_ONLY_OUTPUT',process.stderr);self.assertEqual(before,{p.name:p.read_bytes() for p in output.iterdir()})
  RESULT['cli_reuse_exit_code']=process.returncode
if __name__=='__main__':
 RESULT.update(started_at=datetime.now(timezone.utc).isoformat(),C_reader_raw_sha256=digest(Path(C.__file__).read_bytes()),public_CLI_raw_sha256=digest((ROOT/'scripts/nba_complete_predictive.py').read_bytes()),public_inputs_raw_sha256=digest((P/'inputs.py').read_bytes()))
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Review));RESULT.update(completed_at=datetime.now(timezone.utc).isoformat(),test_methods=result.testsRun,failures=len(result.failures),errors=len(result.errors),new_J_runs=0,new_forecasts_issued=0,new_fit_artifacts_created=0,outcome_scores=0)
 (H/'RESULTS.json').write_text(json.dumps(RESULT,indent=2,sort_keys=True)+'\n');sys.exit(not result.wasSuccessful())
