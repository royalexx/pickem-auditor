"""Research-only historical NHL SOG replay; official retrospective event-time reconstruction.
EXP-P5-NHL-SOG-HIST-20261114. NO certified as-of / sportsbook / production claims.
Reuses frozen v2.nhl_sog_exposure_shadow probability implementations.
"""
from __future__ import annotations
import argparse, bisect, collections, csv, datetime as dt, hashlib, json, math, random
import statistics
from pathlib import Path
from v2 import nhl_sog_exposure_shadow as frozen

EXPERIMENT_ID = "EXP-P5-NHL-SOG-HIST-20261114"
MODEL_IDS = ("M0","M1","M2","M3","M4")
KINDS = {"M0":"plugin_poisson","M1":"mixture_exposure_plugin_poisson",
         "M2":"fixed_exposure_gamma_poisson","M3":"full_gamma_poisson_exposure"}
SCHEMA = "phase5_retrospective_event_time_v1"
MIN_OWN = frozen.MIN_PLAYER_GAMES
MIN_PEERS = frozen.MIN_PEERS
MIN_PEER_GAMES = frozen.MIN_PEER_GAMES
MAX_HIST = frozen.MAX_RATE_GAMES
MAX_PERSIST_DAYS = 21
ESTIMATED_PUBLICATION_LAG_HOURS = 8   # conservative event-time proxy, NOT certified source publication

class ReplayBlocked(ValueError): pass

def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()

def sha(x):return hashlib.sha256(x).hexdigest()

def read_jsonl(path):
    raw=Path(path).read_bytes()
    result=[]
    for n,line in enumerate(raw.splitlines(),1):
        if line.strip():
            try: result.append(json.loads(line))
            except ValueError as exc:raise ReplayBlocked("INVALID_JSON_ROW:"+str(n)) from exc
    return result,sha(raw)

def utc(s):
    if not isinstance(s,str) or "T" not in s:raise ReplayBlocked("TIME_MISSING")
    try:d=dt.datetime.fromisoformat(s.replace("Z","+00:00"))
    except (TypeError,ValueError) as exc:raise ReplayBlocked("TIME_INVALID") from exc
    if d.tzinfo is None:raise ReplayBlocked("TIME_NAIVE")
    return d.astimezone(dt.timezone.utc)

def parse_sources(obs, events):
    """No current roster or final opportunity is ever a feature."""
    schedule={};teams=collections.defaultdict(list)
    for e in events:
        gid=str(e.get("game_id") or "")
        if not gid or gid in schedule:raise ReplayBlocked("DUPLICATE_OR_MISSING_EVENT_ID")
        when=utc(e.get("start_utc")); day=str(e.get("game_date"))
        if len(day)!=10 or when.date() < dt.date.fromisoformat(day):
            raise ReplayBlocked("EVENT_DATE_INVALID")
        if e.get("season") not in ("20232024","20242025","20252026"):
            raise ReplayBlocked("INVALID_SEASON")
        two=e.get("teams")
        if not isinstance(two,list) or len(two)!=2 or len(set(two))!=2:
            raise ReplayBlocked("INVALID_SCHEDULE_TEAMS")
        if not all(isinstance(t,str) and len(t)==3 for t in two):
            raise ReplayBlocked("INVALID_TEAM_ID")
        schedule[gid]={**e,"game_id":gid,"_start":when}
        for team in two:teams[(day,team)].append(gid)
    by_player=collections.defaultdict(list); seen=set(); rejects=collections.Counter()
    for r in obs:
        pid=str(r.get("player_id") or ""); gid=str(r.get("game_id") or "")
        if not pid or not gid or (pid,gid) in seen:raise ReplayBlocked("DUPLICATE_OR_MISSING_PLAYER_GAME")
        seen.add((pid,gid))
        if gid not in schedule:
            rejects["NO_VERIFIED_SCHEDULE_EVENT"]+=1
            continue
        event=schedule[gid]; date=event["game_date"]
        if r.get("game_date")!=date or r.get("season")!=event["season"]:
            raise ReplayBlocked("EVENT_SEASON_OR_DATE_CONFLICT")
        if r.get("team") not in event["teams"]:
            raise ReplayBlocked("HISTORICAL_TEAM_NOT_IN_EVENT")
        if r.get("position_group") not in ("F","D"):
            raise ReplayBlocked("HISTORICAL_ROLE_UNVERIFIED")
        y=r.get("sog");w=r.get("toi_minutes")
        if type(y) is not int or y<0 or isinstance(w,bool) or not isinstance(w,(int,float)) or not math.isfinite(w) or not 0<w<=65:
            rejects["INVALID_OFFICIAL_PLAYED_SOG_TOI"]+=1;continue
        release_bound=event["_start"]+dt.timedelta(hours=ESTIMATED_PUBLICATION_LAG_HOURS)
        by_player[pid].append({**r,"_release":release_bound,"_start":event["_start"]})
    for pid in by_player:
        by_player[pid].sort(key=lambda x:(x["_start"],x["game_id"]))
    return schedule,by_player,rejects

