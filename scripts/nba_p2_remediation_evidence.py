#!/usr/bin/env python3
"""Reproduce P2 repair tests and raw SHA-256 receipts without source collection.
Usage: python scripts/nba_p2_remediation_evidence.py /path/to/full/git/repo
Writes evidence under docs/nba_architecture/p2_remediation_v1_1.
"""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
QA='31435bd571ae1b4a9b7f1e1bbf05e55cef61126f'
G0='59d28dc23be97de2a6a82d22be8338151e31f5b6'

def main():
    repo=Path(sys.argv[1]).resolve()
    out=ROOT/'docs/nba_architecture/p2_remediation_v1_1'
    out.mkdir(parents=True,exist_ok=True)
    commands=[('S_original_22',[sys.executable,'-m','unittest','tests.nba_s_family.test_statistical','-v']),
              ('S_all',[sys.executable,'-m','unittest','discover','-s','tests/nba_s_family','-v']),
              ('G0_regression',[sys.executable,'-m','unittest','discover','-s','tests/nba_architecture','-v']),
              ('example',[sys.executable,'scripts/nba_p2_s_family_example.py']),
              ('owner_interoperability',[sys.executable,'scripts/nba_p2_integration_check.py',str(repo)])]
    results={}
    for name,cmd in commands:
        run=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (out/(name+'.log')).write_text(run.stdout)
        results[name]={'command':cmd,'exit':run.returncode}
    with tempfile.TemporaryDirectory() as directory:
        dst=Path(directory)
        for folder in ['v2','tests']:
            shutil.copytree(ROOT/folder,dst/folder,ignore=shutil.ignore_patterns('__pycache__'))
        paths=subprocess.check_output(['git','-C',str(repo),'ls-tree','-r','--name-only',QA,'tests/nba_architecture'],text=True).splitlines()
        qa_paths=[p for p in paths if '/test_p6_' in p]
        for path in qa_paths:
            (dst/path).write_bytes(subprocess.check_output(['git','-C',str(repo),'show',QA+':'+path]))
        cmd=[sys.executable,'-m','unittest','discover','-s','tests/nba_architecture','-v']
        run=subprocess.run(cmd,cwd=dst,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (out/'G0_plus_P6.log').write_text(run.stdout)
        results['G0_plus_P6']={'command':cmd,'exit':run.returncode,'qa_sha':QA,'copied_tests':qa_paths}
    protected=['v2/nba_architecture','schemas','tests/nba_architecture']
    changed=[]
    for path in protected:
        diff=subprocess.check_output(['git','-C',str(repo),'diff',G0,'96d210a6100085640e7e82928ab1c864839fc454','--',path],text=True)
        if diff: changed.append(path)
    # Verify current working contract bytes against accepted G0 objects.
    originals={}
    for path in ['v2/nba_architecture/v2_contracts.py','v2/nba_architecture/families_v2.py']:
        expected=subprocess.check_output(['git','-C',str(repo),'show',G0+':'+path])
        assert (ROOT/path).read_bytes()==expected,path
        originals[path]=hashlib.sha256(expected).hexdigest()
    tracked=['v2/nba_s_family/model.py','v2/nba_s_family/integration.py',
             'tests/nba_s_family/test_statistical.py','tests/nba_s_family/test_integration.py',
             'scripts/nba_p2_s_family_example.py','scripts/nba_p2_integration_check.py',
             'scripts/nba_p2_remediation_evidence.py',
             'docs/nba_architecture/P2_S_INTERFACES_V1_1.md',
             'docs/nba_architecture/P2_S_FAMILY_HANDOFF_20261116.md']
    raw={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in tracked}
    for path in sorted(out.glob('*.log')):
        raw[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    upstream_raw={}
    for owner,pin,paths in [
        ('P1','e0b8703887d327c8d8ac34807078e75e7b59a540',['v2/nba_architecture/p1_history.py']),
        ('P3','80dbed35f983839f962250ad1c0236061dc6ee00',['v2/nba_o_family.py','v2/nba_opportunity.py']),
        ('P4','b3729c53509cb063e2e451b7e4feb0ac2c6a9552',['v2/nba_joint/p4.py']),
        ('P6',QA,qa_paths+['scripts/nba_p6_g1_owner_negative_probes_20261116.py'])]:
        upstream_raw[owner]={'commit':pin,'raw_sha256':{path:hashlib.sha256(subprocess.check_output(['git','-C',str(repo),'show',pin+':'+path])).hexdigest() for path in paths}}
    receipt=dict(upstream_inspected=upstream_raw,schema='nba-P2-remediation-evidence/1.1.0',parent_sha='96d210a6100085640e7e82928ab1c864839fc454',
        branch='research/nba-p2-s-family-g1-20261116',accepted_G0_sha=G0,
        python=platform.python_version(),packages={p:importlib.metadata.version(p) for p in ['numpy','scipy','jsonschema']},
        tests=results,raw_sha256=raw,G0_contract_raw_sha256=originals,
        verified_historical_training_rows=0,synthetic_only=True,
        independent_review='REQUEST_REQUIRED_AT_FINAL_COMMIT',G1='BLOCKED_SOURCE_AND_P4_ADOPTION')
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    (out/'SHA256SUMS').write_text(''.join(f'{v}  {k}\n' for k,v in sorted(raw.items())))
    print(json.dumps(results,indent=2))
    return int(any(v['exit'] for v in results.values()))
if __name__=='__main__':raise SystemExit(main())
