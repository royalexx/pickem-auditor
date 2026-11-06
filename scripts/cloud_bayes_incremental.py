#!/usr/bin/env python3
"""Online, source-verified Bayesian shadow forecasts for the cloud daily runner.

This is NOT an update to the frozen full hierarchical PyMC/NUTS posterior.
Two distinct sequential models are maintained:
  * Gamma-Poisson player count rates using actual completed-game exposures.
  * A discrete Bayesian log-odds calibration posterior for frozen A/B
    empirical-Bayes forecasts, updated only when their original pregame
    probabilities can be matched to subsequent official settlements.

Updates are prospective, idempotent, content-addressed, chronological and
research-only. No production promotion or changes to frozen training occur.
"""
from __future__ import annotations

import argparse
import base64
import copy
import gzip
import hashlib
import json
import math
import re
import random
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import live_pool_exchange as pool
import population_history as history

SCHEMA = "pickem_incremental_cloud_bayes_v1"
SHADOW_SCHEMA = "pickem_incremental_bayes_shadow_v1"
PREFIX = "data/online_bayes/states/"
BRANCH = "data/live-observations"
GRID = tuple(round(-1.5 + i * .025, 7) for i in range(121))
PRIOR_SD = .40
# Conservative weak fixed priors. Units: expected observed counts / player
# exposure minute (NBA/NHL) or observed offensive/defensive snap (NFL).
# Never interpret them as posterior parameters of the complex NUTS model.
BASE_RATE = {
 "NHL":{"shots on goal":.13,"hits":.105,"blocked shots":.075,"saves":.48},
 "NBA":{"points":.42,"rebounds":.15,"assists":.13,"threes":.055,
        "steals":.035,"blocks":.025,"turnovers":.060,
        "pra":.70,"pr":.57,"pa":.55,"ra":.28},
 "NFL":{"pass attempts":.68,"completions":.43,"targets":.12,
        "receptions":.075,"carries":.23,
        "passing touchdowns":.038,"rushing touchdowns":.010,
        "receiving touchdowns":.009,
        "tackles + assists":.125,"solo tackles":.085,
        "tackle assists":.040,"qb hits":.027,"passes defended":.018}
}
ALPHA0 = 2.0
MIN_PLAYER_GAMES = 5
MIN_CALIBRATION_EVENTS = 100
MIN_CALIBRATION_DAYS = 14

def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False,ensure_ascii=False)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def today():
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/Toronto")).date().isoformat()

def yesterday(day):
    return (date.fromisoformat(day)-timedelta(days=1)).isoformat()

def initial_state():
    return {"schema":SCHEMA,"through":None,"source_days":{},
            "rate":{},"calibration":{},"daily_metrics":{},"bootstrap_rates":{},
            "bootstrap_source":None,
            "counts":{"population_events":0,"verified_binary_forecasts":0,
                      "historical_seed_events":0},
            "publication_eligible":False,"changes_production_model":False,
            "nuts_posterior_updated":False}

def assert_state(s):
    if not isinstance(s,dict) or s.get("schema")!=SCHEMA:
        raise ValueError("INVALID_INCREMENTAL_BAYES_STATE")
    if s.get("through") is not None:date.fromisoformat(s["through"])
    if s.get("publication_eligible") is not False or s.get("nuts_posterior_updated") is not False:
        raise ValueError("UNAUTHORIZED_MODEL_PROMOTION")
    for name in ("source_days","rate","calibration","daily_metrics","counts","bootstrap_rates"):
        if not isinstance(s.get(name),dict):raise ValueError("CORRUPT_STATE_"+name)
    return s

def pack(s):
    assert_state(s)
    return gzip.compress(canonical(s).encode("utf-8"),mtime=0,compresslevel=6)

def unpack(payload):
    return assert_state(json.loads(gzip.decompress(payload)))

def tree(token):
    resp=pool.api("/git/trees/"+BRANCH+"?recursive=1",token=token)
    if resp.get("truncated"):raise RuntimeError("GITHUB_LIVE_POOL_TREE_TRUNCATED")
    return resp.get("tree",[])

