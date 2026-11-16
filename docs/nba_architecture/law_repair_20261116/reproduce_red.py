"""Fresh original-code reproduction in a separate detached worktree."""
import hashlib,json,os,pathlib,re,shutil,subprocess,tempfile
root=pathlib.Path.cwd();out=root/'docs/nba_architecture/law_repair_20261116';parent='e1983b2d0b94742dfb1bf411694dc46c7cad1ac6'
work=pathlib.Path(tempfile.mkdtemp(prefix='g0-law-rejected-'))/'checkout'
subprocess.run(['git','worktree','add','--detach',str(work),parent],check=True,capture_output=True)
try:
 source=root/'tests/nba_architecture/test_g0_law_repair_20261116.py';target=work/'tests/nba_architecture'/source.name;shutil.copyfile(source,target)
 env=os.environ.copy();env['PYTHONPATH']=str(work)+os.pathsep+str(work/'tests/nba_architecture')
 cmd=['python','-m','unittest','test_g0_law_repair_20261116.IndependentReportRegressions','test_g0_law_repair_20261116.LawCouplingControls','-v']
 result=subprocess.run(cmd,cwd=work,env=env,capture_output=True,text=True);log=result.stdout+result.stderr;(out/'red-exact-sha.log').write_text(log)
 assert result.returncode==1 and 'FAILED (failures=21)' in log and '\nERROR:' not in log,log[-3000:]
 receipt=dict(implementation_sha=parent,added_test=str(source.relative_to(root)),added_test_raw_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),command=cmd,expected_red_assertions=21,test_methods=6,unexpected_errors=0,log_sha256=hashlib.sha256(log.encode()).hexdigest(),original_baseline='baseline.log: 242/242 PASS',independent_review=False)
 (out/'red_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
finally:
 subprocess.run(['git','worktree','remove','--force',str(work)],check=True,capture_output=True)
