#!/usr/bin/env python3
"""2016–2025 all-NFL-volume week-frozen, cross-market prequential research.

13 markets: 11 original NFL volume markets plus QB rushing attempts/yards.
The joint challenger transmits one shared simulated team pass/rush opportunity
vector to QB, targets, catches, yards, RB carries, and QB scramble allocation.
A frozen separate player-historical control uses the SAME player/line universe.
All probabilities are postprocessed by a strictly earlier-week Bayesian
binomial calibration of market and role bins. This is NOT authentic historical
sportsbook backtesting; sources are retrospectively downloaded in 2026.
"""
from __future__ import annotations
import argparse,collections,datetime,gzip,hashlib,json,math,pathlib,subprocess,sys
from zoneinfo import ZoneInfo
import numpy as np
from v25_decade_joint_opportunity import (
    OpportunityModel,normalise_player_source,MARKETS as BASE_MARKETS, GROUPS, DEFENSE,
    seed_for
)
from v25_decade_qb_components import QBRushComponentModel,digest as qb_digest

HERE=pathlib.Path(__file__).resolve().parent
SCHEMA="nfl_2016_2025_all13_cross_market_prequential_v1"
EXPERIMENT="EXP_NFL_DECADE_2016_2025_ALL13_PREQUENTIAL_V1"
EXTRA=("qb rushing attempts","qb rushing yards")
MARKETS=tuple(BASE_MARKETS)+EXTRA
QB_EXTRAS={"qb rushing attempts":"carries","qb rushing yards":"rushing yards"}
ROLE_GROUPS={**GROUPS,"QB":tuple(GROUPS["QB"])+EXTRA}
MODELS=("shared_opportunity","player_history")
CALIB_PRIOR_MARKET=36.
CALIB_PRIOR_ROLE=32.
CALIB_DISCOUNT=0.995
ROLLED_YEARS=3
SOURCE_CAPTURE_VERIFIED=False


def require(ok,why):
    if not ok:raise ValueError("DECADE_PREQUENTIAL_REJECTED:"+why)


def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),default=str,
                      allow_nan=False).encode("utf8")


def sha_bytes(raw):return hashlib.sha256(raw).hexdigest()
def sha_file(path):return sha_bytes(pathlib.Path(path).read_bytes())
def read(path):
    raw=pathlib.Path(path).read_bytes()
    if str(path).endswith(".gz"):raw=gzip.decompress(raw)
    return json.loads(raw)


def freeze(path,record):
    path=pathlib.Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    payload=canonical(record)
    payload=(gzip.compress(payload,mtime=0) if path.suffix==".gz"
             else payload+b"\n")
    with path.open("xb") as f:f.write(payload)
    return sha_bytes(payload)


def yearweek_before(r,year,week):
    return r["season"]<year or (r["season"]==year and r["week"]<week)


def asof_depth(year,week,schedule,depth):
    """Never use game-week depth when no provider publication time exists."""
    byteam=collections.defaultdict(list)
    if year<2025:
        for r in depth:
            if r.get("depth_position")!="QB" or str(r.get("depth_team"))!="1":continue
            w=r.get("week")
            if type(w) is not int or not 1<=w<week:continue
            if week-w>2:continue
            team,player=r.get("club_code"),r.get("gsis_id")
            if isinstance(team,str) and isinstance(player,str) and player:
                byteam[team].append((w,player))
    else:
        for r in depth:
            if r.get("pos_abb")!="QB" or r.get("pos_rank")!=1:continue
            team,player=r.get("team"),r.get("gsis_id")
            try:t=datetime.datetime.fromisoformat(r["dt"].replace("Z","+00:00"))
            except (ValueError,TypeError,KeyError):continue
            if t.tzinfo is None or not team or not player:continue
            byteam[team].append((t.astimezone(datetime.timezone.utc),player))
    choices={}
    for g in schedule:
        if g["week"]!=week:continue
        for team in (g["home_team"],g["away_team"]):
            key=(g["game_id"],team)
            require(key not in choices,"duplicate_depth_game_team")
            if year<2025:
                pool=byteam.get(team,[])
                stamp=max((x[0] for x in pool),default=None)
            else:
                local=datetime.datetime.fromisoformat(str(g["gameday"])+"T"+str(g["gametime"]))
                cutoff=(local.replace(tzinfo=ZoneInfo("America/New_York"))
                        .astimezone(datetime.timezone.utc)
                        -datetime.timedelta(hours=2))
                pool=[x for x in byteam.get(team,[]) if x[0]<=cutoff
                      and cutoff-x[0]<=datetime.timedelta(days=10)]
                stamp=max((x[0] for x in pool),default=None)
            ids={pid for t,pid in pool if t==stamp}
            pid=next(iter(ids)) if len(ids)==1 else None
            choices[key]={"player_id":pid,
                "reason":None if pid else "no_unique_qualified_prior_QB1",
                "depth_source_time_or_week":str(stamp) if stamp is not None else None,
                "original_historical_pregame_capture_verified":False,
                "confirmed_live_starter":False}
    require(len(choices)==2*len([g for g in schedule if g["week"]==week]),
            "missing_scheduled_team_game_QB1_records")
    return choices


