"""Manual P3 research forecast runner; never schedules daily tasks or learning.

Usage:
 python -m research.nba_p3_frozen.cli /path/to/p0_request.json
 python -m research.nba_p3_frozen.cli /path/to/p0_request.json --persist

Request contains only P0 already-authenticated feature/model/source records,
never current-game boxscore, final minutes, outcome vault, or synthetic odds.
The request's archive root must hold unchanged original bytes for P0 recheck.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from v2.p0_integrity.contracts import canonical_bytes, validate_record
from .engine import generate


def main(argv=None):
    parser=argparse.ArgumentParser(description="Research-only NBA P3 original-byte verifier and frozen distribution generator")
    parser.add_argument("request_json")
    parser.add_argument("--persist",action="store_true",
                        help="Write to attested P0 /work store; no backfill or overwrite")
    parser.add_argument("--storage-root",default="/work",
                        help="P0 attested storage only; never /tmp")
    args=parser.parse_args(argv)
    request=json.loads(Path(args.request_json).read_text(encoding="utf8"))
    required={
      "feature","model","sources","source_root","event_start_at",
      "forecast_at","code_commit","run_id","season","seed","pipeline",
      "n_scenarios","quote"
    }
    if set(request)!=required:
        parser.error("unexpected_or_missing_request_keys:"+",".join(sorted(set(request)^required)))
    if not isinstance(request["sources"],list):
        parser.error("source_receipt_list_required")
    # Only exact P0 records, never guessed sources or quote terms.
    validate_record("PregameFeatureSnapshot",request["feature"])
    validate_record("ModelArtifact",request["model"])
    for s in request["sources"]:
        validate_record("SourceReceipt",s)
    if request["quote"] is not None:
        validate_record("MarketQuote",request["quote"])
    result=generate(request["feature"],request["model"],request["sources"],
       source_root=request["source_root"],
       event_start_at=request["event_start_at"],
       forecast_at=request["forecast_at"],
       code_commit=request["code_commit"],
       run_id=request["run_id"],
       season=request["season"],
       seed=request["seed"],
       pipeline=request["pipeline"],
       n_scenarios=request["n_scenarios"],
       quote=request["quote"],
       persist=args.persist,storage_root=args.storage_root)
    output={"schema":"NBA-P3-ManualResult/1","status":result.status,
            "reason":result.reason,"forecast":result.forecast,
            "admission":result.admission,"warehouse":result.warehouse,
            "storage":result.storage,
            "original_data_claim":False if not args.persist else
              bool(result.admission and result.admission.get("admission_class") in ("A","B")),
            "promotion_allowed":False,"research_only":True}
    sys.stdout.buffer.write(canonical_bytes(output)+b"\n")
    return 0 if result.status in ("FORECAST_FROZEN","RESEARCH_DRY_RUN") else 2


if __name__=="__main__":
    sys.exit(main())
