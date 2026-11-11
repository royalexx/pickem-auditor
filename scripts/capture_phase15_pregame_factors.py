#!/usr/bin/env python3
"""Append-only optional PRE-GAME Phase1.5 NHL/NBA factor shadow receipt.

Input must contain real producer-supplied pregame numeric factors and source
files; this command never computes/mints absent components from past results.
Runs on next slate only, never retroactively from Nov 10 final box scores.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v2.phase15_pregame_factors import make_shadow_receipt
from v2.official_nba_nhl_capture import SettlementCaptureError


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--source-root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args(argv)
    if a.output.exists() or a.output.resolve()==a.input.resolve():
        p.error("new_output_required_no_retroactive_overwrite")
    try:
        raw=json.loads(a.input.read_text(encoding="utf8"))
        now=datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00","Z")
        result=make_shadow_receipt(raw,source_root=a.source_root,observed_clock=now)
        a.output.parent.mkdir(parents=True,exist_ok=True)
        with a.output.open("x",encoding="utf8") as out:
            json.dump(result,out,sort_keys=True,indent=2,allow_nan=False)
            out.write("\n")
        print(json.dumps({"output":str(a.output),"receipt_sha256":result["receipt_sha256"],
                 "sport":result["sport"],"stat":result["stat"],
                 "production_promotion_allowed":False},sort_keys=True))
        return 0
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print("OPPORTUNITY_FACTOR_CAPTURE_BLOCKED "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":raise SystemExit(main())
