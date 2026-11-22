"""Independent NBA FINAL importer and P5 original-S0 scoring for the morning.

NOT a pregame collector; no prediction regeneration or model fitting.
Uses only the original archived P0 NBA forecasts as event scope.
The ESPN FINAL response is separately captured as original raw bytes,
verified with its own SourceReceipt, and strictly matched to the exact
pregame ESPN event/team/player identity. Absent players remain UNRESOLVED,
never DNP or a synthetic zero. A morning rerun is append-only/idempotent.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256 as hashlib_sha256
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import argparse
import json
import os
import re
import time

from v2.p0_integrity.contracts import (
    record, sha256, canonical_bytes, utc, verify_source_bytes,
)
from v2.p0_integrity.storage import append_immutable, attest_project_storage
from v2.official_nba_nhl_capture import nba_stat_rows, SettlementCaptureError
from research.p5_daily.warehouse import (
    enumerate_p0, recover_frozen_forecasts, recover_official_outcomes,
    run_morning_from_frozen_p0,
)

ROOT=Path("/work")
STAGING=Path("research/v25_remediation/nba_final")
BASE="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event="
EVENT_ID=re.compile(r"^espn:game:([0-9]+)$")
TEAM_ID=re.compile(r"^espn:team:([0-9]+)$")
PLAYER_ID=re.compile(r"^espn:player:([0-9]+)$")

class FinalBlocked(ValueError):
    pass

def require(ok,why):
    if not ok:
        raise FinalBlocked(why)

def stamp(now=None):
    now = datetime.now(timezone.utc) if now is None else now
    require(now.tzinfo is not None and now.utcoffset() is not None,
            "NAIVE_OBSERVATION_CLOCK")
    return now.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00","Z")

def digest(raw):
    return hashlib_sha256(raw).hexdigest()

def atomic_bytes(path,raw):
    require(path.is_relative_to(ROOT), "SOURCE_ARCHIVE_OUTSIDE_P0")
    require(not path.is_symlink() and not any(x.is_symlink() for x in path.parents
        if x not in (Path("/"),ROOT)), "UNSAFE_SOURCE_SYMLINK")
    path.parent.mkdir(parents=True,exist_ok=True)
    flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,"O_NOFOLLOW",0)
    try:
        fd=os.open(path,flags,0o600)
        with os.fdopen(fd,"wb") as out:
            out.write(raw);out.flush();os.fsync(out.fileno())
        state="APPENDED"
    except FileExistsError:
        state="IDEMPOTENT_EXISTING"
    require(path.read_bytes()==raw,"ORIGINAL_OFFICIAL_BYTES_CHANGED")
    return {"status":state,"relative_path":str(path.relative_to(ROOT)),
            "sha256":digest(raw)}

def capture_final(event_numeric, *, opener=urlopen, now=None):
    """One bounded original provider response; never a post-event forecast."""
    require(re.fullmatch(r"[0-9]+",str(event_numeric)) is not None,
            "OFFICIAL_GAME_ID_INVALID")
    url=BASE+str(event_numeric)
    last=None
    for i in range(2):
        try:
            with opener(Request(url,headers={
                "User-Agent":"pickem-auditor-P5-official-final/1",
                "Accept":"application/json"}),timeout=20) as reply:
                if reply.status!=200:
                    raise FinalBlocked("OFFICIAL_HTTP_NON_200:"+str(reply.status))
                raw=reply.read(8*1024*1024+1)
            require(0<len(raw)<=8*1024*1024,"OFFICIAL_RAW_EMPTY_OR_OVERSIZE")
            return {"url":url,"raw":raw,"observed_at":stamp(now)}
        except (HTTPError,URLError,OSError,TimeoutError) as exc:
            last=type(exc).__name__+":"+str(exc)[:170]
            if i==0:time.sleep(.4)
    raise FinalBlocked("OFFICIAL_SOURCE_UNAVAILABLE:"+str(last))

def parse_verified_nba_final(raw, *, original_event_id,
                             expected_team_ids):
    """Read existing independently tested P5 NBA scorecard parser."""
    match=EVENT_ID.fullmatch(original_event_id)
    require(match is not None,"PREGAME_EVENT_NAMESPACE_MISSING")
    require(isinstance(raw,bytes) and bool(raw),"OFFICIAL_RAW_REQUIRED")
    try:
        source=json.loads(raw)
        comps=source["header"]["competitions"]
        require(len(comps)==1 and str(comps[0]["id"])==match.group(1),
                "OFFICIAL_EVENT_IDENTITY_MISMATCH")
        competitor=comps[0]["competitors"]
        require(len(competitor)==2,"OFFICIAL_TEAM_COUNT_INVALID")
        team_by_id={}
        abbreviations=set()
        for c in competitor:
            t=c["team"]
            tid=str(t["id"])
            abbr=str(t["abbreviation"]).upper()
            require(tid not in team_by_id and abbr and abbr not in abbreviations,
                    "OFFICIAL_TEAM_IDENTIFIER_AMBIGUOUS")
            team_by_id[tid]=abbr
            abbreviations.add(abbr)
        expect={TEAM_ID.fullmatch(x).group(1) for x in expected_team_ids
                if TEAM_ID.fullmatch(x)}
        require(len(expect)==2 and expect==set(team_by_id),
                "OFFICIAL_TEAMS_DIFFER_FROM_ORIGINAL_PREGAME")
        played=nba_stat_rows(source,expected_teams=abbreviations)
    except (KeyError,ValueError,TypeError,IndexError,SettlementCaptureError) as exc:
        raise FinalBlocked("OFFICIAL_FINAL_UNVERIFIED:"+str(exc)[:160]) from exc
    return {"event_id":original_event_id,
        "teams":team_by_id,"played":played,
        "game_state":"FINAL","raw_sha256":digest(raw)}

def _original_frozen_scope():
    recovered=recover_frozen_forecasts("/work",sport="NBA")
    group=defaultdict(list)
    for original in recovered["accepted"]:
        f=original["forecast"]
        if f["admission_class"]!="A" or original["feature"]["reconstruction_class"]!="original":
            continue
        if f["uncertainty"].get("family")!="S0" or f["uncertainty"].get("pipeline")!="S_ONLY":
            continue
        if f["eligible"] or set(f["abstention_reasons"])!={"PARTICIPATION_UNRESOLVED",
                            "CONDITIONAL_ON_PLAYING_ONLY","ELIGIBILITY_UNVERIFIED"}:
            continue
        require(EVENT_ID.fullmatch(f["event_id"]) is not None,
                "UNSUPPORTED_EVENT_NAMESPACE")
        require(TEAM_ID.fullmatch(f["team_id"]) is not None and
                TEAM_ID.fullmatch(f["opponent_id"]) is not None,
                "UNSUPPORTED_TEAM_NAMESPACE")
        require(PLAYER_ID.fullmatch(f["player_id"]) is not None,
                "UNSUPPORTED_PLAYER_NAMESPACE")
        group[f["event_id"]].append(original)
    return {"events":group,"rejections":recovered["rejected"],
            "corrupt_or_incomplete":recovered["corrupt_or_incomplete_p0_records"]}

def _first_same_raw_receipt(rawsha,url):
    existing,bad=enumerate_p0("/work","SourceReceipt")
    require(not bad,"OFFICIAL_VAULT_CORRUPT_SOURCE_RECORDS")
    exact=[x["record"] for x in existing.values()
           if x["record"]["source_kind"]=="nba_espn_final_summary" and
              x["record"]["source_id"]==url and
              x["record"]["source_sha256"]==rawsha]
    for r in exact:
        verify_source_bytes(r,"/work")
    exact.sort(key=lambda x:(x["collected_at"],x["receipt_id"]))
    return exact[0] if exact else None

def _archive_final(raw,event_id,url,seen):
    sha=digest(raw)
    target=ROOT/STAGING/"source_bytes"/(sha+".json")
    archive=atomic_bytes(target,raw)
    existing=_first_same_raw_receipt(sha,url)
    if existing is not None:
        return existing
    receipt=record("SourceReceipt",
        receipt_id="nba-final-source:"+event_id+":"+sha+":"+
                   digest(seen.encode())[:18],
        source_id=url,source_kind="nba_espn_final_summary",
        source_available_at=seen,collected_at=seen,
        source_sha256=sha,archive_path=archive["relative_path"],
        provenance_class="collector_possession")
    append_immutable("/work","SourceReceipt",receipt)
    verify_source_bytes(receipt,"/work")
    return receipt

def admit_one_final(forecasts,raw, *,observed_at,url):
    """Persist only independently revalidated player-game facts."""
    require(bool(forecasts),"NO_ORIGINAL_FORECASTS_FOR_EVENT")
    event_id=forecasts[0]["forecast"]["event_id"]
    require(all(item["forecast"]["event_id"]==event_id for item in forecasts),
            "MIXED_EVENT_FORECAST_SCOPE")
    start=forecasts[0]["forecast"]["event_start_at"]
    require(utc(observed_at)>utc(start),"OFFICIAL_OBSERVATION_NOT_AFTER_EVENT")
    teams=set()
    for row in forecasts:
        f=row["forecast"]
        require(f["event_start_at"]==start,"ORIGINAL_GAME_START_CONFLICT")
        teams.update((f["team_id"],f["opponent_id"]))
    data=parse_verified_nba_final(raw,original_event_id=event_id,
                                  expected_team_ids=teams)
    source=_archive_final(raw,event_id,url,observed_at)
    written=[];unresolved=[]
    prior=recover_official_outcomes("/work")["by_stat_identity"]
    for row in forecasts:
        f=row["forecast"]
        team_number=TEAM_ID.fullmatch(f["team_id"]).group(1)
        player_number=PLAYER_ID.fullmatch(f["player_id"]).group(1)
        player=data["played"].get(player_number)
        if player is None:
            unresolved.append({"player_id":f["player_id"],"stat_key":f["stat_key"],
                "reason":"NOT_IN_OFFICIAL_PLAYED_BOX_DNP_NOT_ASSUMED"})
            continue
        if player["team"]!=data["teams"][team_number]:
            unresolved.append({"player_id":f["player_id"],"stat_key":f["stat_key"],
                "reason":"OFFICIAL_PLAYER_TEAM_DISAGREES_WITH_ORIGINAL"})
            continue
        actual=player.get(f["stat_key"])
        require(type(actual) is int and actual>=0,
                "OFFICIAL_STAT_NOT_AN_EXACT_NONNEGATIVE_COUNT")
        key=tuple(f[k] for k in ("sport","event_id","team_id","player_id",
                                 "stat_key","period"))
        if prior.get(key):
            written.append({"player_id":f["player_id"],"stat_key":f["stat_key"],
                            "status":"PRIOR_OFFICIAL_OUTCOME_PRESERVED"})
            continue
        official=record("OutcomeRecord",
            outcome_id="nba-final:"+event_id+":"+f["player_id"]+":"+
                       f["stat_key"]+":"+source["source_sha256"][:20],
            sport="NBA",event_id=f["event_id"],team_id=f["team_id"],
            player_id=f["player_id"],stat_key=f["stat_key"],period=f["period"],
            official_result_available_at=source["collected_at"],
            official_source_receipt_id=source["receipt_id"],
            official_source_sha256=source["source_sha256"],
            actual_value=actual,participation="PLAYED",
            result_version="v1",status="FINAL")
        p=append_immutable("/work","OutcomeRecord",official)
        written.append({"player_id":f["player_id"],"stat_key":f["stat_key"],
            "status":p["status"],"outcome_id":official["outcome_id"],
            "source_sha256":source["source_sha256"],
            "actual":actual})
    return {"event_id":event_id,"original_final_source_sha256":digest(raw),
            "official_source_receipt_id":source["receipt_id"],
            "verified_official":True,"outcome_rows":written,
            "unresolved":unresolved,"research_only":True}

def run_morning(*,max_games=12,clock=None,opener=urlopen,fetch_only=False):
    attest_project_storage("/work")
    require(1<=max_games<=40,"GAME_CAP_INVALID")
    now=datetime.now(timezone.utc) if clock is None else clock()
    require(now.tzinfo is not None and now.utcoffset() is not None,
            "NAIVE_MORNING_CLOCK")
    scope=_original_frozen_scope()
    results=[]
    for event,rows in sorted(scope["events"].items(),
                             key=lambda t:t[1][0]["forecast"]["event_start_at"]):
        if len(results)>=max_games:break
        start=rows[0]["forecast"]["event_start_at"]
        if utc(start)>=utc(now):
            results.append({"event_id":event,"status":"EVENT_NOT_FINISHED"})
            continue
        prior=recover_official_outcomes("/work")["by_stat_identity"]
        uncovered=[r for r in rows
            if tuple(r["forecast"][k] for k in
              ("sport","event_id","team_id","player_id","stat_key","period")) not in prior]
        if not uncovered:
            results.append({"event_id":event,"status":"OFFICIAL_ALREADY_ARCHIVED"})
            continue
        numeric=EVENT_ID.fullmatch(event).group(1)
        try:
            reply=capture_final(numeric,opener=opener,now=now)
            parsed=parse_verified_nba_final(reply["raw"],
                original_event_id=event,
                expected_team_ids={t for r in rows for t in
                    (r["forecast"]["team_id"],r["forecast"]["opponent_id"])})
            if fetch_only:
                results.append({"event_id":event,"status":"OFFICIAL_FINAL_FETCH_VERIFIED_ONLY",
                    "raw_sha256":parsed["raw_sha256"],"original_forecasts":len(rows)})
            else:
                outcome=admit_one_final(rows,reply["raw"],
                    observed_at=reply["observed_at"],url=reply["url"])
                results.append({"event_id":event,"status":"OFFICIAL_FINAL_ADMITTED",
                    "result":outcome})
        except Exception as exc:
            results.append({"event_id":event,"status":"OFFICIAL_FINAL_BLOCKED",
                            "reason":type(exc).__name__+":"+str(exc)[:300]})
    settlement=None
    if not fetch_only:
        try:
            settlement=run_morning_from_frozen_p0(
                root="/work",run_at=stamp(now),
                permit_research_writes=True,update_adapters=None)
        except Exception as exc:
            settlement={"status":"P5_SETTLEMENT_BLOCKED",
                        "reason":type(exc).__name__+":"+str(exc)[:300]}
    report={"schema":"PA-V25-NBA-S0-OFFICIAL-MORNING/1",
       "generated_at":stamp(now),"scope_original_events":len(scope["events"]),
       "scope_rejections":scope["rejections"],"source_integrity_rejections":scope["corrupt_or_incomplete"],
       "official_attempts":results,"settlement":settlement,
       "outcome_rows_created":sum(sum(x["status"]=="APPENDED" for x in
                  y.get("result",{}).get("outcome_rows",[])) for y in results),
       "research_only":True,"no_pregame_prediction_regenerated":True,
       "training_updated":False,"no_new_source_collector_for_pregame":True}
    data=canonical_bytes(report)
    receipt=atomic_bytes(ROOT/STAGING/"morning_reports"/(digest(data)+".json"),data)
    return {"report":report,"receipt":receipt}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--max-games",type=int,default=12)
    p.add_argument("--official-only",action="store_true")
    args=p.parse_args(argv)
    result=run_morning(max_games=args.max_games,fetch_only=args.official_only)
    print(json.dumps(result,sort_keys=True,default=str))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
