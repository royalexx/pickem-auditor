"""Independent, original-source NBA S0 player-prop O/U sidecar.

S0 class A forecasts remain market-free and immutable. This module captures
one bounded original PropLine NBA quote response plus an independent ESPN
pregame event crosswalk, archives raw bytes, admits only matched, two-sided
MarketQuote records, and later scores contracts using FINAL OutcomeRecords.

No betting advice, synthetic lines, player participation imputation,
unverified name-only event matches, or forecast regeneration.
"""
from __future__ import annotations

from collections import defaultdict, Counter
from datetime import datetime, timezone
from hashlib import sha256 as digest_sha
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import argparse
import json
import math
import os
import sys

from v2.p0_integrity.contracts import record, sha256, canonical_bytes, utc, verify_source_bytes
from v2.p0_integrity.storage import attest_project_storage, append_immutable, verify_immutable_record
from research.p5_daily.warehouse import recover_frozen_forecasts, recover_official_outcomes, enumerate_p0

ROOT=Path("/work")
BASE=Path("research/v25_remediation/nba_s0_ou")
PROPLINE="https://api.prop-line.com/v1/sports/basketball_nba/odds"
ESPN="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
MARKETS=("player_points","player_rebounds","player_assists","player_threes")
BOOKS=("pinnacle","fanduel","draftkings","betmgm")

class QuoteBlocked(ValueError):
    pass

def require(ok,reason):
    if not ok:raise QuoteBlocked(reason)

def timestamp(t=None):
    t=datetime.now(timezone.utc) if t is None else t
    require(t.tzinfo is not None and t.utcoffset() is not None,"NAIVE_CLOCK")
    return t.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00","Z")

def odds_helpers():
    # Reuse the existing tested parser; never duplicate its bookmaker/market rules.
    root=Path(__file__).resolve().parents[2]
    if str(root/"scripts") not in sys.path:sys.path.insert(0,str(root/"scripts"))
    from scripts import odds_providers as provider
    return provider

def atomic(relative,raw):
    require(isinstance(raw,bytes) and bool(raw),"EMPTY_ORIGINAL_BYTES")
    path=ROOT/relative
    require(path.is_relative_to(ROOT) and not path.is_symlink() and
            not any(parent.is_symlink() for parent in path.parents
                    if parent not in (Path("/"),ROOT)),"UNSAFE_ARCHIVE_PATH")
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
    except FileExistsError:
        require(path.read_bytes()==raw,"IMMUTABLE_ARCHIVE_COLLISION")
        return str(relative)
    with os.fdopen(fd,"wb") as f:
        f.write(raw);f.flush();os.fsync(f.fileno())
    require(path.read_bytes()==raw,"ARCHIVE_READBACK_FAILED")
    return str(relative)

def original_source(url,raw,at,kind):
    require(utc(at) is not None and url.startswith("https://"),"INVALID_SOURCE")
    digest=digest_sha(raw).hexdigest()
    relative=BASE/"raw"/(digest+".json")
    path=atomic(relative,raw)
    receipt=record("SourceReceipt",
        receipt_id="nba-s0-ou-source:"+sha256({"url":url,"at":at,"sha":digest}),
        source_id=url,source_kind=kind,
        source_available_at=at,collected_at=at,
        source_sha256=digest,archive_path=path,
        provenance_class="collector_possession")
    append_immutable("/work","SourceReceipt",receipt)
    verify_source_bytes(receipt,"/work")
    return receipt

def http_raw(url,*,key=None,opener=urlopen):
    headers={"Accept":"application/json","User-Agent":"pickem-auditor-nba-s0-ou-research/1"}
    if key:headers["X-API-Key"]=key
    with opener(Request(url,headers=headers),timeout=22) as response:
        require(getattr(response,"status",200)==200,"ORIGINAL_HTTP_NON200")
        raw=response.read(8*1024*1024+1)
    require(0<len(raw)<=8*1024*1024,"ORIGINAL_HTTP_EMPTY_OR_OVERSIZE")
    return raw,timestamp()