def select_games(schedule,week):
    result=[]
    for g in schedule:
        if g["week"]!=week:continue
        require(g["home_team"]!=g["away_team"],"same_team_game")
        for team,opp in ((g["home_team"],g["away_team"]),
                         (g["away_team"],g["home_team"])):
            result.append({"game_id":g["game_id"],"team":team,"opponent":opp,
                           "week":week})
    return result


def candidate_markets(role):
    return ROLE_GROUPS.get(role,tuple(BASE_MARKETS[8:]) if role in DEFENSE else ())


def sample_crps(values,obs):
    """Empirical proper count CRPS with O(n log n) pairwise term."""
    a=np.asarray(values,dtype=float)
    a=np.sort(a)
    n=len(a)
    return float(np.mean(np.abs(a-obs))-
           np.dot(2*np.arange(n)-n+1,a)/(n*n))


def model_offer(draws,line):
    if draws is None:return None
    arr=np.asarray(draws,dtype=float)
    require(len(arr)>=64 and np.all(np.isfinite(arr)),"forecast_draws_not_finite")
    higher=int(np.count_nonzero(arr>line))
    q=(higher+.5)/(len(arr)+1.)  # no mechanical 0%/100%
    return {"q_over_raw":float(q),"mean":float(np.mean(arr)),
        "variance":float(np.var(arr)),"draws":arr.tolist(),
        "zero_probability":float(np.mean(arr==0)),
        "n_draws":len(arr),"confidence_exact_zero_one_prevented":True}


