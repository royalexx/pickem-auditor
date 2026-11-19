#!/usr/bin/env python3
"""Opt-in source-only replacement for lexical report selection; no gate upgrade."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v2.nba_architecture.p1_injury_report_v2 import capture_latest
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze-at',required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    result=capture_latest(freeze_at=a.freeze_at,output=a.output)
    print(json.dumps({'status':result['status'],'errors':result['errors'],'selected_url':result.get('selection',{}).get('selected_url')}))
    raise SystemExit(0 if result['status']=='CAPTURED_BOUNDED_UNADMITTED' else 2)
