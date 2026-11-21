"""P2 NHL SOG source-only runner. No model, quotes by default, or settlement.

Examples:
  python -m research.p2_nhl_sog.cli storage
  python -m research.p2_nhl_sog.cli rolling --day 2026-11-21
  python -m research.p2_nhl_sog.cli fixture ordinary_future_game
  python -m research.p2_nhl_sog.cli verify-bundle SHA256
"""
from __future__ import annotations
import argparse
import json
from .source_pipeline import (run_rolling, verify_bundle,
                              current_storage, SourceBlocked)
from .fixtures import CASES,make_case


def main(argv=None):
    p=argparse.ArgumentParser(description="NHL SOG original sources only (P2)")
    p.add_argument("--root",default="/work")
    q=p.add_subparsers(dest="command",required=True)
    rolling=q.add_parser("rolling")
    rolling.add_argument("--day",action="append")
    rolling.add_argument("--early-minutes",type=int,default=60)
    rolling.add_argument("--final-minutes",type=int,default=20)
    rolling.add_argument("--tolerance-minutes",type=int,default=5)
    rolling.add_argument("--max-games",type=int)
    q.add_parser("storage")
    bundle=q.add_parser("verify-bundle")
    bundle.add_argument("sha256")
    synthetic=q.add_parser("fixture")
    synthetic.add_argument("case",choices=CASES)
    args=p.parse_args(argv)
    if args.command=="storage":
        result=current_storage(args.root)
    elif args.command=="rolling":
        if (args.early_minutes <= args.final_minutes or
                args.final_minutes <= 0 or args.tolerance_minutes<0):
            p.error("invalid event-relative window")
        result=run_rolling(args.root,days=args.day,early_minutes=args.early_minutes,
               final_minutes=args.final_minutes,
               tolerance_minutes=args.tolerance_minutes,
               max_games=args.max_games)
    elif args.command=="verify-bundle":
        record,feature=verify_bundle(args.root,args.sha256)
        result={"schema":record["schema"],
                "source_admission":record["source_admission"],
                "p0_feature_snapshot_id":feature["feature_snapshot_id"],
                "verified_source_count":len(feature["source_receipt_ids"]),
                "model_predictions_present":False}
    else:
        result=make_case(args.case)
    print(json.dumps(result,sort_keys=True,ensure_ascii=False,default=str))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
