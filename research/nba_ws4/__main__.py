"""python -m research.nba_ws4 --help"""
import argparse
import json
from pathlib import Path
from .evaluator import append_artifact,evaluate,json_safe
from .joint_contract import validate_fixture
from .calibration import prequential


def main():
    p=argparse.ArgumentParser(description='Research-only NBA evaluator; writes a new content-addressed receipt.')
    p.add_argument('mode',choices=['evaluate','joint-fixture','calibration'])
    p.add_argument('--input',type=Path,required=True);p.add_argument('--source-root',type=Path)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();d=json.loads(a.input.read_bytes())
    if a.mode=='evaluate':
        if a.source_root is None:p.error('--source-root required for evaluate')
        result=evaluate(d['candidates'],root=a.source_root,protocol=d['protocol'])
    elif a.mode=='joint-fixture':result=validate_fixture(d['ws1'],d['ws2'],d['ws3'])
    else:result=prequential(d['rows'],policy=d['policy'])
    print(json.dumps(append_artifact(a.output_dir,'evaluation',json_safe(result)),sort_keys=True))

if __name__=='__main__':main()