def current_state(token, *, before):
    """Only dated states strictly older than the slate in question."""
    end=date.fromisoformat(before)
    found=[]
    for item in tree(token):
        path=item.get("path","")
        if not path.startswith(PREFIX) or not path.endswith(".json.gz"):continue
        label=path[len(PREFIX):]
        match=re.fullmatch(r"(\d{4}-\d\d-\d\d)-([0-9a-f]{64})\.json\.gz",label)
        if not match:continue
        stamp=date.fromisoformat(match.group(1))
        if stamp<end:found.append((stamp,path,match.group(2),item["sha"]))
    if not found:return initial_state(),None
    last=max(stamp for stamp,_,_,_ in found)
    entries=[x for x in found if x[0]==last]
    if len(entries)!=1:
        raise ValueError("AMBIGUOUS_DAILY_BAYES_STATE_SAME_DATE")
    _,path,sha,blob=entries[0]
    raw=pool.read_blob(blob,token=token)
    if digest(raw)!=sha:raise ValueError("ONLINE_STATE_BLOB_DIGEST_MISMATCH")
    state=unpack(raw)
    if state["through"]!=last.isoformat():
        raise ValueError("ONLINE_STATE_DATE_MISMATCH")
    return state,path

def save_state(state, *, token):
    packed=pack(state)
    if not state["through"]:raise ValueError("empty_online_state_date")
    filename=PREFIX+state["through"]+"-"+digest(packed)+".json.gz"
    existing=[p for p in tree(token) if p.get("path","").startswith(
        PREFIX+state["through"]+"-") and p.get("path","").endswith(".json.gz")]
    if existing:
        if len(existing)!=1 or existing[0]["path"]!=filename:
            raise ValueError("IMMUTABLE_DAILY_POSTERIOR_STATE_CONFLICT")
        prior=pool.read_blob(existing[0]["sha"],token=token)
        if prior!=packed:raise ValueError("REMOTE_POSTERIOR_CONTENT_CONFLICT")
        return {"status":"already_present","path":filename,"sha256":digest(packed)}
    result=pool.api("/contents/"+filename,token=token,method="PUT",
                    payload={"message":"Archive chronological online Bayesian posterior through "+
                             state["through"],"content":base64.b64encode(packed).decode(),
                             "branch":BRANCH})
    return {"status":"published","path":filename,"sha256":digest(packed),
            "commit_sha":result.get("commit",{}).get("sha")}

def logsumexp(values):
    if not values:raise ValueError("empty_log_grid")
    m=max(values)
    return m+math.log(sum(math.exp(v-m) for v in values))

def logit(p):
    return math.log(p)-math.log1p(-p)

def sigmoid(x):
    if x>=0:return 1/(1+math.exp(-x))
    t=math.exp(x)
    return t/(1+t)

def start_calibrator():
    prior=[-.5*(b/PRIOR_SD)**2 for b in GRID]
    z=logsumexp(prior)
    return {"logw":[round(x-z,15) for x in prior],"events":0,"days":0}

def predictive_probability(record,p):
    if not 0<p<1:raise ValueError("unsupported_calibration_boundary_probability")
    b=logit(p)
    return sum(math.exp(w)*sigmoid(b+offset)
               for w,offset in zip(record["logw"],GRID))

def update_calibration(record,observations):
    """Batch by game_date so prequential test never uses same-day outcomes."""
    logw=list(record["logw"])
    for p,y in observations:
        if not 0<p<1 or y not in (0,1):
            raise ValueError("INVALID_CALIBRATION_OBSERVATION")
        baseline=logit(p)
        for i,b in enumerate(GRID):
            q=max(1e-12,min(1-1e-12,sigmoid(baseline+b)))
            logw[i]+=math.log(q if y else 1-q)
    z=logsumexp(logw)
    record["logw"]=[round(x-z,15) for x in logw]
    record["events"]+=len(observations)
    record["days"]+=int(bool(observations))

def prob(value):
    try:
        if isinstance(value,bool):return None
        number=float(value)
        return number if math.isfinite(number) and 0<=number<=1 else None
    except (TypeError,ValueError):return None

def decimal_key(value):
    try:return format(float(value),".10g")
    except (TypeError,ValueError):return str(value)

def identity(row):
    return (str(row.get("game_date") or ""),str(row.get("run_id") or ""),
            str(row.get("sport") or ""),
            str(row.get("player_id") or row.get("player") or ""),
            str(row.get("stat") or ""),str(row.get("side") or ""),
            decimal_key(row.get("reference_line")))

