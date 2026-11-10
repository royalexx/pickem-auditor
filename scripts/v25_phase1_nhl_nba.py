#!/usr/bin/env python3
"""One-command V2.5 Phase 1 certified NHL/NBA replay (safe, no settlement needed).

python scripts/v25_phase1_nhl_nba.py \
  --bundle pickem_runs/.../live_pool_...json.gz \
  --attempts pickem_runs/.../all_prepared_props_attempts.json \
  --code-commit <exact-current-implementation-commit> \
  --output reports/phase1_nhl_nba_20261110.json

Output is a new deterministic RESEARCH receipt. Simple baseline distributions
are explicitly computed after the fact and are never mislabeled as historical
predictions. Passing this harness does not promote those counterfactual controls.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from v2.contracts import ContractError
from v2.nhl_nba_phase1 import run_phase1


def no_duplicate_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate_json_key:" + key)
        result[key] = value
    return result


def read_json(raw):
    return json.loads(
        raw, object_pairs_hook=no_duplicate_fields,
        parse_constant=lambda name: (_ for _ in ()).throw(
            ContractError("nonfinite_json_constant:" + name)),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--attempts", required=True, type=Path)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--official-settlements", type=Path,
                        help="optional later official settlement receipt; no synthetic outcomes")
    parser.add_argument("--settlement-source-root", type=Path,
                        help="required original raw official source bytes if settlements supplied")
    parser.add_argument("--seed", type=int, default=20261110)
    args = parser.parse_args(argv)
    inputs = [args.bundle, args.attempts]
    if args.official_settlements:
        inputs.append(args.official_settlements)
    if args.output.exists() or args.output.resolve() in [p.resolve() for p in inputs]:
        parser.error("output_already_exists_or_input_output_collision")
    try:
        if args.bundle.stat().st_size > 100 * 1024 * 1024:
            raise ContractError("oversized_bundle")
        raw = args.bundle.read_bytes()
        if not args.bundle.name.endswith(".json.gz"):
            raise ContractError("bundle_must_be_original_gzip")
        packet = read_json(gzip.decompress(raw))
        original_attempts = args.attempts.read_bytes()
        attempts = read_json(original_attempts)
        settled = None
        settled_sha = None
        if args.official_settlements:
            if args.settlement_source_root is None:
                raise ContractError("official_settlement_raw_source_root_required")
            settlement_raw = args.official_settlements.read_bytes()
            settled = read_json(settlement_raw)
            if not isinstance(settled, list):
                raise ContractError("official_settlement_file_must_be_array")
            settled_sha = hashlib.sha256(settlement_raw).hexdigest()
        with tempfile.TemporaryDirectory(prefix="v25_nhl_nba_original_archives_") as tmp:
            report = run_phase1(
                packet, attempts,
                archive_root=Path(tmp), bundle_sha256=hashlib.sha256(raw).hexdigest(),
                code_commit=args.code_commit,
                settlement_rows=settled,
                settlement_archive_root=args.settlement_source_root,
                seed=args.seed,
            )
        report["input_attempts_sha256"] = hashlib.sha256(original_attempts).hexdigest()
        report["independent_official_settlements_sha256"] = settled_sha
        report["report_sha256"] = hashlib.sha256(
            json.dumps({k:v for k,v in report.items() if k!="report_sha256"},
                       sort_keys=True,separators=(",",":"),allow_nan=False).encode()
        ).hexdigest()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        print(json.dumps({
            "schema": report["schema"],
            "original_forecast_rows": report["original_forecast_rows"],
            "prepared_attempt_count": report["prepared_attempt_count"],
            "retained_paired_contracts": report["retained_paired_contracts"],
            "by_sport": report["by_sport"],
            "settlement_states": report["settlement_states"],
            "output": str(args.output),
            "report_sha256": report["report_sha256"],
            "model_promotion_authorized": False,
        }, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        print("V25_PHASE1_NHL_NBA_REJECTED " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
