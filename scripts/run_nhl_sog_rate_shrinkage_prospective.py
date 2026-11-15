#!/usr/bin/env python3
"""Research-only Phase 5.1 S1 original-source native capture, fail closed.

Never synthesizes source or backdates forecast time. Runs only after an actual
signed C03 same-date batch exists; logs unavailable data as explicit abstentions.
No scheduling or trusted publication.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v2.nhl_sog_rate_shrinkage_prospective import run_day, S1Blocked

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root",type=Path,required=True)
    p.add_argument("--code-commit",required=True)
    a=p.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}",a.code_commit):
        print("PHASE51_S1_BLOCKED UNPINNED_GIT_SHA",file=sys.stderr)
        return 2
    try:
        result=run_day(a.project_root,code_sha=a.code_commit)
    except (S1Blocked,KeyError,ValueError,TypeError,OSError) as exc:
        print("PHASE51_S1_BLOCKED "+type(exc).__name__+":"+str(exc)[:200],
              file=sys.stderr)
        return 2
    print("PHASE51_S1_CAPTURE "+json.dumps(result,sort_keys=True,allow_nan=False))
    return 0 if result["counts"]["FROZEN_S1_M0_M2_RESEARCH"]>0 else 2

if __name__=="__main__":
    raise SystemExit(main())
