#!/usr/bin/env python3
"""Fresh finite P6 full audit. No owner implementation edits or gate acceptance.

All fits/optimizations are existing synthetic engineering fixtures. Historical
warehouse blobs are hashed opaquely only, never decompressed or scored. Fresh
Git checkouts isolate commands that generate disposable upstream/source files.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ASSEMBLY='6dee6e09fa786479dc2e163a33e14257f207b35e'
OWNER_PRS={167:'P1',165:'P2',166:'P3',164:'P4',163:'P5',171:'P0'}
QA=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser()
    for name in ('repo','work','output','pins'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();repo=a.repo.resolve();work=a.work.resolve();out=a.output.resolve()
    work.mkdir(parents=True,exist_ok=False);out.mkdir(parents=True,exist_ok=False)
    startup=json.loads(a.pins.read_bytes());pins={OWNER_PRS[x['pr']]:x['sha'] for x in startup['rows'] if x['pr'] in OWNER_PRS}
    declared=json.loads((QA/'docs/nba_architecture/g1_orchestration_v4_20261116/submission_pins_pre_p6_r2.json').read_bytes())
    assert pins==declared,'FRESH_OWNER_HEAD_DRIFT_REQUIRES_NEW_ASSEMBLY_AND_REVIEW'
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=QA).decode().strip()
    local_pins=out/'exact_owner_pins.json';local_pins.write_text(json.dumps(pins,indent=2)+'\n')
    results=[]
    def checkout(name,sha):
        target=work/name
        subprocess.run(['git','-C',str(repo),'worktree','add','--detach',str(target),sha],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=target).decode().strip()==sha
        return target
    assembly=checkout('assembly_shared',ASSEMBLY);independent=checkout('assembly_independent',ASSEMBLY);p4=checkout('P4_study',pins['P4'])
    def run(label,cmd,cwd=QA,expected=0,env_extra=None):
        env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        env.pop('PYTHONPATH',None)
        if env_extra:env.update(env_extra)
        r=subprocess.run(cmd,cwd=cwd,env=env,capture_output=True)
        for kind,raw in [('stdout',r.stdout),('stderr',r.stderr)]:
            with (out/(label+'.'+kind)).open('xb') as f:f.write(raw)
        row=dict(label=label,command=[str(v) for v in cmd],cwd=str(cwd),exit=r.returncode,expected_exit=expected,pass_check=r.returncode==expected,stdout_raw_sha256=hashlib.sha256(r.stdout).hexdigest(),stderr_raw_sha256=hashlib.sha256(r.stderr).hexdigest())
        results.append(row);print(json.dumps(row),flush=True)
        return row
    def current():
        r=run('current24',[sys.executable,str(QA/'scripts/nba_g1_pre_p6_v4_20261116.py'),'--repo',str(repo),'--pins',str(local_pins),'--work-root',str(work/'owners'),'--output',str(out/'current24')])
        if r['pass_check']:run('boundary5',[sys.executable,str(QA/'scripts/nba_g1_boundary_qc_v4_20261116.py'),'--repo',str(repo),'--pins',str(local_pins),'--owner-checkouts',str(work/'owners'),'--output',str(out/'boundary5')])
    def historical():
        run('historical32',[sys.executable,str(QA/'scripts/nba_p6_g1_reaudit_runner_v3_20261116.py'),'--repo',str(repo),'--work-root',str(work/'historical'),'--output',str(out/'historical32')])
    def shared():
        reference=json.loads((QA/'docs/nba_architecture/p6_independent_v4_20261117/final_v2/assembly_r3_checks/receipt.json').read_bytes())
        assert len(reference['commands'])==17
        rows=[]
        for item in reference['commands']:
            env={} if item['label']=='root_discovery_regression' else dict(PYTHONPATH=str(assembly)+':'+str(assembly/'tests/nba_architecture'))
            r=run('shared_'+item['label'],item['command'],assembly,env_extra=env)
            raw=(out/(r['label']+'.stdout')).read_bytes()+(out/(r['label']+'.stderr')).read_bytes()
            r['tests']=[int(x) for x in re.findall(rb'Ran (\d+) tests?',raw)]
            r['pass_check'] &= r['tests']==item['expected_tests']
            rows.append(r)
        return rows
    def new_checks():
        run('independent11',[sys.executable,str(QA/'scripts/nba_p6_independent_checks_v4_20261117.py'),'--assembly',str(independent),'--expected-assembly',ASSEMBLY,'--output',str(out/'independent11.json')])
    def study():
        env=dict(PYTHONPATH=str(p4))
        r=run('P4_actual256',[sys.executable,'-m','research.nba_p4_latest.repeated_seeds','--output',str(out/'P4_actual256')],p4,env_extra=env)
        if r['pass_check']:
            run('P4_all96',[sys.executable,'-m','research.nba_p4_latest.pool_joint_outputs','--input-dir',str(out/'P4_actual256'),'--output-dir',str(out/'P4_all96')],p4,env_extra=env)
            run('P4_reference_conditioning',[sys.executable,'-m','research.nba_p4_latest.reference_conditioning','--output',str(out/'P4_reference_conditioning.json')],p4,env_extra=env)
            run('P4_independent_pool',[sys.executable,str(QA/'scripts/nba_p6_repeated_map_reference_v4_20261117.py'),'--input',str(out/'P4_actual256'),'--output',str(out/'P4_independent_reference.json')])
    def archive():
        run('opaque_archive99',[sys.executable,str(QA/'docs/nba_architecture/p6_remediation_reaudit_v3_20261116/byte_verification_reproducer.py'),'--repo',str(repo),'--output',str(out/'opaque_archive99')])
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda fn:fn(),[current,historical,shared,new_checks,study,archive]))
    assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=assembly)
    assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=independent)
    assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=p4)
    receipt=dict(schema='NBA_P6_FRESH_FULL_BLOCKER_AUDIT_EXECUTION_20261117',qa_source_commit=source,runner_raw_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),owner_pins=pins,assembly=ASSEMBLY,commands=sorted(results,key=lambda x:x['label']),all_expected_results=all(x['pass_check'] for x in results),tracked_source_unchanged=True,synthetic_only_fitting_and_optimization=True,historical_outcome_decompression_or_scoring=False,gate_acceptance='SEPARATE_REVIEW_REPORT_REQUIRED')
    with (out/'receipt.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
    return int(not receipt['all_expected_results'])


if __name__=='__main__':raise SystemExit(main())
