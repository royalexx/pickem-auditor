"""Unattended REAL original-offer NHL SOG Gamma–Poisson shadows, research only.

Direct quote acquisition and independent C03-signed official NHL schedule/rosters;
frozen PR121 forecasting model and PR122 verification. No upstream publication
signature, live execution guarantee, participation prediction or production effect.
Never reconstructs or retroactively signs a previous source.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from collections import Counter, defaultdict
from decimal import Decimal
import os,sys,json,hashlib,math,shutil,re,unicodedata,time

BASE=Path.cwd()
NOW=datetime.now(timezone.utc)
ET=ZoneInfo("America/Toronto")
DAY=NOW.astimezone(ET).date().isoformat()
SOURCE_DAY=BASE/"reports/v25_sog_source_cert_sprint/2026-11-13"
DAYROOT=BASE/"reports/v25_sog_source_cert_sprint"/DAY
RUN_ID=NOW.strftime("%Y%m%dT%H%M%S%fZ")
BATCH=DAYROOT/("daily_original_gamma_poisson_research_"+RUN_ID)
BATCH.mkdir(parents=True,exist_ok=False)
OLD=SOURCE_DAY/"signed_pr122_20261113T165907226991Z"
# Shared APPEND-ONLY RESEARCH source root: old signed HMAC evidence remains
# byte-immutable; only genuinely new original TLS receipts/quotes get new files.
# Avoid rebuilding 1,176 certified source files on every nightly run.
POOL=OLD/"original_signed_sources"
OLD_POOL=OLD/"original_signed_sources"
PR121=SOURCE_DAY/"research_runner_pr121"
PR122=SOURCE_DAY/"research_code_122"
assert (PR121/"v2/nhl_sog_prospective_runner.py").is_file() and (PR122/"c03_live_transport.py").is_file()
sys.path.insert(0,str(PR121))
sys.path.insert(0,str(PR122))
# NHL-only transport copy: exact archived verifier, explicit research HTTP UA.
sys.path.insert(0,str(BASE/"research/nhl_sog_transport"))
from c03_live_transport import capture_signed_live,verify_signed_capture
from c03_context_cohorts import CohortError
from v2.nhl_sog_prospective_runner import prospective_shadow_attempt
from v2.nhl_sog_exposure_shadow import MIN_PEERS, MIN_PLAYER_GAMES, MIN_PEER_GAMES
import v2
v2.__path__.append(str(BASE/"v2"))
from v2.contracts import MarketQuote
from v2.phase15_nhl_roster import verify_receipt as verify_roster_receipt

CODE_COMMIT="43d4d4c3f3ae082cd2330555f9c92b440664b29d"
SIGNER_COMMIT="faf419f89902f83a46dfba66cd04d2f48ed31776"
MAX_FORECASTS=4
MAX_PER_GAME=2
MIN_LEAD_MINUTES=35
MIN_QUOTA_BEFORE=6
MAX_ROSTER_AGE_H=6
MAX_HISTORY_CALENDAR_AGE_D=75
BOOKS=("pinnacle","draftkings","fanduel","betmgm")
FULL_TEAM_NAMES={
"Anaheim Ducks":"ANA","Boston Bruins":"BOS","Buffalo Sabres":"BUF",
"Calgary Flames":"CGY","Carolina Hurricanes":"CAR","Chicago Blackhawks":"CHI",
"Colorado Avalanche":"COL","Columbus Blue Jackets":"CBJ","Dallas Stars":"DAL",
"Detroit Red Wings":"DET","Edmonton Oilers":"EDM","Florida Panthers":"FLA",
"Los Angeles Kings":"LAK","Minnesota Wild":"MIN","Montreal Canadiens":"MTL",
"Nashville Predators":"NSH","New Jersey Devils":"NJD","New York Islanders":"NYI",
"New York Rangers":"NYR","Ottawa Senators":"OTT","Philadelphia Flyers":"PHI",
"Pittsburgh Penguins":"PIT","San Jose Sharks":"SJS","Seattle Kraken":"SEA",
"St. Louis Blues":"STL","Tampa Bay Lightning":"TBL","Toronto Maple Leafs":"TOR",
"Utah Mammoth":"UTA","Utah Hockey Club":"UTA","Vancouver Canucks":"VAN",
"Vegas Golden Knights":"VGK","Washington Capitals":"WSH","Winnipeg Jets":"WPG"}
def utc(t):
    d=datetime.fromisoformat(str(t).replace("Z","+00:00"))
    if d.tzinfo is None:raise ValueError("NAIVE_TIMESTAMP")
    return d.astimezone(timezone.utc)
def stamp(t):return t.isoformat().replace("+00:00","Z")
def canon(o):return json.dumps(o,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def norm(s):
    s=unicodedata.normalize("NFKD",str(s or "")).casefold()
    return " ".join("".join(c if c.isalnum() else " " for c in s if not unicodedata.combining(c)).split())
def check(cond,why):
    if not cond:raise ValueError(why)
def write_once(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("xb") as f:f.write(payload)
    return sha(payload)
def dec(v):
    v=float(v)
    check(math.isfinite(v) and abs(v)>=100,"INVALID_AMERICAN_ODDS")
    return 1+v/100 if v>=100 else 1+100/(-v)
def sanit(exc):
    # NEVER return exception messages from network auth contexts or secrets.
    if isinstance(exc,HTTPError):return "HTTP_"+str(exc.code)
    if isinstance(exc,URLError):return "URL_ERROR"
    return type(exc).__name__+":"+str(exc)[:100] if type(exc).__name__ in ("CohortError","ExperimentBlocked","RosterEvidenceError","ContractError","ValueError") else type(exc).__name__

manifest={
 "schema":"v25_daily_original_sog_gamma_poisson_research_generator_v1",
 "started_at_utc":stamp(NOW),"slate_date_et":DAY,"experiment_id":"EXP-V25-NHL-SOG-EXPOSURE-EB-001",
 "max_forecasts_per_daily_run":MAX_FORECASTS,"max_forecasts_per_game":MAX_PER_GAME,
 "priority_rule":"first_qualified_original_book_in_pinnacle_draftkings_fanduel_betmgm_then_stable_sha256_player_per_event",
 "code_pin_PR121":CODE_COMMIT,"signer_pin_PR122":SIGNER_COMMIT,
 "research_generator_source_sha256":sha(Path(__file__).read_bytes()),
 "research_generator_source_path":str(Path(__file__).relative_to(BASE)),
 "research_only":True,"model_modified":False,"production_modified":False,
 "tier_publication_allowed":False,"forecast_promotion_allowed":False,
 "raw_provider_publisher_time_verified":False,"source_clock_semantics":"collector_actual_possession_not_authenticated_provider_publication",
 "lineup_participation_confirmed":False,"DNP_risk_modeled":False,
 "source_old_archives_retroactively_signed":False,"attempts":[],
 "failures":[],"counts":Counter(),"signed_captures":[],"original_quote":None,
 "source_pool":str(POOL.relative_to(BASE))}
def fail(stage,reason,subject=None):
    item={"stage":stage,"reason":reason}
    if subject is not None:item["subject"]=subject
    manifest["failures"].append(item)
    manifest["counts"]["blocked_"+stage]+=1
def final(status):
    manifest["finished_at_utc"]=stamp(datetime.now(timezone.utc))
    family=manifest.get("daily_family_freezes",[])
    manifest["daily_family_new_model_records"]=sum(r["newly_frozen"] for r in family)
    manifest["daily_family_previous_model_records"]=sum(r["previously_frozen"] for r in family)
    manifest["daily_family_status"]=("FROZEN" if manifest["daily_family_new_model_records"] else
        "NO_NEW_DAILY_FAMILY_FREEZE")
    manifest["S1_enrollment"]="NOT_ENROLLED_SEPARATE_PR129_PREREGISTRATION_REQUIRED"
    if manifest['daily_family_new_model_records'] or manifest['daily_family_previous_model_records']:
        status='SUCCESS_DAILY_FAMILY_SHADOWS_LEGACY_COHORT_SEPARATE'
    manifest["status"]=status
    manifest["counts"]=dict(manifest["counts"])
    payload=canon(manifest)
    file=BATCH/"daily_research_generation_manifest.json"
    if not file.exists():write_once(file,payload)
    stdout={
     "status":status,"slate_date_et":DAY,
     "daily_family_new_model_records":manifest["daily_family_new_model_records"],
     "daily_family_previous_model_records":manifest["daily_family_previous_model_records"],
     "daily_family_status":manifest["daily_family_status"],
     "two_sided_original_offer_rows":manifest["counts"].get("two_sided_offer_rows",0),
     "native_id_crosswalks":manifest["counts"].get("native_id_qualified",0),
     "selected_forecast_candidates":manifest["counts"].get("selected_candidates",0),
     "genuinely_frozen_shadow_forecasts":manifest["counts"].get("successful_forecasts",0),
     "abstentions":manifest["counts"].get("runner_abstentions",0),
     "skipped_preexisting":manifest["counts"].get("existing_frozen_skipped",0),
     "blocked_stages":manifest["failures"][:12],
     "source_receipt_count":len(manifest["signed_captures"]),
     "receipt_path":str(file.relative_to(BASE)),
     "receipt_sha256":sha(payload),"research_only":True,"production_unchanged":True}
    print("C03_UNATTENDED_ORIGINAL_NHL_SOG_GAMMA_POISSON",json.dumps(stdout,sort_keys=True))
    return stdout

try:
    # 0. Use stable append-only RESEARCH source pool, with immutable original
    # capture bytes and no re-signing/backdating of historical source.
    original_manifest_file=OLD/"signed_original_source_manifest_v1.json"
    historical_file=OLD/"pr121_signed_historical_observation_contracts_parallel_v1.json"
    cat_file=OLD/"signed_nhl_official_only_player_event_identity_catalog_v1.json"
    check(OLD_POOL.is_dir() and all(p.is_file() for p in (original_manifest_file,historical_file,cat_file)),
          "ARCHIVED_SIGNED_NHL_ORIGINALS_MISSING")
    old_manifest=json.loads(original_manifest_file.read_bytes())
    historical=json.loads(historical_file.read_bytes())
    catalog=json.loads(cat_file.read_bytes())
    check(sha(original_manifest_file.read_bytes())=="378da9b68a43295345f2b206618827dbea7eebeb1c34426347a003a3cad7e90a",
          "ARCHIVED_NHL_SIGNATURE_MANIFEST_SHA_MISMATCH")
    check(sha(historical_file.read_bytes())=="9e36153ced6c6e45a39da4fd8631bb101dbc25af4b17afaa3256e540fe894dfb",
          "ARCHIVED_NHL_HISTORY_MANIFEST_SHA_MISMATCH")
    original_items=old_manifest["records"]
    check(len(original_items)==196 and len(historical["signed_observation_contracts_by_player"])==51,
          "HISTORICAL_SIGNED_ARCHIVE_UNEXPECTED_SHAPE")
    # Stop using outdated frozen history beyond a defined research limit.
    manifest["legacy_history_expired"]=(NOW.date()-datetime(2026,11,13,tzinfo=timezone.utc).date()).days>MAX_HISTORY_CALENDAR_AGE_D
    old_count=0
    # Verify previously signed source handles exist; the full independent
    # HMAC/raw-body reconstruction runs inside the unchanged PR121 runner.
    # New C03 signatures are created only by direct live HTTPS transport.
    old_source_handles=0
    for item in original_items:
        rec=item["receipt"]
        for field in ("archive_path","collector_proof_archive_path"):
            handle=POOL/rec[field]
            check(handle.is_file() and handle.resolve().is_relative_to(POOL.resolve()),
                  "OLD_SIGNED_SOURCE_HANDLE_MISSING_OR_UNSAFE")
            old_source_handles+=1
    manifest["source_baseline_copy"]={
       "mode":"SHARED_RESEARCH_APPEND_ONLY_NO_LEGACY_FILE_REWRITES",
       "original_hmac_source_handles_checked":old_source_handles,
       "legacy_signed_manifest_sha256":sha(original_manifest_file.read_bytes()),
       "historical_signed_observation_manifest_sha256":sha(historical_file.read_bytes()),
       "source_root":str(POOL.relative_to(BASE)),
       "old_source_bytes_unmodified":True,
       "new_files_only_original_live_captures_and_structured_quotes":True,
       "source_history_collected_originally_at":old_manifest["source_capture_at"],
       "frozen_historical_population_age_days":(NOW.date()-datetime(2026,11,13,tzinfo=timezone.utc).date()).days,
       "no_daily_history_model_refit_claim":True,
       "historical_sample_more_than_14_days_old":(NOW.date()-datetime(2026,11,13,tzinfo=timezone.utc).date()).days>14}
    index={(item["kind"],str(item["id"])):item["receipt"] for item in original_items}
    own_by=historical["signed_observation_contracts_by_player"]
    catalog_players=catalog["player_records"]
    # New original prior-game evidence, acquired today. Old manifests stay immutable.
    from v2.nhl_sog_history_refresh import load_current
    current,history_ref=load_current(POOL,day=DAY,now=NOW)
    manifest['current_history_manifest']=history_ref
    manifest['history_population_mode']='dynamic_signed_current_roster_daily_family_only'
    own_by=current['signed_observation_contracts_by_player']
    catalog_players=current['player_records']
    manifest['current_history_qualified_players']=current['qualified_players']
    manifest['noncurrent_season_history_exclusions']=current['noncurrent_season_exclusions']
    manifest['source_baseline_copy']['no_daily_history_model_refit_claim']=False
    manifest['daily_fit_kind']='unchanged_analytic_model_on_current_signed_prior_games_no_NUTS'
    # 1. One genuinely new sportsbook provider response; no pasted historical offers.
    key=os.environ.get("PROPLINE_API_KEY")
    if not key and (BASE/"config/credentials.local.json").is_file():
        try:key=json.loads((BASE/"config/credentials.local.json").read_text()).get("PROPLINE_API_KEY")
        except Exception:key=None
    check(isinstance(key,str) and len(key.strip())>=4,"PROPLINE_KEY_UNAVAILABLE")
    check(isinstance(os.environ.get("PICKEM_C03_COLLECTOR_HMAC_KEY_HEX"),str),"C03_HMAC_KEY_UNAVAILABLE")
    headers={"X-API-Key":key.strip(),"Accept":"application/json","User-Agent":"pickem-v25-c03-sog-research/1"}
    with urlopen(Request("https://api.prop-line.com/v1/sports",headers=headers),timeout=15) as resp:
        remaining=resp.headers.get("X-Daily-Remaining")
        check(resp.status==200 and remaining and remaining.isdigit(),"PROPLINE_QUOTA_NOT_VERIFIABLE")
        remaining=int(remaining)
    manifest["quota_before"]=remaining
    check(remaining>=MIN_QUOTA_BEFORE,"PROPLINE_QUOTA_RESERVED_FOR_PRODUCTION")
    url="https://api.prop-line.com/v1/sports/icehockey_nhl/odds?"+urlencode(
         {"markets":"player_shots_on_goal","bookmakers":",".join(BOOKS)},safe=",")
    acquired=datetime.now(timezone.utc)
    with urlopen(Request(url,headers=headers),timeout=25) as resp:
        body=resp.read(20_000_001)
        content_type=resp.headers.get("Content-Type","")
        status=resp.status
    received=datetime.now(timezone.utc)
    check(status==200 and "json" in content_type.lower() and 0<len(body)<=20_000_000,
          "PROPLINE_ORIGINAL_HTTP_RESPONSE_INVALID")
    source_sha=sha(body)
    write_once(BATCH/("original_provider_https_response_"+source_sha+".bin"),body)
    provider=json.loads(body)
    provider_events=provider if isinstance(provider,list) else provider.get("events",provider.get("data",[]))
    check(isinstance(provider_events,list),"PROPLINE_EVENTS_NOT_ARRAY")
    manifest["original_quote"]={
        "source_url":url,"retrieval_started_at_utc":stamp(acquired),"received_at_utc":stamp(received),
        "raw_body_sha256":source_sha,"raw_body_bytes":len(body),
        "original_raw_file":str((BATCH/("original_provider_https_response_"+source_sha+".bin")).relative_to(BASE)),
        "authenticated_upstream_publication_time":False,"one_original_odds_request":True}
    valid_provider_events={}
    for event in provider_events:
        if not isinstance(event,dict):continue
        try:
            started=utc(event["commence_time"])
            if started.astimezone(ET).date().isoformat()!=DAY:continue
            if started<=datetime.now(timezone.utc)+timedelta(minutes=MIN_LEAD_MINUTES):
                fail("PREGAME_LEAD_TOO_SHORT","EVENT_START_TOO_CLOSE",str(event.get("id")));continue
            home=FULL_TEAM_NAMES.get(event.get("home_team"))
            away=FULL_TEAM_NAMES.get(event.get("away_team"))
            if not home or not away or home==away:
                fail("UNKNOWN_PROVIDER_TEAM","NOT_CANONICAL_NHL_TEAM",str(event.get("id")));continue
            eid=str(event["id"])
            check(eid.isdigit() and eid not in valid_provider_events,"DUPLICATE_OR_INVALID_PROVIDER_GAME_ID")
            valid_provider_events[eid]={"raw":event,"start":started,"home":home,"away":away}
        except (KeyError,TypeError,ValueError) as exc:
            fail("INVALID_PROVIDER_EVENT",sanit(exc))
    manifest["counts"]["local_date_future_provider_events"]=len(valid_provider_events)
    if not valid_provider_events:
        final("BLOCKED_NO_FUTURE_ORIGINAL_NHL_EVENTS")
    else:
        # Extract exact original OVER+UNDER pairs with same provider-native NHL player ID.
        quote_rows=[];raw_pairs=[];seen_raw=set()
        for eid,x in sorted(valid_provider_events.items(),key=lambda t:(t[1]["start"],t[0])):
            event=x["raw"]
            for book in event.get("bookmakers") or []:
                if not isinstance(book,dict) or book.get("key") not in BOOKS:continue
                for market in book.get("markets") or []:
                    if not isinstance(market,dict) or market.get("key")!="player_shots_on_goal":continue
                    groups=defaultdict(lambda:defaultdict(list))
                    for o in market.get("outcomes") or []:
                        if not isinstance(o,dict):continue
                        side=str(o.get("name") or "").lower()
                        if side not in ("over","under"):continue
                        name=str(o.get("description") or o.get("player") or "").strip()
                        native=str(o.get("player_id") or "")
                        try:
                            point=o.get("point") if o.get("point") is not None else o.get("line")
                            line=float(point)
                            price=o.get("price") if o.get("price") is not None else o.get(side+"_odds")
                            price=float(price)
                            if not name or not math.isfinite(line) or line<0 or line>15 or not math.isfinite(price) or abs(price)<100:continue
                        except (ValueError,TypeError):continue
                        groups[(name,line,native)][side].append(price)
                    for (name,line,native),sides in groups.items():
                        if len(sides["over"])!=1 or len(sides["under"])!=1:
                            fail("UNPAIRED_OR_AMBIGUOUS_PRICE","INCOMPLETE_OR_MULTIPLE_TWO_SIDED_PRICE",eid);continue
                        pair=(eid,book["key"],name,line,native)
                        if pair in seen_raw:
                            fail("DUPLICATE_ORIGINAL_QUOTE","SOURCE_EVENT_BOOK_NAME_LINE_DUPLICATE",eid);continue
                        seen_raw.add(pair)
                        ov,un=sides["over"][0],sides["under"][0]
                        try:dec(ov);dec(un)
                        except ValueError:
                            fail("BAD_AMERICAN_PRICE","SOG_PRICE_INVALID",eid);continue
                        row={
                        "sport":"NHL","stat":"shots on goal","event_id":eid,"event_id_namespace":"propline",
                        "event_start":stamp(x["start"]),"player":name,
                        "provider_native_player_id":native,
                        "book":book["key"],"line":line,
                        "over_odds":ov,"under_odds":un,
                        "retrieved_at":stamp(received),"source_url":url,
                        "event_home":event["home_team"],"event_away":event["away_team"],
                        "raw_http_body_sha256":source_sha}
                        quote_rows.append(row)
        manifest["counts"]["two_sided_offer_rows"]=len(quote_rows)
        quote_bytes=b"".join(canon(row)+b"\n" for row in quote_rows)
        quote_sha=sha(quote_bytes)
        quote_rel="research_daily_propline_original_"+RUN_ID+"/original_structured_rows_"+quote_sha+".jsonl"
        write_once(POOL/quote_rel,quote_bytes)
        manifest["original_quote"]["structured_rows_sha256"]=quote_sha
        manifest["original_quote"]["structured_rows_path"]=str((POOL/quote_rel).relative_to(BASE))
        manifest["original_quote"]["row_count"]=len(quote_rows)
        if not quote_rows:
            final("BLOCKED_NO_ORIGINAL_TWO_SIDED_SOG_OFFERS")
        else:
            # 2. Original and newly signed official NHL scoreboard, no retro-source clock.
            future_first=min(x["start"] for x in valid_provider_events.values())
            cutoff=datetime.now(timezone.utc)+timedelta(minutes=8)
            check(cutoff<future_first,"FUTURE_EVENT_TOO_CLOSE_FOR_SIGNED_SOURCES")
            def capture(url,kind,sid):
                # Retry only transient original TLS transport failures.
                # An invalid HMAC or invalid event/identity is NEVER retried as
                # a reason to weaken the contract or forge source provenance.
                for attempt_number in range(2):
                    try:
                        rec=capture_signed_live(url,archive_root=POOL,source_namespace="nhl_official",
                             source_id="v25daily:"+DAY+":"+kind+":"+sid,input_cutoff_at=stamp(cutoff),
                             event_start_at=stamp(future_first),timeout=12)
                        doc=verify_signed_capture(rec,archive_root=POOL,freeze=stamp(cutoff),
                                                  event_start=stamp(future_first))
                        break
                    except CohortError as exc:
                        if attempt_number==0 and str(exc).startswith("LIVE_SOURCE_FETCH_FAILED"):
                            time.sleep(1)
                            continue
                        raise
                manifest["signed_captures"].append({"source_kind":kind,"source_id":sid,
                    "received_at":rec["received_at"],"body_sha256":rec["body_sha256"],
                    "proof_sha256":rec["collector_proof_sha256"],"fresh_tls_original":True})
                return rec,doc
            def from_saved(kind,team=None):
                ident=team if team else DAY
                rec=index.get((kind,ident))
                check(isinstance(rec,dict),"NO_ORIGINAL_SIGNED_FALLBACK")
                check(rec["source_url"]==(
                    "https://api-web.nhle.com/v1/score/"+DAY if kind=="score" else
                    "https://api-web.nhle.com/v1/roster/"+team+"/current"),
                    "SIGNED_FALLBACK_SOURCE_ENDPOINT_NOT_CURRENT")
                check(utc(rec["received_at"])<=datetime.now(timezone.utc) and
                      datetime.now(timezone.utc)-utc(rec["received_at"])<=timedelta(hours=MAX_ROSTER_AGE_H),
                      "ORIGINAL_SIGNED_FALLBACK_EXPIRED")
                doc=verify_signed_capture(rec,archive_root=POOL,
                     freeze=stamp(datetime.now(timezone.utc)),event_start=stamp(future_first))
                manifest["signed_captures"].append({"source_kind":kind,"source_id":ident,
                    "received_at":rec["received_at"],"body_sha256":rec["body_sha256"],
                    "proof_sha256":rec["collector_proof_sha256"],"fresh_tls_original":False,
                    "explicit_fallback":"Genuinely original HMAC proof from earlier same date, NOT newly signed"})
                return rec,doc
            from v2.nhl_sog_pregame_schedule import capture_identity, official_games
            schedule_receipt,score=capture_identity(DAY,capture,from_saved,
                lambda stage,exc:fail(stage,sanit(exc)))
            nhl_events=official_games(schedule_receipt["source_url"],score,DAY)
            check(isinstance(nhl_events,list) and nhl_events,"SIGNED_NHL_SCOREBOARD_MISSING_GAMES")
            check(all(str(g.get("season"))==current["admission_required_season"] for g in nhl_events),"SIGNED_SCHEDULE_SEASON_ADMISSION_MISMATCH")
            matches={}
            for eid,e in valid_provider_events.items():
                proposals=[]
                for game in nhl_events:
                    if not isinstance(game,dict):continue
                    if game.get("gameState") not in ("FUT","PRE"):continue
                    h=game.get("homeTeam") or {};a=game.get("awayTeam") or {}
                    if h.get("abbrev")!=e["home"] or a.get("abbrev")!=e["away"]:continue
                    try:
                        start=utc(game["startTimeUTC"])
                        if start!=e["start"]:continue
                        # The signed NHL official mascot is checked against the
                        # raw provider full-name (not inferred solely by static map).
                        official_home=(h.get("name") or h.get("commonName") or {}).get("default")
                        official_away=(a.get("name") or a.get("commonName") or {}).get("default")
                        if not norm(e["raw"]["home_team"]).endswith(norm(official_home)):continue
                        if not norm(e["raw"]["away_team"]).endswith(norm(official_away)):continue
                    except Exception:continue
                    proposals.append(str(game["id"]))
                if len(proposals)==1:
                    matches[eid]={**e,"nhl_id":proposals[0]}
                else:fail("OFFICIAL_EVENT_CROSSWALK","UNIQUE_TEAM_MASCOT_UTC_JOIN_FAILED",eid)
            manifest["counts"]["signed_official_event_crosswalks"]=len(matches)
            if not matches:
                final("BLOCKED_NO_SIGNED_OFFICIAL_EVENT_CROSSWALK")
            else:
                # 3. Capture original official current rosters for both event teams.
                # Any prior HMAC fallback must itself be within the original
                # membership contract's strictly enforced six-hour age.
                rosters={};official_roster_docs={}
                needed=sorted({t for x in matches.values() for t in (x["home"],x["away"])})
                for team in needed:
                    try:
                        r,doc=capture("https://api-web.nhle.com/v1/roster/"+team+"/current","roster",team)
                    except Exception as exc:
                        fail("LIVE_ROSTER_FETCH",sanit(exc),team)
                        try:r,doc=from_saved("roster",team)
                        except Exception as second:
                            fail("SIGNED_ROSTER_ABSENT",sanit(second),team)
                            continue
                    adapted={"schema":"nhl_independent_current_roster_receipt_v1",
                         "team":team,"source_url":r["source_url"],"raw_archive_path":r["archive_path"],
                         "bytes":r["body_bytes"],"sha256":r["body_sha256"],"retrieved_at":r["received_at"],
                         "source_c03_collector_proof_sha256":r["collector_proof_sha256"],
                         "source_c03_collector_signature_verified":True}
                    try:
                        members=verify_roster_receipt(adapted,source_root=POOL,
                             forecast_at=stamp(datetime.now(timezone.utc)),
                             event_start=stamp(future_first),max_age_hours=MAX_ROSTER_AGE_H)
                        check(bool(members),"SIGNED_CURRENT_ROSTER_NO_MEMBERS")
                        rosters[team]=adapted
                        official_roster_docs[team]=doc
                    except Exception as exc:fail("ROSTER_VERIFIER_REJECT",sanit(exc),team)
                manifest["counts"]["signed_current_team_rosters"]=len(rosters)
                # 4. Match provider-native NHL player ID, exact signed profile
                # name and current independent roster presence in appropriate team.
                # Historical raw NHL profiles/logs/finals remain original HMAC-verified.
                prepared=[];profile_cache={}
                for row in quote_rows:
                    eid=row["event_id"];e=matches.get(eid)
                    if not e:continue
                    if e["home"] not in rosters or e["away"] not in rosters:continue
                    native=row["provider_native_player_id"]
                    if not re.fullmatch(r"nhl:\d{7}",native):
                        fail("PROVIDER_NATIVE_ID_MISSING","TWO_SIDED_NATIVE_ID_REQUIRED",eid);continue
                    pid=native.split(":",1)[1]
                    old_records=own_by.get(pid)
                    info=catalog_players.get(pid)
                    if not old_records or len(old_records)<MIN_PLAYER_GAMES or info is None:
                        fail("SIGNED_HISTORY_INSUFFICIENT","OLD_SOURCE_OR_PLAYER_PROFILE_MISSING",pid);continue
                    group=info.get("official_position_group")
                    if group not in ("F","D"):continue
                    team=info.get("official_team")
                    # Team is proven from FRESH OFFICIAL roster, not previous catalog team.
                    roster_matches=[]
                    for t in (e["home"],e["away"]):
                        role_group="forwards" if group=="F" else "defensemen"
                        if any(str(z.get("id"))==pid for z in official_roster_docs[t].get(role_group,[])):
                            roster_matches.append(t)
                    if len(roster_matches)!=1:
                        fail("SIGNED_ROSTER_PLAYER_CROSSWALK","NOT_UNIQUE_WITHIN_EVENT",pid);continue
                    team=roster_matches[0]
                    if pid not in profile_cache:
                        try:
                            profile=verify_signed_capture(old_records[0]["raw_profile_receipt"],
                                archive_root=POOL,freeze=stamp(datetime.now(timezone.utc)),event_start=stamp(e["start"]))
                            f=profile.get("firstName");l=profile.get("lastName")
                            if isinstance(f,dict):f=f.get("default")
                            if isinstance(l,dict):l=l.get("default")
                            check(str(profile.get("playerId"))==pid and isinstance(f,str) and isinstance(l,str),
                                  "SIGNED_NHL_PROFILE_PLAYER_NAME_MISSING")
                            pp=str(profile.get("position") or "")
                            check(("D" if pp=="D" else "F" if pp in ("C","L","R","LW","RW") else None)==group,
                                  "SIGNED_NHL_PROFILE_GROUP_MISMATCH")
                            profile_cache[pid]=(f+" "+l,group,old_records[0]["raw_profile_receipt"]["collector_proof_sha256"])
                        except Exception as exc:
                            fail("SIGNED_PLAYER_PROFILE_REJECT",sanit(exc),pid)
                            profile_cache[pid]=None
                    if not profile_cache.get(pid) or norm(row["player"])!=norm(profile_cache[pid][0]):
                        fail("SOURCE_PLAYER_NAME_MISMATCH","PROVIDER_VS_SIGNED_PROFILE_MISMATCH",pid);continue
                    peergroup=group
                    alternatives=sorted(
                        ((other,obs) for other,obs in own_by.items()
                         if other!=pid and len(obs)>=10 and
                           catalog_players.get(other,{}).get("official_position_group")==peergroup),
                        key=lambda p:(-len(p[1]),p[0]))
                    selected=alternatives[:MIN_PEERS]
                    peers=[z for other,obs in selected for z in obs[-10:]]
                    if len(selected)!=MIN_PEERS or len(peers)<MIN_PEER_GAMES:
                        fail("SIGNED_PEER_HISTORY_INSUFFICIENT","MIN_20_PEERS_200_GAMES_NOT_MET",pid);continue
                    prepared.append({"row":row,"event":e,"player_id":pid,"group":group,
                                     "team":team,"opponent":e["away"] if team==e["home"] else e["home"],
                                     "own":old_records,"peers":peers,
                                     "source_profile_proof":profile_cache[pid][2]})
                manifest["counts"]["native_id_qualified"]=len(prepared)
                # 5. Explicitly exclude already frozen first real player/event
                # snapshot to avoid creating duplicate nightly training evidence.
                previously=set()
                for prior in sorted(DAYROOT.glob("authentic_gamma_poisson_attempt_*/first_real_offer_shadow_attempt_receipt.json")):
                    try:
                        r=json.loads(prior.read_bytes())
                        if r.get("status")!="SHADOW_FORECAST":continue
                        inp=json.loads((prior.parent/"original_quote_and_source_identity_receipt.json").read_bytes())
                        prior_id=(inp.get("chosen_offer_identity") or {}).get("official_nhl_player_id")
                        if not prior_id:
                            prior_id=(inp.get("quote") or {}).get("player_id")
                        if prior_id:previously.add((str(r["official_nhl_event_id"]),str(prior_id)))
                    except Exception:pass
                manifest["counts"]["existing_frozen_player_event_count"]=len(previously)
                # Deterministic book priority, stable player hash, event rotation,
                # no ranking or selection based on probabilities, odds or outcomes.
                selected_by_event=defaultdict(list)
                candidates_by_event=defaultdict(list)
                for row in prepared:
                    ident=(row["event"]["nhl_id"],row["player_id"])
                    if ident in previously:
                        manifest["counts"]["existing_frozen_skipped"]+=1
                        continue
                    candidates_by_event[row["row"]["event_id"]].append(row)
                for eid,lst in candidates_by_event.items():
                    # One offered book per underlying player/event (prefer Pinnacle)
                    per_player={}
                    for candidate in sorted(lst,key=lambda x:BOOKS.index(x["row"]["book"])):
                        per_player.setdefault(candidate["player_id"],candidate)
                    selected_by_event[eid]=sorted(per_player.values(),
                       key=lambda x:sha((eid+":"+x["player_id"]).encode()))
                chosen=[];number=0
                event_order=sorted(selected_by_event,key=lambda eid:(matches[eid]["start"],eid))
                while len(chosen)<MAX_FORECASTS:
                    added=False
                    for eid in event_order:
                        if len([r for r in chosen if r["row"]["event_id"]==eid])>=MAX_PER_GAME:continue
                        choices=selected_by_event[eid]
                        if not choices:continue
                        chosen.append(choices.pop(0));added=True
                        if len(chosen)>=MAX_FORECASTS:break
                    if not added:break
                manifest["counts"]["selected_candidates"]=len(chosen)
                selected_ids={(x["event"]["nhl_id"],x["player_id"]) for x in chosen}
                manifest["candidate_enrollment"]=[{
                    "official_game_id":x["event"]["nhl_id"],"player_id":x["player_id"],
                    "status":"SELECTED" if (x["event"]["nhl_id"],x["player_id"]) in selected_ids else
                       "EXCLUDED_PRIOR_FREEZE" if (x["event"]["nhl_id"],x["player_id"]) in previously else
                       "EXCLUDED_PREREGISTERED_FOUR_CONTRACT_SOURCE_SAMPLE"}
                    for x in prepared]
                # 6. Frozen original offer and complete unchanged runner per player.
                for candidate in chosen:
                    row=candidate["row"];e=candidate["event"];pid=candidate["player_id"]
                    if datetime.now(timezone.utc)>=e["start"]-timedelta(minutes=3):
                        fail("GAME_STARTED_OR_IMMINENT","MIN_THREE_MINUTES_FROZEN_FORECAST_MARGIN",pid)
                        manifest["counts"]["runner_abstentions"]+=1;continue
                    contract_id=sha(canon([quote_sha,row["event_id"],pid,row["book"],row["line"],
                                         row["over_odds"],row["under_odds"]]))[:28]
                    quote={
                        "quote_id":"propline_sog_"+contract_id,"contract_id":"nhl_sog_exact_offer_"+contract_id,
                        "event_id":row["event_id"],"event_start_at":row["event_start"],
                        "sport":"NHL","league":"NHL","season":e["start"].year,
                        "team_id":candidate["team"],"opponent_id":candidate["opponent"],
                        "player_id":pid,"stat_key":"shots on goal","period":"full",
                        "line":float(row["line"]),"book":row["book"],"product_type":"sportsbook_two_sided",
                        "quote_at":row["retrieved_at"],"quote_receipt_sha256":quote_sha,
                        "settlement_policy":"strict_gt_lt_equal_push","quote_kind":"real","accepted":True,
                        "over_decimal_odds":dec(row["over_odds"]),"under_decimal_odds":dec(row["under_odds"]),
                        "quote_archive_path":quote_rel}
                    # Independently replay the exact native-ID/two-sided
                    # offer from the untouched original provider HTTP response.
                    # This second check does not trust the derived quote JSONL.
                    raw_pairs=[]
                    for livebook in e["raw"].get("bookmakers") or []:
                        if livebook.get("key")!=row["book"]:continue
                        for live_market in livebook.get("markets") or []:
                            if live_market.get("key")!="player_shots_on_goal":continue
                            found={"over":[],"under":[]}
                            for outcome in live_market.get("outcomes") or []:
                                if not isinstance(outcome,dict):continue
                                side=str(outcome.get("name") or "").lower()
                                if side not in found:continue
                                if str(outcome.get("player_id") or "")!=row["provider_native_player_id"]:continue
                                if norm(outcome.get("description") or outcome.get("player"))!=norm(row["player"]):continue
                                try:
                                    point=outcome.get("point") if outcome.get("point") is not None else outcome.get("line")
                                    price=outcome.get("price") if outcome.get("price") is not None else outcome.get(side+"_odds")
                                    if float(point)!=row["line"] or float(price)!=row[side+"_odds"]:continue
                                except (ValueError,TypeError):continue
                                found[side].append(outcome)
                            if len(found["over"])==len(found["under"])==1:
                                raw_pairs.append(found)
                    if len(raw_pairs)!=1:
                        fail("INDEPENDENT_RAW_MARKET_OFFER_PROOF",
                             "ORIGINAL_PAIR_NOT_FOUND_UNIQUELY_IN_ORIGINAL_HTTP_BODY",pid)
                        manifest["counts"]["runner_abstentions"]+=1
                        continue
                    MarketQuote(**quote)
                    started=datetime.now(timezone.utc)
                    attempt=DAYROOT/("authentic_gamma_poisson_attempt_"+started.strftime("%Y%m%dT%H%M%S%fZ")+"_"+contract_id[:9])
                    attempt.mkdir(parents=True,exist_ok=False)
                    input_lineage={
                        "schema":"v25_sog_first_real_quote_attempt_input_lineage_v1",
                        "created_at":stamp(started),
                        "real_provider_quote_received_at":row["retrieved_at"],
                        "original_provider_http_body_sha256":source_sha,
                        "original_structured_rows_sha256":quote_sha,
                        "official_signed_manifest_sha256":sha(original_manifest_file.read_bytes()),
                        "new_signed_score_proof_sha256":schedule_receipt["collector_proof_sha256"],
                        "new_signed_roster_proof_sha256":{t:rr["source_c03_collector_proof_sha256"] for t,rr in rosters.items()},
                        "chosen_offer_identity":{
                            "provider_event_id":row["event_id"],"nhl_official_event_id":e["nhl_id"],
                            "official_nhl_player_id":pid,"official_team":candidate["team"],
                            "opponent_team":candidate["opponent"],"provider_player_name":row["player"],
                            "book":row["book"],"line":row["line"],
                            "over_odds":row["over_odds"],"under_odds":row["under_odds"],
                            "event_start":row["event_start"]},
                        "quote":quote,"own_signed_history_count":len(candidate["own"]),
                        "peer_signed_history_count":len(candidate["peers"]),
                        "source_bound_original_native_nhl_player_id":row["provider_native_player_id"],
                        "source_profile_proof_sha256":candidate["source_profile_proof"],
                        "source_pool":str(POOL.relative_to(BASE)),"code_commit":CODE_COMMIT,
                        "current_history_manifest":history_ref,
                        "no_pregame_lineup_confirmation_claim":True,"DNP_mass_not_modeled":True,
                        "original_market_provider_publication_time_unverified":True,
                        "source_retrosigned":False,"production_selection_allowed":False,
                        "tier_authorized":False}
                    input_bytes=canon(input_lineage)
                    write_once(attempt/"original_quote_and_source_identity_receipt.json",input_bytes)
                    bundle={"schema":"v25_sog_prospective_input_v1","quote":quote,
                        "official_position_group":candidate["group"],
                        "official_roster_receipts":{t:rosters[t] for t in (candidate["team"],candidate["opponent"])},
                        "own_official_history":candidate["own"],
                        "peer_official_history":candidate["peers"],
                        "code_commit":CODE_COMMIT,
                        "run_id":"v25_original_sog_daily_"+RUN_ID,
                        "forecast_id":"sog_sh_"+contract_id}
                    # Source-certified family inference is independent of legacy GP success.
                    try:
                        from v2.nhl_sog_daily_runner import freeze_family
                        daily_contract={**quote,"official_game_id":e["nhl_id"],
                            "original_provider_sha256":source_sha,
                            "input_receipt_sha256":sha(input_bytes),
                            "current_history_manifest_sha256":history_ref["sha256"],
                            "research_protocol":"NHL_SOG_DAILY_EXPANDED_HISTORY_20261119",
                            "signed_schedule_proof_sha256":schedule_receipt["collector_proof_sha256"]}
                        receipt=freeze_family(bundle,daily_contract,source_root=POOL,
                            ledger_path=BASE/"reports/nhl_sog_daily_v1/ledger.sqlite")
                        manifest.setdefault("daily_family_freezes",[]).append(receipt)
                    except Exception as exc:
                        fail("DAILY_FAMILY_FREEZE",sanit(exc),pid)
                    try:
                        # Do not silently enroll expanded histories in the old confirmatory cohort.
                        if pid in current['signed_observation_contracts_by_player']:
                            a={"status":"ABSTAIN","reason":"EXPANDED_HISTORY_SEPARATE_DAILY_FAMILY_COHORT"}
                            res={"attempt_receipt":{"sha256":None}}
                        else:
                            res=prospective_shadow_attempt(bundle,source_root=POOL,output_root=attempt/"output")
                            a=res["attempt"]
                    except Exception as exc:
                        # Preserve initial receipt and fail closed; never forge
                        # model snapshots when an unexpected exception occurs.
                        a={"status":"ABSTAIN","reason":"UNEXPECTED:"+sanit(exc)}
                        res={"attempt_receipt":{"sha256":None}}
                    completed=datetime.now(timezone.utc)
                    wrapper={
                      "experiment":"EXP-V25-NHL-SOG-EXPOSURE-EB-001",
                      "attempt_started_utc":stamp(started),"attempt_finished_utc":stamp(completed),
                      "status":a["status"],"reason":a.get("reason"),
                      "official_nhl_event_id":e["nhl_id"],"provider_event_id":row["event_id"],
                      "player":row["player"],"team":candidate["team"],"line":row["line"],"book":row["book"],
                      "original_provider_offer_sha256":source_sha,"quote_archive_sha256":quote_sha,
                      "run_input_receipt_sha256":sha(input_bytes),
                      "attempt_sha256":res["attempt_receipt"]["sha256"],
                      "snapshot_reference":a.get("snapshot_artifact"),
                      "model_reference":a.get("model_artifact"),
                      "three_way_probabilities":a.get("three_way_probabilities"),
                      "baseline_three_way":a.get("baseline_three_way"),
                      "fully_certified_publisher_attestation":False,
                      "research_shadow_only":True,"production_unchanged":True,"tier_allowed":False}
                    payload=canon(wrapper)
                    write_once(attempt/"first_real_offer_shadow_attempt_receipt.json",payload)
                    manifest["attempts"].append({
                        "player_id":pid,"player":row["player"],"provider_event_id":row["event_id"],
                        "official_nhl_event_id":e["nhl_id"],"book":row["book"],"line":row["line"],
                        "source_quote_sha256":quote_sha,"status":a["status"],"reason":a.get("reason"),
                        "attempt_started_at":stamp(started),"attempt_finished_at":stamp(completed),
                        "receipt_path":str((attempt/"first_real_offer_shadow_attempt_receipt.json").relative_to(BASE)),
                        "receipt_sha256":sha(payload),
                        "full_model_sha256":(a.get("model_artifact") or {}).get("sha256"),
                        "full_forecast_sha256":(a.get("snapshot_artifact") or {}).get("sha256")})
                    if a["status"]=="SHADOW_FORECAST":
                        manifest["counts"]["successful_forecasts"]+=1
                    else:
                        manifest["counts"]["runner_abstentions"]+=1
                        fail("RUNNER_SOURCE_CONTRACT",a.get("reason") or "UNKNOWN",pid)
                final("SUCCESS_RESEARCH_SHADOWS" if manifest["counts"]["successful_forecasts"] else "BLOCKED_NO_CERTIFIED_FORECAST")
except Exception as exc:
    fail("BATCH_FATAL",sanit(exc))
    final("BLOCKED_FAIL_CLOSED")