def child_forecast(packet,*,samples=128,seed=20162025):
    required={"schema","experiment","season","week","history",
              "pbp_prior","games","qb1","calibration_preimage",
              "source_capture_certified","no_current_game_outcomes"}
    require(set(packet)==required,"unregistered_child_input")
    require(packet["schema"]==SCHEMA and packet["experiment"]==EXPERIMENT,
            "wrong_experiment_input")
    require(packet["source_capture_certified"] is False and
            packet["no_current_game_outcomes"] is True,
            "source_truth_or_current_game_in_child")
    year=packet["season"];week=packet["week"]
    require(2016<=year<=2025 and 1<=week<=18,"out_of_scope_calendar")
    hist=packet["history"];pbp=packet["pbp_prior"]
    require(hist and pbp and all(yearweek_before(x,year,week) for x in hist) and
            all(yearweek_before(x,year,week) for x in pbp),
            "current_or_future_week_leak_in_predictor")
    require(type(samples) is int and 64<=samples<=1024,"bad_samples")
    model=OpportunityModel(hist,week,forecast_season=year)
    run_types=QBRushComponentModel(pbp,forecast_year=year,forecast_week=week)
    offers=[];excluded=collections.Counter()
    selection=packet["qb1"]
    shared_allocation_checks=0
    for g in packet["games"]:
        team=g["team"];event=g["game_id"];opponent=g["opponent"]
        qb1=selection.get(event+"|"+team)
        require(qb1 is not None,"qb1_source_gate_missing")
        if team not in model.byteam:
            excluded["team_prior_unavailable"]+=1;continue
        result=model.forecast_team(team,event,n=samples,
              seed=seed_for(seed,year,week,event,team))
        require(result["conservation_ok"] is True,"joint_market_volume_allocation_failed")
        shared_allocation_checks+=1
        allowed=set(model.candidates(team))
        for pid,role in sorted(model.candidates(team).items()):
            markets=candidate_markets(role)
            for market in markets:
                if role=="QB" and pid!=qb1["player_id"]:
                    excluded["QB_backup_or_no_qualified_prior_QB1"]+=1
                    continue
                source=QB_EXTRAS.get(market,market)
                historical=model._player_rows(pid,source)
                if not historical:
                    excluded["player_stat_history_unavailable"]+=1
                    continue
                # Same offered synthetic player/line for both models; only
                # earlier appearance history is used to choose the line.
                numbers=[p["values"][source] for _,p in historical]
                line=math.floor(float(np.median(numbers[-8:])))+.5
                x=result["draws"].get(pid,{}).get(market)
                simple=result["simple_control"].get(pid,{}).get(market)
                component_meta=None
                if market in EXTRA and role=="QB":
                    team_pass=np.asarray(result["team_pass_attempts"],dtype=float)
                    p=run_types._params(pid)
                    pass_rows=model._player_rows(pid,"pass attempts")
                    passer_mean=float(np.mean([p_["values"]["pass attempts"]
                                               for _,p_ in pass_rows])) if pass_rows else float(np.mean(team_pass))
                    factor=float(np.clip(p["dropback_mu"]/max(1.,passer_mean),.75,1.6))
                    # Same simulated passing workload informs scramble chances.
                    shared_drop=np.rint(team_pass*factor).astype(np.int64)
                    special=run_types.draw(pid,n=samples,
                        seed=seed_for(seed,year,week,event,team,pid,"qbtype"),
                        dropback_samples=shared_drop)
                    x=np.asarray(special["qb_rushing_attempts" if
                          market=="qb rushing attempts" else "qb_rushing_yards"],dtype=float)
                    simple=model.independent(team,pid,"QB",source,
                          np.random.default_rng(seed_for(seed,year,week,event,team,pid,market,"prior")),
                          samples)
                    component_meta={"shares_team_pass_workload":True,
                      "types":tuple(special["counts"]),
                      "raw_source_reconciled":True,
                      "cold_start":special["QB_cold_start_no_prior_games"]}
                mm={"shared_opportunity":model_offer(x,line),
                    "player_history":model_offer(simple,line)}
                if all(v is None for v in mm.values()):
                    excluded["both_models_abstained"]+=1;continue
                offers.append({"season":year,"week":week,"game_id":event,
                    "team":team,"opponent":opponent,"player_id":pid,
                    "role":role,"market":market,"line":line,
                    "line_policy":"own_prior_eight_appearance_median_plus_half",
                    "current_participation_verified":False,
                    "depth_is_not_confirmed_starter":role=="QB",
                    "original_pregame_source_capture_verified":False,
                    "component_meta":component_meta,
                    "forecast_models":mm})
    unique={(r["game_id"],r["team"],r["player_id"],r["market"],r["line"])
            for r in offers}
    require(len(unique)==len(offers),"duplicated_original_offer")
    return {"schema":SCHEMA,"season":year,"week":week,
        "input_sha256":sha_bytes(canonical(packet)),
        "n_source_game_teams":len(packet["games"]),
        "n_shared_team_volume_allocations":shared_allocation_checks,
        "models":MODELS,"markets":MARKETS,
        "offers":offers,"abstentions":dict(excluded),
        "forecasts_did_not_see_current_week_scores":True,
        "original_pregame_provider_publication_certified":False,
        "production_authorized":False,"tiers_authorized":False}


class OnlineCalibrator:
    """Prior-market/role-bin Bayesian calibration updated AFTER weekly score.

    Calibrate outcome probability without backfitting finished games to
    themselves. Market-wide bins share experience with role bins; separate
    models remain independent. Recency discount at season/week boundaries.
    """
    def __init__(self):self.stats={}
    @staticmethod
    def key(model,market,role,bin_):
        return "|".join((model,market,role,str(bin_)))
    def apply(self,model,market,role,p):
        b=min(9,max(0,int(10*p)))
        g=self.stats.get(self.key(model,market,"GLOBAL",b),[0.,0.])
        r=self.stats.get(self.key(model,market,role,b),[0.,0.])
        middle=(CALIB_PRIOR_MARKET*p+g[1])/(CALIB_PRIOR_MARKET+g[0])
        return float(np.clip((CALIB_PRIOR_ROLE*middle+r[1])/
                            (CALIB_PRIOR_ROLE+r[0]),1e-6,1-1e-6))
    def train_after_week(self,observations):
        # No outcomes from week being forecast appear before this call.
        for name,v in list(self.stats.items()):
            self.stats[name]=[v[0]*CALIB_DISCOUNT,v[1]*CALIB_DISCOUNT]
        for item in observations:
            model,market,role,p,y=item
            b=min(9,max(0,int(10*p)))
            for str_role in ("GLOBAL",role):
                key=self.key(model,market,str_role,b)
                s=self.stats.setdefault(key,[0.,0.])
                s[0]+=1.;s[1]+=y
    def receipt(self):
        return {"schema":"online_calibrator_market_and_role_bins_v1",
          "prior_market":CALIB_PRIOR_MARKET,"prior_role":CALIB_PRIOR_ROLE,
          "weekly_discount":CALIB_DISCOUNT,
          "state":self.stats}


