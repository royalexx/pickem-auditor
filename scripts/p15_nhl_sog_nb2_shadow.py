#!/usr/bin/env python3
"""Generate one append-only pre-event NHL SOG fixed-NB2 shadow manifest.

This script does not call a statistical trainer, alter production forecasts,
or certify a player's participation. It reads original Phase1 pregame
inputs and independent official roster bytes, then freezes its own receipt.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v2.phase15_nb2_shadow import build_prospective_shadow


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase1",type=Path,required=True)
    p.add_argument("--roster-manifest",type=Path,required=True)
    p.add_argument("--roster-root",type=Path,required=True)
    p.add_argument("--experiment-spec",type=Path,required=True)
    p.add_argument("--code-commit",required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    if args.output.exists() or args.output.resolve() in (
            args.phase1.resolve(),args.roster_manifest.resolve(),
            args.experiment_spec.resolve()):
        p.error("append_only_output_required")
    try:
        phase1_raw=args.phase1.read_bytes()
        report=build_prospective_shadow(
            phase1=json.loads(phase1_raw),
            phase1_bytes_sha256=hashlib.sha256(phase1_raw).hexdigest(),
            roster_manifest=json.loads(args.roster_manifest.read_bytes()),
            roster_root=args.roster_root,
            model_revision=args.code_commit,
            now=datetime.now(timezone.utc),
            experiment_spec=json.loads(args.experiment_spec.read_bytes()),
        )
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open("x",encoding="utf8") as f:
            json.dump(report,f,sort_keys=True,indent=2,allow_nan=False)
            f.write("\n")
        print(json.dumps({
          "schema":report["schema"],"output":str(args.output),
          "original_NHL_contracts":report["NHL_original_contracts"],
          "shadow_accepted":report["NHL_shadow_accepted"],
          "attempt_exclusions":report["NHL_shadow_attempt_status"],
          "receipt_sha256":hashlib.sha256(args.output.read_bytes()).hexdigest(),
          "promotion_allowed":False,
        },sort_keys=True))
        return 0 if report["NHL_shadow_accepted"] else 2
    except (ValueError,TypeError,OSError,KeyError) as exc:
        print("PROSPECTIVE_NB2_SHADOW_BLOCKED "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