def event_crosswalk(raw,forecasts):
    """Bind ESPN numeric event/team IDs to genuine pregame abbreviations."""
    provider=odds_helpers()
    try:events=json.loads(raw)["events"]
    except (KeyError,ValueError,TypeError) as exc:
        raise QuoteBlocked("ESPN_SCHEDULE_SCHEMA") from exc
    result={}
    by_event=defaultdict(list)
    for item in forecasts:by_event[item["forecast"]["event_id"]].append(item)
    for event in events:
        gid="espn:game:"+str(event.get("id",""))
        if gid not in by_event:continue
        rows=by_event[gid]
        require(len(event.get("competitions",[]))==1,"ESPN_EVENT_AMBIGUOUS")
        teams=event["competitions"][0]["competitors"]
        require(len(teams)==2,"ESPN_TEAM_COUNT")
        expected={x for f in rows for x in
                  (f["forecast"]["team_id"],f["forecast"]["opponent_id"])}
        discovered={"espn:team:"+str(t["team"]["id"]):provider.normalize_team(
            t["team"].get("abbreviation")) for t in teams}
        require(set(discovered)==expected and all(discovered.values()) and
                len(set(discovered.values()))==2,"ESPN_TEAM_CROSSWALK_CONFLICT")
        require(abs((provider.parse_time(event.get("date"))-
                     utc(rows[0]["forecast"]["event_start_at"])).total_seconds())<=60,
                "ESPN_TIPOFF_CHANGED")
        status=event.get("status",{}).get("type",{}).get("name")
        require(status=="STATUS_SCHEDULED","ESPN_EVENT_NOT_SCHEDULED")
        result[gid]={"start":event["date"],"teams":discovered}
    return result

def identity_match(quote,original,verified,*,captured_at):
    """No join by name alone: exact ESPN event teams, start, player+team."""
    p=odds_helpers()
    f=original["forecast"]
    feat=original["feature"]["features"]
    require(quote.get("sport")=="NBA","QUOTE_NOT_NBA")
    require(f["event_id"] in verified,"ORIGINAL_ESPN_EVENT_NOT_VERIFIED")
    game=verified[f["event_id"]]
    expected_team=game["teams"][f["team_id"]]
    provider_teams=quote.get("event_teams")
    require(isinstance(provider_teams,list) and
            set(provider_teams)==set(game["teams"].values()) and
            len(provider_teams)==2,"QUOTE_EVENT_TEAM_CROSSWALK")
    q_start=p.parse_time(quote.get("event_start"))
    require(q_start is not None and
            abs((q_start-utc(game["start"])).total_seconds())<=60,
            "QUOTE_EVENT_START_CONFLICT")
    require(quote.get("stat")==f["stat_key"],"QUOTE_STAT_MISMATCH")
    require(p.normalize_player(quote.get("player"))==
            p.normalize_player(feat.get("current_name")) and
            bool(feat.get("current_name")),"QUOTE_PLAYER_NAME_CONFLICT")
    require(not quote.get("team") or quote["team"]==expected_team,
            "QUOTE_PLAYER_TEAM_CONFLICT")
    require(utc(captured_at)<utc(f["event_start_at"]),
            "QUOTE_AFTER_EVENT")
    require(quote.get("book") in
            ("Pinnacle","FanDuel","DraftKings","BetMGM"),
            "UNAPPROVED_BOOK")
    require(isinstance(quote.get("line"),(float,int)) and
            not isinstance(quote.get("line"),bool) and
            math.isfinite(quote["line"]) and quote["line"]>=0,
            "INVALID_OU_LINE")
    require(type(quote.get("over_odds")) in (int,float) and
            type(quote.get("under_odds")) in (int,float) and
            abs(quote["over_odds"])>=100 and abs(quote["under_odds"])>=100,
            "TWO_SIDED_PRICES_REQUIRED")
    return True