def settle(pred,actual,cal):
    """Score strictly AFTER immutable weekly forecast SHA is recorded."""
    oracle={(g["event_id"],g["team"]):g for g in actual}
    out=[];updated=[]
    coverage=collections.Counter()
    for f in pred["offers"]:
        g=oracle.get((f["game_id"],f["team"]))
        if g is None or f["player_id"] not in g["players"]:
            out.append({"key":(f["game_id"],f["team"],f["player_id"],f["market"]),
                        "status":"no_original_player_observation_not_imputed"})
            coverage["no_original_player_observation_not_imputed"]+=1
            continue
        p=g["players"][f["player_id"]]
        if f["market"] in EXTRA:
            truth=p["values"].get(QB_EXTRAS[f["market"]])
        else:
            truth=p["values"].get(f["market"])
        if truth is None:
            coverage["market_stat_unavailable"]+=1
            out.append({"key":(f["game_id"],f["team"],f["player_id"],f["market"]),
                        "status":"market_stat_unavailable"})
            continue
        y=int(truth>f["line"])
        result={"season":f["season"],"week":f["week"],
            "game_id":f["game_id"],"team":f["team"],"player_id":f["player_id"],
            "role":f["role"],"market":f["market"],"line":f["line"],
            "actual":truth,"observed_over":y,"model_scores":{},
            "status":"scored_as_same_contract"}
        for name,offer in f["forecast_models"].items():
            if offer is None:continue
            p_raw=offer["q_over_raw"]
            p_cal=cal.apply(name,f["market"],f["role"],p_raw)
            draws=offer["draws"]
            result["model_scores"][name]={
                "p_over_raw":p_raw,"p_over_online":p_cal,
                "brier_raw":(p_raw-y)**2,"brier_online":(p_cal-y)**2,
                "logloss_raw":-math.log(max(1e-12,p_raw if y else 1-p_raw)),
                "logloss_online":-math.log(max(1e-12,p_cal if y else 1-p_cal)),
                "crps":sample_crps(draws,truth),
                "predicted_mean":offer["mean"],
                "mean_residual":offer["mean"]-truth,
                "interval_10_90_covers":float(np.quantile(draws,.1)<=truth<=
                                               np.quantile(draws,.9)),
                "p_zero":offer["zero_probability"],
                "selected_side_correct_raw":int((p_raw>.5)==bool(y)) if p_raw!=.5 else None,
                "selected_side_correct_online":int((p_cal>.5)==bool(y)) if p_cal!=.5 else None,
                }
            updated.append((name,f["market"],f["role"],p_raw,y))
        coverage["scored_contracts"]+=1
        out.append(result)
    return out,updated,dict(coverage)


