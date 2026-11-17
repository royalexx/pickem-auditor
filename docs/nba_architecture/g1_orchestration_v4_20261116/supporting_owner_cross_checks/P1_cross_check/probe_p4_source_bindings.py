import copy,hashlib,json,subprocess,tempfile
from pathlib import Path
from v2.nba_architecture.v2_contracts import seal
from v2.nba_joint.latest_upstream import prepare,load_upstream,FIXTURES
from v2.nba_joint import integration_v2 as j
root=prepare();p2,p3=load_upstream(root)
data=json.loads((FIXTURES/'inputs.json').read_bytes())
p=data['pregame'];manifest=data['source_manifest'];roles=data['roles']
a={k:p2.FittedS((FIXTURES/(k+'.json')).read_bytes()) for k in ('points','rebounds','assists','threes','three_conversion')}
results=[]
for case in ('valid_synthetic_control','artifact_raw_corruption','postcutoff_manifest_clock','wrong_role_identity','target_game_identity','declared_cutoff_reseal','real_mode_closed'):
 pp,mm,rr,aa=copy.deepcopy(p),copy.deepcopy(manifest),copy.deepcopy(roles),dict(a)
 mode='latest_synthetic_engineering'
 if case=='artifact_raw_corruption':aa['points']=p2.FittedS(a['points'].payload+b' ')
 elif case=='postcutoff_manifest_clock':next(iter(mm.values()))['available_at']='2099-01-01T00:00:00Z'
 elif case=='wrong_role_identity':rr[next(iter(rr))]='false_role'
 elif case=='target_game_identity':pp.pop('content_hash');pp['game_id']='espn:game:synthetic-wrong';pp=seal(pp)
 elif case=='declared_cutoff_reseal':pp.pop('content_hash');pp['training_cutoff_at']='2099-01-01T00:00:00Z';pp=seal(pp)
 elif case=='real_mode_closed':mode='real'
 try:j.validate_artifacts(pp,aa,mm,rr,evidence_mode=mode);accepted=True;error=None
 except Exception as e:accepted=False;error=str(e)
 results.append(dict(case=case,accepted=accepted,error=error))
with tempfile.TemporaryDirectory() as td:
 copied=prepare(td);path=Path(copied)/'P2/v2/nba_s_family/model.py';path.write_bytes(path.read_bytes()+b'\n')
 try:load_upstream(copied);accepted=True;error=None
 except Exception as e:accepted=False;error=str(e)
 results.append(dict(case='upstream_code_corruption',accepted=accepted,error=error))
receipt=dict(stage='PRE_P6_QUALITY_CONTROL_NO_GATE_ACCEPTANCE',p4_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_hashes={name:hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in ('v2/nba_joint/integration_v2.py','v2/nba_joint/latest_upstream.py','research/nba_p4_latest/upstream_registry.json')},results=results)
out=Path('/workspace/work/p1_quality_control_v4/p4_source_bindings_qc.json');out.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