def event_identity(row):
    # All over/under quotes from the same player event/stat are ONE
    # validation observation; no double counting 1.5 and 2.5 lines.
    return (str(row.get("game_date") or ""),str(row.get("sport") or ""),
            str(row.get("event_id_namespace") or ""),
            str(row.get("event_id") or row.get("matchup") or ""),
            str(row.get("player_id") or row.get("player") or ""),
            str(row.get("stat") or ""))

def timestamp(value):
    try:
        dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError,TypeError):return None

def settled_matches(afternoon,morning,day):
    # Match against the same first archived batch selected by morning restore.
    # Mixing reruns would create contradictory original forecasts/sidecars.
    canonical_days=pool.canonical_afternoon_docs(afternoon)
    forecasts={}
    shadows={"bayesian_a":{},"bayesian_b":{}}
    for doc in ([canonical_days[day]] if day in canonical_days else []):
        if doc.get("game_date")!=day:raise ValueError("MIXED_FORECAST_DATES")
        for row in doc.get("forecasts",[]):
            key=identity(row)
            if key in forecasts and canonical(forecasts[key])!=canonical(row):
                raise ValueError("ORIGINAL_PREGAME_FORECAST_CONFLICT")
            forecasts[key]=row
        for model in shadows:
            for row in (doc.get("shadow") or {}).get(model,[]):
                key=identity(row)
                if key in shadows[model] and canonical(shadows[model][key])!=canonical(row):
                    raise ValueError("ORIGINAL_BAYESIAN_FORECAST_CONFLICT")
                shadows[model][key]=row
    settles={}
    for doc in morning:
        if doc.get("game_date")!=day:raise ValueError("MIXED_SETTLEMENT_DATES")
        for row in doc.get("settlements",[]):
            key=identity(row)
            if key in settles:
                prior=settles[key]
                if (prior.get("actual_stat"),prior.get("outcome"))!=(
                     row.get("actual_stat"),row.get("outcome")):
                    raise ValueError("CONFLICTING_OFFICIAL_SETTLEMENT")
                # Repeated morning settlement is idempotent; retain the
                # earlier timestamp without rewriting the original forecast.
                if str(row.get("settled_at") or "") >= str(prior.get("settled_at") or ""):
                    continue
            settles[key]=row
    candidates=[]
    for key,final in settles.items():
        old=forecasts.get(key)
        if old is None or old.get("actual_stat") is not None:continue
        when,start=timestamp(old.get("forecast_at")),timestamp(old.get("event_start"))
        if not when or not start or when>=start:continue
        if final.get("outcome") not in ("win","loss") or final.get("actual_stat") is None:continue
        models={}
        for name in shadows:
            source=shadows[name].get(key)
            if source and source.get("status")=="forecast" and (
                 source.get("publication_eligible") is False):
                q,push=prob(source.get("q_win")),prob(source.get("q_push"))
                if q is not None and push is not None and push<1 and q<=1-push:
                    conditional=q/(1-push)
                    if 0<conditional<1:models[name]=conditional
        candidates.append((event_identity(old),when.isoformat(),key,
                           1 if final["outcome"]=="win" else 0,models))
    # Choose EARLIEST forecast per event/player/stat, regardless of number
    # of lines or which side was quoted; all chosen models share its timestamp.
    chosen={}
    for event,at,key,y,models in sorted(candidates,key=lambda r:(r[1],str(r[2]))):
        if event not in chosen:chosen[event]=(at,key,y,models)
    return list(chosen.items())

def population_rows(morning,day):
    seen={}
    for doc in morning:
        receipt=doc.get("population_collection_receipt")
        if not isinstance(receipt,dict) or receipt.get("status")!="complete":
            raise ValueError("MORNING_SOURCES_INCOMPLETE_DO_NOT_UPDATE_POSTERIOR")
        for row in doc.get("population",[]):
            history.validate(row)
            if row["game_date"]!=day:raise ValueError("POPULATION_GAME_DATE_CONFLICT")
            key=(row["sport"],row["stat"],str(row["game_id"]),str(row["player_id"]))
            prior=seen.get(key)
            if prior is not None and prior!=row:
                raise ValueError("CONFLICTING_DUPLICATE_POPULATION_OBSERVATION")
            seen[key]=row
    return [seen[k] for k in sorted(seen)]