def poisson_contract(lam,line):
    require(type(lam) in (int,float) and math.isfinite(lam) and
            0<=lam<=300,"S0_POISSON_PARAMETER_INVALID")
    require(type(line) in (int,float) and math.isfinite(line) and
            0<=line<=1000,"NBA_PROP_LINE_INVALID")
    integer=float(line).is_integer()
    under_max=math.ceil(line)-1 if not integer else int(line)-1
    def mass(k):
        if k<0:return 0.
        if lam==0:return 1. if k==0 else 0.
        return math.exp(-lam+k*math.log(lam)-math.lgamma(k+1))
    under=math.fsum(mass(i) for i in range(under_max+1))
    push=mass(int(line)) if integer else 0.
    over=max(0.,1.-under-push)
    tot=under+push+over
    require(abs(tot-1)<1e-9,"OU_PROBABILITY_MASS")
    return {"under":under,"push":push,"over":over}

def implied(american):
    require(type(american) in (int,float) and math.isfinite(american)
            and abs(american)>=100,"INVALID_AMERICAN_PRICE")
    return 100/(american+100) if american>0 else -american/(-american+100)

def market_probabilities(over_odds,under_odds):
    a,b=implied(over_odds),implied(under_odds)
    require(a+b>0,"INVALID_TWO_SIDED_OVERROUND")
    return {"over_no_vig":a/(a+b),"under_no_vig":b/(a+b),
            "raw_over_implied":a,"raw_under_implied":b,"overround":a+b-1}

def qualified_forecasts(*,now=None):
    at=timestamp(now)
    recovered=recover_frozen_forecasts("/work",sport="NBA")
    results=[]
    for original in recovered["accepted"]:
        f=original["forecast"]
        if (f.get("model_id")!="PA-V25-NBA-S0-CONDITIONAL-PLAYED" or
            f["admission_class"]!="A" or f["eligible"] or
            f["stat_key"] not in ("points","rebounds","assists","threes") or
            original["feature"]["reconstruction_class"]!="original"):
            continue
        if utc(f["event_start_at"])<=utc(at):continue
        results.append(original)
    return results,recovered