def summarise(rows):
    summary={}
    for market in MARKETS:
        summary[market]={}
        for model in MODELS:
            exact=[r for r in rows if r.get("status")=="scored_as_same_contract" and
                   r["market"]==market and model in r["model_scores"]]
            if not exact:continue
            d=[r["model_scores"][model] for r in exact];n=len(d)
            pack={"n":n,"games":len({r["game_id"] for r in exact}),
                "brier_raw":float(np.mean([x["brier_raw"] for x in d])),
                "brier_online":float(np.mean([x["brier_online"] for x in d])),
                "logloss_raw":float(np.mean([x["logloss_raw"] for x in d])),
                "logloss_online":float(np.mean([x["logloss_online"] for x in d])),
                "crps":float(np.mean([x["crps"] for x in d])),
                "count_mean_bias":float(np.mean([x["mean_residual"] for x in d])),
                "interval_10_90_coverage":float(np.mean([x["interval_10_90_covers"] for x in d])),
                "claim_p_over_raw":float(np.mean([x["p_over_raw"] for x in d])),
                "claim_p_over_online":float(np.mean([x["p_over_online"] for x in d])),
                "actual_over_rate":float(np.mean([r["observed_over"] for r in exact]))}
            for variant in ("raw","online"):
                picks=[(r,x) for r,x in zip(exact,d)
                       if max(x[f"p_over_{variant}"],1-x[f"p_over_{variant}"])>=.8]
                pack["conf80_"+variant]={
                   "n":len(picks),
                   "claimed":float(np.mean([max(x[f"p_over_{variant}"],
                        1-x[f"p_over_{variant}"]) for r,x in picks])) if picks else None,
                   "hit":float(np.mean([int((x[f"p_over_{variant}"]>.5)==bool(r["observed_over"]))
                                     for r,x in picks])) if picks else None,
                   "under_n":sum(x[f"p_over_{variant}"]<.5 for r,x in picks)}
            summary[market][model]=pack
        both=[r for r in rows if r.get("status")=="scored_as_same_contract" and
              r["market"]==market and all(x in r["model_scores"] for x in MODELS)]
        if both:
            summary[market]["matched_joint_minus_player"]={
                "n":len(both),
                "brier_raw":float(np.mean([r["model_scores"][MODELS[0]]["brier_raw"]-
                                           r["model_scores"][MODELS[1]]["brier_raw"] for r in both])),
                "brier_online":float(np.mean([r["model_scores"][MODELS[0]]["brier_online"]-
                                           r["model_scores"][MODELS[1]]["brier_online"] for r in both])),
                "crps":float(np.mean([r["model_scores"][MODELS[0]]["crps"]-
                                     r["model_scores"][MODELS[1]]["crps"] for r in both])),
                "games":len({r["game_id"] for r in both})}
    return summary


def validate_sources(root,manifest):
    require(manifest.get("schema")=="NFL_2016_2025_RETROSPECTIVE_WEEKLY_SOURCE_V1",
            "source_manifest_schema_mismatch")
    require(manifest.get("original_historical_pregame_availability_verified") is False,
            "fake_original_source_certification")
    for filename,sha in manifest["source_files"].items():
        require(sha_file(root/filename)==sha,"source_sha_changed:"+filename)
    require(all((root/f"stats_{y}.json.gz").is_file() for y in range(2014,2026)),
            "no_full_initial_training_and_decade_source")


