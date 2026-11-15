#!/usr/bin/env python3
"""Consume the fixed expanded WS1 pin offline; publish a NEW immutable WS2 ledger."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v2.nfl_volume_distributions import run

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True,help='Read-only WS1 project storage root')
    parser.add_argument('--out',type=Path,required=True,help='New directory; must not exist')
    args=parser.parse_args()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=Path(__file__).resolve().parents[1],text=True).strip()
    print(json.dumps(run(args.root,args.out,commit),sort_keys=True))