def bootstrap_history(token, *,before,lookback_days=520):
    """Read verified 2024+ population shards from a PINNED historical Git commit.

    Only completed games strictly BEFORE the first day of new cloud evidence.
    Old player exposures get a discounted 0.15 likelihood power after 120 days;
    this is a conservative power-prior model, not the joint NUTS posterior.
    Population states remain frozen, and these source observations are NOT
    written back to the frozen historical branch.
    """
    cutoff=date.fromisoformat(before)
    oldest=cutoff-timedelta(days=lookback_days)
    ref=pool.api("/git/ref/heads/data/bayesian-history",token=token)
    commit=(ref.get("object") or {}).get("sha")
    if not isinstance(commit,str) or not re.fullmatch("[0-9a-f]{40}",commit):
        raise ValueError("UNPINNED_HISTORICAL_SOURCE_COMMIT")
    payload=pool.api("/git/trees/"+commit+"?recursive=1",token=token)
    if payload.get("truncated"):raise ValueError("TRUNCATED_HISTORICAL_SOURCE_TREE")
    rate={}
    processed=set()
    source_hashes=[]
    accepted=0
    for entry in sorted(payload.get("tree",[]),key=lambda e:e.get("path","")):
        filename=entry.get("path","")
        if entry.get("type")!="blob" or not filename.startswith("data/bayesian_warehouse/populations/") or not filename.endswith(".jsonl.gz"):
            continue
        try:
            season=int(Path(filename).stem.split(".")[0])
        except ValueError:
            continue
        if season < oldest.year-1 or season > cutoff.year+1:
            continue
        sport,slug=filename.split("/")[3:5]
        if sport.upper() not in BASE_RATE:
            continue
        # Do not ingest an unsupported market just because a shard exists.
        if slug not in {history.slug(k) for k in BASE_RATE[sport.upper()]}:
            continue
        archive=pool.read_blob(entry["sha"],token=token)
        source_hashes.append((filename,digest(archive)))
        for line in gzip.decompress(archive).decode("utf-8").splitlines():
            if not line.strip():continue
            row=json.loads(line)
            history.validate(row)
            game=date.fromisoformat(row["game_date"])
            if not oldest<=game<cutoff or row["family"]!="count":
                continue
            if not history.market_eligible(row):
                continue
            key=(row["sport"],row["stat"],str(row["game_id"]),str(row["player_id"]))
            if key in processed:raise ValueError("DUPLICATE_HISTORICAL_SOURCE_OBSERVATION")
            processed.add(key)
            rateid="|".join((row["sport"],row["stat"],str(row["season"]),str(row["player_id"])))
            current=rate.get(rateid)
            if current is None:
                mean=BASE_RATE[row["sport"]][row["stat"]]
                current={"alpha":ALPHA0,"beta":ALPHA0/mean,"games":0,
                         "sport":row["sport"],"stat":row["stat"],
                         "season":str(row["season"]),"player_id":str(row["player_id"]),
                         "position":row["position"],"last_game":None,
                         "historical_seed_games":0,"live_games":0}
            power=1.0 if (cutoff-game).days<=120 else .15
            current["alpha"]+=power*int(row["value"])
            current["beta"]+=power*float(row["workload"])
            current["games"]+=1
            current["historical_seed_games"]+=1
            if current["last_game"] is None or row["game_date"]>current["last_game"]:
                current["last_game"]=row["game_date"]
            rate[rateid]=current
            accepted+=1
    state=initial_state()
    state["rate"]=rate
    state["bootstrap_rates"]=copy.deepcopy(rate)
    state["bootstrap_source"]={"historical_commit":commit,
         "cutoff_exclusive":before,"lookback_days":lookback_days,
         "verified_population_rows":accepted,
         "archive_shard_count":len(source_hashes),
         "source_digest":digest(canonical(source_hashes).encode()),
         "posterior_note":"Gamma-Poisson discounted historical power-prior shadow only; no NUTS posterior update"}
    state["counts"]["historical_seed_events"]=accepted
    return state


def rate_key(row):
    return "|".join(map(str,(row["sport"],row["stat"],row["season"],row["player_id"])))

