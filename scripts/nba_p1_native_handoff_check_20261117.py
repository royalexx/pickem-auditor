#!/usr/bin/env python3
"""Offline exact-head P1 verification; no fitting or historical evaluation.

Creates a fresh receipt directory and extracts immutable QA tools by exact Git
object. It does not rewrite fixtures, sources, results or past receipts.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

QA='ddc60a83f6c9a2b863f5e7a44823bffa3b01e048'
G0='59d28dc23be97de2a6a82d22be8338151e31f5b6'
PROBE_SHA='fa8012e260a21caacb2fcebadc02a2deddaf957bc4425b8128dcae2c83ba9e52'


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True)
    a=p.parse_args(argv)
    root=Path(__file__).resolve().parents[1]
    out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=root)
    head=git('rev-parse','HEAD').decode().strip()
    controls=out/'controls';controls.mkdir()
    for path in git('ls-tree','-r','--name-only',QA,'tests/nba_architecture').decode().splitlines():
        if Path(path).name.startswith('test_p6_'):
            (controls/Path(path).name).write_bytes(git('show',QA+':'+path))
    scripts=out/'qa_tools';scripts.mkdir()
    names=['nba_p6_g1_owner_negative_probes_20261116.py',
           'nba_p6_g1_remediation_adversarial_v3_20261116.py',
           'nba_p6_g1_green_after_fix_v3_20261116.py']
    for name in names:
        (scripts/name).write_bytes(git('show',QA+':scripts/'+name))
    assert hashlib.sha256((scripts/names[0]).read_bytes()).hexdigest()==PROBE_SHA
    cmds=[('architecture',[sys.executable,'-m','unittest','discover','-s','tests/nba_architecture','-v']),
          ('preflight',[sys.executable,'-m','unittest','discover','-s','tests','-p','test_nba_p1_source_preflight.py','-v']),
          ('P6_controls',[sys.executable,'-m','unittest','discover','-s',str(controls),'-v'])]
    cmds.extend((name,[sys.executable,str(scripts/name),'P1']) for name in names)
    results=[]
    for name,cmd in cmds:
        start=time.monotonic()
        r=subprocess.run(cmd,cwd=root,env=dict(os.environ,PYTHONPATH='.:tests/nba_architecture',OPENBLAS_NUM_THREADS='1'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        log=out/(name+'.log');log.write_bytes(r.stdout)
        results.append(dict(name=name,owner_sha=head,command=cmd,exit=r.returncode,
            tests=[int(n) for n in re.findall(rb'Ran (\d+) tests?',r.stdout)],
            seconds=time.monotonic()-start,log=log.name,
            raw_sha256=hashlib.sha256(r.stdout).hexdigest()))
        print(name,r.returncode,results[-1]['tests'],flush=True)
    protected=['v2/nba_architecture/v2_contracts.py','v2/nba_architecture/exposure_v2.py',
               'v2/nba_architecture/families_v2.py','tests/nba_architecture/test_v2_contracts.py']
    inherited={path:git('rev-parse',head+':'+path)==git('rev-parse',G0+':'+path) for path in protected}
    receipt=dict(schema='nba-p1-native-handoff-execution/1.0.0',owner_sha=head,
        qa_sha=QA,accepted_g0_sha=G0,inherited_g0_blobs_equal=inherited,
        original_probe_sha256=PROBE_SHA,executions=results,
        producer_source_sha256=hashlib.sha256((root/'v2/nba_architecture/p1_handoff.py').read_bytes()).hexdigest(),
        permanent_regression_sha256=hashlib.sha256((root/'tests/nba_architecture/test_p1_native_handoff_20261117.py').read_bytes()).hexdigest(),
        source_admission='BLOCKED',independent_acceptance='NOT_AWARDED_BY_OWNER',
        historical_fitting_or_evaluation_performed=False)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return int(any(r['exit'] for r in results) or not all(inherited.values()))


if __name__=='__main__':
    raise SystemExit(main())
