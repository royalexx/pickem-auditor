"""WS1 emergency prospective NFL feature adapter: append-only, source-traceable, research only.

This script does not create models or forecast probabilities and does not touch the
canonical source capture. Newly obtained public historical data are retained byte-
for-byte, with actual receipt timestamps; no historical pregame status is inferred.
"""
from __future__ import annotations
import csv
import gzip
import hashlib
import io
import json
import math
import os
import re
import sys
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("reports/nfl_20261115_prospective")
ARCHIVE = Path("reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/source_bundle")
PUBLIC = {
    "players": "https://github.com/nflverse/nflverse-data/releases/download/players/players.csv",
    "stats2026": "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.csv",
    "games2026": "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv",
    "snaps2026": "https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_2026.csv",
}
STATS = {"pass attempts":"attempts","completions":"completions","passing yards":"passing_yards",
         "rush attempts":"carries","rushing yards":"rushing_yards",
         "receptions":"receptions","receiving yards":"receiving_yards",
         "tackles + assists":"tackles_combined"}
NUMERIC = ("attempts","completions","passing_yards","carries","rushing_yards","receptions",
           "receiving_yards","targets","def_tackles_solo","def_tackles_with_assist",
           "def_tackle_assists")
UTC = timezone.utc
def now(): return datetime.now(UTC).isoformat().replace("+00:00","Z")
def stamp(s):
    if not isinstance(s,str): raise ValueError("MISSING_TIMESTAMP")
    d=datetime.fromisoformat(s.replace("Z","+00:00"))
    if d.tzinfo is None: raise ValueError("NAIVE_TIMESTAMP")
    return d.astimezone(UTC)
def sha(b): return hashlib.sha256(b).hexdigest()
def canonical(o):return (json.dumps(o,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)+"\n").encode()
def norm(v):
    s=unicodedata.normalize("NFKD",str(v or "")).encode("ascii","ignore").decode().casefold()
    return re.sub("[^a-z0-9]","",s)
def numeric(v):
    if v in ("",None):return None
    try:
        f=float(v)
        return f if math.isfinite(f) else None
    except (TypeError,ValueError): return None
def rows_json_gz(path,expect):
    b=path.read_bytes()
    if sha(b)!=expect: raise ValueError("HISTORICAL_RAW_SHA_MISMATCH:"+str(path))
    d=json.loads(gzip.decompress(b))
    if not isinstance(d,dict) or not isinstance(d.get("rows"),list):raise ValueError("BAD_HISTORICAL_SCHEMA")
    return d["rows"],len(b)
def unchanged(path,b):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=b:raise ValueError("IMMUTABLE_PATH_CONFLICT:"+str(path))
    else:
        with path.open("xb") as f:f.write(b)
    return {"path":str(path),"sha256":sha(b),"size":len(b)}
def fetch_public(label,url,required=False):
    """One WS1-only raw acquisition; no source identity re-dating."""
    directory=ROOT/"source_control"/"feature_source_receipts"
    directory.mkdir(parents=True,exist_ok=True)
    # Reuse the same hashed receipt on repeated local invocations of this adapter.
    rp=directory/(label+"_CAPTURE.json")
    if rp.exists():
        rec=json.loads(rp.read_bytes())
        p=Path(rec["raw_path"]);b=p.read_bytes()
        if sha(b)!=rec["sha256"]:raise ValueError("EXISTING_RAW_TAMPER:"+label)
        return list(csv.DictReader(io.StringIO(b.decode("utf-8-sig")))),rec
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"PickemAuditor-WS1-research/1.0"})
        with urllib.request.urlopen(req,timeout=18) as response:
            b=response.read(25000000)
            if len(b)>=25000000:raise ValueError("SOURCE_TOO_LARGE")
            hdr={k:v for k,v in response.headers.items()
                 if k.lower() in ("last-modified","etag","content-type")}
            final_url=response.url
        at=now()
        raw_path=directory/"raw"/(sha(b)+".csv")
        unchanged(raw_path,b)
        sample=list(csv.DictReader(io.StringIO(b.decode("utf-8-sig"))))
        if not sample:raise ValueError("EMPTY_SOURCE")
        receipt={"source":label,"requested_url":url,"resolved_url":final_url,
                 "observed_received_at":at,"earliest_forecaster_availability_at":at,
                 "upstream_publication_verified":False,"headers_not_publication_proof":hdr,
                 "sha256":sha(b),"raw_path":str(raw_path),"size_bytes":len(b),
                 "row_count":len(sample),"schema_columns":list(sample[0])}
        unchanged(rp,canonical(receipt))
        return sample,receipt
    except Exception as e:
        if required:raise
        return [],{"source":label,"status":"UNAVAILABLE","error":type(e).__name__+":"+str(e)[:240],
                   "attempt_observed_at":now(),"requested_url":url}
