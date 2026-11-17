import base64,copy,hashlib,importlib.util,json,subprocess
from pathlib import Path
from v2.nba_architecture.v2_contracts import canonical,seal
ROOT=Path('/workspace/work/p1_quality_control_v4')
spec=importlib.util.spec_from_file_location('v2.nba_c.qc_native_snapshot',ROOT/'p5_native_snapshot.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=json.loads((ROOT/'p1_valid_two_revision_export.json').read_text())
def reseal_revision(e):
 rev=e['revisions'][1];r=rev['record'];r=seal({k:v for k,v in r.items() if k!='content_hash'});rev['record']=r
 raw=canonical(r)+b'\n';rev['record_raw_base64']=base64.b64encode(raw).decode();rev['record_raw_sha256']=hashlib.sha256(raw).hexdigest()
 return r
results=[]
for name in ('valid_control','backdated_correction','wrong_team_correction','statistics_disagree_with_retained_official_raw','accounting_bundle_not_joined_to_record_descriptor'):
 e=copy.deepcopy(p)
 if name=='backdated_correction':
  e['revisions'][1]['record']['observed_at']='2026-11-16T18:59:59Z';reseal_revision(e)
 elif name=='wrong_team_correction':
  e['revisions'][1]['record']['team_id']='nba:team:2';r=reseal_revision(e);e['team_id']=r['team_id']
 elif name=='statistics_disagree_with_retained_official_raw':
  e['revisions'][1]['record']['stats']['points']=12;r=reseal_revision(e);e['stats']=r['stats']
 elif name=='accounting_bundle_not_joined_to_record_descriptor':
  c=e['revisions'][1]['accounting_evidence']['capture'];c['retrieved_at']='2026-11-16T21:00:00Z'
 (ROOT/(name+'.json')).write_text(json.dumps(e,indent=2)+'\n')
 try:
  m.validate_p1_export(e,outcome=True);accepted=True;error=None
 except Exception as exc:
  accepted=False;error=type(exc).__name__+':'+str(exc)
 results.append(dict(case=name,accepted=accepted,error=error))
receipt=dict(stage='PRE_P6_IMPLEMENTATION_QUALITY_CONTROL_NOT_INDEPENDENT_ACCEPTANCE',p5_base_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),p5_native_source_raw_sha256=hashlib.sha256((ROOT/'p5_native_snapshot.py').read_bytes()).hexdigest(),p1_exact_sha='a3263bc840c9973fddaaf9025358b7780d03664b',source_status='SYNTHETIC_ENGINEERING_ACTUAL_P1_EXPORT',results=results)
(ROOT/'p5_correction_integrity_red_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