def histories_as_of(by_player,cutoff,target_date):
    """Materialize a feature-only view; target and future labels never enter the model."""
    view={}
    for pid,rows in by_player.items():
        eligible=[r for r in rows if r["_release"] < cutoff and r["game_date"] < target_date]
        if eligible:view[pid]=eligible
    return view

def build_params(pid,history):
    own=history.get(pid,[])[-MAX_HIST:]
    if len(own)<MIN_OWN:raise ReplayBlocked("THIN_OWN_HISTORY")
    group=own[-1]["position_group"]
    peers_by={k:v[-MAX_HIST:] for k,v in history.items()
              if k!=pid and v and v[-1]["position_group"]==group}
    if len(peers_by)<MIN_PEERS:raise ReplayBlocked("THIN_PEER_PLAYERS")
    peers=[r for k in sorted(peers_by) for r in peers_by[k]]
    if len(peers)<MIN_PEER_GAMES:raise ReplayBlocked("THIN_PEER_GAMES")
    for row in own+peers:
        try:frozen.bin_toi_minutes(row["toi_minutes"])
        except frozen.ExperimentBlocked as exc:raise ReplayBlocked("EXPOSURE_BIN_INVALID") from exc
    rate_peer=math.fsum(r["sog"] for r in peers)/math.fsum(r["toi_minutes"] for r in peers)
    if rate_peer<=0:raise ReplayBlocked("ZERO_PEER_RATE")
    a=frozen.TAU_MINUTES*rate_peer+math.fsum(r["sog"] for r in own)
    b=frozen.TAU_MINUTES+math.fsum(r["toi_minutes"] for r in own)
    ownrate=math.fsum(r["sog"] for r in own)/math.fsum(r["toi_minutes"] for r in own)
    w0=float(statistics.median(r["toi_minutes"] for r in own[-5:]))
    h=collections.Counter(frozen.bin_toi_minutes(r["toi_minutes"]) for r in peers)
    recent=own[-frozen.MAX_EXPOSURE_GAMES:]
    n=collections.Counter(frozen.bin_toi_minutes(r["toi_minutes"]) for r in recent)
    pi=[(w,(n[w]+frozen.ETA_GAMES*h[w]/len(peers))/(len(recent)+frozen.ETA_GAMES))
        for w in sorted(set(h)|set(n))]
    if abs(math.fsum(p for _,p in pi)-1)>1e-10:raise ReplayBlocked("EXPOSURE_PMF_NOT_NORMALIZED")
    mu,var=frozen._moments(pi,a/b,a,b)
    model={"schema":frozen.SCHEMA,"rate_a":a,"rate_b":b,"exposure_pmf":pi,
           "plugin_rate":ownrate,"plugin_exposure":w0,"mean":mu,"variance":var}
    ab=frozen.same_data_ablations(model)
    stats={"own_n":len(own),"peer_n":len(peers_by),"peer_games":len(peers),
           "expected_sog":ab["full_gamma_poisson_exposure"]["mean"],
           "hist_toi":statistics.mean(r["toi_minutes"] for r in own[-10:]),
           "toi_sd":statistics.pstdev(r["toi_minutes"] for r in own[-10:]),
           "hist_team":own[-1]["team"],"hist_role":group,
           "last_played_date":own[-1]["game_date"],
           "last_feature_game_start":max(r["_start"] for r in own+peers).isoformat(),
           "last_feature_release_bound":max(r["_release"] for r in own+peers).isoformat(),
           "model_means":{z:ab[KINDS[z]]["mean"] for z in ("M0","M1","M2","M3")}}
    stats["model_means"]["M4"]=ownrate*w0
    return model,stats

