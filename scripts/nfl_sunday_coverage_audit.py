"""Independent full-slate research-only receipt/coverage audit (no source fetching)."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from hashlib import sha256
import argparse
import json

from nfl_sunday_source_contract import VERSION, expected_events, instant, canonical, write_immutable
from nfl_sunday_handoff import load_control

def audit(manifest_path):
    manifest_path=Path(manifest_path)
    manifest,file_sha=load_control(manifest_path)
    root=manifest_path.parents[2]
    errors=[]
    check=Counter()
    raw_receipts=manifest.get("sources") or {}
    for name,receipt in raw_receipts.items():
        rel=Path(str(receipt.get("archive_path") or ""))
        if rel.is_absolute() or ".." in rel.parts or not rel.parts:
            errors.append("unsafe_source_path:"+name);continue
        path=(root/rel).resolve()
        if not path.is_relative_to(root.resolve()):
            errors.append("out_of_root_source:"+name);continue
        if not path.exists():
            errors.append("missing_original_source:"+name);continue
        body=path.read_bytes()
        if sha256(body).hexdigest()!=receipt.get("sha256"):
            errors.append("raw_source_sha_mismatch:"+name);continue
        if len(body)!=receipt.get("size_bytes"):
            errors.append("raw_source_size_mismatch:"+name);continue
        try:
            when=instant(receipt.get("source_received_at"))
            freeze=instant(manifest["input_freeze_at"])
            if when>freeze:
                errors.append("future_source:"+name)
        except ValueError:
            errors.append("invalid_source_clock:"+name)
        check["raw_source_verified"]+=1
    expected={(e["away"],e["home"],e["scheduled_kickoff"])
              for e in expected_events()}
    observed={(e.get("away"),e.get("home"),e.get("scheduled_kickoff"))
              for e in manifest.get("events",[])}
    if observed!=expected:
        errors.append("schedule_12_fixture_disagreement")
    if any(not e.get("schedule_verified") for e in manifest.get("events",[])):
        errors.append("not_all_12_fixtures_espn_verified")
    market=Counter()
    reasons=Counter()
    players=set()
    pairs=set()
    books=set()
    eligible=set()
    certified=set()
    identity_to_quotes={}
    for r in manifest.get("candidates") or []:
        check["original_quote_observations"]+=1
        q=r.get("original_quote") or {}
        market[str(r.get("stat"))]+=1
        reason=r.get("source_validation_failure") or "PASS"
        reasons[reason]+=1
        pair=q.get("event_teams") or []
        if len(pair)==2 and pair[0]!=pair[1]:
            pairs.add(frozenset(pair))
        if r.get("source_certified"):
            check["source_certified"]+=1
            certified.add(r.get("event_id"))
            if reason!="PASS" or not r.get("player_id") or not r.get("event_id"):
                errors.append("false_source_certificate:"+str(r.get("candidate_id"))[:12])
            if not q.get("event_id") or r.get("provider_event_id")!=str(q["event_id"]):
                errors.append("provider_event_mismatch")
            if r.get("team") not in pair or r.get("opponent") not in pair:
                errors.append("resolved_team_outside_original_event")
            try:
                if not instant(r["source_received_at"])<=instant(r["input_freeze_at"])<instant(r["event_start_at"]):
                    errors.append("time_travel_certified")
            except (ValueError,KeyError,TypeError):
                errors.append("invalid_certified_time")
            players.add(r["player_id"])
            books.add(r.get("book"))
        if r.get("research_shadow_eligible"):
            check["research_shadow_eligible"]+=1
            eligible.add(r.get("event_id"))
            if not r.get("source_certified"):
                errors.append("invalid_shadow_without_source_certificate")
        if r.get("forecast_eligible"):
            check["forecast_eligible"]+=1
            if not r.get("source_certified"):
                errors.append("invalid_trusted_forecast")
        key=(r.get("event_id"),r.get("player_id"),r.get("stat"),
             r.get("period"),r.get("book"),r.get("line"))
        identity_to_quotes.setdefault(key,[]).append(r)
    if len(pairs)!=12:
        errors.append("not_12_original_provider_game_pairs")
    if check["original_quote_observations"]!=manifest.get("attempted_contracts"):
        errors.append("attempted_denominator_mismatch")
    if check["source_certified"]!=manifest.get("source_certified_quotes"):
        errors.append("source_certified_denominator_mismatch")
    if check["research_shadow_eligible"]!=manifest.get("research_shadow_eligible_quotes"):
        errors.append("research_shadow_denominator_mismatch")
    if check["forecast_eligible"]!=manifest.get("forecast_eligible_contracts"):
        errors.append("forecast_denominator_mismatch")
    for key,rows in identity_to_quotes.items():
        if len(rows)>1 and any(r.get("source_certified") for r in rows):
            errors.append("colliding_live_quote_admitted")
    return {
        "schema":"nfl_ws1_full_slate_independent_source_audit_v1",
        "manifest_file_sha256":file_sha,
        "manifest_canonical_sha256":sha256(canonical(manifest)).hexdigest(),
        "original_observations":check["original_quote_observations"],
        "raw_receipts_observed":len(raw_receipts),
        "raw_receipts_sha_verified":check["raw_source_verified"],
        "expected_games":12,
        "original_provider_distinct_game_pairs":len(pairs),
        "espn_verified_scheduled_games":len([x for x in manifest["events"]
                                             if x.get("schedule_verified")]),
        "games_with_certified_original_quotes":len(certified),
        "games_with_research_shadow_candidates":len(eligible),
        "unique_verified_players":len(players),
        "unique_verified_books":len(books),
        "source_certified_quotes":check["source_certified"],
        "research_shadow_eligible_quotes":check["research_shadow_eligible"],
        "forecast_eligible_quotes":check["forecast_eligible"],
        "by_market":dict(sorted(market.items())),
        "source_rejection_reasons":dict(sorted(reasons.items())),
        "critical_errors":errors,
        "independent_source_audit_pass":not errors,
        "claims":"Source/identity integrity only; NOT proof of forecast calibration, player availability, or real-money edge",
    }

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-manifest",type=Path,required=True)
    p.add_argument("--audit-out",type=Path,required=True)
    args=p.parse_args(argv)
    result=audit(args.source_manifest)
    digest=write_immutable(args.audit_out,result)
    print(json.dumps({"receipt_sha256":digest,**result},sort_keys=True,indent=2))
    if result["critical_errors"]:
        raise SystemExit(2)

if __name__=="__main__":
    main()
