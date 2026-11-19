#!/usr/bin/env python3
"""NBA default research entrypoint: supported subset, explicit abstentions."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v2.nba_architecture.research_profile_v1 import build_requests
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture-dir',type=Path,required=True);p.add_argument('--cohort',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=build_requests(a.capture_dir,json.loads(a.cohort.read_bytes()))
    with a.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','coverage')}))
