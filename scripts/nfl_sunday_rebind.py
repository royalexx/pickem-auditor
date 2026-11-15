"""Read-only pregame source rebinding after source-identity parser fixes.

Reads ONLY the original immutable quote+ESPN bytes captured in the preceding
run. Does not contact odds providers, collect new data, rewrite original
forecasts, or infer an upstream provider publication timestamp.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import argparse
import json

from nfl_sunday_source_contract import (
    VERSION, canonical, instant, utc, build_universe, freeze_manifest,
)
from nfl_sunday_capture import roster_athletes, depth_qb, injuries_by_player

def load_raw(root, receipt):
    if not isinstance(receipt, dict):
        raise ValueError("RAW_RECEIPT_MISSING")
    rel = Path(str(receipt.get("archive_path") or ""))
    if not rel.parts or rel.is_absolute() or ".." in rel.parts:
        raise ValueError("RAW_SOURCE_PATH_UNSAFE")
    path=(Path(root)/rel).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError("RAW_SOURCE_ESCAPES_ROOT")
    body=path.read_bytes()
    if sha256(body).hexdigest()!=receipt.get("sha256"):
        raise ValueError("RAW_SOURCE_SHA_MISMATCH")
    if receipt.get("size_bytes")!=len(body) or receipt.get("source_bytes_verified") is not True:
        raise ValueError("RAW_SOURCE_BYTES_UNVERIFIED")
    return json.loads(body)

def rebind(root, original_path, code_sha):
    root=Path(root)
    original_path=Path(original_path)
    raw=original_path.read_bytes()
    archive=json.loads(raw)
    if archive.get("schema")!=VERSION or raw!=canonical(archive)+b"\n":
        raise ValueError("ORIGINAL_MANIFEST_SCHEMA_OR_BYTES_INVALID")
    if original_path.stem!=sha256(canonical(archive)).hexdigest():
        raise ValueError("ORIGINAL_MANIFEST_CANONICAL_SHA_MISMATCH")
    sources=archive["sources"]
    freeze=instant(archive["input_freeze_at"])
    for name, receipt in sources.items():
        _ = load_raw(root, receipt)
        if instant(receipt.get("source_received_at"))>freeze:
            raise ValueError("ORIGINAL_SOURCE_RECEIVED_AFTER_FREEZE:"+name)
    rosters, depth_qbs, injuries={},{},{}
    for name, receipt in sources.items():
        if not name.startswith("espn_") or not name.endswith("_roster"):
            continue
        team=name[len("espn_"):-len("_roster")]
        payload=load_raw(root,receipt)
        rosters[team]={
            "athletes":roster_athletes(payload),
            "receipt_sha256":receipt["sha256"],
        }
    for name,receipt in sources.items():
        if not name.startswith("espn_") or not name.endswith("_depthcharts"):
            continue
        team=name[len("espn_"):-len("_depthcharts")]
        head=depth_qb(load_raw(root,receipt))
        if head:
            depth_qbs[team]=head
    for name,receipt in sources.items():
        if not name.startswith("espn_") or not name.endswith("_injuries"):
            continue
        team=name[len("espn_"):-len("_injuries")]
        injuries[team]=injuries_by_player(load_raw(root,receipt))
    quotes=[row["original_quote"] for row in archive["candidates"]]
    manifest=build_universe(
        events=archive["events"],quotes=quotes,quote_receipts=sources,
        rosters=rosters,depth_qbs=depth_qbs,injuries=injuries,
        nfl_rows=[],freeze_at=archive["input_freeze_at"],code_sha=code_sha)
    manifest["rebind_provenance"]={
        "status":"research_only_rebuild_from_original_pregame_frozen_raw_sources",
        "old_manifest_canonical_sha256":sha256(canonical(archive)).hexdigest(),
        "old_manifest_file_sha256":sha256(raw).hexdigest(),
        "repair_commit":code_sha,
        "rebind_executed_at":utc(datetime.now(timezone.utc)),
        "original_quote_count":len(quotes),
        "read_only_original_raw_sources_verified":len(sources),
        "no_original_provider_requests":True,
        "original_frozen_input_clock_preserved":True,
        "upstream_publication_truth_not_retrocertified":True,
        "original_forecast_probabilities_not_recomputed":True,
        "roster_teams_with_verified_source":len(rosters),
        "teams_with_independent_depth_order_qb":len(depth_qbs),
        "injury_teams_with_independently_archived_source":len(injuries),
    }
    manifest["runtime"]=archive.get("runtime",{})
    manifest["runtime"]={
        **manifest["runtime"],
        "source_identity_repair":"independent_unique_espn_roster_on_provider_event_pair",
        "c03_strict_cohorts":"NOT_INTEGRATED_IN_THIS_RESEARCH_CAPTURE",
        "no_provider_requests_in_rebind":True,
    }
    receipt=freeze_manifest(root,manifest)
    reason=Counter(row.get("source_validation_failure") or "PASS"
                   for row in manifest["candidates"])
    report={
        "status":"REBIND_FROM_ORIGINAL_ARCHIVED_SOURCE_ONLY",
        "receipt":receipt,
        "quotes":manifest["attempted_contracts"],
        "quote_source_certified":manifest["source_certified_quotes"],
        "forecast_eligible":manifest["forecast_eligible_contracts"],
        "roster_teams":len(rosters),
        "expected_qb_teams":len(depth_qbs),
        "failures":dict(sorted(reason.items())),
    }
    print(json.dumps(report,indent=2,sort_keys=True))
    return report

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive-root",type=Path,required=True)
    p.add_argument("--original-manifest",type=Path,required=True)
    p.add_argument("--code-sha",required=True)
    a=p.parse_args(argv)
    rebind(a.archive_root,a.original_manifest,a.code_sha)

if __name__=="__main__":
    main()