def capture_original_ou(*,day,key=None,opener=urlopen,clock=None):
    """Capture once per event/day when genuine pregame S0 is already frozen.

    Fail closed on unavailable key, broken identity or post-tip data.
    Original source bytes are preserved even when every candidate is rejected.
    """
    attest_project_storage("/work")
    now=datetime.now(timezone.utc) if clock is None else clock()
    at=timestamp(now)
    from zoneinfo import ZoneInfo
    require(day==now.astimezone(ZoneInfo("America/Toronto")).date().isoformat(),
            "ONLY_CURRENT_DAY_ORIGINAL_ODDS")
    rows,recovery=qualified_forecasts(now=now)
    rows=[r for r in rows if utc(r["forecast"]["event_start_at"]).astimezone(
        ZoneInfo("America/Toronto")).date().isoformat()==day]
    if not rows:
        return {"status":"NO_FROZEN_UPCOMING_S0_TO_PRICE","candidate_forecasts":0,
                "matched_quotes":0,"research_only":True}
    secret=os.environ.get("PROPLINE_API_KEY","").strip() if key is None else key
    if not secret:
        return {"status":"NO_AUTHENTIC_PROPLINE_CREDENTIAL","candidate_forecasts":len(rows),
                "matched_quotes":0,"research_only":True}
    # Credential never appears in URL, persisted log or exception text.
    provider=odds_helpers()
    remain,err=provider.PropLineProvider._daily_quota_check(secret)
    if err or remain is None or remain<1:
        return {"status":"PROPLINE_QUOTA_OR_ACCESS_BLOCKED","reason":err or "NO_REQUEST_BUDGET",
                "candidate_forecasts":len(rows),"matched_quotes":0,"research_only":True}
    query=urlencode({"markets":",".join(MARKETS),"bookmakers":",".join(BOOKS)},safe=",")
    odds_url=PROPLINE+"?"+query
    # The capture receipt is per project/day/provider/event scope and is
    # reserved before the request. Never overwrite or retry a claimed attempt.
    events=sorted({r["forecast"]["event_id"] for r in rows})
    attempt_id=sha256({"day":day,"events":events,"model":"S0","source":"PropLine"})
    attempt_rel=BASE/"claims"/(attempt_id+".json")
    claim=canonical_bytes({"schema":"PA-V25-NBA-OU-CAPTURE-CLAIM/1",
                           "day":day,"events":events,"created_at":at})
    claim_path=ROOT/attempt_rel
    claim_path.parent.mkdir(parents=True,exist_ok=True)
    try:
        fd=os.open(claim_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,"O_NOFOLLOW",0),0o600)
    except FileExistsError:
        return {"status":"DAILY_OU_SCOPE_ALREADY_CLAIMED","candidate_forecasts":len(rows),
                "matched_quotes":0,"research_only":True}
    with os.fdopen(fd,"wb") as out:out.write(claim);out.flush();os.fsync(out.fileno())
    try:
        # Independent ESPN source must also be original pregame; all events
        # are identity checked before any P0 MarketQuote admission.
        espn_url=ESPN+"?dates="+day.replace("-","")+"&limit=100"
        espn_raw,espn_at=http_raw(espn_url,opener=opener)
        schedule=event_crosswalk(espn_raw,rows)
        if not schedule:
            return {"status":"ESPN_ORIGINAL_CROSSWALK_UNAVAILABLE",
                    "candidate_forecasts":len(rows),"matched_quotes":0,"research_only":True}
        esrc=original_source(espn_url,espn_raw,espn_at,"nba_ou_espn_crosswalk")
        raw,captured_at=http_raw(odds_url,key=secret,opener=opener)
        source=original_source(odds_url,raw,captured_at,"nba_propline_original_player_props")
        payload=json.loads(raw)
        events_payload=(payload if isinstance(payload,list) else
                        payload.get("events",payload.get("data",[])))
        require(isinstance(events_payload,list),"PROPLINE_PAYLOAD_SCHEMA")
        candidates=[]
        for e in events_payload:
            if isinstance(e,dict) and not e.get("is_outright"):
                candidates.extend(provider.quotes_from_event(e,sport="NBA",
                    retrieved_at=captured_at,source_url=odds_url))
        by_name=defaultdict(list)
        for item in rows:
            f=item["forecast"]
            k=(f["event_id"],f["stat_key"],
               provider.normalize_player(item["feature"]["features"].get("current_name")))
            by_name[k].append(item)
        matched=[];rejected=Counter()
        for q in candidates:
            qevent=next((gid for gid,details in schedule.items()
                if set(q.get("event_teams") or [])==set(details["teams"].values()) and
                q.get("event_start") and provider.parse_time(q["event_start"]) is not None and
                abs((provider.parse_time(q["event_start"])-utc(details["start"])).total_seconds())<=60),None)
            if qevent is None:
                rejected["EVENT_TEAM_TIME_UNMATCHED"]+=1;continue
            k=(qevent,q.get("stat"),provider.normalize_player(q.get("player")))
            originals=by_name.get(k,[])
            if len(originals)!=1:
                rejected["AMBIGUOUS_OR_UNKNOWN_ESPN_PLAYER"]+=1;continue
            original=originals[0]
            try:identity_match(q,original,schedule,captured_at=captured_at)
            except QuoteBlocked as exc:
                rejected[str(exc)]+=1;continue
            f=original["forecast"]
            terms={"over_american":q["over_odds"],"under_american":q["under_odds"],
                   "provider_event_id":q.get("event_id"),"provider_updated_at":q.get("retrieved_at"),
                   "raw_quote_path":source["archive_path"],
                   "espn_crosswalk_receipt_id":esrc["receipt_id"],
                   "relation_to_original_forecast":("AT_OR_BEFORE_FORECAST" if
                        utc(captured_at)<=utc(f["forecast_at"]) else
                        "POST_FORECAST_PREGAME"),
                   "source":"PropLine","research_only":True}
            contract={"event":f["event_id"],"player":f["player_id"],
                "stat":f["stat_key"],"period":f["period"],"book":q["book"],
                "line":q["line"],"over":q["over_odds"],"under":q["under_odds"]}
            contract_id="nba-s0-ou-contract:"+sha256(contract)
            quote_id="nba-s0-ou-quote:"+sha256({"contract":contract,"source":source["source_sha256"],"at":captured_at})
            quote=record("MarketQuote",quote_id=quote_id,contract_id=contract_id,
                event_id=f["event_id"],sport="NBA",team_id=f["team_id"],
                opponent_id=f["opponent_id"],player_id=f["player_id"],
                stat_key=f["stat_key"],period=f["period"],
                quote_timestamp=captured_at,event_start_at=f["event_start_at"],
                book=q["book"],product_type="player_prop",
                quote_kind="real",line=q["line"],side="paired",
                source_receipt_id=source["receipt_id"],source_sha256=source["source_sha256"],
                terms=terms,accepted=True,reject_reason=None)
            append_immutable("/work","MarketQuote",quote)
            matched.append({"quote_id":quote_id,"contract_id":contract_id,
                "forecast_id":f["forecast_id"],"stat":f["stat_key"],
                "player_id":f["player_id"],"book":q["book"],"line":q["line"]})
        report={"schema":"PA-V25-NBA-S0-OU-ORIGINAL-QUOTE-CAPTURE/1",
            "day":day,"captured_at":captured_at,"source_receipt_id":source["receipt_id"],
            "source_sha256":source["source_sha256"],"espn_crosswalk_sha256":esrc["source_sha256"],
            "candidate_forecasts":len(rows),"raw_parsed_two_sided_quotes":len(candidates),
            "matched_quotes":len(matched),"matched":matched,
            "rejections":dict(sorted(rejected.items())),
            "research_only":True,"original_forecast_changes":False}
        payload=canonical_bytes(report)
        relative=BASE/"capture_receipts"/(digest_sha(payload).hexdigest()+".json")
        atomic(relative,payload)
        return {"status":"QUOTES_CAPTURED_OR_ABSTAINED","receipt":str(relative),**report}
    except Exception as exc:
        # Do not include raw HTTP error text or API keys in persisted diagnostic.
        report={"schema":"PA-V25-NBA-S0-OU-ERROR/1","day":day,
            "failure_class":type(exc).__name__,
            "reason":str(exc)[:120] if isinstance(exc,QuoteBlocked) else "PROVIDER_OR_STORAGE_ERROR",
            "research_only":True}
        payload=canonical_bytes(report)
        relative=BASE/"capture_errors"/(digest_sha(payload).hexdigest()+".json")
        atomic(relative,payload)
        return {"status":"OU_CAPTURE_BLOCKED",**report,"receipt":str(relative)}

