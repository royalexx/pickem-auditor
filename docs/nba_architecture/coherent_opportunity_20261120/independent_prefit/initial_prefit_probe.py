"""Independent coherent fitter protocol; real-source posteriors never assembled."""
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
import copy,json,math,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from scripts.nba_genuine_s import frozen_inputs
from v2.nba_joint import coherent_components_v1 as F
from v2.nba_architecture.prospective_s_sources_v1 import build_dataset
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
P=ROOT/'docs/nba_architecture/coherent_opportunity_20261120';H=Path(__file__).resolve().parent;OLD=ROOT/'docs/nba_architecture/complete_predictive_20261120';ARCHIVE=ROOT/'docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive';INPUTS=frozen_inputs(ARCHIVE);RESULT={}
SOURCE=dict(raw_dir=OLD/'raw',population_path=OLD/'PBP_POPULATION.json',original_raw_dir=INPUTS['raw_dir'],spec_path=INPUTS['spec_path'],profile_path=OLD/'independent_c_profile/DECISION.json')
ARGS=dict(protocol_path=P/'PROTOCOL.json',old_model_path=OLD/'fitted_j/event_model.json',old_admission_path=OLD/'independent_j_artifact/ARTIFACT_ADMISSION.json',source_inputs=SOURCE,original_raw_dir=INPUTS['raw_dir'],spec_path=INPUTS['spec_path'],policy_path=INPUTS['policy_path'])
def row(pid='MOCK:p',team='MOCK:A',role='MOCK:G',include=True):
 return dict(player_id=pid,team_id=team,role=role,fit_included=include,exact_seconds=600,official_counts=dict(fieldGoalsAttempted=8,threePointersAttempted=3,fieldGoalsMade=4,threePointersMade=1,freeThrowsAttempted=4,freeThrowsMade=3,turnovers=1))
def fixture():
 rates={k:dict(alpha=2.,beta=10.) for k in ('points','rebounds','assists','threes','turnovers')};players=[];records=[]
 for t in ('MOCK:A','MOCK:B'):
  for i in range(7):
   pid=t+':p'+str(i);players.append(dict(player_id=pid,team_id=t,role='MOCK:G',rates=copy.deepcopy(rates),ft_non3_point_share=dict(alpha=1,beta=2)))
   records.extend(row(pid,t) for _ in range(5))
 records.extend(row('MOCK:residual:'+str(i),'MOCK:A' if i%2 else 'MOCK:B') for i in range(386));records.extend(row('MOCK:excluded:'+str(i),include=False) for i in range(242))
 old=dict(named_players=players,residual_groups={t:dict(rates=copy.deepcopy(rates),ft_non3_point_share=dict(alpha=1,beta=1)) for t in ('MOCK:A','MOCK:B')},s3_artifact_sha256='c'*64,S1_use='MOCK_OLD_REFERENCE',S3_use='MOCK_OLD_REFERENCE')
 return old,records
