#!/usr/bin/env python3
"""Replay 2024 THEN 2025 QB1 rushing decompositions under strict as-of packets.

Research-only two-season retrospective. Not originally published pregame odds;
the 2024 depth source has WEEK timestamps, so only prior-week QB1 is used.
The 2025 QB1 selection and both original research lines are read unmodified
from the pre-existing frozen 2025 archived experiment.

Every week's forecast is written by an independent subprocess before its
official outcomes are imported into that week's settlement. Code, inputs,
source hashes, comparisons and declined candidate denominators are immutable.
"""
from __future__ import annotations
import argparse,collections,datetime,hashlib,json,math,pathlib,subprocess,sys
import numpy as np
from v25_qb_rush_components import QBRushComponentModel,SCHEMA as COMPONENT_SCHEMA,digest,require,ComponentModelError,seed_from
from v25_opportunity_distribution import OpportunityModel,normalise_player_source
from v25_opportunity_repair_replay import read,write_once,file_hash,sample_score,probability_score,metrics,paired
from v25_opportunity_2025_replay import game_paired

HERE=pathlib.Path(__file__).resolve().parent
SCHEMA="v25_nfl_qb_rush_types_2024_2025_retrospective_replay_v1"
EXPERIMENT="EXP_NFL_QB_RUSH_SCRAMBLE_DESIGNED_KNEEL_2024_2025_V1"
MARKETS={"qb rushing attempts":"carries","qb rushing yards":"rushing yards"}
NAMES={"qb rushing attempts":"qb_rushing_attempts","qb rushing yards":"qb_rushing_yards"}
MODELS=("component_types","historic_player_prior")


def fail(m):
    raise RuntimeError("QB_COMPONENT_REPLAY_FAILED:"+m)


def must(ok,m):
    if not ok:fail(m)


def sha_file(f):return hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest()


def source_files(root,manifest):
    must(manifest.get("schema")=="nfl_qb_run_type_2024_2025_frozen_research_sources_v1",
         "wrong_research_PBP_manifest")
    must(manifest.get("original_pregame_publication_certified") is False,
         "retrospective_data_misrepresented_as_original_pregame")
    sources={}
    for y in range(2021,2026):
        file=root/f"qb_components_{y}.json.gz"
        must(file.is_file() and sha_file(file)==manifest["sha256"][f"pbp_{y}"],
             "PBP_source_digest_changed:"+str(y))
        d=read(file)
        must(d.get("schema")=="p25_pbp_qb_component_source_v1" and d["year"]==y,
             "PBP_wrong_season")
        sources[y]=d["rows"]
    for key,filename in (("depth_2024","depth_qb1_2024_lag_only.json.gz"),
                         ("schedule_2024","schedule_2024.json.gz")):
        file=root/filename
        must(file.is_file() and sha_file(file)==manifest["sha256"][key],
             "other_original_source_digest_changed:"+key)
    return sources


def choose_lagged_2024_qb1(depth,schedule):
    """2024 weekly NFLverse depth rows have NO actual publish UTC.

    Use strictly earlier-week depth for a conservative research proxy, not
    same-week rows whose original pregame availability is unknown.
    """
    depth_by=collections.defaultdict(list)
    for r in depth:
        if (r.get("season")!=2024 or r.get("depth_position")!="QB"
                or str(r.get("depth_team"))!="1"):continue
        if r.get("week") not in range(1,19):continue
        if not r.get("gsis_id") or not r.get("club_code"):continue
        depth_by[r["club_code"]].append((int(r["week"]),str(r["gsis_id"])))
    chosen=[];seen=set()
    for g in sorted(schedule,key=lambda r:(r["week"],r["game_id"])):
        must(g.get("season")==2024 and g.get("game_type")=="REG",
             "2024_schedule_season_or_type_wrong")
        week=int(g["week"])
        for team,opponent in ((g["home_team"],g["away_team"]),
                              (g["away_team"],g["home_team"])):
            key=(g["game_id"],team)
            must(key not in seen,"2024_duplicate_team_game")
            seen.add(key)
            recent=[(w,p) for w,p in depth_by.get(team,())
                    if w<week and (week-w)<=2]
            srcweek=max((w for w,p in recent),default=None)
            ids={p for w,p in recent if w==srcweek}
            pid=next(iter(ids)) if len(ids)==1 else None
            reason=None if pid else "no_unique_prior_week_depth_QB1"
            chosen.append({"game_id":g["game_id"],"team":team,"opponent":opponent,
              "week":week,"player_id":pid,"reason":reason,
              "source_qualified_asof_week":srcweek,
              "source_semantics":"lagged_2024_weekly_QB1_research_proxy",
              "actual_original_pregame_release_time_known":False,
              "is_confirmed_starter":False})
    must(len(chosen)==544 and len(seen)==544,"missing_2024_team_game")
    return chosen


