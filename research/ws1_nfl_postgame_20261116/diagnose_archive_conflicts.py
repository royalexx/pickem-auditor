"""WS1 provenance quarantine for the three original 2026-11-05 morning archives.

Reads only public, original immutable GitHub source bodies. DOES NOT choose a
winner, fill a missing row, update Bayes state, or change any collector.
"""
from __future__ import annotations
import collections,gzip,hashlib,json,pathlib
import requests
from scripts.population_replay_guard import reconcile_population
from research.ws6_nfl_sunday_20261115.independent_postgame_20261116 import frozen_write

OUT=pathlib.Path("reports/nfl_20261115_prospective/ws1_postgame_recovery_20261116_v1")
BASE="https://raw.githubusercontent.com/royalexx/pickem-auditor/data/live-observations/data/live_pool/2026-11-05/morning/"
ARCHIVES=[
    "435dc438488a47922e3c77d7f07589213be60a4a7f14317f0824d5b334a5cd1d",
    "8884b489ea9178afe03af713d01cce962346144a1ad150f64ef753f462eb9dcd",
    "e3a2f836cfcc8b148f0c89df983d35ce96cfcbba80f6a3db1699fc10f8a39a7b"
]
def dumps(x):
    return (json.dumps(x,sort_keys=True,indent=2,allow_nan=False,ensure_ascii=False)+"\n").encode()
def run():
    docs=[];source_meta=[]
    for sha in ARCHIVES:
        path=OUT/"nov05_original_source"/(sha+".json.gz")
        if path.exists():b=path.read_bytes()
        else:
            r=requests.get(BASE+sha+".json.gz",timeout=45)
            r.raise_for_status()
            b=r.content
        actual=hashlib.sha256(b).hexdigest()
        if actual!=sha:raise RuntimeError("MUTATED_ORIGINAL_NOV05_ARCHIVE:"+sha)
        frozen_write(path,b)
        d=json.loads(gzip.decompress(b))
        if d.get("game_date")!="2026-11-05" or d.get("phase")!="morning":
            raise RuntimeError("ORIGINAL_ARCHIVE_DATE_OR_PHASE_MISMATCH")
        docs.append(d)
        source_meta.append({"path":str(path),"source_url":BASE+sha+".json.gz",
            "sha256":sha,"size":len(b),"captured_at":d.get("captured_at_utc"),
            "population_rows":len(d.get("population",[])),
            "source_status":(d.get("population_collection_receipt") or {}).get("status")})
    accepted,report=reconcile_population(docs,"2026-11-05")
    if accepted or report["posterior_update_allowed"]:
        raise RuntimeError("UNSAFE_NOV05_COLLISION_AUTOMATICALLY_RESOLVED")
    all_groups=collections.Counter(tuple(c["varying_fields"]) for c in report["quarantine"])
    sports=collections.Counter(c["identity"]["sport"] for c in report["quarantine"])
    family_groups=collections.Counter(c["identity"]["stat"] for c in report["quarantine"])
    report_obj={"schema":"PA_WS1_NOV05_IMMUTABLE_POPULATION_COLLISION_EVIDENCE_V1",
        "status":"BLOCKED_CONFLICTING_PROVENANCE_NO_POSTERIOR_UPDATE",
        "original_archives":source_meta,
        "original_total_population_rows":sum(len(d.get("population",[])) for d in docs),
        "distinct_observation_identities":report["distinct_identity_count"],
        "exact_retry_excess":report["exact_retry_count"],
        "conflicting_identity_groups":report["conflicting_identity_count"],
        "invalid_receipts_or_rows":report["malformed_or_incomplete_count"],
        "variation_fields":{",".join(k):v for k,v in sorted(all_groups.items())},
        "conflicts_by_sport":dict(sports),"conflicts_by_stat":dict(family_groups),
        "reconciler_report_sha256":report["report_sha256"],
        "input_mutated":False,"posterior_update_allowed":False,
        "resolution":"PRESERVE_ALL_VARIANTS; REQUIRE_ORIGINAL_SOURCE_OWNER_RECONCILIATION"}
    report_path=OUT/"nov05_collision_summary.json"
    frozen_write(report_path,dumps(report_obj))
    # Full per-identity source-hash variants. This is an audit pointer ledger:
    # it DOES NOT recreate or alter any of the 6,240 original rows.
    ledger=OUT/"nov05_conflict_rejection_ledger_682.jsonl"
    frozen_write(ledger,b"".join((json.dumps(x,sort_keys=True,allow_nan=False)+"\n").encode() for x in report["quarantine"]))
    r={"summary_sha256":hashlib.sha256(report_path.read_bytes()).hexdigest(),
       "rejection_ledger_sha256":hashlib.sha256(ledger.read_bytes()).hexdigest(),**report_obj}
    print(json.dumps(r,sort_keys=True))
if __name__=="__main__":run()
