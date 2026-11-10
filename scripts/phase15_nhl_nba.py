#!/usr/bin/env python3
"""Read-only NHL/NBA Phase 1.5 diagnostic over a certified Phase 1 receipt.

CLI: python scripts/phase15_nhl_nba.py --phase1 RECEIPT.json
     --output NEW_RECEIPT.json

No price invention, no reforecast, no posterior training and no Tier release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from v2.contracts import ContractError
from v2.phase15_nhl_nba import diagnose
from phase15_diagnostics import power_table


def _unique(pairs):
    d={}
    for k,v in pairs:
        if k in d:raise ContractError("phase15_duplicate_json_field:"+k)
        d[k]=v
    return d


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase1",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--seed",type=int,default=20261110)
    args=p.parse_args(argv)
    if args.output.exists() or args.output.resolve()==args.phase1.resolve():
        p.error("immutable_phase15_receipt_exists_or_input_collision")
    try:
        raw=args.phase1.read_bytes()
        if not raw or len(raw)>50_000_000:
            raise ContractError("phase15_missing_or_oversized_phase1")
        data=json.loads(raw,object_pairs_hook=_unique,
                        parse_constant=lambda k:(_ for _ in ()).throw(
                            ContractError("phase15_nonfinite_json:"+k)))
        unique_games=len({(c["sport"],c["event_id"]) for c in data["contracts"]})
        mean_cluster=len(data["contracts"])/unique_games if unique_games else 1
        power=power_table(alpha=.05,target=.80,weekly=0,
                          mean_game_cluster=mean_cluster)
        report=diagnose(data,seed=args.seed,power=power)
        report["input_phase1_receipt_bytes_sha256"]=hashlib.sha256(raw).hexdigest()
        # Hash all fields except the final attached digest.
        from v2.phase15_nhl_nba import digest
        report["diagnostic_receipt_sha256"]=digest(
            {k:v for k,v in report.items() if k!="diagnostic_receipt_sha256"})
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open("x",encoding="utf8") as fh:
            json.dump(report,fh,indent=2,sort_keys=True,allow_nan=False)
            fh.write("\n")
        print(json.dumps({
            "output":str(args.output),"sha256":report["diagnostic_receipt_sha256"],
            "cohort_contracts":report["contracts"],
            "scored":report["actual_scored_contracts"],
            "decision":report["investment_decision"],
            "gate_B":report["gates"]["B_directional_accuracy"]["status"],
            "gate_C":report["gates"]["C_opportunity_error"]["status"],
            "promotion_authorized":False,
        },sort_keys=True))
        return 0
    except (OSError,ValueError,TypeError,KeyError,OverflowError) as exc:
        print("PHASE15_NHL_NBA_REJECTED "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
