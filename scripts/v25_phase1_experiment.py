#!/usr/bin/env python3
"""One-command, deterministic Phase 1 baseline and frozen-snapshot evaluation.

Runs research in isolation. Historical rolling baselines are counterfactual,
NOT newly forged original pregame forecasts. Existing V1 snapshots remain
immutable. Never overwrites an experiment receipt or changes production.
Example:
  python scripts/v25_phase1_experiment.py --input examples/v25_phase1_synthetic_fixture.json --output reports/v25_phase1_example.json --code-commit <actual_sha>
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v2.contracts import ContractError
from v2.experiment import run_experiment


def _no_duplicate_fields(pairs):
    out={}
    for key,value in pairs:
        if key in out:
            raise ContractError("duplicate_json_key:"+key)
        out[key]=value
    return out


def _read_json(path: Path):
    raw=path.read_bytes()
    if not raw or len(raw)>128*1024*1024:
        raise ContractError("missing_or_oversized_experiment_input")
    obj=json.loads(raw,object_pairs_hook=_no_duplicate_fields,
                   parse_constant=lambda value: (_ for _ in ()).throw(
                       ContractError("nonfinite_json:"+value)))
    return obj,hashlib.sha256(raw).hexdigest()


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--protocol",type=Path,default=Path(__file__).resolve().parents[1]/
                   "config/experiment_specs/v25_rolling_2024.json")
    p.add_argument("--code-commit",required=True,
                   help="exact 40-char Git SHA of the implementation used")
    p.add_argument("--seed",type=int,default=20261109)
    p.add_argument("--original-archive-root",type=Path,default=None,
                   help="optional real Phase 0R source root for frozen V1 eligibility")
    args=p.parse_args(argv)
    if args.output.exists() or args.output.resolve() in (args.input.resolve(),args.protocol.resolve()):
        p.error("immutable_experiment_receipt_already_exists_or_input_is_output")
    try:
        payload,input_sha=_read_json(args.input)
        protocol,protocol_sha=_read_json(args.protocol)
        checker=None
        if "legacy_originals" in payload and args.original_archive_root is not None:
            # This imports the authenticated production Phase 0R validator only.
            # Never replace it with a permissive checker when unavailable.
            try:
                sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
                from phase0r_contract import strict_snapshot_status
                checker=strict_snapshot_status
            except ImportError:
                checker=None
        result=run_experiment(payload,protocol,
                              input_sha256=input_sha,
                              protocol_sha256=protocol_sha,
                              code_commit=args.code_commit,seed=args.seed,
                              strict_checker=checker,archive_root=args.original_archive_root)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open("x",encoding="utf-8") as dst:
            json.dump(result,dst,sort_keys=True,indent=2,allow_nan=False)
            dst.write("\n")
        print(json.dumps({
            "schema":result["schema"],"receipt":str(args.output),
            "receipt_sha256":result["receipt_sha256"],
            "replay_workstreams":[k for k in ("rolling","frozen","legacy_v1") if k in result],
            "promotion_authorized":False,
        },sort_keys=True))
        return 0
    except (OSError,TypeError,ValueError,KeyError,ContractError) as exc:
        print("V25_PHASE1_REJECTED "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
