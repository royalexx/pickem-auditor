import pathlib,subprocess,concurrent.futures,os,json,hashlib,sys
out=pathlib.Path('/workspace/nba-proof/independent/sections');out.mkdir(exist_ok=False)
root=pathlib.Path('/workspace/p6-reviewed');script=pathlib.Path('/workspace/nba-remediation/scripts/nba_p6_independent_checks_v4_20261117.py');env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
def run(name):
 cmd=[sys.executable,str(script),'--assembly',str(root),'--expected-assembly','bafbcf2a09add125247c91c1cc8fc8d98987b5e9','--section',name,'--output',str(out/(name+'.json'))]
 r=subprocess.run(cmd,cwd=root,env=env,capture_output=True)
 for kind,raw in [('stdout',r.stdout),('stderr',r.stderr)]: (out/(name+'.'+kind)).write_bytes(raw)
 return dict(section=name,command=cmd,exit=r.returncode)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool: results=list(pool.map(run,['physical','scores','quarantine','cutoff','optimizer','native','joint','replay','incompatibility','discovery']))
(out/'receipt.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results))