def self_test():
    assert stamp("2026-11-15T14:19:00Z")<stamp("2026-11-15T18:00:00Z")
    try:stamp("2026-11-15T10:00:00")
    except ValueError:pass
    else:raise AssertionError("naive time accepted")
    assert norm("Amon-Ra St. Brown")==norm("Amon Ra St Brown")
    assert numeric(float("nan")) is None
    assert numeric(-2)==-2
    assert count_stat({"def_tackles_solo":2,"def_tackles_with_assist":3,"def_tackle_assists":1},
                      "tackles + assists")==6
    assert count_stat({"def_tackles_solo":2,"def_tackles_with_assist":None,"def_tackle_assists":1},
                      "tackles + assists") is None
    assert not ready_clock({"source_received_at":"2026-11-15T14:00:00Z",
                            "event_start_at":"2026-11-15T14:30:00Z"},
                           "2026-11-15T14:31:00Z")
    assert ready_clock({"source_received_at":"2026-11-15T14:00:00Z",
                        "event_start_at":"2026-11-15T14:30:00Z"},
                       "2026-11-15T14:20:00Z")
    return 8
def count_stat(row,stat):
    if stat=="tackles + assists":
        values=[numeric(row.get(k)) for k in
                ("def_tackles_solo","def_tackles_with_assist","def_tackle_assists")]
        return None if any(v is None for v in values) else sum(values)
    return numeric(row.get(STATS[stat]))
def ready_clock(row,freeze):
    return (stamp(row["source_received_at"])<=stamp(freeze)<
            stamp(row["event_start_at"]))
