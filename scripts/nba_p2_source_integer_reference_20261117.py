#!/usr/bin/env python3
"""Synthetic integer-source references; refuses to overwrite output receipts."""
import argparse
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tests.nba_s_family.test_source_accounting_v1 import shooting_reference,combo_reference
from v2.nba_s_family.source_accounting import validate_count_feasibility
from v2.nba_s_family.model import SFError


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--p1-sha',required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();assert re.fullmatch('[0-9a-f]{40}',args.p1_sha)
    args.output.mkdir(parents=True,exist_ok=False)
    p1path='v2/nba_architecture/p1_integer_accounting.py'
    raw=subprocess.check_output(['git','-C',str(args.repo),'show',args.p1_sha+':'+p1path])
    rng=random.Random(14817);cases=[];failures=[]
    result=dict(scope='SYNTHETIC_SUPPORTING_QC_NOT_INDEPENDENT_GATE_ACCEPTANCE',P1=args.p1_sha,
        P1_source_sha256=hashlib.sha256(raw).hexdigest(),P2=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
        P2_source_sha256=hashlib.sha256((ROOT/'v2/nba_s_family/source_accounting.py').read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),seed=14817)
    try:
        result['exhaustive_shooting']=shooting_reference();result['exhaustive_combinations']=combo_reference()
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'p1.py';p.write_bytes(raw);spec=importlib.util.spec_from_file_location('p1_integer_reference',p)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            for i in range(5000):
                fga=rng.randrange(6);a3=rng.randrange(fga+1);t=rng.randrange(a3+1);two=rng.randrange(fga-a3+1)
                fta=rng.randrange(6);ftm=rng.randrange(fta+1);oreb=rng.randrange(5);dreb=rng.randrange(5);ast=rng.randrange(5)
                whole=dict(points=2*two+3*t+ftm,fgm=two+t,fga=fga,threes=t,fg3a=a3,ftm=ftm,fta=fta,rebounds=oreb+dreb,oreb=oreb,dreb=dreb,assists=ast)
                whole.update(pr=whole['points']+whole['rebounds'],pa=whole['points']+ast,ra=whole['rebounds']+ast,pra=whole['points']+whole['rebounds']+ast)
                subset={k:v for k,v in whole.items() if rng.random()<.5}
                if subset and i%2:
                    k=rng.choice(list(subset));subset[k]=max(0,subset[k]+rng.choice([-1,1]))
                p1=module.partial_counts_feasible(subset)
                try:p2=validate_count_feasibility(subset)
                except SFError as exc:
                    if exc.reason!='P1_NATIVE_INTEGER_ACCOUNTING_INFEASIBLE':raise
                    p2=False
                row=dict(input=subset,P1=p1,P2=p2);cases.append(row)
                if p1!=p2:failures.append(row)
        result.update(cases=len(cases),failures=failures,status='PASS_FINITE_ENGINEERING_COMPARISON' if not failures else 'FAIL')
    except BaseException as exc:
        result.update(status='FAILED_EXECUTION',error=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
    data=json.dumps(cases,sort_keys=True,indent=2)+'\n';(args.output/'cases.json').write_text(data)
    result['case_input_output_raw_sha256']=hashlib.sha256(data.encode()).hexdigest()
    (args.output/'result.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True,indent=2));return int(result['status']!='PASS_FINITE_ENGINEERING_COMPARISON')*2

if __name__=='__main__':raise SystemExit(main())
