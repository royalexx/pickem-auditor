#!/usr/bin/env python3
"""Reproduce independent exact-head P6 v3 suites without owner implementation edits.

Supply a full Git object database and fresh disposable work/output directories.
The known RED P2/P5 tests remain RED; expected outcomes are verified separately.
No retrospective forecast evaluation or real model-weight fitting is invoked.
"""
import argparse,concurrent.futures,hashlib,json,os,re,subprocess,sys
from pathlib import Path

PINS={
 'P1':'201ff0aacbd398c7a260f1af3b1c16f4dd8abaa3',
 'P2':'7ca4269c98a27def485eaa8122ea7148cd0c2c0a',
 'P3':'191b3f654b3a3ca7dc813edbfc9aacdf35729dff',
 'P4':'cf5483a16279b8af606caef415e9abacc8c41aab',
 'P5':'e46abacecc4f3147aa28d5351515aeca07c17f48'}
OLD={'P1':'e0b8703887d327c8d8ac34807078e75e7b59a540','P2':'96d210a6100085640e7e82928ab1c864839fc454','P5':'1d7b8471a85e9d3dafaf809acacfeca6e980dc81'}
UPSTREAM=[('WS1','53c01a9eabb9ed09b5c3186eae0d086b07bcc891',['-s','tests/nba_ws1']),('WS2','02426dd1b9c2b0cca28eaf69888adadc0021afa5',['-s','tests','-p','test_nba_opportunity.py']),('WS4','9821694260edb08b7414f02adea8c1fb3fd3b13c',['-s','tests/nba_ws4']),('WS5','cdf926f56e86bc9d25576acff61fd6f091313159',['-s','tests','-p','test_nba_joint*.py'])]
QA_PIN='31435bd571ae1b4a9b7f1e1bbf05e55cef61126f'
G0='59d28dc23be97de2a6a82d22be8338151e31f5b6'

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--work-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
 repo=args.repo.resolve();work=args.work_root.resolve();out=args.output.resolve();work.mkdir(parents=True,exist_ok=False);out.mkdir(parents=True,exist_ok=False)
 scripts=Path(__file__).resolve().parent;controls=work/'controls';controls.mkdir();results=[]
 def git(*argv):return subprocess.check_output(['git','-C',str(repo),*argv])
 for p in git('ls-tree','-r','--name-only',QA_PIN,'tests/nba_architecture').decode().splitlines():
  if Path(p).name.startswith('test_p6_'): (controls/Path(p).name).write_bytes(git('show',QA_PIN+':'+p))
 probe=scripts/'nba_p6_g1_owner_negative_probes_20261116.py';assert hashlib.sha256(probe.read_bytes()).hexdigest()=='fa8012e260a21caacb2fcebadc02a2deddaf957bc4425b8128dcae2c83ba9e52'
 def checkout(name,sha):
  root=work/name;subprocess.run(['git','-C',str(repo),'worktree','add','--detach',str(root),sha],check=True,stdout=subprocess.DEVNULL)
  assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip()==sha
  return root
 def run(root,label,cmd,expected=0):
  env=dict(os.environ,PYTHONPATH=f'{root}:{root}/tests/nba_architecture',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
  r=subprocess.run(cmd,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);log=out/(label+'.log');log.write_bytes(r.stdout)
  row=dict(label=label,owner_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip(),command=cmd,exit=r.returncode,expected_exit=expected,expectation_met=r.returncode==expected,tests=[int(x) for x in re.findall(rb'Ran (\d+) tests?',r.stdout)],sha256=hashlib.sha256(r.stdout).hexdigest());expected_counts={'P1_G0_owner':[331],'P2_G0_owner':[267],'P3_G0_owner':[306],'P4_G0_owner':[321],'P5_G0_owner':[267],'P1_preflight':[9],'P2_family':[30],'P5_family':[48],'P4_pinned_upstream':[321,83,16,22],'WS1':[25],'WS2':[25],'WS4':[33],'WS5':[63]}
  if label.endswith('_P6'): expected_counts[label]=[83]
  if label in expected_counts: row['expectation_met'] &= row['tests']==expected_counts[label]
  if label.endswith('_adversarial_v3'):
   d=json.loads(r.stdout);failures=[c['case'] for c in d['cases'] if c['status']=='FAIL']
   exact={'P2_adversarial_v3':['conditional_S_to_J_must_honor_P_training_cutoff_not_just_freeze'],'P5_adversarial_v3':['nested_target_result_and_actual_minutes_in_forecast_pipeline']}.get(label,[])
   row['observed_red_cases']=failures;row['expectation_met'] &= failures==exact
  results.append(row);print(json.dumps(row),flush=True);return r
 def family(name):
  root=checkout(name,PINS[name]);run(root,name+'_G0_owner',[sys.executable,'-m','unittest','discover','-s','tests/nba_architecture','-v']);run(root,name+'_P6',[sys.executable,'-m','unittest','discover','-s',str(controls),'-v'])
  if name=='P1':run(root,name+'_preflight',[sys.executable,'-m','unittest','discover','-s','tests','-p','test_nba_p1_source_preflight.py','-v'])
  if name in ('P2','P5'):run(root,name+'_family',[sys.executable,'-m','unittest','discover','-s','tests/nba_s_family' if name=='P2' else 'tests/nba_c','-v'])
  run(root,name+'_adversarial_v3',[sys.executable,str(scripts/'nba_p6_g1_remediation_adversarial_v3_20261116.py'),name],2 if name in ('P2','P5') else 0)
  if name in OLD:
   run(root,name+'_historical_probe',[sys.executable,str(probe),name]);run(root,name+'_green_after_fix',[sys.executable,str(scripts/'nba_p6_g1_green_after_fix_v3_20261116.py'),name])
   oldroot=checkout('old_'+name,OLD[name]);run(oldroot,name+'_before_probe',[sys.executable,str(probe),name],0 if name=='P2' else 2)
  if name=='P4':run(root,'P4_pinned_upstream',[sys.executable,'-m','research.nba_p4_integration.checks'])
 with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(family,PINS))
 for name,sha,selection in UPSTREAM:
  root=checkout(name,sha);run(root,name,[sys.executable,'-m','unittest','discover',*selection,'-v'])
 (out/'runner_results.json').write_text(json.dumps(results,indent=2)+'\n')
 return int(not all(r['expectation_met'] for r in results))
if __name__=='__main__':raise SystemExit(main())