def pmfs(model):
    """Frozen original PMFs M0..M3; M4 fixed r=4 and identical M0 mean."""
    mu=model["plugin_rate"]*model["plugin_exposure"]
    r=4.
    def nb(k):
        if mu==0:return float(k==0)
        return math.exp(math.lgamma(k+r)-math.lgamma(r)-math.lgamma(k+1)
                        +r*math.log(r/(r+mu))+k*math.log(mu/(r+mu)))
    ans={}
    for mid in MODEL_IDS:
        p=[];running=0.
        for k in range(256):
            v=nb(k) if mid=="M4" else frozen._mass(model,k,KINDS[mid])
            if not math.isfinite(v) or v < 0:raise ReplayBlocked("INVALID_PMF:"+mid)
            p.append(v);running+=v
            if k>=20 and 1-running<1e-12:break
        if abs(math.fsum(p)-1)>2e-10:
            raise ReplayBlocked("PMF_TRUNCATION_OR_NORMALIZATION:"+mid)
        ans[mid]=p
    return ans

def _frozen_mass_at(model,mid,k):
    if mid!="M4":return frozen._mass(model,k,KINDS[mid])
    mu=model["plugin_rate"]*model["plugin_exposure"];r=4.
    if mu==0:return float(k==0)
    return math.exp(math.lgamma(k+r)-math.lgamma(r)-math.lgamma(k+1)
                    +r*math.log(r/(r+mu))+k*math.log(mu/(r+mu)))

def distribution_score(p,y,model=None,mid=None):
    # Scoring-time tail extension uses the ALREADY SEALED model parameters, never
    # fits or changes the original forecast. Finite PMF truncation is not a
    # valid reason to drop an unusual high-SOG result from the matched cohort.
    if y>=len(p):
        if model is None or mid not in MODEL_IDS or y>2000:
            raise ReplayBlocked("TARGET_OUTSIDE_MATHEMATICAL_SUPPORT")
        p=p+[_frozen_mass_at(model,mid,k) for k in range(len(p),y+1)]
    cy=0.;crps=0.
    for k,pk in enumerate(p):
        cy+=pk
        crps+=(cy-float(y<=k))**2
    return {"crps":crps,"nll":-math.log(max(p[y],1e-300)),
            "mean":math.fsum(k*v for k,v in enumerate(p)),
            "variance":None, "zero":p[0],"tail6":math.fsum(p[6:]),
            "pit":None, "_cdf_left":math.fsum(p[:y]),"_pmf_at_y":p[y]}

def summarize(rows,ids=MODEL_IDS):
    if not rows:return {"n":0}
    out={"n":len(rows),"days":len({r["date"] for r in rows}),
         "games":len({r["game_id"] for r in rows}),
         "players":len({r["player_id"] for r in rows}),
         "models":{}}
    for mid in ids:
        sr=[r["scores"][mid] for r in rows]; actual=[r["actual_sog"] for r in rows]
        means=[z["mean"] for z in sr];obs=statistics.mean(actual)
        out["models"][mid]={"crps":statistics.mean(z["crps"] for z in sr),
          "nll":statistics.mean(z["nll"] for z in sr),
          "mean_predicted":statistics.mean(means),"mean_observed":obs,
          "mean_bias":statistics.mean(means)-obs,
          "mean_squared_error":statistics.mean((m-y)**2 for m,y in zip(means,actual)),
          "mean_predictive_variance":statistics.mean(z["variance"] for z in sr),
          "zero_predicted":statistics.mean(z["zero"] for z in sr),
          "zero_observed":statistics.mean(y==0 for y in actual),
          "tail6_predicted":statistics.mean(z["tail6"] for z in sr),
          "tail6_observed":statistics.mean(y>=6 for y in actual),
          "crps_minus_m0":statistics.mean(z["crps"]-b["crps"]
                  for z,b in zip(sr,[r["scores"]["M0"] for r in rows])),
          "nll_minus_m0":statistics.mean(z["nll"]-b["nll"]
                  for z,b in zip(sr,[r["scores"]["M0"] for r in rows]))}
    return out

def bootstrap_dates(rows, model, metric, seed=20261114, reps=1000):
    by=collections.defaultdict(list)
    for row in rows:
        by[row["date"]].append(row["scores"][model][metric]-row["scores"]["M0"][metric])
    ds=sorted(by)
    if len(ds)<2:return None
    means=[statistics.mean(by[d]) for d in ds]
    rng=random.Random(seed)
    simulated=sorted(statistics.mean(rng.choices(means,k=len(means))) for _ in range(reps))
    return {"date_equal_delta":statistics.mean(means),
            "ci95_descriptive":[simulated[int(.025*(reps-1))],simulated[int(.975*(reps-1))]],
            "dates":len(ds),"method":"paired_date_cluster_bootstrap_exploratory"}