def read_original_2025_qb1(frozen):
    payload=read(frozen/"SOURCE_QB1_ASOF_SELECTION.json.gz")
    selected=[]
    for row in payload["selected"]:
        must(row["is_authoritative_starter_confirmation"] is False and
             row["original_pregame_capture_verified"] is False,
             "original_QB1_depth_verification_overstated")
        selected.append({"game_id":row["event_id"],"team":row["team"],
             "opponent":row["opponent"],"week":row["week"],
             "player_id":row["player_id"],"reason":row["reason"],
             "source_qualified_asof_week":None,
             "source_dated_at":row["source_dated_at"],
             "source_semantics":"dated_2025_QB1_from_unmodified_prior_frozen_replay",
             "actual_original_pregame_release_time_known":False,
             "is_confirmed_starter":False})
    must(len(selected)==544 and len({(r["game_id"],r["team"]) for r in selected})==544,
         "original_2025_QB1_source_coverage_changed")
    return selected


def create_packet(year,week,history,pbp,selection,old_2025_forecasts):
    must(year in (2024,2025) and 1<=week<=18,"year_week_invalid")
    must(all(g["season"]<year or (g["season"]==year and g["week"]<week)
             for g in history),"future_or_current_player_stats_leak")
    must(all(g["season"]<year or (g["season"]==year and g["week"]<week)
             for g in pbp),"future_or_current_PBP_leak")
    slate=[g for g in selection if g["week"]==week]
    must(len(slate)>0,"empty_schedule_week")
    if year==2025:
        must(isinstance(old_2025_forecasts,dict),"missing_pre_frozen_2025_predictions")
    eligible=[]
    abstain=[]
    # Construct the SYNTHETIC target line from precisely earlier player game
    # records, except 2025 which MUST reuse original archived lines verbatim.
    byid=collections.defaultdict(list)
    for g in history:
        for pid,p in g["players"].items():
            if p["role"]=="QB":
                byid[pid].append((g["season"],g["week"],p["values"]))
    for row in slate:
        pid=row["player_id"]
        if not pid:
            abstain.append({**row,"reason":row["reason"] or "qb1_source_missing"})
            continue
        for market,col in MARKETS.items():
            original_key=(row["game_id"],row["team"],pid,market)
            old=old_2025_forecasts.get(original_key) if year==2025 else None
            if year==2025 and old is None:
                abstain.append({**row,"market":market,"reason":"not_in_original_frozen_2025_offer_universe"})
                continue
            if year==2024:
                past=[x[col] for s,w,x in byid.get(pid,[]) if col in x]
                if not past:
                    abstain.append({**row,"market":market,"reason":"QB1_no_prior_2024_offered_line"})
                    continue
                line=math.floor(float(np.median(past[-8:])))+.5
                historical=None
            else:
                line=float(old["research_line"])
                must(old["player_id"]==pid and old["team"]==row["team"]
                     and old["market"]==market and old["depth_chart_qb1"] is True,
                     "2025_original_eligible_contract_identity_changed")
                historical=old["draws"]["expanding"]
                must(historical is not None,"missing_frozen_2025_control_draws")
            eligible.append({**row,"market":market,"source_stat":col,
                "line":line,"frozen_2025_original_control_draws":historical,
                "old_2025_original_offer_provided":year==2025})
    need={(g["game_id"],g["team"],g["player_id"],g["market"]) for g in eligible}
    must(len(need)==len(eligible),"duplicate_QB_offered_contract")
    return {"schema":SCHEMA,"year":year,"week":week,
        "historical_player_stats_only":history,
        "historical_component_PBP_only":pbp,
        "source_qualified_QB1_candidates":eligible,
        "original_abstentions":abstain,
        "oracle_and_current_week_labels_excluded":True,
        "synthetic_lines_not_original_sportsbook":True,
        "production_allowed":False}