class Review(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.data=build_dataset(INPUTS['raw_dir'],INPUTS['spec_path'],INPUTS['policy_path'])
 def test_01_closed_gate_precedes_all_sources_output_and_assembly(self):
  self.assertIsNone(F.PREFIT_SHA)
  with tempfile.TemporaryDirectory() as t,patch.object(F,'read_native_outcomes') as source,patch.object(F,'assemble') as assemble:
   out=Path(t)/'out'
   with self.assertRaisesRegex(ValueError,'PREFIT_REVIEW_CLOSED'):F.fit(approval_path='missing',output=out,**ARGS)
   source.assert_not_called();assemble.assert_not_called();self.assertFalse(out.exists())
 def test_02_actual_source_sufficient_statistics_without_fitting(self):
  self.assertEqual(self.data['payload_sha256'],F.DATASET_SHA);included=[r for r in self.data['records'] if r['fit_included']];self.assertEqual((len(self.data['records']),len(included)),(698,456));old=json.loads(ARGS['old_model_path'].read_bytes());named={p['player_id'] for p in old['named_players']};checks=[]
  pools=[]
  for p in old['named_players']:
   own=[r for r in included if r['player_id']==p['player_id']];peers=[r for r in included if r['player_id']!=p['player_id'] and r['role']==p['role']];pools.extend([(p['player_id']+':own',own),(p['player_id']+':peers',peers)])
   self.assertGreaterEqual(len(own),5)
  for t in old['residual_groups']:pools.append(('RESIDUAL:'+t,[r for r in included if r['team_id']==t and r['player_id'] not in named]))
  for label,rows in pools:
   expected={k:0 for k in ('twoPA','twoPM','threePA','threePM','FTA','FTM','TO')}
   for r in rows:
    c=r['official_counts'];values=[c['fieldGoalsAttempted']-c['threePointersAttempted'],c['fieldGoalsMade']-c['threePointersMade'],c['threePointersAttempted'],c['threePointersMade'],c['freeThrowsAttempted'],c['freeThrowsMade'],c['turnovers']]
    for k,v in zip(expected,values):expected[k]+=v
   actual=F.sufficient(rows);self.assertEqual(actual['counts'],expected);self.assertEqual(actual['rows'],len(rows));self.assertLess(abs(actual['reported_minutes']-sum(r['exact_seconds'] for r in rows)/60),1e-10)
   self.assertTrue(all(expected[k]>0 for k in ('twoPA','threePA','FTA')));checks.append(dict(label=label,**actual))
  self.assertEqual(len(checks),30);RESULT['actual_source_sufficient_statistics']=checks
 def test_03_synthetic_posterior_and_assembler_likelihood_contract(self):
  own=[row() for _ in range(5)];peers=[row('MOCK:peer') for _ in range(8)];p=F.posterior(own,peers)
  for key,value in [('twoPA',5),('threePA',3),('FTA',4),('TO',1)]:
   r=p['attempt_posteriors'][key];self.assertAlmostEqual(r['alpha'],.5+180*(value/10)+5*value);self.assertEqual(r['beta'],231.)
  self.assertAlmostEqual(p['conversion2']['alpha'],.5+40*(3/5)+15);self.assertAlmostEqual(p['conversion2']['beta'],.5+40*(2/5)+10)
  old,records=fixture();before=copy.deepcopy(old);model=F.assemble(old,records);self.assertEqual(old,before);self.assertFalse(model['independent_points_or_threes_posteriors']);self.assertFalse(model['posterior_of_joint_event_process']);self.assertEqual(model['legacy_S3_comparator_raw_sha256'],'c'*64);self.assertNotIn('s3_artifact_sha256',model)
  for p in model['named_players']+list(model['residual_groups'].values()):self.assertEqual(set(p['rates']),{'assists','rebounds'});self.assertEqual(set(p['attempt_posteriors']),{'twoPA','threePA','FTA','TO'});self.assertNotIn('ft_non3_point_share',p);self.assertIn('NOT_FULL_EVENT_POSTERIOR',p['likelihood_scope'])
  with self.assertRaises(ValueError):F.assemble(old,records[:-1])
 def test_04_synthetic_row_negative_controls(self):
  for exposure in (0,-1,True,float('nan'),float('inf')):
   bad=row();bad['exact_seconds']=exposure
   with self.subTest(exposure=str(exposure)),self.assertRaises(ValueError):F.sufficient([bad])
  bad=row();bad['official_counts']['freeThrowsMade']=5
  with self.assertRaisesRegex(ValueError,'ROW_CONVERSION'):F.sufficient([bad,row()])
  peers=[row('MOCK:peer')];peers[0]['official_counts'].update(threePointersAttempted=0,threePointersMade=0)
  with self.assertRaisesRegex(ValueError,'NO_PEER_CONVERSION'):F.posterior([row()],peers)
 def test_05_mocked_actual_source_public_fit_is_create_only(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);approval=t/'MOCK_APPROVAL';approval.write_bytes(canonical(dict(kind='REVIEW_MOCK_ONLY',decided_at='2026-11-20T12:00:00+00:00')));out=t/'mock_output'
   with patch.object(F,'PREFIT_SHA',digest(approval.read_bytes())),patch.object(F,'assemble',return_value=dict(kind='REVIEW_SYNTHETIC_PAYLOAD_NO_REAL_COMPONENT_FIT')) as assemble:
    receipt=F.fit(approval_path=approval,output=out,**ARGS);self.assertEqual(assemble.call_count,1);self.assertEqual(receipt['model_raw_sha256'],digest((out/'model.json').read_bytes()));self.assertLessEqual(receipt['started_at'],receipt['completed_at']);self.assertLessEqual(receipt['completed_at'],receipt['verified_at']);self.assertFalse(receipt['release']);before={f.name:f.read_bytes() for f in out.iterdir()}
    with self.assertRaises(FileExistsError):F.fit(approval_path=approval,output=out,**ARGS)
    self.assertEqual(assemble.call_count,1);self.assertEqual(before,{f.name:f.read_bytes() for f in out.iterdir()});RESULT['mock_protocol_receipt']=receipt
 def test_06_exact_upstream_source_and_code_mutations(self):
  controls=[]
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);approval=t/'MOCK_APPROVAL';approval.write_bytes(canonical(dict(kind='REVIEW_MOCK_ONLY',decided_at='2026-11-20T12:00:00+00:00')))
   for key in ('protocol_path','old_model_path','old_admission_path'):
    dest=t/key;dest.write_bytes(ARGS[key].read_bytes()+b' ');args=dict(ARGS);args[key]=dest
    with self.subTest(key=key),patch.object(F,'PREFIT_SHA',digest(approval.read_bytes())),self.assertRaises(ValueError) as error:F.fit(approval_path=approval,output=t/(key+'_out'),**args)
    controls.append(dict(input=key,rejected=str(error.exception)))
   profile=t/'profile';profile.write_bytes(SOURCE['profile_path'].read_bytes()+b' ');args=dict(ARGS,source_inputs=dict(SOURCE,profile_path=profile))
   with patch.object(F,'PREFIT_SHA',digest(approval.read_bytes())),self.assertRaisesRegex(ValueError,'UNREVIEWED_EVIDENCE_PROFILE'):F.fit(approval_path=approval,output=t/'bad_profile',**args)
   args=dict(ARGS,original_raw_dir=t/'wrong_root')
   with patch.object(F,'PREFIT_SHA',digest(approval.read_bytes())),self.assertRaisesRegex(ValueError,'SAME_DIRECT_SOURCE'):F.fit(approval_path=approval,output=t/'wrong_root_out',**args)
   reader=ROOT/'v2/nba_architecture/conditional_c_v1.py';read=Path.read_bytes
   def changed(path):return read(path)+b' ' if path.resolve()==reader.resolve() else read(path)
   with patch.object(F,'PREFIT_SHA',digest(approval.read_bytes())),patch.object(Path,'read_bytes',new=changed),self.assertRaisesRegex(ValueError,'NATIVE_C_READER_CODE'):F.fit(approval_path=approval,output=t/'bad_code',**ARGS)
  RESULT['raw_byte_controls']=controls;RESULT['C_profile_direct_source_and_reader_code_controls']='REJECTED'
 def test_07_approval_and_completion_clock_and_readback_guards(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);approval=t/'MOCK_APPROVAL';approval.write_bytes(canonical(dict(kind='REVIEW_MOCK_ONLY',decided_at='2030-01-01T00:00:00+00:00')))
   with patch.object(F,'PREFIT_SHA',digest(approval.read_bytes())),patch.object(F,'assemble') as assemble,self.assertRaisesRegex(ValueError,'PRE_SOURCE_MODEL_OR_REVIEW_CLOCK'):F.fit(approval_path=approval,output=t/'future',**ARGS)
   assemble.assert_not_called();self.assertFalse((t/'future').exists());approval.write_bytes(canonical(dict(kind='REVIEW_MOCK_ONLY',decided_at='2026-11-20T12:00:00+00:00')))
   class Clock:
    values=iter(['2026-11-20T13:00:00+00:00','2026-11-20T12:59:59+00:00','2026-11-20T13:00:01+00:00'])
    @classmethod
    def now(cls,tz):return datetime.fromisoformat(next(cls.values))
   with patch.object(F,'PREFIT_SHA',digest(approval.read_bytes())),patch.object(F,'assemble',return_value=dict(kind='REVIEW_MOCK_ONLY')),patch.object(F,'datetime',Clock),self.assertRaisesRegex(ValueError,'FIT_CLOCK_REVERSAL'):F.fit(approval_path=approval,output=t/'badclock',**ARGS)
   self.assertFalse((t/'badclock/FIT_RECEIPT.json').exists())
   write=Path.write_bytes;target=t/'badwrite/model.json'
   def corrupt(path,raw):return write(path,raw+b' ' if path==target else raw)
   with patch.object(F,'PREFIT_SHA',digest(approval.read_bytes())),patch.object(F,'assemble',return_value=dict(kind='REVIEW_MOCK_ONLY')),patch.object(Path,'write_bytes',new=corrupt),self.assertRaisesRegex(ValueError,'PERSISTED_MODEL_BYTES'):F.fit(approval_path=approval,output=t/'badwrite',**ARGS)
   self.assertFalse((t/'badwrite/FIT_RECEIPT.json').exists())
if __name__=='__main__':
 RESULT.update(started_at=datetime.now(timezone.utc).isoformat(),compiler_raw_sha256=digest(Path(F.__file__).read_bytes()))
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Review));RESULT.update(completed_at=datetime.now(timezone.utc).isoformat(),test_methods=result.testsRun,failures=len(result.failures),errors=len(result.errors),actual_component_fits=0,new_real_model_artifacts=0,new_forecasts=0,new_J_runs=0,outcome_scores=0)
 (H/'RESULTS.json').write_text(json.dumps(RESULT,indent=2,sort_keys=True)+'\n');sys.exit(not result.wasSuccessful())
