"""WS1 original-source-to-frozen-research-to-ESPN-final adapter (v1).

Research-only. Never creates probabilities or odds, never rewrites upstream.
Consumes the independent WS6 scorer's verified boxscore parser, not a new
settlement scoring engine. Original provider/product certification is BLOCKED.
"""
from __future__ import annotations
import collections, datetime as dt, hashlib, json, pathlib, re

from research.ws6_nfl_sunday_20261115.independent_postgame_20261116 import (
    MAP, assess, get_stat, official_sources, rows as readrows,
    verify_joint_contract_identity, frozen_write
)
VERSION="PA_WS1_FROZEN_RESEARCH_SETTLEMENT_ROUTER_V2"
R=pathlib.Path("reports/nfl_20261115_prospective")
OUT=R/"ws1_postgame_recovery_20261116_v2"
QUOTES=R/"ensemble_20261115_research_shadow/comparison_original_quotes_1845.jsonl"
PIN=R/"source_control/HANDOFF_PIN.json"
CAPTURE=R/"source_control/captures/ab2eebf29ea0dfcf9b2cc4ff5287b898e6b7b15238ea059a11df3ac399ccc6c8.json"
RAW=R/"source_control/raw/6993a07ebce5001a55729ff556765bff388bc91cb5235416af9cd26401ede14a.bin"
WS5=pathlib.Path("calibration_models/market_benchmarks_v1/original_quote_benchmarks_ab4ecbccd1c6fc37878907ad38c751fd577bdceba7385a6034e35953430a143c.jsonl")
JHANDOFF=R/"joint_models/all_market_v04/WS6_HANDOFF_20261115.json"
JDIR=R/"joint_models/all_market_v04/frozen"
TACKLE=R/"tackle_repair_v252/committed_20261115T172653Z/COMMITTED_EXECUTION_BINDING.json"
FROZEN_EXPECTED={
    str(QUOTES):"0e398b781070ce648b7dc46bf726f6eed850b40e67366de355d516ff028ecc8f",
    str(CAPTURE):"5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71",
    str(RAW):"6993a07ebce5001a55729ff556765bff388bc91cb5235416af9cd26401ede14a",
    str(WS5):"ab4ecbccd1c6fc37878907ad38c751fd577bdceba7385a6034e35953430a143c",
}

def hashfile(path, expected=None):
    p=pathlib.Path(path)
    if not p.is_file():raise RuntimeError("MISSING_FROZEN_SOURCE:"+str(path))
    sha=hashlib.sha256(p.read_bytes()).hexdigest()
    if expected and sha!=expected:raise RuntimeError("TAMPERED_FROZEN_SOURCE:"+str(path))
    return sha
def iso(s):
    if not isinstance(s,str):return None
    try:
        d=dt.datetime.fromisoformat(s.replace("Z","+00:00"))
        return d.astimezone(dt.timezone.utc) if d.tzinfo is not None else None
    except (ValueError,TypeError):return None
