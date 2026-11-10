#!/usr/bin/env python3
"""Read-only replay of independently archived V2.5 shadow forecasts.

Usage: python scripts/v25_phase1_replay.py --input archived.json --output receipt.json
The input must have top-level arrays quotes, forecasts, settlements. Every
forecast must be an ORIGINAL frozen snapshot, never recomputed from outcomes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v2.contracts import ContractError, parse_quote, parse_snapshot, canonical_hash
from v2.evaluation import Settlement, evaluate


def _unique_keys(pairs):
    seen = {}
    for k, v in pairs:
        if k in seen:
            raise ContractError("duplicate_json_key:" + k)
        seen[k] = v
    return seen


def replay(payload: dict, *, baseline_model: str = "frozen_v1", seed: int = 20261109) -> dict:
    if not isinstance(payload, dict) or any(k not in payload for k in ("quotes", "forecasts", "settlements")):
        raise ContractError("missing_replay_arrays")
    if any(not isinstance(payload[k], list) for k in ("quotes", "forecasts", "settlements")):
        raise ContractError("invalid_replay_arrays")
    quotes = [parse_quote(row) for row in payload["quotes"]]
    forecasts = [parse_snapshot(row) for row in payload["forecasts"]]
    settlements = [Settlement(**row) for row in payload["settlements"]]
    return evaluate(quotes, forecasts, settlements, baseline_model=baseline_model, bootstrap_seed=seed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--baseline-model", default="frozen_v1")
    parser.add_argument("--seed", type=int, default=20261109)
    args = parser.parse_args()
    if args.output.exists() or args.input.resolve() == args.output.resolve():
        parser.error("output_already_exists_or_input_would_be_overwritten")
    try:
        source = args.input.read_bytes()
        payload = json.loads(source, object_pairs_hook=_unique_keys,
                             parse_constant=lambda x: (_ for _ in ()).throw(ContractError("nonfinite_json:"+x)))
        result = replay(payload, baseline_model=args.baseline_model, seed=args.seed)
        result["input_sha256"] = hashlib.sha256(source).hexdigest()
        result["receipt_sha256"] = canonical_hash(result)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as out:
            json.dump(result, out, sort_keys=True, indent=2, allow_nan=False)
            out.write("\n")
        print(json.dumps({"receipt": str(args.output), "receipt_sha256": result["receipt_sha256"],
                          "promotion_authorized": False}, sort_keys=True))
        return 0
    except (ContractError, ValueError, TypeError, KeyError, OSError) as exc:
        print("PHASE1_REJECTED " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
