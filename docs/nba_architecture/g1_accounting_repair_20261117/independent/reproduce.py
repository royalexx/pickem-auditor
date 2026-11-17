#!/usr/bin/env python3
"""Portable independent repair regression: synthetic inputs only."""
import argparse,concurrent.futures,hashlib,json,os,pathlib,subprocess,sys
p=argparse.ArgumentParser();p.add_argument('--candidate',type=pathlib.Path,required=True);p.add_argument('--audit',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--include-suites',action='store_true');a=p.parse_args()
root=a.candidate.resolve();audit=a.audit.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip()=='bafbcf2a09add125247c91c1cc8fc8d98987b5e9'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=audit).decode().strip()=='b7ca2899ab8d902cda62bfb802ab74dcb5598a30'
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONPATH=str(root)+':'+str(root/'tests/nba_architecture'))
commands={'expanded':[sys.executable,str(pathlib.Path(__file__).with_name('expanded_matrix.py')),'--assembly',str(root),'--output',str(out/'expanded.json')]}
for name,file in [('matrix','raw_display_matrix'),('public','hidden_credit_rounding_adversary'),('status','rounding_status_alias_adversary')]:
 commands[name]=[sys.executable,str(audit/f'scripts/nba_p6_{file}_20261117.py'),'--assembly',str(root),'--output',str(out/(name+'.json'))]
if a.include_suites:
 for name,path in [('architecture','nba_architecture'),('S','nba_s_family'),('C','nba_c')]:commands[name]=[sys.executable,'-m','unittest','discover','-s',f'tests/{path}','-v']
def run(item):
 name,cmd=item;r=subprocess.run(cmd,cwd=root,env=env,capture_output=True)
 for kind,raw in [('stdout',r.stdout),('stderr',r.stderr)]: (out/(name+'.'+kind)).write_bytes(raw)
 return dict(label=name,command=cmd,exit=r.returncode,stdout_sha256=hashlib.sha256(r.stdout).hexdigest(),stderr_sha256=hashlib.sha256(r.stderr).hexdigest())
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: rows=list(pool.map(run,commands.items()))
receipt=dict(schema='NBA_P6_PORTABLE_REPAIR_REVIEW_V1',candidate='bafbcf2a09add125247c91c1cc8fc8d98987b5e9',audit_source='b7ca2899ab8d902cda62bfb802ab74dcb5598a30',commands=rows,source_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),all_pass=all(x['exit']==0 for x in rows))
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt));sys.exit(not receipt['all_pass'])