def forecast_child(packet,n,seed):
    must(set(packet)=={"schema","year","week","historical_player_stats_only",
        "historical_component_PBP_only","source_qualified_QB1_candidates",
        "original_abstentions","oracle_and_current_week_labels_excluded",
        "synthetic_lines_not_original_sportsbook","production_allowed"},
        "unregistered_current_week_child_input_field")
    must(packet["schema"]==SCHEMA and packet["oracle_and_current_week_labels_excluded"] is True
         and packet["production_allowed"] is False,"wrong_forecast_packet")
    year=packet["year"];week=packet["week"]
    must(all(g["season"]<year or (g["season"]==year and g["week"]<week)
             for g in packet["historical_player_stats_only"]),"current_week_stats_leak")
    must(all(g["season"]<year or (g["season"]==year and g["week"]<week)
             for g in packet["historical_component_PBP_only"]),"current_week_PBP_leak")
    components=QBRushComponentModel(packet["historical_component_PBP_only"],
             forecast_year=year,forecast_week=week)
    baseline=(OpportunityModel(packet["historical_player_stats_only"],week,forecast_season=year)
              if year==2024 else None)
    # Joint draws for a QB are generated ONCE and shared by attempts and
    # yards, preserving the physical interpretation of run components.
    cache={};outputs=[]
    for c in packet["source_qualified_QB1_candidates"]:
        key=(c["game_id"],c["team"],c["player_id"])
        if key not in cache:
            cache[key]=components.draw(c["player_id"],n=n,seed=seed_from(
                seed,year,week,c["game_id"],c["team"],c["player_id"]))
        sampled=cache[key]
        if sampled is None:continue
        forecast=sampled[NAMES[c["market"]]]
        if year==2024:
            baseline_seed=seed_from(seed,year,week,c["game_id"],c["team"],c["player_id"],c["market"],"baseline")
            x=baseline.independent(c["team"],c["player_id"],"QB",c["source_stat"],
                      np.random.default_rng(baseline_seed),n)
            old=x.tolist() if x is not None else None
        else:
            old=c["frozen_2025_original_control_draws"]
        outputs.append({"season":year,"week":week,"game_id":c["game_id"],
            "team":c["team"],"player_id":c["player_id"],"role":"QB",
            "market":c["market"],"source_stat":c["source_stat"],
            "research_line":c["line"],"source_semantics":c["source_semantics"],
            "proven_original_2024_2025_pregame_starter":False,
            "original_historical_line":year==2025,
            "draws":{"component_types":forecast,"historic_player_prior":old},
            "component_counts":sampled["counts"],
            "component_yards":sampled["type_yards"],
            "posterior_summary":sampled["parameters"],
            "source_training_receipt":sampled["source_reconciliation"],
            "cold_start":sampled["QB_cold_start_no_prior_games"],
            "production_authorized":False})
    return {"schema":SCHEMA,"year":year,"week":week,
        "input_sha256":digest(packet),
        "forecasted_contracts":outputs,"abstentions":packet["original_abstentions"],
        "unique_QB1_only":True,"only_past_PBP_used":True,
        "promotable":False}


