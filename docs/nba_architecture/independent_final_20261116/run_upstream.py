import subprocess, pathlib, json, sys
repo='/workspace/pickem-auditor'
out=pathlib.Path('/workspace/nba-g0/docs/nba_architecture/independent_final_20261116')
results=[]
for label,sha,args in [('WS1','53c01a9eabb9ed09b5c3186eae0d086b07bcc891',['-s','tests/nba_ws1']),('WS2','02426dd1b9c2b0cca28eaf69888adadc0021afa5',['-s','tests','-p','test_nba_opportunity.py']),('WS4','9821694260edb08b7414f02adea8c1fb3fd3b13c',['-s','tests/nba_ws4']),('WS5','cdf926f56e86bc9d25576acff61fd6f091313159',['-s','tests','-p','test_nba_joint*.py'])]:
 path='/workspace/upstream-'+label
 subprocess.run(['git','-C',repo,'worktree','add','--detach',path,sha],check=True,capture_output=True)
 cmd=[sys.executable,'-m','unittest','discover']+args+['-v']
 r=subprocess.run(cmd,cwd=path,capture_output=True,text=True)
 (out/(label+'.log')).write_text(r.stdout+r.stderr)
 results.append(dict(label=label,sha=sha,command=cmd,exit=r.returncode,summary=r.stderr.splitlines()[-5:]))
(out/'upstream.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