def atomic_new(path,body):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("xb") as f:f.write(body)
    return sha(body)

def run(observation_path,schedule_path,output_root,config,code_sha="uncommitted"):
    observations,obs_hash=read_jsonl(observation_path)
    events,event_hash=read_jsonl(schedule_path)
    schedule,by_player,source_rejects=parse_sources(observations,events)
    first,last=config["evaluation_start"],config["evaluation_end"]
    if not first<=last or not config["historical_only"] or config.get("market_replay") is not False:
        raise ReplayBlocked("RESEARCH_CONFIGURATION_INVALID")
    candidates=[];abstain=collections.Counter();feature_by_date={}
    game_list=sorted((x for x in schedule.values() if first<=x["game_date"]<=last),
                    key=lambda x:(x["_start"],x["game_id"]))
    # SCHEDULE is independent of target player SOG/TOI. Prior-only roster construction.
    for event in game_list:
        cutoff=event["_start"]-dt.timedelta(minutes=60)
        day=event["game_date"];key=day
        # First scheduled start for each day establishes a common conservative
        # source cutoff; later games cannot acquire outcomes from same-day play.
        if key not in feature_by_date:feature_by_date[key]=histories_as_of(by_player,cutoff,day)
        hist=feature_by_date[key]
        for team in event["teams"]:
            for pid,h in sorted(hist.items()):
                lastobs=h[-1]
                if lastobs["team"]!=team:continue
                age=(dt.date.fromisoformat(day)-dt.date.fromisoformat(lastobs["game_date"])).days
                if age>MAX_PERSIST_DAYS:continue
                candidates.append({"game_id":event["game_id"],"date":day,"season":event["season"],
                                   "cutoff":cutoff,"player_id":pid,"team":team,"history":hist})
    selected=[];forcast_reasons=collections.Counter()
    for c in candidates:
        try:
            model,info=build_params(c["player_id"],c["history"])
            if info["hist_team"]!=c["team"]:raise ReplayBlocked("HISTORICAL_TEAM_MISMATCH")
            if utc(info["last_feature_release_bound"])>=c["cutoff"]:
                raise ReplayBlocked("CUT_OFF_VIOLATION")
            distributions=pmfs(model)
            selected.append({"experiment_id":EXPERIMENT_ID,"game_id":c["game_id"],
                "date":c["date"],"season":c["season"],"player_id":c["player_id"],
                "team":c["team"],"cutoff_utc":c["cutoff"].isoformat(),
                "model_ids":list(MODEL_IDS),"source_classification":SCHEMA,
                "fit":info,"distribution_params":model,
                "count_pmfs":distributions})
        except (ReplayBlocked,frozen.ExperimentBlocked,ValueError) as exc:
            forcast_reasons[str(exc)]+=1
    # Outcome counts and labels are not in any selected forecast object or PMF.
    identity={(r["game_id"],r["player_id"]) for r in selected}
    if len(identity)!=len(selected):raise ReplayBlocked("DUPLICATE_FORECAST")
    config_hash=sha(canonical(config))
    stable_manifest={"schema":"phase5_frozen_research_manifest_v1",
        "experiment_id":EXPERIMENT_ID,"code_sha":code_sha,
        "obs_input_sha256":obs_hash,"schedule_input_sha256":event_hash,
        "config_sha256":config_hash,"model_implementation":"v2.nhl_sog_exposure_shadow frozen main",
        "model_ids":MODEL_IDS,"retrospective_source_possession_only":True,
        "no_pregame_source_certification":True,"no_original_book_quotes":True,
        "no_prospective_inference_or_production":True,
        "game_candidates":len(game_list),"candidate_player_games":len(candidates),
        "forecast_count":len(selected),"abstention_reasons":dict(forcast_reasons),
        "raw_source_rejects":dict(source_rejects)}
    run_id=sha(canonical(stable_manifest))[:20]
    root=Path(output_root)/run_id
    if root.exists():raise ReplayBlocked("IMMUTABLE_RUN_ALREADY_EXISTS")
    output=b"".join(canonical(s)+b"\n" for s in selected)
    manbytes=canonical(stable_manifest)
    atomic_new(root/"manifest.json",manbytes)
    forecast_sha=atomic_new(root/"sealed_forecasts.jsonl",output)
    # ONLY NOW join the historical played-game outcome vault for D1.
    target={(r["game_id"],r["player_id"]):r for x in by_player.values() for r in x}
    scores=[];unscored=collections.Counter()
    for s in selected:
        yrow=target.get((s["game_id"],s["player_id"]))
        if yrow is None:
            unscored["NOT_IN_OFFICIAL_PLAYED_GAME_LOG_DNP_OR_MISSING"]+=1
            continue
        y=yrow["sog"];m={}
        for mid,p in s["count_pmfs"].items():
            z=distribution_score(p,y,s["distribution_params"],mid)
            z["variance"]=math.fsum((k-z["mean"])**2*v for k,v in enumerate(p))
            key=sha(canonical([s["game_id"],s["player_id"],mid]))
            rnd=random.Random(int(key[:16],16)).random()
            z["pit"]=z.pop("_cdf_left")+rnd*z.pop("_pmf_at_y")
            m[mid]=z
        scores.append({"date":s["date"],"season":s["season"],"game_id":s["game_id"],
            "player_id":s["player_id"],"group":s["fit"]["hist_role"],
            "hist_toi":s["fit"]["hist_toi"],"toi_sd":s["fit"]["toi_sd"],
            "hist_n":s["fit"]["own_n"],"forecast_sog":s["fit"]["expected_sog"],
            "actual_sog":y,"actual_toi":yrow["toi_minutes"],"scores":m})
    def groupby(fn):
        d=collections.defaultdict(list)
        for r in scores:d[fn(r)].append(r)
        return {str(k):summarize(v) for k,v in sorted(d.items())}
    groupings={
      "season":groupby(lambda r:r["season"]),
      "role":groupby(lambda r:r["group"]),
      "historical_toi":groupby(lambda r:"low_<13" if r["hist_toi"]<13 else "moderate_13_to_20" if r["hist_toi"]<20 else "high_20_plus"),
      "expected_sog":groupby(lambda r:"low_<1.5" if r["forecast_sog"]<1.5 else "moderate_1.5_to_3.5" if r["forecast_sog"]<3.5 else "high_3.5_plus"),
      "history_games":groupby(lambda r:"5_to_9" if r["hist_n"]<10 else "10_to_19" if r["hist_n"]<20 else "20"),
      "opportunity_volatility":groupby(lambda r:"stable_<3min" if r["toi_sd"]<3 else "volatile_3min_plus"),
      "observed_tail":groupby(lambda r:"y>=6" if r["actual_sog"]>=6 else "y<6"),
      "expected_zero":groupby(lambda r:"p0>=0.25" if r["scores"]["M3"]["zero"]>=0.25 else "p0<0.25")}
    full=summarize(scores)
    uncertainty={mid:{metric:bootstrap_dates(scores,mid,metric)
        for metric in ("crps","nll")} for mid in MODEL_IDS if mid!="M0"}
    report={"experiment_id":EXPERIMENT_ID,"status":"EXPLORATORY_EVENT_TIME_ONLY",
       "run_id":run_id,"forecast_sha256":forecast_sha,"manifest_sha256":sha(manbytes),
       "source_seasons":sorted(set(r["season"] for r in observations)),
       "source_obs":len(observations),"source_players":len(by_player),
       "schedule_games":len(schedule),"candidate_games":len(game_list),
       "candidate_player_games":len(candidates),"matched_played":len(scores),
       "forecasted":len(selected),"unscored_forecasts":dict(unscored),
       "forecast_abstentions":dict(forcast_reasons),"source_rejects":dict(source_rejects),
       "overall":full,"groupings":groupings,"clustered_uncertainty":uncertainty,
       "D2_original_line":"NOT_EXECUTABLE_NO_AUTHENTIC_HISTORICAL_QUOTES",
       "source_label":"retrospective event-time reconstruction, not certified as-of",
       "eligibility":"last confirmed team appearance <=21d before target game; no target results",
       "feature_rule":"strict prior game date and prior start+8h before target start-60min",
       "original_source_capture_does_not_precede_historical_games":True,
       "model_selection_inference":"exploratory only; no candidate promotion"}
    receipt=atomic_new(root/"score_report.json",canonical(report))
    atomic_new(root/"scored_played.jsonl",b"".join(canonical(s)+b"\n" for s in scores))
    report["score_report_sha256"]=receipt
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--observations",required=True);ap.add_argument("--schedule",required=True)
    ap.add_argument("--output-root",required=True);ap.add_argument("--config",required=True)
    ap.add_argument("--code-sha",default="uncommitted")
    args=ap.parse_args()
    cfg=json.loads(Path(args.config).read_bytes())
    print(json.dumps(run(args.observations,args.schedule,args.output_root,cfg,args.code_sha),
                     sort_keys=True,allow_nan=False))
if __name__=="__main__":main()