def verify_ou_against_official():
    """Independent AFTER-game research diagnostics; does not edit P5 S0 scores."""
    attest_project_storage("/work")
    originals=recover_frozen_forecasts("/work",sport="NBA")
    official=recover_official_outcomes("/work")["by_stat_identity"]
    quotes,corrupt=enumerate_p0("/work","MarketQuote")
    sources,source_bad=enumerate_p0("/work","SourceReceipt")
    require(not corrupt and not source_bad,"MARKET_OR_SOURCE_VAULT_CORRUPTION")
    by_identity={(f["forecast"]["event_id"],f["forecast"]["player_id"],
                  f["forecast"]["stat_key"],f["forecast"]["period"]):f
                 for f in originals["accepted"]
                 if f["forecast"].get("model_id")=="PA-V25-NBA-S0-CONDITIONAL-PLAYED"}
    count=Counter();details=[]
    for entry in quotes.values():
        q=entry["record"]
        if not q["quote_id"].startswith("nba-s0-ou-quote:") or not q["accepted"]:continue
        key=(q["event_id"],q["player_id"],q["stat_key"],q["period"])
        original=by_identity.get(key)
        if original is None:
            count["FORECAST_NOT_FOUND"]+=1;continue
        f=original["forecast"]
        outcome_key=tuple(f[x] for x in ("sport","event_id","team_id","player_id","stat_key","period"))
        candidates=official.get(outcome_key,[])
        if not candidates:
            count["OFFICIAL_OUTCOME_PENDING"]+=1;continue
        outcome=candidates[-1]["outcome"]
        source=sources.get(q["source_receipt_id"])
        if (source is None or
            source["record"]["source_sha256"]!=q["source_sha256"]):
            count["ORIGINAL_QUOTE_SOURCE_MISSING"]+=1;continue
        verify_source_bytes(source["record"],"/work")
        crosswalk=sources.get(q["terms"].get("espn_crosswalk_receipt_id"))
        if not crosswalk:
            count["ORIGINAL_ESPN_CROSSWALK_MISSING"]+=1;continue
        verify_source_bytes(crosswalk["record"],"/work")
        if outcome["status"]!="FINAL" or outcome["participation"]!="PLAYED":
            count["DNP_OR_UNFINAL"]+=1;continue
        require(utc(q["quote_timestamp"])<utc(f["event_start_at"]) and
                utc(f["forecast_at"])<utc(f["event_start_at"]),"NO_PREGAME_QUOTE_OR_FORECAST")
        require(f["distribution"]["kind"]=="poisson","S0_DISTRIBUTION_MISMATCH")
        pm=poisson_contract(f["distribution"]["parameters"]["rate"],q["line"])
        mk=market_probabilities(q["terms"]["over_american"],q["terms"]["under_american"])
        actual=outcome["actual_value"]
        outcome_side="over" if actual>q["line"] else "under" if actual<q["line"] else "push"
        denom=pm["over"]+pm["under"]
        r={"schema":"PA-V25-NBA-S0-OU-POSTGAME/1",
           "forecast_id":f["forecast_id"],"original_forecast_sha256":original["original_forecast_sha256"],
           "quote_id":q["quote_id"],"quote_sha256":sha256(q),
           "outcome_id":outcome["outcome_id"],"outcome_sha256":sha256(outcome),
           "event_id":f["event_id"],"player_id":f["player_id"],
           "stat_key":f["stat_key"],"book":q["book"],"line":q["line"],
           "actual":actual,"result":outcome_side,
           "predicted_probabilities":pm,
           "model_over_given_no_push":pm["over"]/denom if denom>0 else None,
           "market_probabilities":mk,
           "source_sha256":q["source_sha256"],
           "quote_relation":q["terms"]["relation_to_original_forecast"],
           "research_only":True,"betting_eligible":False,
           "did_not_regenerate_forecast":True}
        raw=canonical_bytes(r)
        relative=BASE/"postgame_contracts"/(digest_sha(raw).hexdigest()+".json")
        atomic(relative,raw)
        count["CONTRACT_VERIFIED"]+=1
        details.append({"event_id":f["event_id"],"player_id":f["player_id"],
             "stat":f["stat_key"],"book":q["book"],"line":q["line"],
             "actual":actual,"result":outcome_side,"receipt":str(relative)})
    return {"status":"NBA_S0_OU_POSTGAME_RESEARCH_AUDIT",
            "checked":dict(count),"matched_contracts":len(details),
            "details":details,"research_only":True,
            "no_betting_hit_rate_claimed":True}

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=("capture","verify"))
    parser.add_argument("--day")
    args=parser.parse_args(argv)
    if args.action=="capture":
        require(bool(args.day),"DAY_REQUIRED")
        out=capture_original_ou(day=args.day)
    else:out=verify_ou_against_official()
    print(json.dumps(out,sort_keys=True,default=str))

if __name__=="__main__":
    main()