def _score_forecast(f,oracle):
    key=(f["game_id"],f["team"],f["player_id"])
    current=oracle.get(key)
    if current is None:
        return {"game_id":f["game_id"],"team":f["team"],
            "player_id":f["player_id"],"market":f["market"],
            "state":"MISSING_OR_DNP_NO_IMPUTATION"}
    col=f["source_stat"]
    if col not in current["values"]:
        return {"game_id":f["game_id"],"team":f["team"],
            "player_id":f["player_id"],"market":f["market"],
            "state":"MISSING_STAT_NO_IMPUTATION"}
    actual=float(current["values"][col])
    line=f["research_line"]
    if actual==line:
        return {"game_id":f["game_id"],"team":f["team"],
            "player_id":f["player_id"],"market":f["market"],
            "state":"PUSH","actual":actual}
    labels=[]
    for model,values in f["draws"].items():
        if values is None:continue
        # Jeffreys a-priori regularization applies identically to BOTH
        # challengers, preventing impossible empirical 0%/100% probabilities.
        n=len(values)
        p=(sum(x>line for x in values)+.5)/(n+1.)
        summary=sample_score(values,actual,line)
        summary.update(probability_score(p,int(actual>line)))
        labels.append({"model":model,
            **{k:f[k] for k in ("season","week","game_id","team","player_id","role",
                                  "market","research_line")},
            "line":line,"probability_rule":"Jeffreys_0.5_0.5_fixed_precommitted",
            "cold_start":f["cold_start"],**summary})
    return {"game_id":f["game_id"],"team":f["team"],
      "player_id":f["player_id"],"market":f["market"],
      "state":"SETTLED","actual":actual,"scores":labels}


def _metrics(rows):
    d=metrics(rows)
    if not rows:return d
    d["game_count"]=len({r["game_id"] for r in rows})
    d["week_count"]=len({r["week"] for r in rows})
    return d


