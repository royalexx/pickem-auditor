"""P5 research-only manual readback / dry-run; no scheduler and no collectors.

Usage:
    python -m scripts.p5_daily_research --as-of 2026-11-21T12:00:00Z
    python -m scripts.p5_daily_research --as-of ... --mode research-settle --confirm-isolated

The write mode is prohibited for operational use pending independent P6.
"""
from __future__ import annotations
import argparse
import json
import sys

from research.p5_daily.warehouse import run_morning_from_frozen_p0

def main(argv=None):
    p=argparse.ArgumentParser(description="P5 P0-ledger research only")
    p.add_argument("--as-of",required=True,
       help="UTC official observation cutoff, e.g. 2026-11-21T12:00:00Z")
    p.add_argument("--root",default="/work")
    p.add_argument("--mode",choices=("inventory","research-settle"),default="inventory")
    p.add_argument("--confirm-isolated",action="store_true")
    args=p.parse_args(argv)
    if args.mode=="research-settle" and not args.confirm_isolated:
        p.error("RESEARCH_SETTLEMENT_REQUIRES_EXPLICIT_ISOLATED_OPT_IN")
    if args.mode=="research-settle" and args.root!="/work":
        p.error("P0_STORAGE_ROOT_MUST_BE_ORIGINAL_ATTESTED_WORK")
    result=run_morning_from_frozen_p0(root=args.root,run_at=args.as_of,
       permit_research_writes=args.mode=="research-settle",update_adapters=None)
    print(json.dumps(result,sort_keys=True,indent=2,default=str))
    if any(result.get(x) for x in ("forecast_rejections","record_rejections",
                                    "official_rejections")):
        return 3
    return 0

if __name__=="__main__":
    sys.exit(main())
