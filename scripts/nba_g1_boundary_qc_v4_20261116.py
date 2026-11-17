#!/usr/bin/env python3
"""Separate the blocked authentic case from exact-owner synthetic compatibility."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    p=argparse.ArgumentParser()
    for k in ('repo','pins','owner-checkouts','output'):
        p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();repo=a.repo.resolve();roots=a.owner_checkouts.resolve();out=a.output.resolve()
    out.mkdir(parents=True,exist_ok=False);pins=json.loads(a.pins.read_text());results=[]
    for name in ('P1','P2','P3','P4','P5'):
        actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=roots/name).decode().strip()
        assert actual==pins[name],(name,actual)
    def run(owner,label,cmd,expected=0):
        r=subprocess.run(cmd,cwd=roots/owner,capture_output=True,env=dict(os.environ,PYTHONPATH=f'{roots/owner}:{roots/owner}/tests/nba_architecture',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
        for kind,raw in [('stdout',r.stdout),('stderr',r.stderr)]:(out/(label+'.'+kind)).write_bytes(raw)
        row=dict(owner=owner,owner_sha=pins[owner],label=label,command=cmd,exit=r.returncode,stdout_raw_sha256=hashlib.sha256(r.stdout).hexdigest(),stderr_raw_sha256=hashlib.sha256(r.stderr).hexdigest(),pass_check=r.returncode==expected)
        results.append(row);print(json.dumps(row),flush=True);return r,row
    target=out/'authentic_pregame_snapshot.json'
    r,row=run('P1','authentic_first_boundary',[sys.executable,'scripts/nba_p1_build_pregame.py','--input','docs/nba_architecture/p1_remediation_20261117/real_ws1_manifest.json','--output',str(target),'--source-root','docs/nba_architecture/p1_remediation_20261117','--require-official-evidence'],2)
    row['pass_check']=r.returncode!=0 and b'OFFICIAL_SOURCE_EVIDENCE_REQUIRED' in r.stdout+r.stderr and not target.exists()
    row['disposition']='BLOCKED_AT_P1_OFFICIAL_SOURCE_ADMISSION_BEFORE_G'
    if not row['pass_check']:raise RuntimeError('AUTHENTIC_BOUNDARY_CHANGED_REQUIRES_INSPECTION')
    # These are independent synthetic engineering cases. The authentic case
    # above never proceeds to G/O/S/J/C and never receives fabricated inputs.
    commands=[
        ('P2','synthetic_latest_P1_P3_to_P2',[sys.executable,'scripts/nba_p2_latest_interop_v1_2.py','--repo',str(repo),'--p1-sha',pins['P1'],'--p3-sha',pins['P3']]),
        ('P3','synthetic_latest_P1_to_P3',[sys.executable,'scripts/nba_p3_native_handoff_check_v4_20261116.py','--p1-root',str(roots/'P1'),'--output',str(out/'P3_native_output')]),
        ('P5','synthetic_latest_owner_native_C',[sys.executable,'scripts/nba_p5_native_handoff_verify_v1.py','--repo',str(repo),'--p1-sha',pins['P1'],'--p2-sha',pins['P2'],'--p3-sha',pins['P3'],'--p4-sha',pins['P4'],'--output',str(out/'P5_native_output')]),
        ('P4','synthetic_independent_analytical_reference',[sys.executable,'-m','research.nba_p4_latest.numerical_reference']),
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda x:run(*x),commands))
    receipt=dict(schema='NBA_G1_BOUNDARY_PRE_P6_QC_V4',independent_acceptance=False,pins=pins,authentic_stopped_before_G=True,synthetic_cases_are_separate=True,commands=results,all_expected_results=all(x['pass_check'] for x in results))
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return int(not receipt['all_expected_results'])

if __name__=='__main__':raise SystemExit(main())