def update_one_day(state,day,afternoon,morning):
    assert_state(state)
    date.fromisoformat(day)
    if state["through"] is not None and day<=state["through"]:
        raise ValueError("NON_FORWARD_ONLINE_BAYES_UPDATE")
    if not morning:raise ValueError("MISSING_VERIFIED_MORNING_BUNDLE")
    source_rows=population_rows(morning,day)
    for row in source_rows:
        if row["family"]!="count" or row["stat"] not in BASE_RATE.get(row["sport"],{}):
            continue
        key=rate_key(row)
        current=state["rate"].get(key)
        if current is None:
            center=BASE_RATE[row["sport"]][row["stat"]]
            current={"alpha":ALPHA0,"beta":ALPHA0/center,"games":0,
                     "sport":row["sport"],"stat":row["stat"],
                     "season":str(row["season"]),"player_id":str(row["player_id"]),
                     "position":row["position"],"last_game":None}
        elif current["position"]!=row["position"]:
            # A player moved positions during the season: update the count
            # rate but retain the original group provenance for auditing.
            current["position_change_seen"]=True
        current["alpha"]+=int(row["value"])
        current["beta"]+=float(row["workload"])
        current["games"]+=1
        current["live_games"]=int(current.get("live_games",0))+1
        current["last_game"]=day
        state["rate"][key]=current
    matches=settled_matches(afternoon,morning,day)
    observations=defaultdict(list)
    model_count=0
    for _,(_,key,y,models) in matches:
        for name,p in models.items():
            if not 0<p<1:continue
            observations["|".join((key[2],key[4],name))].append((p,y))
            model_count+=1
    daily={}
    for key,batch in sorted(observations.items()):
        record=state["calibration"].setdefault(key,start_calibrator())
        # Evaluate the entire day's batch from YESTERDAY's posterior, then
        # assimilate the whole day. No same-game or same-day look-ahead.
        metrics={"n":len(batch),"brier_base":0.0,"brier_online":0.0,
                 "logloss_base":0.0,"logloss_online":0.0}
        for p,y in batch:
            q=predictive_probability(record,p)
            metrics["brier_base"]+=(p-y)**2
            metrics["brier_online"]+=(q-y)**2
            metrics["logloss_base"]+=-math.log(max(1e-12,p if y else 1-p))
            metrics["logloss_online"]+=-math.log(max(1e-12,q if y else 1-q))
        daily[key]=metrics
        update_calibration(record,batch)
    state["daily_metrics"][day]=daily
    state["source_days"][day]=digest(canonical({
        "population":source_rows,"matches":[(list(event),at,list(key),y,models)
                                             for event,(at,key,y,models) in matches]}).encode())
    state["through"]=day
    state["counts"]["population_events"]+=len(source_rows)
    state["counts"]["verified_binary_forecasts"]+=len(matches)
    return {"date":day,"population_rows":len(source_rows),"matched_player_stat_events":len(matches),
            "calibration_model_observations":model_count,
            "active_player_rates":len(state["rate"])}

def rebuild(docs,*,through,seed=None):
    state=copy.deepcopy(seed) if seed is not None else initial_state()
    grouped=defaultdict(lambda:{"afternoon":[],"morning":[]})
    for document,path in docs:
        day=document["game_date"]
        if day<=through:grouped[day][document["phase"]].append(document)
    stats=[]
    for day in sorted(grouped):
        if not grouped[day]["morning"]:
            continue
        stats.append(update_one_day(state,day,grouped[day]["afternoon"],grouped[day]["morning"]))
    return state,stats

