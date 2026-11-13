#!/usr/bin/env python3
"""Append-only Phase 1.5 pregame opportunity-factor shadow capture.

Modes:
  producer  — legacy single-contract v1 receipt (requires full producer factors)
  bundle    — v2 manifest from frozen capture bundle JSON (AVAILABLE / UNMEASURED)

Never computes missing factors from postgame results.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from v2.phase15_pregame_factors import (
    DEFAULT_EXPERIMENT,
    build_capture_manifest,
    make_shadow_receipt,
    producer_payload_to_v2_bundle,
    write_capture_manifest,
)
from v2.official_nba_nhl_capture import SettlementCaptureError


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("producer", "bundle"), default="producer")
    p.add_argument("--input", type=Path, help="Producer payload or frozen bundle JSON")
    p.add_argument("--source-root", type=Path, help="Root for archived source bytes")
    p.add_argument("--output", type=Path, help="Output file (producer) or directory (bundle)")
    p.add_argument("--run-id", default=None, help="Capture run id (bundle mode)")
    p.add_argument("--experiment-id", default=DEFAULT_EXPERIMENT)
    p.add_argument(
        "--negative-control",
        action="store_true",
        help="Attach synthetic INVALID negative-control receipt to manifest",
    )
    a = p.parse_args(argv)
    if not a.input or not a.input.is_file():
        p.error("input_required_existing_file")
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    try:
        raw = json.loads(a.input.read_text(encoding="utf-8"))
        if a.mode == "producer":
            if not a.source_root or not a.output:
                p.error("producer_requires_source_root_and_output_file")
            if a.output.exists() or a.output.resolve() == a.input.resolve():
                p.error("new_output_required_no_retroactive_overwrite")
            result = make_shadow_receipt(raw, source_root=a.source_root, observed_clock=now)
            a.output.parent.mkdir(parents=True, exist_ok=True)
            with a.output.open("x", encoding="utf-8") as out:
                json.dump(result, out, sort_keys=True, indent=2, allow_nan=False)
                out.write("\n")
            print(
                json.dumps(
                    {
                        "mode": "producer",
                        "schema": result.get("schema"),
                        "output": str(a.output),
                        "receipt_sha256": result["receipt_sha256"],
                        "sport": result.get("sport"),
                        "stat": result.get("stat"),
                        "production_promotion_allowed": False,
                    },
                    sort_keys=True,
                )
            )
            return 0
        out_dir = a.output or Path("reports/phase15_factor_captures")
        if out_dir.exists() and out_dir.is_file():
            p.error("bundle_output_must_be_directory")
        bundle = raw
        if bundle.get("schema") != "v25_phase15_frozen_capture_bundle_v1":
            if a.run_id is None:
                p.error("bundle_requires_schema_or_explicit_run_id")
            bundle = producer_payload_to_v2_bundle(
                raw, run_id=a.run_id, experiment_id=a.experiment_id
            )
        elif a.run_id:
            bundle["run_id"] = a.run_id
        manifest = build_capture_manifest(
            bundle,
            source_root=a.source_root,
            observed_clock=now,
            include_negative_control=a.negative_control,
        )
        receipt = write_capture_manifest(manifest, out_dir)
        print(
            json.dumps(
                {
                    "mode": "bundle",
                    "schema": manifest["schema"],
                    "output": receipt["path"],
                    "manifest_sha256": manifest["manifest_sha256"],
                    "contract_count": manifest["contract_count"],
                    "row_count": manifest["row_count"],
                    "four_factor_attribution_possible": manifest["four_factor_attribution_possible"],
                    "written": receipt.get("written", True),
                    "production_promotion_allowed": False,
                },
                sort_keys=True,
            )
        )
        return 0
    except (OSError, ValueError, TypeError, KeyError, SettlementCaptureError) as exc:
        print("OPPORTUNITY_FACTOR_CAPTURE_BLOCKED " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
