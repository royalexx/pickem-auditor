"""Public compiler source counterexample: no J parameters or fit artifacts created."""
from pathlib import Path
from types import ModuleType,SimpleNamespace
import json,re,sys,tempfile
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from scripts.nba_genuine_s import frozen_inputs
from v2.nba_joint import real_event_parameters_v1 as repaired
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.pbp_evidence_v1 import read_population
from v2.nba_s_family import model as native
P=ROOT/'docs/nba_architecture/complete_predictive_20261120';H=Path(__file__).resolve().parent;OLD=ROOT/'docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive'
parent_raw=(OLD/'forecast.json').read_bytes();parent=json.loads(parent_raw);original_inputs=dict(frozen_inputs(OLD),forecast_at=parent['forecast_at'])
replay_inputs=dict(law_snapshot_path=P/'FULL_S_CANDIDATE.json',cohort=json.loads((P/'FULL_FORECAST_COHORT.json').read_bytes()),admission_path=P/'independent_full_law/ADMISSION.json',original_inputs=original_inputs,pbp_raw_dir=P/'raw',pbp_population_path=P/'PBP_POPULATION.json',model_card_path=P/'FULL_PLAYED_MODEL_CARD.json',protocol_path=P/'independent_protocol/DECISION.json')
old=ModuleType('review_old_J_compiler');old.__file__=str(H/'OLD_COMPILER.py');exec(compile((H/'OLD_COMPILER.py').read_bytes(),old.__file__,'exec'),old.__dict__)
class ReachedOutputBeforeCompile(RuntimeError):pass
def stop():raise ReachedOutputBeforeCompile('REACHED_OUTPUT_WITH_UNREVIEWED_PBP_NO_MODEL_COMPILED')
report={}
with tempfile.TemporaryDirectory() as t:
 t=Path(t);raw=t/'raw';raw.mkdir();population=json.loads((P/'PBP_POPULATION.json').read_bytes());changed=None
 for name in population['sources']:
  d=raw/name;d.mkdir()
  for fn in ('body.raw','receipt.json'):(d/fn).symlink_to((P/'raw'/name/fn).resolve())
  if changed is None:
   b=(d/'body.raw').read_bytes();match=re.search(rb'(<script[^>]+id="__NEXT_DATA__"[^>]*>)(.*?)(</script>)',b,re.S);value=json.loads(match[2]);actions=value['props']['pageProps']['playByPlay']['actions']
   row=next((r for r in actions if r['actionType']=='Free Throw' and 'Free Throw 1 of 2' in r['description']),None)
   if row:
    before=row['description'];row['description']=before.replace('Free Throw 1 of 2','Free Throw 1 of 3',1)
    forged=b[:match.start(2)]+json.dumps(value,separators=(',',':')).encode()+b[match.end(2):]
    original_receipt=json.loads((d/'receipt.json').read_bytes());original_receipt['raw_sha256']=digest(forged);original_receipt['bytes']=len(forged)
    for fn,data in [('body.raw',forged),('receipt.json',canonical(original_receipt))]:
     path=d/fn;path.unlink();path.write_bytes(data)
    population['sources'][name]['body_sha256']=digest(forged);population['sources'][name]['receipt_sha256']=digest(canonical(original_receipt));changed=dict(game=name,action_id=row['actionId'],before=before,forged=row['description'],body_sha256=digest(forged))
 pop=t/'unreviewed_population.json';pop.write_bytes(canonical(population));facts=read_population(raw,pop,original_inputs['raw_dir']);assert facts['rejected_games']==0;assert all(r['facts']['all_credited_event_counts_reconciled'] for r in facts['rows'])
 approval=t/'review_mock_approval';approval.write_bytes(b'REVIEW_MOCK_NOT_AUTHORIZATION')
 args=dict(approval_path=approval,full_forecast_raw=(P/'actual_full_forecast/forecast.json').read_bytes(),parent_raw=parent_raw,full_replay_inputs=replay_inputs,original_raw_dir=original_inputs['raw_dir'],spec_path=original_inputs['spec_path'],policy_path=original_inputs['policy_path'],pbp_raw_dir=raw,pbp_population_path=pop,s3_path=P/'fitted_s3/three_conversion.json',s3_receipt_path=P/'fitted_s3/FIT_RECEIPT.json',s3_admission_path=P/'independent_s3_artifact/ARTIFACT_ADMISSION.json',full_admission_path=P/'independent_full_law/ADMISSION.json',j_card_path=P/'J_MODEL_CARD.json')
 proxy=SimpleNamespace(__file__=native.__file__,FittedS=native.FittedS,fit=lambda *a,**k:native.FittedS((P/'fitted_s3/three_conversion.json').read_bytes()))
 old.PREFIT_APPROVAL_SHA=digest(approval.read_bytes());old.native=proxy;old._now=stop
 try:old.fit_event_parameters(**args,output=t/'old_output')
 except ReachedOutputBeforeCompile as e:report['old_result']=str(e)
 else:raise AssertionError('old control did not reach output marker')
 assert list((t/'old_output').iterdir())==[]
 previous=repaired.PREFIT_APPROVAL_SHA;repaired.PREFIT_APPROVAL_SHA=digest(approval.read_bytes())
 try:
  try:repaired.fit_event_parameters(**args,output=t/'repaired_output')
  except ValueError as e:report['repaired_result']=str(e)
  else:raise AssertionError('repaired compiler accepted unreviewed PBP')
 finally:repaired.PREFIT_APPROVAL_SHA=previous
 assert not (t/'repaired_output').exists()
 report.update(mutation=changed,unreviewed_population_sha256=digest(pop.read_bytes()),all20_games_and14_credit_fields_reconcile=True,no_real_J_compile_performed=True,new_fit_artifacts_created=0,old_compiler_snapshot_sha256=digest((H/'OLD_COMPILER.py').read_bytes()),repaired_compiler_sha256=digest(Path(repaired.__file__).read_bytes()))
print(json.dumps(report,indent=2,sort_keys=True));(H/'SOURCE_BINDING_RESULTS.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