def run_update(*,token,as_of,weekly_rebuild=False):
    cutoff=date.fromisoformat(as_of)
    target=(cutoff-timedelta(days=1)).isoformat()
    previous,source=current_state(token,before=as_of)
    # Already persisted through yesterday: do not mutate or duplicate.
    if previous["through"]==target:
        return {"status":"already_current","through":target,"source":source,
                "population_events":previous["counts"]["population_events"]}
    after=(date.fromisoformat(previous["through"])+timedelta(days=1)).isoformat() if previous["through"] else None
    docs=list(pool.iter_remote_docs(token=token,before=as_of,after=after))
    grouped=defaultdict(lambda:{"afternoon":[],"morning":[]})
    for doc,path in docs:grouped[doc["game_date"]][doc["phase"]].append(doc)
    if previous["through"] is None:
        start_dates=sorted(day for day,groups in grouped.items() if groups["morning"])
        if not start_dates:
            raise ValueError("NO_MORNING_BUNDLE_TO_SEED_BAYES")
        previous=bootstrap_history(token,before=start_dates[0])
    revised=copy.deepcopy(previous)
    results=[]
    for day in sorted(grouped):
        if day>target:continue
        if not grouped[day]["morning"]:
            # No synthetic zero observations for dates with absent source.
            continue
        results.append(update_one_day(revised,day,grouped[day]["afternoon"],grouped[day]["morning"]))
    if not results or revised["through"]!=target:
        raise ValueError("LATEST_COMPLETED_GAME_DATE_HAS_NO_VERIFIED_SOURCE_BUNDLE")
    if weekly_rebuild:
        # Exact replay from the immutable cloud archive, not a new scrape
        # or a costly PyMC/NUTS fit. This catches silent state drift.
        full_docs=list(pool.iter_remote_docs(token=token,before=as_of))
        seed=initial_state()
        seed["rate"]=copy.deepcopy(revised["bootstrap_rates"])
        seed["bootstrap_rates"]=copy.deepcopy(revised["bootstrap_rates"])
        seed["bootstrap_source"]=copy.deepcopy(revised["bootstrap_source"])
        seed["counts"]["historical_seed_events"]=revised["counts"]["historical_seed_events"]
        check,_=rebuild(full_docs,through=target,seed=seed)
        if canonical(revised)!=canonical(check):
            raise ValueError("WEEKLY_FULL_REPLAY_DIFFERED_FROM_DAILY_POSTERIOR")
    receipt=save_state(revised,token=token)
    return {**receipt,"through":revised["through"],"source_records":results,
            "weekly_full_replay_checked":weekly_rebuild,
            "population_events":revised["counts"]["population_events"],
            "calibration_events":revised["counts"]["verified_binary_forecasts"],
            "active_player_rates":len(revised["rate"]),
            "historical_seed_events":revised["counts"]["historical_seed_events"],
            "approved_for_production":False}

def _negbin_pmf(alpha,beta,exposure,k):
    """Gamma-Poisson posterior predictive count PMF without random sampling."""
    if not alpha>0 or not beta>0 or not exposure>0 or k<0:
        raise ValueError("invalid_online_count_predictive")
    return math.exp(math.lgamma(alpha+k)-math.lgamma(alpha)-math.lgamma(k+1)+
                    alpha*math.log(beta/(beta+exposure))+
                    k*math.log(exposure/(beta+exposure)))

def count_probability(record,*,exposure,line,side):
    if not math.isfinite(exposure) or not 0<exposure<=300 or not math.isfinite(line) or line<0:
        raise ValueError("invalid_count_forecast_exposure_or_line")
    threshold=int(math.floor(line))
    mass=sum(_negbin_pmf(record["alpha"],record["beta"],exposure,k)
             for k in range(threshold+1))
    push=(_negbin_pmf(record["alpha"],record["beta"],exposure,threshold)
          if abs(line-threshold)<1e-9 else 0.0)
    over=max(0,min(1,1-mass))
    under=max(0,min(1,mass-push))
    q=over if side=="over" else under if side=="under" else None
    if q is None:raise ValueError("invalid_prop_side")
    return q,push

def calibrator_ready(record):
    return record["events"]>=MIN_CALIBRATION_EVENTS and record["days"]>=MIN_CALIBRATION_DAYS

def read_jsonl(path):
    if not Path(path).is_file():return []
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]

