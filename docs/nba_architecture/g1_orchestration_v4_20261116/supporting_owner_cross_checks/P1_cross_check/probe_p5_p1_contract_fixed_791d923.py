import base64,copy,hashlib,importlib.util,json,subprocess
from pathlib import Path
from v2.nba_architecture.v2_contracts import canonical,seal
ROOT=Path('/workspace/work/p1_quality_control_v4')
spec=importlib.util.spec_from_file_location('v2.nba_c.qc_repair_snapshot',ROOT/'p5_native_fixed_791d923.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=json.loads((ROOT/'p1_valid_two_revision_export.json').read_text());p['revisions']=p['revisions'][:1];p['correction_version']=1

def finish(e):
 rev=e['revisions'][0];r=rev['record'];r=seal({k:v for k,v in r.items() if k!='content_hash'});rev['record']=r
 raw=canonical(r)+b'\n';rev['record_raw_base64']=base64.b64encode(raw).decode();rev['record_raw_sha256']=hashlib.sha256(raw).hexdigest()
 for dest,src in (('participation','state'),('stats','stats'),('displayed_minutes','minutes'),('vault_schema','schema'),('team_id','team_id')):e[dest]=r[src]
 return e
results=[]
for name in ('valid_control','unsupported_vault_state','unsupported_vault_schema','unsupported_vault_kind','raw_shooting_accounting_impossible'):
 e=copy.deepcopy(p);rev=e['revisions'][0];r=rev['record']
 if name=='unsupported_vault_state':r['state']='FAKE';r['minutes']=None;r['stats']={};e['exact_minutes']=None
 elif name=='unsupported_vault_schema':r['schema']='arbitrary-vault/9000'
 elif name=='unsupported_vault_kind':r['kind']='not_an_official_outcome'
 elif name=='raw_shooting_accounting_impossible':
  node=rev['accounting_evidence'];game=json.loads(base64.b64decode(node['raw_base64']));game['game']['homeTeam']['players'][0]['statistics']['fieldGoalsMade']=1
  raw=canonical(game);sha=hashlib.sha256(raw).hexdigest();node['capture']['raw_sha256']=sha;node['raw_base64']=base64.b64encode(raw).decode()
  r['accounting_evidence']['capture']['raw_sha256']=sha;r['source_raw_sha256']=sha
  rev['source_raw_sha256']=sha;rev['source_raw_base64']=base64.b64encode(raw).decode();r['stats']['fgm']=1
 finish(e)
 (ROOT/(name+'_p5_contract_fixed_791d923_probe.json')).write_text(json.dumps(e,indent=2)+'\n')
 try:m.validate_p1_export(e,outcome=True);accepted=True;error=None
 except Exception as ex:accepted=False;error=type(ex).__name__+':'+str(ex)
 results.append(dict(case=name,accepted=accepted,error=error))
receipt=dict(stage='PRE_P6_QC_NO_INDEPENDENT_ACCEPTANCE',p5_git_base=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),p5_raw_source_sha256=hashlib.sha256((ROOT/'p5_native_fixed_791d923.py').read_bytes()).hexdigest(),snapshot_may_be_uncommitted=True,results=results)
(ROOT/'p5_p1_contract_fixed_791d923_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