def norm(s):return re.sub(r"[^a-z0-9]","",str(s).lower())
def as_json(p):return json.loads(pathlib.Path(p).read_bytes())
def dump_json(p,obj):
    b=(json.dumps(obj,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode("utf-8")
    frozen_write(p,b)
    return hashlib.sha256(b).hexdigest()
def dump_jsonl(p,records):
    b=b"".join((json.dumps(r,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n").encode("utf-8") for r in records)
    frozen_write(p,b)
    return hashlib.sha256(b).hexdigest()

def classify_metadata(row,provider):
    """Conservative: never use linked descriptions to fabricate correct player."""
    reasons=list(provider.get("reasons") or [])
    pd=provider.get("original_provider_market_description")
    if pd and norm(row["player"]) not in norm(pd):
        reasons.append("CLAIMED_PROVIDER_DESCRIPTION_PLAYER_MISMATCH")
    if provider.get("settlement_status") not in ("CERTIFIED_ORIGINAL_SETTLEMENT",):
        reasons.append("ORIGINAL_SETTLEMENT_TERMS_UNVERIFIED")
    if provider.get("source_certified") is not True:
        reasons.append("WS5_SOURCE_NOT_CERTIFIED")
    # No official provider contract schema/period/payout equivalence is established.
    reasons.append("PERIOD_PRICE_AND_PRODUCT_TERMS_NOT_INDEPENDENTLY_CERTIFIED")
    return sorted({str(x) for x in reasons})

def validate_quote(original, linked,provider):
    errors=[]
    if not linked:
        errors.append("MISSING_ARCHIVED_ORIGINAL_SOURCE_LINK")
    else:
        if linked.get("quote_id")!=original["quote_id"]:
            errors.append("QUOTE_ID_MISMATCH")
        if str(linked.get("event_id"))!=str(original.get("event_id")):
            errors.append("EVENT_ID_MISMATCH")
        if linked.get("original_record"):
            raw=linked["original_record"]
            if norm(raw.get("player"))!=norm(original.get("player")):
                errors.append("ORIGINAL_PLAYER_LABEL_MISMATCH")
            if str(raw.get("book")).lower()!=str(original.get("book")).lower():
                errors.append("BOOK_MISMATCH")
            if raw.get("stat")!=original.get("stat"):
                errors.append("MARKET_MISMATCH")
            if float(raw.get("line"))!=float(original.get("line")):
                errors.append("ORIGINAL_LINE_MISMATCH")
            if raw.get("over_odds")!=original.get("over_odds") or raw.get("under_odds")!=original.get("under_odds"):
                errors.append("ORIGINAL_PRICE_PAIR_MISMATCH")
            if str(raw.get("event_start"))!=str(original.get("kickoff_utc")):
                errors.append("ORIGINAL_EVENT_START_MISMATCH")
        if linked.get("source_sha256")!=FROZEN_EXPECTED[str(RAW)]:
            errors.append("ORIGINAL_RAW_RECEIPT_SHA_MISMATCH")
        source_t=iso(linked.get("source_received_at"))
        ko=iso(original.get("kickoff_utc"))
        if ko and (source_t is None or source_t>=ko):
            errors.append("SOURCE_RECEIPT_NOT_PREGAME")
    if not provider or provider.get("quote_id")!=original["quote_id"]:
        errors.append("MISSING_WS5_QUOTE_IDENTITY")
    return sorted(set(errors))

def main():
    sha={k:hashfile(k,v) for k,v in FROZEN_EXPECTED.items()}
    sha[str(PIN)]=hashfile(PIN)
    sha[str(JHANDOFF)]=hashfile(JHANDOFF)
    sha[str(TACKLE)]=hashfile(TACKLE)
    pin=as_json(PIN)
    if pin.get("source_control_manifest_sha256")!=sha[str(CAPTURE)]:
        raise RuntimeError("WS1_AUTHORITY_PIN_CONFLICT")
    quote_rows=readrows(QUOTES); provider_rows=readrows(WS5)
    assert len(quote_rows)==len(provider_rows)==1845
    byqid={}
    for q in quote_rows:
        if not q.get("quote_id") or q["quote_id"] in byqid:
            raise RuntimeError("INVALID_OR_DUPLICATED_ORIGINAL_QUOTE_ID")
        byqid[q["quote_id"]]=q
    ws5={}
    for w in provider_rows:
        k=w.get("quote_id")
        if k in ws5 or k not in byqid:raise RuntimeError("INVALID_WS5_JOIN")
        ws5[k]=w
    if set(byqid)!=set(ws5):raise RuntimeError("MISSING_WS5_QUOTES")

    handoff=as_json(JHANDOFF)["handoff"]
    ld=handoff["original_contract_ledger"]
    jpath=JDIR/pathlib.Path(ld["path"]).name
    sha[str(jpath)]=hashfile(jpath,ld["sha256"])
    jr=as_json(jpath)
    if len(jr)!=5535:raise RuntimeError("UNEXPECTED_J_FORECAST_LEDGER_COUNT")
    source_by_id={}
    new_j=collections.defaultdict(list)
    # J3 is an explicit abstention; never treat J3 as frozen game scenario.
    for x in jr:
        qid=x.get("quote_id")
        if qid not in byqid:raise RuntimeError("JOINT_QUOTE_NOT_IN_ORIGINAL_UNIVERSE")
        if x.get("model_id")=="J1":
            if qid in source_by_id:
                raise RuntimeError("JOINT_DUPLICATE_SOURCE_ID")
            source_by_id[qid]=x
        if x.get("model_id") in ("J1","J2") and x.get("status")=="FORECAST":
            verify_joint_contract_identity(byqid[qid],x)
            new_j[qid].append(x)
    if len(source_by_id)!=1845:raise RuntimeError("MISSING_CANONICAL_SOURCE_CROSSWALK")
    new_j_event_ids={str(r["event_id"]) for r in jr if r.get("model_id")=="J1" and r.get("status")=="FORECAST"}
    forecast_receipts={}
    for item in handoff["forecast_files"]:
        p=JDIR/pathlib.Path(item["path"]).name
        hx=hashfile(p,item["sha256"])
        d=as_json(p)
        t=iso(d.get("forecast_created_at"))
        ko=iso(item.get("kickoff"))
        rec=d.get("source_receipts",{})
        t_build=iso(rec.get("built_at"))
        t_train=iso(rec.get("model_training_cutoff_conservative_snapshot_at"))
        if None in (t,ko,t_build,t_train) or not t_train<=t_build<=t<ko:
            raise RuntimeError("J_SIMULATION_OR_INPUT_NOT_PREGAME:"+str(p))
        if item["sha256"] in forecast_receipts:raise RuntimeError("REPEATED_J_EVENT_FILE")
        forecast_receipts[item["sha256"]]={"path":str(p),"sha256":hx,"created_at":d["forecast_created_at"],
            "training_cutoff":rec.get("model_training_cutoff_conservative_snapshot_at"),
            "built_at":rec.get("built_at"),"kickoff_utc":item["kickoff"]}
        sha[str(p)]=hx
    for r in jr:
        if r.get("model_id") in ("J1","J2") and r.get("status")=="FORECAST":
            if r.get("forecast_file_sha256") not in forecast_receipts:
                raise RuntimeError("J_FORECAST_USES_UNPINNED_EVENT_VERSION")

    events={str(r["event_id"]) for r in quote_rows if r.get("event_id")}
    files,official=official_sources(events)
    # IMPORTANT: independent WS6 official_sources() reuses original immutable
    # ESPN archive bytes and errors on absent/malformed completed game; no
    # outside source used for pregame player/quote certification.
    for ev,o in official["events"].items():
        sha[o["path"]]=o["sha256"]
    sha[official["scoreboard"]["path"]]=official["scoreboard"]["sha256"]
    counters=collections.Counter()
    provider_reasons=collections.Counter()
    model_counters=collections.Counter()
    lineage=[]
    rejections=[]
    flat_records=[]
    for orig in quote_rows:
        qid=orig["quote_id"]
        source=source_by_id[qid];ws=ws5[qid]
        integrity=validate_quote(orig,source,ws)
        provider_issues=classify_metadata(orig,ws)
        provider_reasons.update(provider_issues)
        event=str(orig.get("event_id") or "")
        market=MAP.get(orig["stat"])
        player_id=str(source.get("player_id") or ws.get("player_id") or "")
        z,stat_state,player=get_stat(event,player_id,orig["player"],market,files) if event and market else (None,"UNMATCHED_EVENT_OR_MARKET",None)
        if market=="tackles_assists" and stat_state=="OBSERVED":
            stat_state="TACKLE_DEFINITION_UNVERIFIED"
        if integrity:
            source_status="SOURCE_INTEGRITY_REJECT"
        elif not orig.get("source_identity_verified"):
            source_status="WS1_SOURCE_IDENTITY_REJECT"
        elif not orig.get("research_shadow_eligible"):
            source_status="WS1_RESEARCH_ELIGIBILITY_EXCLUDE"
        else:
            source_status="RESEARCH_ONLY_SOURCE_IDENTITY"
        counters[source_status]+=1
        if integrity or provider_issues:
            rejections.append({"observation_index":orig["observation_index"],"quote_id":qid,
                "source_integrity":integrity,"provider_product_reasons":provider_issues,
                "raw_provider_description":ws.get("original_provider_market_description"),
                "player":orig["player"],"event_id":orig.get("event_id"),"line":orig["line"]})
        per_model={}
        attempts={}
        for key,v in orig.get("models",{}).items():
            attempts[key]={"forecast_at":v.get("forecast_at"),"over":v.get("over"),
                           "under":v.get("under"),"push":v.get("push"),
                           "frozen_path":str(QUOTES),"frozen_sha256":sha[str(QUOTES)],
                           "freeze_integrity":"COMPOSITE_ORIGINAL_HISTORICAL_RECEIPT_REQUIRES_MODEL_FILE_RECHECK"}
        for j in new_j.get(qid,[]):
            key=j["model_id"]+"_v04_2_3"
            ff=forecast_receipts[j["forecast_file_sha256"]]
            attempts[key]={"forecast_at":ff["created_at"],"over":j["p_over"],"under":j["p_under"],
                           "push":j["p_push"],"frozen_path":ff["path"],"frozen_sha256":ff["sha256"],
                           "training_cutoff":ff["training_cutoff"],"input_built_at":ff["built_at"],
                           "freeze_integrity":"ORIGINAL_EVENT_FILE_SHA_VERIFIED"}
        ko=iso(orig.get("kickoff_utc")); recv=iso(source.get("source_received_at"))
        for model,m in sorted(attempts.items()):
            t=iso(m.get("forecast_at"))
            if model in ("J1_original","J2_original") and event in new_j_event_ids:
                state="SUPERSEDED_OLDER_J_VERSION_NOT_SCORED"
            elif not ko or not recv or not t or not recv<=t<ko:
                state="FORECAST_TIME_OR_SOURCE_NOT_PREGAME"
            elif orig.get("missing",{}).get(model):
                state="MODEL_FLAGGED_UNAVAILABLE"
            elif stat_state!="OBSERVED":
                state="OUTCOME_"+stat_state
            else:
                try:
                    s=assess(float(m["over"]),float(m["push"]),z,float(orig["line"]))
                    if not s:state="INVALID_FROZEN_PROBABILITIES"
                    else:state=("PUSH_RESEARCH_ONLY" if s["direction"]=="PUSH"
                                else "OBSERVED_RESEARCH_ONLY")
                except (TypeError,ValueError):
                    state="INVALID_FROZEN_PROBABILITIES";s=None
            model_counters[(model,state)]+=1
            per_model[model]={"state":state,"path":m["frozen_path"],
                "sha256":m["frozen_sha256"],"forecast_at":m["forecast_at"],
                "training_cutoff":m.get("training_cutoff"),"input_built_at":m.get("input_built_at"),
                "p_over":m["over"],"p_under":m["under"],"p_push":m["push"],
                "source_receipt_at":source.get("source_received_at"),
                "official_value":z,"official_game_event":event,
                "official_sha256":official["events"].get(event,{}).get("sha256"),
                "result":s if state in ("PUSH_RESEARCH_ONLY","OBSERVED_RESEARCH_ONLY") else None,
                "component_freeze":m["freeze_integrity"],
                "market_certified":False,"production_allowed":False}
            if state in ("PUSH_RESEARCH_ONLY","OBSERVED_RESEARCH_ONLY"):
                flat_records.append({"model":model,"event_id":event,"player_id":player_id,
                    "stat":market,"period":"full_game","line":orig["line"],
                    "quote_id":qid,"book":orig["book"],"result":s,"score_quality":"RESEARCH_ONLY_UNCERTIFIED"})
        lineage.append({"observation_index":orig["observation_index"],"quote_id":qid,
            "candidate_id":orig["candidate_id"],"event_id":event or None,
            "kickoff_utc":orig.get("kickoff_utc"),"player":orig["player"],
            "player_id_espn":player_id or None,"player_gsis":source.get("gsis_id"),
            "book":orig["book"],"stat":orig["stat"],"line":orig["line"],
            "period":source.get("period"),"source_received_at":source.get("source_received_at"),
            "quote_reported_at":ws.get("quote_reported_at"),
            "source_sha256":source.get("source_sha256"),"provider_market_key":ws.get("provider_market_key"),
            "original_market_description":ws.get("original_provider_market_description"),
            "over_odds":orig.get("over_odds"),"under_odds":orig.get("under_odds"),
            "source_research_eligibility":source_status,"source_integrity_rejections":integrity,
            "provider_reasons":provider_issues,
            "official_stat":z,"official_status":stat_state,
            "models":per_model,"market_certified":False,"eligible_for_posterior_training":False})
    assert len(lineage)==1845
    unique_contracts={(r["event_id"],r["player_id_espn"] or norm(r["player"]),r["stat"],r["line"],r["period"]) for r in lineage}
    # No impossible claim of 1,845 independent sporting events: repeated
    # books/alternate lines remain separate original quotes and are linked.
    summary={"schema":VERSION,"date":"2026-11-15","status":"RESEARCH_REPLAY_ONLY_MARKET_CERTIFICATION_BLOCKED",
        "original_quote_observations":1845,"source_statuses":dict(counters),
        "unique_event_player_stat_line_period_contracts":len(unique_contracts),
        "duplicate_book_observation_excess":1845-len(unique_contracts),
        "official_final_games":len(official["events"]),"provider_reason_instances_non_disjoint":dict(provider_reasons),
        "model_contract_statuses":{k[0]+"|"+k[1]:v for k,v in sorted(model_counters.items())},
        "original_rejection_rows":len(rejections),
        "research_outcome_rows_with_book_duplicates":len(flat_records),
        "market_certified_contracts":0,"bayesian_incremental_eligible":0,
        "original_slate_archives_modified":False,"legacy_60_40_modified":False}
    manifest={"schema":"PA_WS1_RESEARCH_ARCHIVE_ROUTING_MANIFEST_V1",
        "source_pins":sha,"input_sources":{"original_quotes":str(QUOTES),"canonical_ws1_manifest":str(CAPTURE),
            "original_raw_quote_body":str(RAW),"ws5_market_audit":str(WS5),
            "ws4_canonical_joint_ledger":str(jpath),"original_tackle_repair_commit":str(TACKLE)},
        "authoritative_joint_versions":"ws4_all_market_v0.4.2_or_0.4.3",
        "superseded_joint_versions_excluded":True,
        "older_j_original_rows_retained_but_not_scored_where_v04_available":True,"j3_all_market_forecasts":0,
        "separate_s2_o_tackle_composite_existence_not_market_certification":True,
        "official_final_evidence_source":"ESPN_FINAL_RAW_ARCHIVED_IN_DEEPNOTE",
        "source_side_odds_reconstructed":False,"research_only":True,"automatic_settlement_to_legacy_disabled":True,
        "daily_schedules_changed":False,"source_certification_newly_granted":False}
    manifest_sha=dump_json(OUT/"routing_manifest.json",manifest)
    l_sha=dump_jsonl(OUT/"lineage_1845.jsonl",lineage)
    rej_sha=dump_jsonl(OUT/"rejections.jsonl",rejections)
    sum_sha=dump_json(OUT/"recovery_summary.json",summary)
    receipt={"schema":"PA_WS1_RESEARCH_POSTGAME_REPLAY_RECEIPT_V1",
            "manifest_sha256":manifest_sha,"lineage_sha256":l_sha,
            "rejections_sha256":rej_sha,"summary_sha256":sum_sha,
            "source_quote_sha256":sha[str(QUOTES)],"input_write_operations":0,
            "production_writes":0,"model_parameters_changed":False}
    dump_json(OUT/"replay_receipt.json",receipt)
    print(json.dumps({"output_dir":str(OUT),"manifest":receipt,"summary":summary},sort_keys=True))
if __name__=="__main__":main()