def forecast_sidecar(*,root,date_text,state,out):
    """Immutable new fifth-model sidecar; base four models remain untouched."""
    slate_day=date.fromisoformat(date_text)
    if state["through"] is not None and date.fromisoformat(state["through"])>=slate_day:
        raise ValueError("ONLINE_INFERENCE_USED_FUTURE_GAME_RESULTS")
    snapshots=read_jsonl(Path(root)/"data/prop_snapshots.jsonl")
    a=read_jsonl(Path(root)/"data/bayesian_shadow"/(date_text+".jsonl"))
    b=read_jsonl(Path(root)/"data/bayesian_b_shadow"/(date_text+".jsonl"))
    indices={"bayesian_a":{identity(r):r for r in a},
             "bayesian_b":{identity(r):r for r in b}}
    latest=[r for r in snapshots if r.get("game_date")==date_text and r.get("run_type")=="shadow"]
    if not latest:raise ValueError("NO_SAME_DAY_FROZEN_SOURCE_FORECASTS")
    run=max(latest,key=lambda r:(str(r.get("forecast_at") or ""),str(r.get("run_id") or ""))).get("run_id")
    rows=[r for r in latest if r.get("run_id")==run]
    outputs=[]
    seen=set()
    for row in rows:
        key=identity(row)
        if key in seen:continue
        seen.add(key)
        result={k:row.get(k) for k in ("game_date","run_id","forecast_at","event_start",
                                      "event_id","sport","player","player_id","team",
                                      "stat","side","reference_line")}
        result.update(schema=SHADOW_SCHEMA,version=SCHEMA,
                      publication_eligible=False,production_weights_changed=False,
                      nuts_posterior_updated=False,training_data_through=state["through"],
                      original_source_forecast_id=digest(canonical(key).encode()),
                      models={})
        for model in ("bayesian_a","bayesian_b"):
            src=indices[model].get(key)
            prediction={"status":"unavailable","reason":"no_qualified_prior_completed_game_calibration"}
            if src and src.get("status")=="forecast":
                p,push=prob(src.get("q_win")),prob(src.get("q_push"))
                cid="|".join((row.get("sport",""),row.get("stat",""),model))
                cal=state["calibration"].get(cid)
                if p is not None and push is not None and push<1 and p<=1-push and 0<p/(1-push)<1 and cal:
                    q=predictive_probability(cal,p/(1-push))*(1-push)
                    prediction={"status":"research_shadow" if calibrator_ready(cal) else "warmup",
                                "q_win":round(q,10),"q_push":push,
                                "baseline_q_win":p,"posterior_events":cal["events"],
                                "posterior_days":cal["days"],
                                "approved_for_production":False}
            result["models"][model+"_online_calibrated"]=prediction
        # Independent count-rate update from actual finished player-game
        # stat/exposure, NOT an approximation to NUTS's player/team effects.
        ratekey="|".join((str(row.get("sport")),str(row.get("stat")),
                          str(slate_day.year if row.get("sport")!="NFL" else slate_day.year),
                          str(row.get("player_id"))))
        if row.get("sport")=="NHL":
            season_prefix=str(slate_day.year if slate_day.month>=7 else slate_day.year-1)
        elif row.get("sport")=="NBA":
            season_prefix=str(slate_day.year+1 if slate_day.month>=7 else slate_day.year)
        else:
            season_prefix=str(slate_day.year if slate_day.month>=7 else slate_day.year-1)
        ratekey="|".join((str(row.get("sport")),str(row.get("stat")),
                          season_prefix,str(row.get("player_id"))))
        rate=state["rate"].get(ratekey)
        bsrc=indices["bayesian_b"].get(key) or {}
        exposure=bsrc.get("workload_mean")
        prediction={"status":"unavailable","reason":"unseen_player_or_missing_exposure"}
        if rate and rate["games"]>=MIN_PLAYER_GAMES:
            # Future exposure is a pregame Engine B estimate. Never infer it
            # from the target game's postgame workload.
            try:
                ex=float(exposure)
                q,push=count_probability(rate,exposure=ex,
                                         line=float(row["reference_line"]),side=row["side"])
                prediction={"status":"research_shadow","q_win":round(q,10),
                            "q_push":round(push,10),"posterior_games":rate["games"],
                            "historical_seed_games":rate.get("historical_seed_games",0),
                            "live_games":rate.get("live_games",0),
                            "posterior_mean_rate":rate["alpha"]/rate["beta"],
                            "estimated_future_exposure":ex,
                            "approved_for_production":False}
            except (ValueError,TypeError,OverflowError):pass
        result["models"]["player_rate_gamma_poisson"]=prediction
        outputs.append(result)
    target=Path(out);target.parent.mkdir(parents=True,exist_ok=True)
    if target.is_file():
        existing=read_jsonl(target)
        if existing!=outputs:raise ValueError("IMMUTABLE_ONLINE_PREGAME_SIDECAR_CONFLICT")
    else:target.write_text("".join(canonical(r)+"\n" for r in outputs),encoding="utf-8")
    return {"schema":SHADOW_SCHEMA,"date":date_text,"rows":len(outputs),
            "training_data_through":state["through"],
            "online_calibrated":sum(any(v.get("status")=="research_shadow" for v in r["models"].values())
                                    for r in outputs),
            "production_models_changed":False,"publication_eligible":False,
            "sidecar_path":str(target)}

