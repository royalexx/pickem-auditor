#!/usr/bin/env python3
"""Reproducible P1 read-only importer of exported WS1 Record/Receipt envelopes.

No network operations or independent NBA collection. The caller must supply a
frozen, exact input JSON manifest and historical event/schedule metadata.
Usage:
 python scripts/nba_p1_build_pregame.py \
   --input ws1_prior_rows_and_schedule.json \
   --output frozen/espn_game_123_pregame.json

Input JSON contains "schedule" (event identity and all three UTC cutoffs),
"entries" (list of {"record": WS1 Record asdict, "receipt": WS1 Receipt
asdict}), "ingested_at" (actual observed conversion timestamp) and optional
"original_bytes" mapping receipt IDs to relative source paths. If original
bytes are unavailable, sources are always explicitly marked unverified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from v2.nba_architecture.p1_history import build_historical_pregame, freeze_historical


def strict_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("DUPLICATE_INPUT_JSON_KEY")
        obj[key] = value
    return obj


def execute(input_path, output_path, *, source_root=None, require_official_evidence=False):
    raw = Path(input_path).read_bytes()
    payload = json.loads(raw, object_pairs_hook=strict_object,
                         parse_constant=lambda _: (_ for _ in ()).throw(
                             ValueError("NONFINITE_INPUT_JSON")))
    required = {"schedule", "entries", "ingested_at", "original_bytes"}
    if not required <= set(payload) or set(payload) - required - {"official_game_evidence"}:
        raise ValueError("INVALID_INPUT_MANIFEST_FIELDS")
    source_files = {}
    originals = payload["original_bytes"]
    if originals and source_root is None:
        raise ValueError("ORIGINAL_BYTES_ROOT_REQUIRED")
    if source_root is not None:
        root = Path(source_root).resolve(strict=True)
        for receipt_id, relative in sorted(originals.items()):
            if not isinstance(relative, str) or not relative:
                raise ValueError("INVALID_SOURCE_PATH")
            src = (root / relative).resolve(strict=True)
            if not src.is_relative_to(root) or not src.is_file():
                raise ValueError("SOURCE_PATH_ESCAPE")
            source_files[receipt_id] = src.read_bytes()
    evidence = {}
    descriptors = payload.get("official_game_evidence", {})
    if not isinstance(descriptors, dict):
        raise ValueError("OFFICIAL_EVIDENCE_MAPPING_INVALID")
    def load_official(item):
        if source_root is None:
            raise ValueError("ORIGINAL_BYTES_ROOT_REQUIRED")
        if set(item) != {"capture", "source_path", "prior"}:
            raise ValueError("OFFICIAL_EVIDENCE_DESCRIPTOR_FIELDS")
        root = Path(source_root).resolve(strict=True)
        src = (root / item["source_path"]).resolve(strict=True)
        if not src.is_relative_to(root) or not src.is_file():
            raise ValueError("SOURCE_PATH_ESCAPE")
        return dict(capture=item["capture"], raw=src.read_bytes(),
                    prior=[load_official(x) for x in item["prior"]])
    for gid, descriptor in descriptors.items():
        evidence[gid] = load_official(descriptor)
    keys = {"game_id", "team_ids", "event_start_at", "input_freeze_at",
            "forecast_at", "training_cutoff_at", "decision_local_date"}
    if set(payload["schedule"]) != keys:
        raise ValueError("INVALID_SCHEDULE_FIELDS")
    obj = build_historical_pregame(
        **payload["schedule"], entries=payload["entries"],
        ingested_at=payload["ingested_at"],
        verified_source_bytes=source_files, official_game_evidence=evidence,
        require_official_evidence=require_official_evidence)
    sha = freeze_historical(output_path, obj)
    return dict(
        status="HISTORICAL_RECONSTRUCTION_UNCERTIFIED",
        input_manifest_sha256=hashlib.sha256(raw).hexdigest(),
        snapshot_sha256=sha,
        source_receipts=len(obj["sources"]), players=len(obj["players"]),
        features=len(obj["features"]),
        source_original_bytes_verified=sum(
            "Supplied source bytes match their source SHA;" in r["asof_limitations"]
            for r in obj["sources"]),
        unresolved_exposure_records=sum(
            f["value"] == "UNRESOLVED_OFFICIAL_DURATION_AND_SOURCE"
            for f in obj["features"] if f["name"].endswith(":source_status")),
        original_offers=0, forecast_scoring_performed=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--require-official-evidence", action="store_true",
                        help="Block all prior rows without official evidence; required for exposure handoff")
    ns = parser.parse_args(argv)
    try:
        receipt = execute(ns.input, ns.output, source_root=ns.source_root,
                          require_official_evidence=ns.require_official_evidence)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        blocked = dict(status="BLOCKED", code=str(exc), output_written=False,
                       rejection_scope="ENTIRE_INPUT_MANIFEST")
        if ns.input.is_file():
            failed_raw = ns.input.read_bytes()
            blocked["input_manifest_sha256"] = hashlib.sha256(failed_raw).hexdigest()
            try:
                failed = json.loads(failed_raw)
                if isinstance(failed.get("entries"), list):
                    blocked["attempted_entries"] = len(failed["entries"])
            except (ValueError, UnicodeDecodeError, AttributeError):
                pass
        print(json.dumps(blocked, sort_keys=True))
        return 2
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
