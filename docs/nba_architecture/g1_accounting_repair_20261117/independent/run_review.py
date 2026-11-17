import concurrent.futures,subprocess,os,pathlib,json,hashlib,sys
out=pathlib.Path('/workspace/nba-proof/independent/exact');out.mkdir(exist_ok=False)
root=pathlib.Path('/workspace/p6-reviewed');qa=pathlib.Path('/workspace/nba-remediation');env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONPATH=str(root)+':'+str(root/'tests/nba_architecture'))
commands={
'expanded':[sys.executable,'/workspace/nba-proof/independent/expanded_matrix.py','--assembly',str(root),'--output',str(out/'expanded.json')],
'matrix':[sys.executable,str(qa/'scripts/nba_p6_raw_display_matrix_20261117.py'),'--assembly',str(root),'--output',str(out/'matrix.json')],
'public':[sys.executable,str(qa/'scripts/nba_p6_hidden_credit_rounding_adversary_20261117.py'),'--assembly',str(root),'--output',str(out/'public.json')],
'status':[sys.executable,str(qa/'scripts/nba_p6_rounding_status_alias_adversary_20261117.py'),'--assembly',str(root),'--output',str(out/'status.json')],
'architecture':[sys.executable,'-m','unittest','discover','-s','tests/nba_architecture','-v'],
'S':[sys.executable,'-m','unittest','discover','-s','tests/nba_s_family','-v'],
'C':[sys.executable,'-m','unittest','discover','-s','tests/nba_c','-v']}
def run(item):
 name,cmd=item;p=subprocess.run(cmd,cwd=root,env=env,capture_output=True)
 for kind,raw in [('stdout',p.stdout),('stderr',p.stderr)]: (out/(name+'.'+kind)).write_bytes(raw)
 return {'name':name,'command':cmd,'exit':p.returncode,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: rows=list(pool.map(run,commands.items()))
receipt={'reviewer':'/root/p6_independent','candidate_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip(),'commands':rows,'run_review_source_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'all_pass':all(x['exit']==0 for x in rows)}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