def monitoring(state, *,window_days=30):
    """Prospective, paired same-slate scoring; never a deployment approval."""
    today_date=date.fromisoformat(state["through"]) if state["through"] else None
    start=today_date-timedelta(days=window_days-1) if today_date else None
    totals=defaultdict(lambda:{"n":0,"brier_base":0.0,"brier_online":0.0,
                               "logloss_base":0.0,"logloss_online":0.0,"days":0})
    differences=defaultdict(list)
    for day,groups in state["daily_metrics"].items():
        if start and date.fromisoformat(day)<start:continue
        for key,values in groups.items():
            t=totals[key]
            differences[key].append((day,values["n"],
                 values["brier_base"]-values["brier_online"]))
            t["days"]+=1
            for col in ("n","brier_base","brier_online","logloss_base","logloss_online"):
                t[col]+=values[col]
    report={}
    for key,t in sorted(totals.items()):
        n=t["n"]
        # Resample whole game DATES, never pretend each overlapping player
        # prop is an independent outcome. This is a diagnostic uncertainty
        # interval, not permission to deploy model probabilities.
        lower=None
        day_values=differences[key]
        if n>=80 and len(day_values)>=10:
            rng=random.Random(31027)
            changes=[]
            for _ in range(400):
                sample=[day_values[rng.randrange(len(day_values))]
                        for _ in range(len(day_values))]
                denominator=sum(v[1] for v in sample)
                if denominator:
                    changes.append(sum(v[2] for v in sample)/denominator)
            if changes:
                changes.sort()
                lower=changes[int(.05*(len(changes)-1))]
        report[key]={"paired_events":n,"game_dates":t["days"],
                     "date_cluster_bootstrap_lower90":lower,
                     "baseline_brier":t["brier_base"]/n if n else None,
                     "online_brier":t["brier_online"]/n if n else None,
                     "baseline_logloss":t["logloss_base"]/n if n else None,
                     "online_logloss":t["logloss_online"]/n if n else None,
                     "preliminary_brier_improvement":t["brier_base"]/n-t["brier_online"]/n if n else None,
                     "research_qualified":n>=200 and t["days"]>=20 and
                         lower is not None and lower>0 and
                         t["brier_online"]<t["brier_base"] and t["logloss_online"]<t["logloss_base"],
                     "automatic_production_approval":False}
    return {"schema":"pickem_online_bayes_monitor_v1","as_of":state["through"],
            "window_days":window_days,"markets":report,
            "nuts_refit_recommendation":"Consider a separate newly frozen periodic full NUTS refit when source coverage, posterior convergence or holdout drift requires it; never start Dell/self-hosted training automatically.",
            "cloud_replay_weekly_on_monday":True,
            "publication_eligible":False}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    up=sub.add_parser("update")
    up.add_argument("--as-of",default=today())
    up.add_argument("--weekly-rebuild",action="store_true")
    up.add_argument("--report")
    infer=sub.add_parser("shadow")
    infer.add_argument("--date",default=today())
    infer.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    infer.add_argument("--out")
    infer.add_argument("--report")
    args=parser.parse_args(argv)
    import os
    token=os.environ.get("GITHUB_TOKEN")
    if not token:raise RuntimeError("Encrypted GITHUB_TOKEN needed for private GitHub state")
    if args.command=="update":
        report=run_update(token=token,as_of=args.as_of,weekly_rebuild=args.weekly_rebuild)
        state,_=current_state(token,before=args.as_of)
        report["monitor"]=monitoring(state)
    else:
        state,source=current_state(token,before=args.date)
        report=forecast_sidecar(root=args.root,date_text=args.date,state=state,
            out=args.out or str(args.root/"data/online_bayes_shadow"/(args.date+".jsonl")))
        report["state_source"]=source
    if args.report:
        p=Path(args.report);p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print(json.dumps(report,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