def run(args):
    must(not args.output_dir.exists(),"append_only_2024_2025_replay_required")
    spec=read(args.protocol)
    must(spec.get("experiment_id")==EXPERIMENT and
         spec.get("production_allowed") is False and
         spec.get("fixed_QB_scramble_kneel_components") is True,
         "unpreregistered_distribution_hypothesis")
    n=spec["samples"];seed=spec["seed"]
    must(type(n) is int and n in (256,512,1024,2048),"bad_samples")
    source_root=args.source_root.resolve()
    manifest=read(source_root/"source_manifest.json")
    pbp=source_files(source_root,manifest)
    allstat=read(args.stats_2021_2024)
    stat2025=read(args.stats_2025)
    normalized=normalise_player_source(allstat["rows"],rejection_ledger=[])
    norm2025=normalise_player_source(stat2025["rows"],rejection_ledger=[],
                                      allowed_seasons=(2025,))
    must(len({g["event_id"] for g in normalized if g["season"]==2024})==272,
         "incorrect_2024_team_game_stats")
    must(len({g["event_id"] for g in norm2025})==272,"incorrect_2025_team_game_stats")
    schedule2024=read(source_root/"schedule_2024.json.gz")["rows"]
    roster2024=read(source_root/"depth_qb1_2024_lag_only.json.gz")["rows"]
    schedule2025=read(args.schedule_2025)["rows"]
    must(len(schedule2025)==272,"2025_games_mismatch")
    select={2024:choose_lagged_2024_qb1(roster2024,schedule2024),
            2025:read_original_2025_qb1(args.frozen_2025_run)}
    args.output_dir.mkdir(parents=True,exist_ok=False)
    codedir=args.output_dir/"code";codedir.mkdir()
    tofreeze=("v25_qb_rush_components.py","v25_qb_rush_components_replay.py",
              "v25_opportunity_distribution.py","v25_opportunity_repair_replay.py",
              "v25_opportunity_2025_replay.py",
              "v25_nfl_2024_all_volume_rolling_calibration.py",
              "nfl_contract_settlement.py")
    codehash={}
    for filename in tofreeze:
        raw=(HERE/filename).read_bytes();(codedir/filename).write_bytes(raw)
        codehash[filename]=hashlib.sha256(raw).hexdigest()
    files={"source_manifest":source_root/"source_manifest.json",
           "stats_2021_2024":args.stats_2021_2024,"stats_2025":args.stats_2025,
           "schedule_2025":args.schedule_2025,"original_2025_QB1_selection":
               args.frozen_2025_run/"SOURCE_QB1_ASOF_SELECTION.json.gz",
           "protocol":args.protocol}
    sourcehash={name:file_hash(path) for name,path in files.items()}
    sourcehash.update(manifest["sha256"])
    write_once(args.output_dir/"EXPERIMENT_FREEZE.json",
         {"schema":SCHEMA,"study":EXPERIMENT,"protocol":spec,
          "sources":sourcehash,"code_hashes":codehash,
          "source_original_game_publication_verified":False,
          "known_retrospective_2024_2025":True})
    weekly=[];all_scores=collections.defaultdict(list);attempts=collections.Counter()
    file_manifest=[]
    for year in (2024,2025):
        prior_stats=[g for g in normalized if g["season"]<year]
        if year==2025:
            prior_stats=[*normalized]
        history_pbp=[x for y,rows in pbp.items() if y<year for x in rows]
        oracle_games=([g for g in normalized if g["season"]==year]
                      if year==2024 else norm2025)
        oracle_games_by_week=collections.defaultdict(list)
        for g in oracle_games:oracle_games_by_week[g["week"]].append(g)
        for week in range(1,19):
            priorstats_source=[g for g in prior_stats if
              g["season"]<year or (g["season"]==year and g["week"]<week)]
            priorpbp=[x for x in history_pbp if
              x["season"]<year or (x["season"]==year and x["week"]<week)]
            old2025={}
            if year==2025:
                oldpacket=read(args.frozen_2025_run/f"week_{week:02d}_forecast.json.gz")
                must(oldpacket["week"]==week and oldpacket["schema"]=="v25-qb1-2025-forecast-v1",
                     "original_frozen_2025_model_mismatch")
                old2025={(x["game_id"],x["team"],x["player_id"],x["market"]):x
                       for x in oldpacket["contracts"]}
                must(len(old2025)==len(oldpacket["contracts"]),"original_QB1_forecast_duplicate")
            packet=create_packet(year,week,priorstats_source,priorpbp,select[year],old2025)
            base=args.output_dir/f"{year}_week_{week:02d}"
            snap=base.with_name(base.name+"_input.json.gz")
            forecast=base.with_name(base.name+"_forecast.json.gz")
            scored=base.with_name(base.name+"_settlement.json.gz")
            sh=write_once(snap,packet)
            child=subprocess.run([sys.executable,str((codedir/"v25_qb_rush_components_replay.py").resolve()),
                   "forecast","--input",str(snap),"--output",str(forecast),
                   "--samples",str(n),"--seed",str(seed)],
                   capture_output=True,text=True,timeout=240)
            must(child.returncode==0,
                 f"forecast_child_{year}_week_{week}_failed:"+child.stderr[-1300:])
            pred=read(forecast)
            must(pred["input_sha256"]==digest(packet) and pred["week"]==week and
                 pred["year"]==year,"bad_forecast_input_binding")
            cohort=oracle_games_by_week[week]
            candidates={(g["event_id"],g["team"],pid):p
                        for g in cohort for pid,p in g["players"].items()
                        if p["role"]=="QB"}
            settlement=[_score_forecast(f,candidates) for f in pred["forecasted_contracts"]]
            result={"schema":SCHEMA,"year":year,"week":week,
               "no_game_outcome_reused_for_forecast":True,"predicted_n":len(pred["forecasted_contracts"]),
               "source_selected_n":len([x for x in select[year] if x["week"]==week]),
               "original_QB1_abstentions":pred["abstentions"],"results":settlement}
            stsha=write_once(scored,result)
            for x in settlement:
                attempts[year,x["state"]]+=1
                for row in x.get("scores",[]):
                    all_scores[year,row["market"],row["model"]].append(row)
            attempts[year,"candidate_source_team_games"]+=len([x for x in select[year] if x["week"]==week])
            attempts[year,"prereq_abstentions"]+=len(pred["abstentions"])
            file_manifest.append({"year":year,"week":week,
                "input":sh,"forecast":file_hash(forecast),"settlement":stsha})
            weekly.append({"year":year,"week":week,
               "eligible_QB1_contracts":len(pred["forecasted_contracts"]),
               "source_abstentions":len(pred["abstentions"]),
               "settled":sum(x["state"]=="SETTLED" for x in settlement),
               "unmatched":sum(x["state"].startswith("MISSING") for x in settlement)})
            # ONLY after official settlement do current week rows enter the
            # next week's pregame history. Both modalities update together.
            prior_stats.extend(cohort)
            history_pbp.extend([x for x in pbp[year] if x["week"]==week])
            print("QB_RUSH_COMPONENT_WEEK_DONE",year,week,"forecast",len(pred["forecasted_contracts"]),
                  "scored",weekly[-1]["settled"],flush=True)
    report={"schema":SCHEMA,"status":"COMPLETE_RESEARCH_ONLY",
       "experiment_id":EXPERIMENT,
       "source_hashes":sourcehash,"code_hashes":codehash,
       "accepted_season_years":[2024,2025],
       "original_2025_line_model_forecasts_unchanged":True,
       "2024_depth_only_prior_week":True,"2025_depth_original_retrospective_UTC":True,
       "2024_and_2025_historically_exposed":True,
       "not_source_certified_orig_pregame":True,
       "no_original_betting_lines":True,
       "type_distribution":"scramble+designed+kneel+other",
       "stat":"QB rushing attempts and yards",
       "partial_publication":False,"production_allowed":False,
       "tier1_tier2_authorized":False,"NUTS_or_heavy_training":False,
       "source_original_attempts":dict((str(year),{k[1]:v for k,v in attempts.items()
                                       if k[0]==year}) for year in (2024,2025)),
       "weekly":weekly,"file_manifest":file_manifest,"season_results":{}}
    for year in (2024,2025):
        bymarket={}
        for market in MARKETS:
            a=all_scores[year,market,"component_types"]
            b=all_scores[year,market,"historic_player_prior"]
            c={k:v for k,v in ((("component_types",_metrics(a)),
                                ("historic_player_prior",_metrics(b))))}
            c["matched_model_minus_prior"]={
                field:{"week":paired(a,b,field),"game":game_paired(a,b,field)}
                for field in ("brier","log_loss","crps","bias")}
            c["same_contracts_required"]=True
            c["n_matched"] = c["matched_model_minus_prior"]["brier"]["week"].get("n",0)
            bymarket[market]=c
        report["season_results"][str(year)]=bymarket
    report["receipt_sha256"]=digest(report)
    write_once(args.output_dir/"FINAL_COMPONENT_2024_2025_REPORT.json",report)
    print("QB_COMPONENT_REPLAY_FINISHED",json.dumps({
        "seasons":report["season_results"],"coverage":report["source_original_attempts"],
        "receipt":report["receipt_sha256"]},sort_keys=True)[:23000],flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="command",required=True)
    f=sub.add_parser("forecast")
    f.add_argument("--input",type=pathlib.Path,required=True)
    f.add_argument("--output",type=pathlib.Path,required=True)
    f.add_argument("--samples",type=int,required=True)
    f.add_argument("--seed",type=int,required=True)
    r=sub.add_parser("run")
    for name in ("source-root","stats-2021-2024","stats-2025","schedule-2025",
                 "frozen-2025-run","protocol","output-dir"):
        r.add_argument("--"+name,type=pathlib.Path,required=True)
    a=p.parse_args()
    if a.command=="forecast":
        write_once(a.output,forecast_child(read(a.input),a.samples,a.seed))
    else:run(a)


if __name__=="__main__":main()