def main():
    tests=self_test()
    pin_path=ROOT/"source_control/HANDOFF_PIN.json"
    pin_bytes=pin_path.read_bytes();pin=json.loads(pin_bytes)
    assert pin["source_control_manifest_sha256"]=="5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71"
    source_path=ROOT/pin["source_control_manifest_relative_path"]
    source_bytes=source_path.read_bytes()
    if sha(source_bytes)!=pin["source_control_manifest_sha256"]:raise ValueError("CANONICAL_SOURCE_PIN_MISMATCH")
    manifest=json.loads(source_bytes)
    if len(manifest["candidates"])!=1845 or sum(bool(c["research_shadow_eligible"]) for c in manifest["candidates"])!=1753:
        raise ValueError("CANONICAL_DENOMINATOR_CHANGED")
    freeze=now()
    input_manifest=json.loads((ARCHIVE/"MANIFEST.json").read_bytes())
    capture=input_manifest["collected_utc"]
    if stamp(capture)>stamp(freeze):raise ValueError("HISTORICAL_CAPTURE_FROM_FUTURE")
    inputs=[]
    records=[];catalog={};team_by_game=defaultdict(lambda:defaultdict(lambda:Counter()))
    for season in range(2016,2026):
        gp=ARCHIVE/f"games_{season}.json.gz"
        g,gs=rows_json_gz(gp,input_manifest["source_files"][gp.name])
        inputs.append({"path":str(gp),"sha256":input_manifest["source_files"][gp.name],
                       "rows":len(g),"source_first_verified_available_at":capture})
        for x in g:
            if str(x.get("game_type"))!="REG":continue
            gid=str(x.get("game_id") or "")
            day=str(x.get("gameday") or "")
            if not gid or not day or day[:10]>="2026-11-15":continue
            catalog[gid]={"game_id":gid,"date":day,"home":x.get("home_team"),
                          "away":x.get("away_team"),"week":x.get("week"),
                          "season":season,"game_final_at":None,
                          "first_verified_source_available_at":capture,
                          "game_final_time_not_independently_recorded":True}
        sp=ARCHIVE/f"stats_{season}.json.gz"
        rows,_=rows_json_gz(sp,input_manifest["source_files"][sp.name])
        inputs.append({"path":str(sp),"sha256":input_manifest["source_files"][sp.name],
                       "rows":len(rows),"source_first_verified_available_at":capture})
        for r in rows:
            gid=str(r.get("game_id") or "")
            if gid not in catalog or int(r.get("season",0))!=season or r.get("season_type")!="REG":continue
            pid=str(r.get("player_id") or "")
            if not pid or pid.lower()=="nan":continue
            rr={"game_id":gid,"game_date":catalog[gid]["date"],
                "season":season,"week":r.get("week"),
                "gsis_id":pid,"team":r.get("team"),"opponent":r.get("opponent_team"),
                "position":r.get("position"),
                "source_available_at":capture,"source_sha256":input_manifest["source_files"][sp.name],
                "source_file":str(sp)}
            for k in NUMERIC:rr[k]=numeric(r.get(k))
            records.append(rr)
    # New evidence is acquired by WS1 only; its actual raw bytes are content-hashed.
    new_receipts={}
    dataset={}
    for name,url in PUBLIC.items():
        data,receipt=fetch_public(name,url)
        dataset[name]=data;new_receipts[name]=receipt
    freeze=now()
    # Official 2026 weekly history: join only completed pre-today scheduled
    # games and retain the exact source retrieval time. Never use today's scores.
    g2026={}
    if dataset["games2026"] and dataset["stats2026"]:
        for g in dataset["games2026"]:
            if str(g.get("season"))!="2026" or str(g.get("game_type"))!="REG":continue
            day=str(g.get("gameday") or "")
            if not day or day[:10]>="2026-11-15" or numeric(g.get("result")) is None:continue
            gid=str(g.get("game_id") or "")
            if not gid:continue
            g2026[(str(g.get("week")),str(g.get("home_team")))] = (gid,day,g)
            g2026[(str(g.get("week")),str(g.get("away_team")))] = (gid,day,g)
            catalog[gid]={"game_id":gid,"date":day,"home":g.get("home_team"),
                          "away":g.get("away_team"),"week":g.get("week"),
                          "season":2026,"game_final_at":None,
                          "first_verified_source_available_at":new_receipts["games2026"]["observed_received_at"],
                          "game_final_time_not_independently_recorded":True}
        included=0
        for r in dataset["stats2026"]:
            if str(r.get("season"))!="2026" or r.get("season_type")!="REG":continue
            team=r.get("recent_team") or r.get("team")
            match=g2026.get((str(r.get("week")),str(team)))
            if match is None:continue
            gid,day,_=match
            pid=str(r.get("player_id") or r.get("gsis_id") or "")
            if not pid or pid.lower()=="nan":continue
            at=new_receipts["stats2026"]["observed_received_at"]
            if stamp(at)>stamp(freeze): continue
            rr={"game_id":gid,"game_date":day,"season":2026,"week":r.get("week"),
                "gsis_id":pid,"team":team,"opponent":r.get("opponent_team"),
                "position":r.get("position"),"source_available_at":at,
                "source_sha256":new_receipts["stats2026"]["sha256"],
                "source_file":new_receipts["stats2026"]["raw_path"]}
            for k in NUMERIC:rr[k]=numeric(r.get(k))
            records.append(rr);included+=1
        print("2026 source joined completed player game rows",included,"verified games",len(set(t[0] for t in g2026.values())))
    # Players official ESPN<->GSIS crosswalk, exact ID rather than name guess.
    bridge=defaultdict(set);names={}
    for r in dataset["players"]:
        espn=str(r.get("espn_id") or r.get("player_espn_id") or "").strip()
        gsis=str(r.get("gsis_id") or r.get("player_gsis_id") or "").strip()
        if not espn or not gsis or gsis.lower() in ("nan","none"):continue
        if espn.endswith(".0"):espn=espn[:-2]
        bridge[espn].add(gsis)
        names[(espn,gsis)]=r.get("display_name") or r.get("player_name") or ""
    # Strictly use histories with actual raw source receipt timestamps.
    by_player=defaultdict(list);team_games=defaultdict(lambda:defaultdict(list))
    for r in records:
        if not r["team"] or r["game_id"] not in catalog:continue
        if stamp(r["source_available_at"])>stamp(freeze):continue
        by_player[r["gsis_id"]].append(r)
        team_games[r["team"]][r["game_id"]].append(r)
    for rows in by_player.values(): rows.sort(key=lambda x:(x["game_date"],str(x["week"]),x["game_id"]))
    team_history=[]
    for team,games in sorted(team_games.items()):
        for gid,subset in sorted(games.items(),key=lambda g:catalog[g[0]]["date"]):
            all_pass=[r["attempts"] for r in subset if r["attempts"] is not None]
            all_rush=[r["carries"] for r in subset if r["carries"] is not None]
            team_history.append({"team":team,"game_id":gid,"game_date":catalog[gid]["date"],
                "season":catalog[gid]["season"],"week":catalog[gid]["week"],
                "pass_attempts_from_player_stats":sum(all_pass),
                "rush_attempts_from_player_stats":sum(all_rush),
                "team_plays":None,"sacks":None,
                "team_plays_unavailable":True,"sacks_unavailable":True,
                "source_available_at":max(r["source_available_at"] for r in subset),
                "source_sha256":sorted(set(r["source_sha256"] for r in subset))})
    snaps_receipt=new_receipts["snaps2026"]
    # No speculative snap join: source alone does not establish same player/game.
    defensive_snaps_available=False
    events=manifest["events"]; contracts=[];priors=[];history=[];cohort=Counter()
    for c in manifest["candidates"]:
        reasons=[]
        status={"SOURCE_IDENTITY_CERTIFIED":bool(c.get("source_certified")),
                "PREGAME_FEATURES_AVAILABLE":False,
                "CONDITIONAL_ON_APPEARANCE_FORECASTABLE":False,
                "STARTER_ELIGIBLE":c.get("eligibility_status")=="EXPECTED_STARTER_SOURCE_BACKED",
                "PRODUCT_TERMS_VERIFIED":False,"FULLY_CERTIFIED":False,"ABSTAIN":True}
        if not status["SOURCE_IDENTITY_CERTIFIED"]:reasons.append(c.get("source_validation_failure") or "SOURCE_IDENTITY_UNVERIFIED")
        if not c.get("research_shadow_eligible"):reasons.append(c.get("eligibility_reason") or "SOURCE_SHADOW_INELIGIBLE")
        if not ready_clock(c,freeze):reasons.append("KICKOFF_PASSED_OR_BAD_CAPTURE_CLOCK")
        if not bridge.get(str(c.get("player_id"))):reasons.append("ESPN_GSIS_CROSSWALK_UNAVAILABLE")
        if len(bridge.get(str(c.get("player_id")),[]))>1:reasons.append("AMBIGUOUS_ESPN_GSIS_CROSSWALK")
        gsis=next(iter(bridge[str(c["player_id"])])) if len(bridge.get(str(c.get("player_id")),[]))==1 else None
        if gsis and norm(c.get("player"))!=norm(names.get((str(c["player_id"]),gsis))):
            reasons.append("INDEPENDENT_NAME_ID_MISMATCH")
        hist=by_player.get(gsis,[]) if gsis else []
        hist=[x for x in hist if x["game_date"]<"2026-11-15"]
        recent=[x for x in hist if x["season"]>=2024]
        vals=[(x,count_stat(x,c["stat"])) for x in recent]
        valid=[(x,v) for x,v in vals if v is not None]
        if len(valid)<2:reasons.append("INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY")
        qb_market=c.get("stat") in ("pass attempts","completions","passing yards")
        if qb_market and not status["STARTER_ELIGIBLE"]:reasons.append("QB_STARTER_NOT_SOURCE_BACKED")
        if c.get("eligibility_status")=="BACKUP_INELIGIBLE":reasons.append("QB_BACKUP_EXCLUDED")
        if hist and gsis and len(valid)>=2:
            hrecent=valid[-10:]
            v=[x[1] for x in hrecent]
            p={"candidate_id":c["candidate_id"],"espn_player_id":c.get("player_id"),
               "gsis_player_id":gsis,"player_name":c.get("player"),
               "historical_game_rows":len(hist),"recent_verifiable_stat_rows":len(valid),
               "stat":c["stat"],"market_column":STATS[c["stat"]],
               "mean_last3":sum(v[-3:])/len(v[-3:]),
               "mean_last5":sum(v[-5:])/len(v[-5:]),
               "mean_last10":sum(v)/len(v),
               "minimum_last10":min(v),"maximum_last10":max(v),
               "last_game_date":hrecent[-1][0]["game_date"],
               "history_training_data_cutoff_at":max(x[0]["source_available_at"] for x in valid),
               "source_sha256s":sorted(set(x[0]["source_sha256"] for x in valid)),
               "current_roster_team":c.get("team"),
               "last_historical_team":hrecent[-1][0]["team"],
               "transfer_or_team_change_possible":hrecent[-1][0]["team"]!=c.get("team"),
               "defensive_snaps":None,"defensive_snap_status":"NOT_AUTHENTICATED"}
            priors.append(p)
            for h,vv in hrecent:history.append({"candidate_id":c["candidate_id"],**h})
            status["PREGAME_FEATURES_AVAILABLE"]=True
        else:p=None
        permitted=not reasons and status["PREGAME_FEATURES_AVAILABLE"]
        status["CONDITIONAL_ON_APPEARANCE_FORECASTABLE"]=permitted
        status["ABSTAIN"]=not permitted
        if permitted:
            assert status["SOURCE_IDENTITY_CERTIFIED"]
            assert stamp(c["source_received_at"])<=stamp(freeze)<stamp(c["event_start_at"])
        item={"candidate_id":c["candidate_id"],"quote_id":c["quote_id"],
              "event_id":c.get("event_id"),"player_id":c.get("player_id"),
              "gsis_player_id":gsis,"team":c.get("team"),"opponent":c.get("opponent"),
              "player":c.get("player"),"position":c.get("position"),
              "stat":c.get("stat"),"period":c.get("period"),"line":c.get("line"),
              "book":c.get("book"),"event_start_at":c.get("event_start_at"),
              "source_received_at":c.get("source_received_at"),
              "original_quote_observed_at":c.get("source_received_at"),
              "original_quote_reported_at":c.get("original_quote_reported_at"),
              "original_quote_reported_time_semantics":c.get("original_quote_reported_time_semantics"),
              "source_sha256":c.get("source_sha256"),"input_freeze_at":c.get("input_freeze_at"),
              "feature_freeze_at":freeze,"forecast_at":None,
              "model_training_cutoff_at":None,"model_artifact_sha256":None,
              "source_manifest_file_sha256":pin["source_control_manifest_sha256"],
              "status":status,"abstention_reasons":sorted(set(reasons)),
              "prior_candidate_id":p["candidate_id"] if p else None,
              "product_terms":c.get("settlement_semantics"),
              "availability_status":"PREGAME_INACTIVES_NOT_CERTIFIED",
              "unconditional_participation_probability":None,
              "conditional_on_appearance_only":permitted,
              "research_only":True}
        contracts.append(item)
        cohort[(item["event_id"],item["stat"])] += 1
    # Shared history tables, exact offers, WS3 normalization and fail-closed ledger.
    root=ROOT/"source_control"/"feature_store"
    tables={
      "events":events,
      "team_history":team_history,
      "player_history_last10_by_contract":history,
      "pregame_roster_availability":[{"event_id":c["event_id"],"player_id":c["player_id"],
           "eligibility_status":c.get("eligibility_status"),
           "expected_qb_starter_source_backed":c.get("eligibility_status")=="EXPECTED_STARTER_SOURCE_BACKED",
           "injury_inactive_verification":False,"participation_probability":None,
           "roster_receipt_sha256":c.get("roster_receipt_sha256")} for c in manifest["candidates"]],
      "historical_statistical_priors":priors,
      "original_contracts":contracts,
      "ws1-nfl-pregame-opportunity-v1":[{
          "schema":"ws1-nfl-pregame-opportunity-v1",
          "candidate_id":c["candidate_id"],"event_id":c["event_id"],"player_id":c["player_id"],
          "gsis_player_id":c["gsis_player_id"],"team":c["team"],"opponent":c["opponent"],
          "stat":c["stat"],"period":c["period"],"line":c["line"],"book":c["book"],
          "quote_id":c["quote_id"],"source_sha256":c["source_sha256"],
          "source_manifest_file_sha256":c["source_manifest_file_sha256"],
          "event_start_at":c["event_start_at"],
          "original_quote_observed_at":c["original_quote_observed_at"],
          "input_freeze_at":c["input_freeze_at"],"feature_freeze_at":freeze,
          "history_prior":next((p for p in priors if p["candidate_id"]==c["candidate_id"]),None),
          "status":c["status"],"abstention_reasons":c["abstention_reasons"],
          "research_only":True}
          for c in contracts]
    }
    paths={}
    for label,rr in tables.items():
        b=b"".join(canonical(row) for row in rr)
        dest=root/(label+"_"+sha(b)+".jsonl")
        paths[label]={"path":str(dest),"sha256":sha(b),"rows":len(rr),"size_bytes":len(b)}
        unchanged(dest,b)
    by_gm=defaultdict(lambda:{"original_quotes":0,"source_identity_certified":0,
               "feature_ready":0,"conditional_forecast_permitted":0,"fully_certified":0,
               "abstentions":0,"reasons":Counter()})
    for c in contracts:
        q=by_gm[(c["event_id"],c["stat"])]
        q["original_quotes"]+=1
        q["source_identity_certified"]+=int(c["status"]["SOURCE_IDENTITY_CERTIFIED"])
        q["feature_ready"]+=int(c["status"]["PREGAME_FEATURES_AVAILABLE"])
        q["conditional_forecast_permitted"]+=int(c["status"]["CONDITIONAL_ON_APPEARANCE_FORECASTABLE"])
        q["fully_certified"]+=int(c["status"]["FULLY_CERTIFIED"])
        q["abstentions"]+=int(c["status"]["ABSTAIN"])
        q["reasons"].update(c["abstention_reasons"])
    coverage=[{"event_id":event,"stat":market,**{k:(dict(sorted(v.items())) if k=="reasons" else v)
                  for k,v in values.items()}} for (event,market),values in sorted(by_gm.items())]
    cb=b"".join(canonical(x) for x in coverage)
    coverage_path=root/("per_game_market_"+sha(cb)+".jsonl")
    unchanged(coverage_path,cb)
    paths["per_game_market"]={"path":str(coverage_path),"sha256":sha(cb),"rows":len(coverage)}
    summary={"original_quotes":len(contracts),
             "source_identity_certified":sum(c["status"]["SOURCE_IDENTITY_CERTIFIED"] for c in contracts),
             "feature_ready":sum(c["status"]["PREGAME_FEATURES_AVAILABLE"] for c in contracts),
             "conditional_forecasts_permitted":sum(c["status"]["CONDITIONAL_ON_APPEARANCE_FORECASTABLE"] for c in contracts),
             "fully_certified":sum(c["status"]["FULLY_CERTIFIED"] for c in contracts),
             "abstentions":sum(c["status"]["ABSTAIN"] for c in contracts),
             "verified_event_rows":len(events),"team_history_rows":len(team_history),
             "history_player_game_rows":len(records),"distinct_history_players":len(by_player),
             "espn_gsis_crosswalk_id_count":len(bridge)}
    if summary["original_quotes"]!=summary["conditional_forecasts_permitted"]+summary["abstentions"]:
        raise ValueError("ABSTENTION_DENOMINATOR_NONCONSERVATION")
    if summary["fully_certified"]!=0:raise ValueError("UNSUPPORTED_FULL_RELEASE")
    pin_out={
      "schema":"ws1_nfl_sunday_immutable_forecast_feature_pin_v1",
      "date":"2026-11-15","status":"PROSPECTIVE_RESEARCH_ONLY_NO_PRODUCTION_RELEASE",
      "feature_freeze_at":freeze,"generated_at":now(),
      "original_handoff_pin_path":str(pin_path),"original_handoff_pin_sha256":sha(pin_bytes),
      "canonical_source_manifest_path":str(source_path),
      "canonical_source_manifest_file_sha256":sha(source_bytes),
      "original_source_input_freeze_at":manifest["input_freeze_at"],
      "archived_history_source_manifest_path":str(ARCHIVE/"MANIFEST.json"),
      "archived_history_manifest_file_sha256":sha((ARCHIVE/"MANIFEST.json").read_bytes()),
      "archived_history_capture_first_verified_at":capture,
      "history_original_pregame_availability_verified":False,
      "history_evidence_files":inputs,"new_raw_source_receipts":new_receipts,
      "tables":paths,"per_game_market_coverage":coverage,
      "summary":summary,"validation":{
           "preflight_adversarial_assertions":tests,"original_source_bytes_verified":True,
           "historical_file_sha_verifications":len(inputs),
           "new_raw_source_hash_verifications":sum(1 for x in new_receipts.values() if "sha256" in x),
           "all_original_quote_ids_retained":True,"all_abstentions_retained":True,
           "no_same_day_or_future_game_features":True,
           "no_fabricated_probabilities":True,"no_verified_product_terms":True},
      "historical_uncertainties":["No authenticated 2016-2025 historical pregame source-time claims",
        "No complete team scrimmage plays or sacks from reduced weekly player-stats bundle",
        "2026 source missing or rejected when independent schedule/final evidence is unavailable",
        "Player-snap participation requires independently joined source",
        "Historical original QB starter evidence not independently time-verified",
        "Quote ownership and source identity do not verify final inactives or product void/payout rules"],
      "release_authority":False,"no_model_training_or_forecasts_generated_by_ws1":True,
      "no_original_source_recollection":True
    }
    output=canonical(pin_out)
    sha_pin=sha(output)
    immutable_path=root/"pins"/sha_pin/"FORECAST_FEATURE_PIN.json"
    unchanged(immutable_path,output)
    root_pin=ROOT/"FORECAST_FEATURE_PIN.json"
    if not root_pin.exists():unchanged(root_pin,output)
    print(json.dumps({"feature_pin_path":str(immutable_path),"feature_pin_sha256":sha_pin,
                      "root_pin_path":str(root_pin),"summary":summary,
                      "preflight_assertions":tests,"sources":{k:v.get("status","CAPTURED")
                                for k,v in new_receipts.items()},
                      "coverage_rows":len(coverage)},sort_keys=True))
if __name__=="__main__":main()
