"""Read-only adapter for the actual WS1 source-control manifest.

This native packet contains source candidates, not usable frozen model
probability receipts. Preserve its rejection/eligibility decisions exactly;
never synthesize missing controls or re-certify rejected source identities.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from . import shadow as s

SCHEMA = "nfl_20261115_source_control_v1"


def consume(path, expected_sha, *, source_root, now):
    path, root = Path(path), Path(source_root).resolve()
    raw = path.read_bytes()
    if s.sha(raw) != expected_sha:
        raise ValueError("WS1_manifest_file_hash_mismatch")
    manifest = json.loads(raw)
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode()
    if raw != canonical+b"\n" or path.stem != s.sha(canonical):
        raise ValueError("WS1_manifest_canonical_or_content_address_mismatch")
    if manifest.get("schema") != SCHEMA or manifest.get("date") != s.DAY:
        raise ValueError("wrong_WS1_schema_or_date")
    if s.timestamp(manifest["input_freeze_at"]) > s.timestamp(now):
        raise ValueError("future_WS1_freeze")
    verified = {}
    for name, receipt in manifest["sources"].items():
        source = (root/receipt["archive_path"]).resolve()
        if not source.is_relative_to(root):
            raise ValueError("WS1_source_path_escape")
        if s.sha(source.read_bytes()) != receipt["sha256"]:
            raise ValueError("WS1_original_source_bytes_hash_mismatch")
        verified[name] = receipt["sha256"]
    # Reuse the same model registry and no-training gate, not a second model implementation.
    report = s.build({"input_freeze_at": manifest["input_freeze_at"]}, {}, [], [], now=now)
    rows = []
    originals = manifest["candidates"]
    controls = Counter()
    duplicates = Counter(row.get("candidate_id") for row in originals)
    for index, original in enumerate(originals):
        for name, block in original.get("frozen_control", {}).items():
            if isinstance(block, dict) and block.get("probability") is not None:
                controls[name] += 1
        reason = original.get("source_validation_failure")
        if duplicates[original.get("candidate_id")] > 1:
            reason = "WS1_duplicate_candidate_id"
        if not reason and original.get("source_certified") is not True:
            reason = "WS1_source_not_certified"
        if not reason and original.get("forecast_eligible") is not True:
            reason = original.get("forecast_eligibility_reason") or "WS1_forecast_not_eligible"
        if not reason:
            # Native v1 has no paired frozen model probabilities, precise original
            # quote publication proof, or verified book settlement rules.
            reason = "WS1_native_probability_and_settlement_adapter_incomplete"
        for candidate in s.CONFIG:
            rows.append({"input_index": index, "contract_id": original.get("candidate_id"),
                         "candidate_id": original.get("candidate_id"), "quote_id": original.get("quote_id"),
                         "event_id": original.get("event_id"), "player_id": original.get("player_id"),
                         "stat": original.get("stat"), "line": original.get("line"),
                         "period": original.get("period"), "book": original.get("book"),
                         "source_sha256": original.get("source_sha256"),
                         "candidate": candidate, "model_id": report["registry"][candidate]["model_id"],
                         "status": "abstain", "reason": reason,
                         "WS1_source_validation_failure": original.get("source_validation_failure"),
                         "WS1_forecast_eligibility_reason": original.get("forecast_eligibility_reason"),
                         "input_freeze_at": original.get("input_freeze_at")})
    report.update(forecasts=rows, input_manifest_sha256=expected_sha,
                  WS1_canonical_sha256=s.sha(canonical), WS1_schema=SCHEMA,
                  original_input_rows=len(originals), original_unique_candidate_ids=len(duplicates),
                  original_WS1_code_sha=manifest.get("code_sha"),
                  verified_original_source_sha256=verified,
                  original_market_coverage=manifest.get("market_coverage"),
                  original_WS1_failures=manifest.get("failures"),
                  original_source_certified=manifest.get("source_certified_quotes"),
                  original_forecast_eligible=manifest.get("forecast_eligible_contracts"),
                  original_nonnull_control_counts=dict(controls),
                  original_source_rows_sha256=s.sha(s.canonical(originals)),
                  status="BLOCKED_BY_WS1_SOURCE_AND_FROZEN_CONTROL_EVIDENCE")
    report["coverage"] = {name: {"input_contracts": len(originals), "forecast_contracts": 0,
        "abstentions": dict(Counter(r["reason"] for r in rows if r["candidate"] == name))}
        for name in s.CONFIG}
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.out.resolve().is_relative_to((Path.cwd()/"calibration_models").resolve()):
        raise ValueError("output_must_be_in_owned_calibration_models_directory")
    result = consume(args.manifest, args.manifest_sha256, source_root=args.source_root,
                     now=datetime.now(timezone.utc).isoformat())
    digest = s.write_exclusive(args.out, result)
    print(json.dumps({"output_sha256": digest, "original_contract_rows": result["original_input_rows"],
                      "verified_sources": len(result["verified_original_source_sha256"]),
                      "coverage": result["coverage"],
                      "control_counts": result["original_nonnull_control_counts"],
                      "source_hashes": result["source_code_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
