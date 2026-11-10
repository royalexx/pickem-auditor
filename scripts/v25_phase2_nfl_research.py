#!/usr/bin/env python3
"""One-command Phase 2 NFL research (NO production execution or historical certification).

python scripts/v25_phase2_nfl_research.py \
  --input examples/v25_phase2_nfl_synthetic_case.json \
  --output /tmp/nfl-p2-research-receipt.json \
  --code-commit <exact-40-character-git-commit> --n-scenarios 256

Outputs are immutable; all original input bytes are SHA-256 bound. This CPU
prototype does not infer current lineups or real bookmaker prices.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v2.contracts import ContractError, canonical_hash
from v2.nfl_opportunity import (simulate_nfl_opportunities,
                                replay_nfl_opportunity_cases)


def _strict_object(pairs):
    seen={}
    for k,v in pairs:
        if k in seen:
            raise ContractError("duplicate_phase2_json_key:"+k)
        seen[k]=v
    return seen


def _read(path: Path):
    raw=path.read_bytes()
    if not raw or len(raw)>64*1024*1024:
        raise ContractError("empty_or_oversize_phase2_input")
    obj=json.loads(raw,object_pairs_hook=_strict_object,
                   parse_constant=lambda k: (_ for _ in ()).throw(
                       ContractError("nonfinite_phase2_json:"+k)))
    return obj,hashlib.sha256(raw).hexdigest()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--code-commit",required=True)
    parser.add_argument("--seed",type=int,default=20261110)
    parser.add_argument("--n-scenarios",type=int,default=256)
    parser.add_argument("--mode",choices=("single","replay"),default="single")
    parser.add_argument("--summary-only",action="store_true",
                        help="Only store SHA-bound distributions, not raw scenario ensemble")
    args=parser.parse_args(argv)
    if (args.output.exists() or args.input.resolve()==args.output.resolve()
            or (len(args.code_commit)!=40
                or any(c not in "0123456789abcdef" for c in args.code_commit))):
        parser.error("immutable_output_exists_or_invalid_git_commit")
    try:
        payload,input_sha=_read(args.input)
        if args.mode=="single":
            result=simulate_nfl_opportunities(
                payload,seed=args.seed,n_scenarios=args.n_scenarios,
                store_scenarios=not args.summary_only)
        else:
            if not isinstance(payload,dict) or payload.get("schema")!=(
                    "v25-nfl-p2-replay-input-v1"):
                raise ContractError("wrong_phase2_replay_schema")
            result=replay_nfl_opportunity_cases(
                payload["cases"],seed=args.seed,n_scenarios=args.n_scenarios)
        receipt={
            "schema":"v25-nfl-phase2-research-receipt-1",
            "code_commit":args.code_commit,
            "original_file_bytes_sha256":input_sha,
            "input_mode":args.mode,
            "algorithm_seed":args.seed,
            "n_scenarios":args.n_scenarios,
            "research_result":result,
            "source_publication_trust_verified":False,
            "historical_live_originality_claim":False,
            "phase0r_approval":False,
            "phase1_production_approval":False,
            "automatic_promotion_authorized":False,
            "heavy_training_started":False,
        }
        receipt["receipt_sha256"]=canonical_hash(receipt)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open("x",encoding="utf-8") as handle:
            json.dump(receipt,handle,indent=2,sort_keys=True,allow_nan=False)
            handle.write("\n")
        print(json.dumps({
            "receipt":str(args.output),
            "input_sha256":input_sha,
            "receipt_sha256":receipt["receipt_sha256"],
            "promotion_authorized":False,
            "mode":args.mode,
        },sort_keys=True))
        return 0
    except (ContractError,KeyError,TypeError,ValueError,OSError) as exc:
        print("PHASE2_RESEARCH_REJECTED "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
