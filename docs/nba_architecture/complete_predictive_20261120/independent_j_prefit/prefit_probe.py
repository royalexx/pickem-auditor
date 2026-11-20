"""Independent closed compiler protocol; successful compile parameters are synthetic."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from datetime import datetime,timezone
import json,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from scripts.nba_genuine_s import frozen_inputs
from v2.nba_joint import real_event_parameters_v1 as writer
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.prospective_s_sources_v1 import build_dataset
from v2.nba_s_family import model as native
P=ROOT/'docs/nba_architecture/complete_predictive_20261120';H=Path(__file__).resolve().parent;OLD=ROOT/'docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive';RESULT={}
parent_raw=(OLD/'forecast.json').read_bytes();parent=json.loads(parent_raw);original=dict(frozen_inputs(OLD),forecast_at=parent['forecast_at'])
replay=dict(law_snapshot_path=P/'FULL_S_CANDIDATE.json',cohort=json.loads((P/'FULL_FORECAST_COHORT.json').read_bytes()),admission_path=P/'independent_full_law/ADMISSION.json',original_inputs=original,pbp_raw_dir=P/'raw',pbp_population_path=P/'PBP_POPULATION.json',model_card_path=P/'FULL_PLAYED_MODEL_CARD.json',protocol_path=P/'independent_protocol/DECISION.json')
args=dict(full_forecast_raw=(P/'actual_full_forecast/forecast.json').read_bytes(),parent_raw=parent_raw,full_replay_inputs=replay,original_raw_dir=original['raw_dir'],spec_path=original['spec_path'],policy_path=original['policy_path'],pbp_raw_dir=P/'raw',pbp_population_path=P/'PBP_POPULATION.json',s3_path=P/'fitted_s3/three_conversion.json',s3_receipt_path=P/'fitted_s3/FIT_RECEIPT.json',s3_admission_path=P/'independent_s3_artifact/ARTIFACT_ADMISSION.json',full_admission_path=P/'independent_full_law/ADMISSION.json',j_card_path=P/'J_MODEL_CARD.json')
class Prefit(unittest.TestCase):
 def test_01_closed_gate_before_inputs_and_output(self):
  self.assertIsNone(writer.PREFIT_APPROVAL_SHA)
  with tempfile.TemporaryDirectory() as temp,patch.object(writer,'read_issued_forecast') as read:
   out=Path(temp)/'out'
   with self.assertRaisesRegex(ValueError,'PREFIT_REVIEW_CLOSED'):writer.fit_event_parameters(approval_path='absent',output=out,**args)
   read.assert_not_called();self.assertFalse(out.exists())
 def test_02_actual_readonly_source_and_pure_conversion_formula(self):
  data=build_dataset(original['raw_dir'],original['spec_path'],original['policy_path']);self.assertEqual(data['payload_sha256'],writer.DATASET_SHA)
  rows=[r for r in data['records'] if r['fit_included']];self.assertEqual(len(rows),456);rolemap=json.loads((P/'independent_s3_artifact/ARTIFACT_ADMISSION.json').read_bytes())['exact_current_target_role_map'];checks=[]
  for pid,role in rolemap.items():
   own=[r for r in rows if r['player_id']==pid];peers=[r for r in rows if r['player_id']!=pid and r['role']==role]
   for made,attempted in [('two_made','two_attempts'),('freeThrowsMade','freeThrowsAttempted')]:
    def counts(pool,key):
     return sum((r['official_counts']['fieldGoalsMade']-r['official_counts']['threePointersMade'] if key=='two_made' else r['official_counts']['fieldGoalsAttempted']-r['official_counts']['threePointersAttempted'] if key=='two_attempts' else r['official_counts'][key]) for r in pool)
    m,n,pm,pn=counts(own,made),counts(own,attempted),counts(peers,made),counts(peers,attempted);actual=writer._conversion(own,peers,made,attempted)
    self.assertAlmostEqual(actual['alpha'],.5+m+40*pm/pn,places=11);self.assertAlmostEqual(actual['beta'],.5+n-m+40*(1-pm/pn),places=11)
    checks.append(dict(player_id=pid,role=role,conversion=made,own_makes=m,own_attempts=n,peer_makes=pm,peer_attempts=pn))
  RESULT['readonly_conversion_source_checks']=checks
 def test_03_mock_parameter_compile_create_only(self):
  # Real upstream binding checks run; all new rate/conversion and pace calculations
  # below use synthetic counts. This is not an actual J working-model fit.
  with tempfile.TemporaryDirectory() as temp:
   t=Path(temp);approval=t/'MOCK_APPROVAL';approval.write_bytes(canonical(dict(kind='REVIEW_SYNTHETIC_PROTOCOL_NOT_AUTHORIZATION',decided_at='2026-11-20T03:00:00+00:00')));out=t/'mock_output'
   proxy=SimpleNamespace(__file__=native.__file__,FittedS=native.FittedS,fit=lambda *a,**k:native.FittedS((P/'fitted_s3/three_conversion.json').read_bytes()),predict_conditional=native.predict_conditional)
   constants=dict(two_made=1,two_attempts=2,freeThrowsMade=1,freeThrowsAttempted=2,points=6,threePointersMade=1,threePointersAttempted=2,reboundsTotal=1,assists=1,turnovers=1)
   counter=[0]
   def fake_page(raw):
    counter[0]+=1;i=counter[0]
    c=dict(fieldGoalsAttempted=90+i,fieldGoalsMade=50,freeThrowsAttempted=20,freeThrowsMade=15,reboundsTotal=40,reboundsOffensive=10,reboundsDefensive=30,assists=25,turnovers=10)
    return dict(game=dict(period=4,homeTeam=dict(statistics=c),awayTeam=dict(statistics=c)))
   with patch.object(writer,'PREFIT_APPROVAL_SHA',digest(approval.read_bytes())),patch.object(writer,'native',proxy),patch.object(writer,'_moments',side_effect=lambda rows,key:len(rows)*constants[key]),patch.object(writer,'next_data',side_effect=fake_page):
    receipt=writer.fit_event_parameters(approval_path=approval,output=out,**args);model=json.loads((out/'event_model.json').read_bytes())
    self.assertEqual(len(model['named_players']),14);self.assertEqual(set(model['residual_groups']),{'espn:team:16','espn:team:29'});self.assertFalse(model['posterior_of_joint_event_process']);self.assertIsNone(model['genuine_participation_probability']);self.assertFalse(model['production_release'])
    self.assertEqual(receipt['PBP_actions'],10463);self.assertLessEqual(receipt['started_at'],receipt['completed_at']);self.assertEqual(receipt['model_raw_sha256'],digest((out/'event_model.json').read_bytes()))
    before={f.name:f.read_bytes() for f in out.iterdir()}
    with self.assertRaises(FileExistsError):writer.fit_event_parameters(approval_path=approval,output=out,**args)
    self.assertEqual(before,{f.name:f.read_bytes() for f in out.iterdir()});RESULT['mock_protocol_receipt']=receipt;RESULT['mock_parameters_are_synthetic']=True
 def test_04_bad_approvals_admissions_card_and_artifact_reject(self):
  with tempfile.TemporaryDirectory() as temp:
   t=Path(temp);approval=t/'MOCK_APPROVAL';approval.write_bytes(canonical(dict(kind='REVIEW_MOCK_NOT_AUTHORIZATION',decided_at='2026-11-20T03:00:00+00:00')));items=[('full_admission_path',P/'independent_full_law/ADMISSION.json'),('s3_admission_path',P/'independent_s3_artifact/ARTIFACT_ADMISSION.json'),('j_card_path',P/'J_MODEL_CARD.json'),('s3_path',P/'fitted_s3/three_conversion.json')];checks=[]
   for key,path in items:
    bad=t/key;bad.write_bytes(path.read_bytes()+b' ');values=dict(args);values[key]=bad;out=t/(key+'_out')
    with self.subTest(key=key),patch.object(writer,'PREFIT_APPROVAL_SHA',digest(approval.read_bytes())),self.assertRaises(ValueError) as error:writer.fit_event_parameters(approval_path=approval,output=out,**values)
    self.assertFalse(out.exists());checks.append(dict(input=key,rejected=str(error.exception)))
   RESULT['binding_controls']=checks
 def test_05_future_prefit_clock_rejects_before_output(self):
  with tempfile.TemporaryDirectory() as temp:
   t=Path(temp);approval=t/'MOCK_FUTURE_APPROVAL';approval.write_bytes(canonical(dict(kind='REVIEW_MOCK_NOT_AUTHORIZATION',decided_at='2027-11-20T03:00:00+00:00')));out=t/'future_out'
   with patch.object(writer,'PREFIT_APPROVAL_SHA',digest(approval.read_bytes())),self.assertRaisesRegex(ValueError,'CLOCK') as error:writer.fit_event_parameters(approval_path=approval,output=out,**args)
   self.assertFalse(out.exists());RESULT['future_approval_clock_rejected']=str(error.exception)
if __name__=='__main__':
 RESULT.update(started_at=datetime.now(timezone.utc).isoformat(),compiler_raw_sha256=digest(Path(writer.__file__).read_bytes()))
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Prefit));RESULT.update(completed_at=datetime.now(timezone.utc).isoformat(),test_methods=result.testsRun,failures=len(result.failures),errors=len(result.errors),actual_J_compiles=0,new_fit_artifacts_created=0,outcome_scores=0)
 (H/'RESULTS.json').write_text(json.dumps(RESULT,indent=2,sort_keys=True)+'\n');sys.exit(not result.wasSuccessful())
