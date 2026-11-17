#!/usr/bin/env python3
"""Exact-commit implementation QC. This runner awards no independent acceptance.

Every model/optimizer fixture run here is synthetic engineering. The accepted
upstream suites were separately reexecuted at their immutable pins in the v3
baseline reproduction. This runner checks the submitted current owners.
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

G0='59d28dc23be97de2a6a82d22be8338151e31f5b6'
AUDIT='ddc60a83f6c9a2b863f5e7a44823bffa3b01e048'
PROBE_SHA='fa8012e260a21caacb2fcebadc02a2deddaf957bc4425b8128dcae2c83ba9e52'

def main():
    ap=argparse.ArgumentParser()
    for name in ('repo','pins','work-root','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    args=ap.parse_args();repo=args.repo.resolve();work=args.work_root.resolve();out=args.output.resolve()
    pins=json.loads(args.pins.read_text())
    work.mkdir(parents=True,exist_ok=False);out.mkdir(parents=True,exist_ok=False)
    def git(*v):return subprocess.check_output(['git','-C',str(repo),*v])
    controls=work/'independent_prior_controls';controls.mkdir()
    for p in git('ls-tree','-r','--name-only',AUDIT,'tests/nba_architecture').decode().splitlines():
        if Path(p).name.startswith('test_p6_'):
            (controls/Path(p).name).write_bytes(git('show',AUDIT+':'+p))
    scripts=Path(__file__).resolve().parent
    assert hashlib.sha256((scripts/'nba_p6_g1_owner_negative_probes_20261116.py').read_bytes()).hexdigest()==PROBE_SHA
    rows=[];comparisons=[]
    def run(root,label,cmd):
        env=dict(os.environ,PYTHONPATH=f'{root}:{root}/tests/nba_architecture',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        r=subprocess.run(cmd,cwd=root,env=env,capture_output=True)
        raw=r.stdout+r.stderr;log=out/(label+'.log');log.write_bytes(raw)
        row=dict(label=label,owner_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip(),command=cmd,exit=r.returncode,tests=[int(x) for x in re.findall(rb'Ran (\d+) tests?',raw)],log=log.name,raw_sha256=hashlib.sha256(raw).hexdigest(),pass_check=r.returncode==0)
        family=label.split('_')[0]
        if label.endswith('_architecture'):
            floor={'P1':331,'P2':267,'P3':306,'P4':321,'P5':267}[family]
            row['pass_check'] &= len(row['tests'])==1 and row['tests'][0]>=floor
        if label.endswith('_prior_P6'):
            row['pass_check'] &= row['tests']==[83]
        if label.endswith('_family'):
            floor={'P2':30,'P5':48}[family]
            row['pass_check'] &= len(row['tests'])==1 and row['tests'][0]>=floor
        row['tracked_source_unchanged']=subprocess.run(['git','diff','--quiet','HEAD'],cwd=root).returncode==0
        row['pass_check'] &= row['tracked_source_unchanged']
        row['pass_check'] &= not bool(re.search(rb'OK \(.*(?:skipped|expected failures)',raw))
        rows.append(row);print(json.dumps(row),flush=True)
        return row
    def family(name):
        sha=pins[name];root=work/name
        subprocess.run(['git','-C',str(repo),'worktree','add','--detach',str(root),sha],check=True,stdout=subprocess.DEVNULL)
        assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip()==sha
        inherited=[]
        for p in git('ls-tree','-r','--name-only',G0,'v2/nba_architecture','tests/nba_architecture').decode().splitlines():
            expected=git('show',G0+':'+p);actual=(root/p).read_bytes()
            inherited.append(dict(path=p,raw_sha256=hashlib.sha256(actual).hexdigest(),match=actual==expected))
        changed=git('diff','--name-status',G0,sha).decode()
        comparisons.append(dict(owner=name,sha=sha,g0_inherited=inherited,changed_paths=changed))
        run(root,name+'_architecture',[sys.executable,'-m','unittest','discover','-s','tests/nba_architecture','-v'])
        run(root,name+'_prior_P6',[sys.executable,'-m','unittest','discover','-s',str(controls),'-v'])
        if name in ('P2','P5'):
            run(root,name+'_family',[sys.executable,'-m','unittest','discover','-s','tests/nba_s_family' if name=='P2' else 'tests/nba_c','-v'])
        if name=='P1':
            run(root,name+'_preflight',[sys.executable,'-m','unittest','discover','-s','tests','-p','test_nba_p1_source_preflight.py','-v'])
        if name in ('P1','P2','P5'):
            run(root,name+'_original_probe',[sys.executable,str(scripts/'nba_p6_g1_owner_negative_probes_20261116.py'),name])
            run(root,name+'_preserved_green',[sys.executable,str(scripts/'nba_p6_g1_green_after_fix_v3_20261116.py'),name])
        run(root,name+'_adversarial_v3',[sys.executable,str(scripts/'nba_p6_g1_remediation_adversarial_v3_20261116.py'),name])
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(family,('P1','P2','P3','P4','P5')))
    result=dict(schema='NBA_G1_PRE_P6_QC_V4',independent_acceptance=False,runner_raw_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),qa_code_commit=git('rev-parse','HEAD').decode().strip(),pins=pins,commands=sorted(rows,key=lambda x:x['label']),comparisons=sorted(comparisons,key=lambda x:x['owner']),all_commands_pass=all(x['pass_check'] for x in rows),g0_intact=all(x['match'] for r in comparisons for x in r['g0_inherited']))
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    return int(not(result['all_commands_pass'] and result['g0_intact']))

if __name__=='__main__':raise SystemExit(main())