def run(args):
    require(not args.output_dir.exists(),"append_only_output_required")
    spec=read(args.protocol)
    require(spec.get("experiment_id")==EXPERIMENT and
            spec.get("production_authorized") is False and
            spec.get("seasons")==list(range(2016,2026)) and
            spec.get("all_original_volume_markets")==list(BASE_MARKETS) and
            spec.get("qb_rush_extension_markets")==list(EXTRA) and
            spec.get("joint_shared_pass_and_rush_workload") is True,
            "experiment_spec_not_locked")
    n=spec["samples"];seed=spec["seed"]
    require(type(n) is int and 64<=n<=512,"invalid_n_samples")
    source=args.source_root;manifest=read(source/"MANIFEST.json")
    validate_sources(source,manifest)
    pbp={}
    for y in range(2014,2026):
        place=(args.pbp_old if y<=2020 else args.pbp_new)/f"qb_components_{y}.json.gz"
        require(place.exists(),"missing_historical_QB_PBP:"+str(y))
        d=read(place)
        require(d["year"]==y and d["schema"]=="p25_pbp_qb_component_source_v1",
                "QB_PBP_schema_or_year_mismatch")
        pbp[y]=d["rows"]
    allgames={}
    for y in range(2014,2026):
        data=read(source/f"stats_{y}.json.gz")
        require(data["season"]==y,"season_source_file_mismatch")
        rejections=[]
        team_games=normalise_player_source(data["rows"],rejection_ledger=rejections,
               allowed_seasons=tuple(range(2014,2026)))
        allgames[y]=team_games
        # Always preserve data rejections; never turn unknown placeholders into zeros.
    schedules={y:read(source/f"games_{y}.json.gz")["rows"] for y in range(2016,2026)}
    depths={y:read(source/f"qb_depth_{y}.json.gz")["rows"] for y in range(2016,2026)}
    args.output_dir.mkdir(parents=True,exist_ok=False)
    code_dir=args.output_dir/"frozen_code";code_dir.mkdir()
    filenames=("v25_decade_prequential.py","v25_decade_joint_opportunity.py",
               "v25_decade_qb_components.py")
    codehash={}
    for name in filenames:
        raw=(HERE/name).read_bytes();(code_dir/name).write_bytes(raw)
        codehash[name]=sha_bytes(raw)
    receipt={"schema":SCHEMA,"experiment":EXPERIMENT,
        "source_manifest_sha256":sha_file(source/"MANIFEST.json"),
        "all_original_source_sha256":manifest["source_files"],
        "PBP_old_manifest_sha256":sha_file(args.pbp_old/"SOURCE_MANIFEST.json"),
        "PBP_new_manifest_sha256":sha_file(args.pbp_new/"source_manifest.json"),
        "codehash":codehash,"spec_sha256":sha_file(args.protocol),
        "years":spec["seasons"],"markets":list(MARKETS),
        "QB1": "previous_week_depth_only_until_2024_2025_UTC_if_past_kickoff",
        "original_quotes_not_verified":True,"nonproduction":True}
    freeze(args.output_dir/"FROZEN_START_RECEIPT.json",receipt)
    calibration=OnlineCalibrator()
    all_aggregated=[];artifacts=[];coverage=collections.Counter()
    frozen_count=0
    for year in range(2016,2026):
        schedule=schedules[year]
        require(250<=len(schedule)<=272,"unexpected_schedule_games")
        for week in sorted({g["week"] for g in schedule}):
            prev=[g for y in range(max(2014,year-ROLLED_YEARS),year)
                  for g in allgames[y]]
            prev.extend(g for g in allgames[year] if g["week"]<week)
            previous_pbp=[g for y in range(max(2014,year-ROLLED_YEARS),year)
                          for g in pbp[y]]
            previous_pbp.extend(g for g in pbp[year] if g["week"]<week)
            require(all(yearweek_before(g,year,week) for g in prev+previous_pbp),
                    "prior_history_current_game_leak")
            depth=asof_depth(year,week,schedule,depths[year])
            match=select_games(schedule,week)
            original_packet={"schema":SCHEMA,"experiment":EXPERIMENT,"season":year,
                "week":week,"history":prev,"pbp_prior":previous_pbp,
                "games":match,"qb1":{g+"|"+t:v for (g,t),v in depth.items()},
                "calibration_preimage":calibration.receipt(),
                "source_capture_certified":False,"no_current_game_outcomes":True}
            prefix=f"{year}_week_{week:02d}"
            inp=args.output_dir/f"{prefix}_before_outcomes.json.gz"
            pred_path=args.output_dir/f"{prefix}_predictions.json.gz"
            settled_path=args.output_dir/f"{prefix}_settlements.json.gz"
            prior_sha=freeze(inp,original_packet)
            # Fresh worker has NO labels and NO original outcome file args.
            cmd=[sys.executable,str(code_dir/"v25_decade_prequential.py"),
               "forecast","--input",str(inp),"--output",str(pred_path),
               "--samples",str(n),"--seed",str(seed)]
            child=subprocess.run(cmd,cwd=code_dir,text=True,capture_output=True,timeout=220)
            require(child.returncode==0,
                f"forecaster_failed_{year}_week_{week}:"+child.stderr[-2000:])
            pred=read(pred_path)
            require(pred["input_sha256"]==sha_bytes(canonical(original_packet))
                    and pred["season"]==year and pred["week"]==week,
                    "child_forecast_not_bound_to_before_outcomes_input")
            pred_sha=sha_file(pred_path)
            # Reading current-week official labels is only allowed AFTER
            # both input and forecast files have been physically closed.
            truth=[g for g in allgames[year] if g["week"]==week]
            observed,updates,counts=settle(pred,truth,calibration)
            stsha=freeze(settled_path,{"schema":SCHEMA,"year":year,"week":week,
                  "forecast_sha256":pred_sha,"revealed_only_after_freeze":True,
                  "scored":observed,"coverage":counts})
            calibration.train_after_week(updates)
            all_aggregated.extend(observed)
            frozen_count+=1
            for k,v in counts.items():coverage[f"{year}|{k}"]+=v
            artifacts.append({"season":year,"week":week,
                 "preweek_sha256":prior_sha,"forecasts_sha256":pred_sha,
                 "settlement_sha256":stsha,
                 "original_source_game_teams":len(match),
                 "offered_contracts":len(pred["offers"]),
                 "scored_contracts":counts.get("scored_contracts",0),
                 "raw_preweek_calibrator_sha256":sha_bytes(canonical(original_packet["calibration_preimage"]))})
            if week==max({g["week"] for g in schedule}):
                print("DECADE_SEASON_DONE",json.dumps({
                  "year":year,"weeks":week,"season_source_games":len(schedule),
                  "offers":sum(x["offered_contracts"] for x in artifacts if x["season"]==year),
                  "scored":sum(x["scored_contracts"] for x in artifacts if x["season"]==year),
                  "calibration_groups":len(calibration.stats)},sort_keys=True),flush=True)
            elif week in (1,5,10,15):
                print("DECADE_PROGRESS",year,week,"offered",len(pred["offers"]),
                      "scored",counts.get("scored_contracts",0),flush=True)
        yearrows=[r for r in all_aggregated if r.get("season")==year and r.get("status")=="scored_as_same_contract"]
        yreport={"schema":SCHEMA,"season":year,"completed_weeks":len({g["week"] for g in schedule}),
                 "source_games":len(schedule),"offered_contracts":
                       sum(x["offered_contracts"] for x in artifacts if x["season"]==year),
                 "scored_contracts":len(yearrows),"calibration":summarise(yearrows),
                 "model_promotion_allowed":False,"original_bookmaker_prices_available":False}
        freeze(args.output_dir/f"SEASON_{year}_PROPER_SCORES.json",yreport)
    final={"schema":SCHEMA,"experiment":EXPERIMENT,
        "status":"COMPLETE_RESEARCH_ONLY","count_of_seasons":10,
        "season_range":[2016,2025],"weekly_forecast_reveal_cycles":frozen_count,
        "all_original_markets":list(BASE_MARKETS),
        "QB_rushing_extension":list(EXTRA),"all_volume_markets_tracked":list(MARKETS),
        "original_real_quote_lines_available":False,
        "original_provider_pregame_capture_certified":False,
        "histories_development_exposed":True,
        "production_allowed":False,"tiers_allowed":False,
        "joint_crossmarket_team_pass_rush_volume":True,
        "QB_scramble_uses_shared_team_pass_volume":True,
        "weekly_and_season_source_archive":artifacts,
        "source_receipt":receipt,"total_offered":sum(a["offered_contracts"] for a in artifacts),
        "total_scored":sum(a["scored_contracts"] for a in artifacts),
        "season_summaries":{},
        "all_seasons_proper_scores":summarise(all_aggregated)}
    for y in range(2016,2026):
        doc=read(args.output_dir/f"SEASON_{y}_PROPER_SCORES.json")
        final["season_summaries"][str(y)]={"scored":doc["scored_contracts"],
                    "offered":doc["offered_contracts"],"markets":doc["calibration"]}
    final["result_sha256"]=sha_bytes(canonical(final))
    freeze(args.output_dir/"FINAL_2016_2025_RESEARCH_REPORT.json",final)
    print("DECADE_PREQUENTIAL_COMPLETE",json.dumps({
        "cycles":frozen_count,"offered":final["total_offered"],
        "scored":final["total_scored"],"receipt":final["result_sha256"],
        "market_names":list(MARKETS),"no_production_promotion":True},sort_keys=True),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="action",required=True)
    f=sub.add_parser("forecast")
    f.add_argument("--input",required=True,type=pathlib.Path)
    f.add_argument("--output",required=True,type=pathlib.Path)
    f.add_argument("--samples",type=int,required=True)
    f.add_argument("--seed",type=int,required=True)
    r=sub.add_parser("run")
    for v in ("source-root","pbp-old","pbp-new","protocol","output-dir"):
        r.add_argument("--"+v,required=True,type=pathlib.Path)
    a=p.parse_args()
    if a.action=="forecast":
        freeze(a.output,child_forecast(read(a.input),samples=a.samples,seed=a.seed))
    else:run(a)


if __name__=="__main__":
    main()
