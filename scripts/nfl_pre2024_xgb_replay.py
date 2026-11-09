#!/usr/bin/env python3
"""End-to-end 2021-23 PBP/NGS + Optuna-XGBoost; freeze ALL 2024 before settlement.

Commands:
  python nfl_pre2024_xgb_replay.py freeze --root ...
  python nfl_pre2024_xgb_replay.py evaluate --root ...

Mandatory design: no >=2024 observation can enter training, CV, fitted trees,
feature selection, model choice, calibration or engine weights. The 2024
schedule can define game candidates; no 2024 stats are downloaded until
every one of the 18 weekly forecasts is frozen and SHA256-locked.

Research-only synthetic thresholds and unknown roster offers. NEVER publish
the ranked picks as real sportsbook propositions.
"""
from __future__ import annotations
from collections import defaultdict
import argparse,csv,hashlib,json,math
from datetime import date
from pathlib import Path

import nfl_pre2024_xgboost_optuna as xgbm
import nfl_pre2024_team_defense_challenger as opp
from nfl_pre2024_pbp_ngs_sources import (
    CUTOFF,TRAINING_SEASONS,aggregate_games,ngs_pre2024_rows,
    assert_pre2024_training_inputs)
from population_nfl import normalize_season,fetch_season

VERSION="nfl_pre2024_tpe_xgb_locked_2024_v1"
SOURCE_CUTOFF="2024-01-01"
EVAL_SEASON=2024
MIN_FIRST_2024_PLAYER_AGE_DAYS=0
MAX_FIRST_2024_PLAYER_AGE_DAYS=85
REPLAY_WEEK_MAX=18
PBP_COLUMNS=("game_id","play_id","season","week","season_type",
   "posteam","defteam","pass_attempt","rush_attempt","qb_dropback","qb_hit",
   "sack","air_yards","complete_pass","receiver_player_id",
   "passing_yards","rushing_yards","score_differential","qtr")
NGS_KEEP={
 "passing":("season","season_type","week","team_abbr","player_gsis_id",
   "avg_intended_air_yards","completion_percentage_above_expectation",
   "avg_time_to_throw","expected_completion_percentage","attempts"),
 "receiving":("season","season_type","week","team_abbr","player_gsis_id",
   "avg_cushion","avg_separation","percent_share_of_intended_air_yards",
   "avg_yac_above_expectation","targets"),
 "rushing":("season","season_type","week","team_abbr","player_gsis_id",
   "rush_yards_over_expected_per_att","percent_attempts_gte_eight_defenders",
   "expected_rush_yards","rush_attempts"),
}

def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False).encode()

def atomic_new(path,obj):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise RuntimeError("refuse_existing_artifact:"+str(path))
    blob=canonical(obj)
    path.write_bytes(blob)
    return hashlib.sha256(blob).hexdigest()

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def pre2024_sources():
    """No 2024-season loader in this function, full stop."""
    import nflreadpy
    source=[]
    schedule={}
    schedule_by_teamweek={}
    raw_sources={}
    for year in TRAINING_SEASONS:
        if year>=2024:raise RuntimeError("future_year_in_training_loader")
        stats,snaps,fixtures=fetch_season(year)
        rows,coverage=normalize_season(stats,snaps,fixtures,year,cutoff=SOURCE_CUTOFF)
        if any(r["game_date"]>=SOURCE_CUTOFF for r in rows):
            raise RuntimeError("training_cannot_include_2024_calendar_dates")
        source.extend(rows)
        raw_sources[str(year)]=dict(normalized=len(rows),
                stat_source_rows=len(stats),snap_source_rows=len(snaps),
                recorded_match_coverage=coverage)
        for f in fixtures:
            if (f.get("game_type")!="REG" or int(f.get("season",0))!=year
                or str(f.get("gameday") or "")>=SOURCE_CUTOFF):
                continue
            gid=str(f["game_id"])
            day=str(f["gameday"])
            schedule[gid]=day
            for team in (f["home_team"],f["away_team"]):
                key=(year,int(f["week"]),str(team))
                if key in schedule_by_teamweek and schedule_by_teamweek[key]!=day:
                    raise RuntimeError("duplicate_team_week_schedule")
                schedule_by_teamweek[key]=day
    if not source or not schedule:
        raise RuntimeError("no_pre2024_training_source")
    pbp_games=[];coverage_by_season={}
    # Game-local postgame identity is permissible for constructing that
    # completed game's training aggregate. A player identity learned from
    # later games is NOT permissible for older chronological training data.
    position={(str(r["game_id"]),str(r["player_id"])):r["position"]
              for r in source if r["stat"]=="targets"}
    for year in TRAINING_SEASONS:
        pbp=nflreadpy.load_pbp(seasons=[year])
        import polars as pl
        keep=[k for k in PBP_COLUMNS if k in pbp.columns]
        if len(keep)!=len(PBP_COLUMNS):
            raise RuntimeError("required_pre2024_pbp_columns_missing:"+str(set(PBP_COLUMNS)-set(keep)))
        slim=pbp.select(keep).to_dicts()
        del pbp
        games,cov=aggregate_games(slim,schedule,player_position=position,ftn_rows=())
        del slim
        pbp_games.extend(games)
        coverage_by_season[str(year)]=cov
    ngs={}
    ngs_coverage={}
    for kind in NGS_KEEP:
        allrows=[]
        for year in TRAINING_SEASONS:
            ngsframe=nflreadpy.load_nextgen_stats(seasons=[year],stat_type=kind)
            keep=[k for k in NGS_KEEP[kind] if k in ngsframe.columns]
            if len(keep)!=len(NGS_KEEP[kind]):
                raise RuntimeError("missing_ngs_fields:"+kind)
            observed=ngsframe.select(keep).to_dicts()
            rows=ngs_pre2024_rows(observed,kind,schedule_by_teamweek)
            allrows.extend(rows)
        ngs[kind]=allrows
        ngs_coverage[kind]=len(allrows)
    assert_pre2024_training_inputs(player_rows=source,pbp_games=pbp_games,
                                   ngs_rows=[r for rows in ngs.values() for r in rows])
    record=dict(cutoff=SOURCE_CUTOFF,training_seasons=list(TRAINING_SEASONS),
        pre2024_player_market_rows=len(source),pre2024_pbp_team_games=len(pbp_games),
        pre2024_ngs_rows=ngs_coverage,source_coverage=raw_sources,
        pbp_coverage=coverage_by_season,
        ftn_records_admitted=0,ftn_provenance_status="2024_09_pulled_files_quarantined")
    return source,pbp_games,ngs,record

def eligible_previous_roster(state):
    """No 2024 player name, roster, active, target or snap data is accessible."""
    out={}
    for pid,last in state["latest_by_player"].items():
        if int(last["season"])!=2023:continue
        seen=date.fromisoformat(last["gameday"])
        age=(CUTOFF-seen).days
        if not MIN_FIRST_2024_PLAYER_AGE_DAYS<=age<=MAX_FIRST_2024_PLAYER_AGE_DAYS:
            continue
        out[str(pid)]=last
    return out

def frozen_2024_schedule_only():
    import nflreadpy
    records=nflreadpy.load_schedules(seasons=[2024]).to_dicts()
    selected=[]
    # DO NOT pass any actual scores, player participation or results.
    for r in records:
        if r.get("game_type")!="REG" or int(r.get("season",0))!=2024:
            continue
        week=int(r["week"])
        if week not in range(1,REPLAY_WEEK_MAX+1):continue
        selected.append({k:r[k] for k in ("game_id","gameday","week",
                                          "home_team","away_team")})
    if not selected or set(x["week"] for x in selected)!=set(range(1,19)):
        raise RuntimeError("incomplete_2024_schedule")
    return sorted(selected,key=lambda r:(r["week"],r["game_id"]))

def make_frozen_forecasts(state,fitted,schedule):
    roster=eligible_previous_roster(state)
    byteam=defaultdict(list)
    for pid,p in roster.items():byteam[p["team"]].append((pid,p))
    candidates=[]
    for game in schedule:
        for team,opponent in ((game["home_team"],game["away_team"]),
                              (game["away_team"],game["home_team"])):
            for pid,person in byteam.get(team,()):
                pos=person["position"]
                for m in xgbm.MARKETS:
                    if pos not in opp.ROLE_POS[m] or fitted.get(m) is None:continue
                    line=opp.research_line(state,stat=m,player_id=pid,
                        position=pos,team=team,asof=SOURCE_CUTOFF)
                    if line is None:continue
                    feature=xgbm.make_feature(state,stat=m,player_id=pid,
                        position=pos,team=team,opponent=opponent,
                        asof=SOURCE_CUTOFF)
                    if feature is None:continue
                    challenger=xgbm.predict_market(fitted[m],state,m,pid,pos,team,opponent)
                    player_only,history=opp.predict(state,stat=m,
                        player_id=pid,position=pos,team=team,opponent=opponent,
                        asof=SOURCE_CUTOFF,variant="player_only")
                    team_only,teammeta=opp.predict(state,stat=m,
                        player_id=pid,position=pos,team=team,opponent=opponent,
                        asof=SOURCE_CUTOFF,variant="no_ngs")
                    if any(v is None for v in (challenger,player_only,team_only)):
                        continue
                    if any(not math.isfinite(x) for x in (challenger,player_only,team_only)):
                        raise RuntimeError("nonfinite_frozen_forecast")
                    candidates.append({
                     "year":2024,"week":game["week"],"game_id":game["game_id"],
                     "player_id":pid,"team":team,"opponent":opponent,
                     "position":pos,"stat":m,"line":line,
                     "line_source":"historical_2023_player_role_synthetic_unverified",
                     "predicted_mean_xgboost":challenger,
                     "predicted_mean_player_only":player_only,
                     "predicted_mean_pbp_team":team_only,
                     "p_over_xgboost":opp.prob_over(challenger,line,m),
                     "p_over_player_only":opp.prob_over(player_only,line,m),
                     "p_over_pbp_team":opp.prob_over(team_only,line,m),
                     "model_asof":SOURCE_CUTOFF,
                     "player_roster_2024_verified":False,
                     "bookmaker_quote_2024_verified":False,
                     "pre2024_training_only":True,
                     "ftn_charted_reads_admitted":False})
    identities=[(x["game_id"],x["player_id"],x["stat"]) for x in candidates]
    if len(set(identities))!=len(identities):
        raise RuntimeError("duplicate_frozen_prediction_identity")
    return sorted(candidates,key=lambda r:(r["week"],r["game_id"],r["player_id"],r["stat"]))

def freeze(root,trials=8):
    root=Path(root)
    if root.exists():
        raise RuntimeError("immutable_run_already_exists")
    root.mkdir(parents=True)
    rows,games,ngs,source_receipt=pre2024_sources()
    print("PRE2024_SOURCE_ONLY",json.dumps({k:v for k,v in source_receipt.items()
          if k not in ("source_coverage","pbp_coverage")}),flush=True)
    state=opp.historical_sources(rows,games,ngs)
    grouped=xgbm.make_training_rows(state,rows)
    import xgboost
    fitted={};trials_meta={}
    for m in xgbm.MARKETS:
        model,metadata=xgbm.fit_one_market(grouped[m],m,trials=trials)
        if model is None:
            raise RuntimeError("missing_pre2024_model_market:"+m+":"+str(metadata))
        fitted[m]=model
        trials_meta[m]=metadata
        modelpath=root/"models"/(m.replace(" ","_").replace("+","plus")+".ubj")
        modelpath.parent.mkdir(parents=True,exist_ok=True)
        model.save_model(str(modelpath))
        print("PRE2024_TPE_MARKET",m,metadata["rows"],
              round(metadata["best_cv_negative_loglik"],6),flush=True)
    schedule=frozen_2024_schedule_only()
    packets=make_frozen_forecasts(state,fitted,schedule)
    if not packets:raise RuntimeError("empty_2024_frozen_candidate_universe")
    # Lock every week before any 2024 outcomes are loaded, queried or scored.
    hashes={}
    for week in range(1,19):
        selected=[p for p in packets if p["week"]==week]
        hashes[str(week)]=atomic_new(root/f"FROZEN/2024_week_{week:02d}.json",
                                     {"week":week,"year":2024,"predictions":selected,
                                      "outcomes_exposed":False,
                                      "model_asof":SOURCE_CUTOFF})
    model_files={p.name:sha(p) for p in (root/"models").glob("*.ubj")}
    manifest=dict(schema=VERSION,stage="frozen_before_2024_outcomes",
        source_receipt=source_receipt,
        params_by_market=trials_meta,model_artifact_sha256=model_files,
        number_of_model_markets=len(fitted),week_hashes=hashes,
        number_of_weeks=18,forecasted=len(packets),
        train_max_allowed_exclusive=SOURCE_CUTOFF,
        no_2024_player_ngs_pbp_ftn_training=True,
        no_2024_tuning_or_retraining=True,
        no_2024_outcomes_accessed=True,
        all_18_weeks_frozen_before_scoring=True,
        roster_asof="inferred_from_2023_not_verified_2024",
        sportsbook_line_asof="synthetic_pre2024_not_available_bookmaker",
        production_eligible=False,
        algorithm="Optuna_TPE_XGBoost_with_PBP_and_NGS_pre2024")
    atomic_new(root/"FROZEN_MANIFEST.json",manifest)
    print("FROZEN_2024_ALL_18_WEEKS",len(packets),
          "sha",sha(root/"FROZEN_MANIFEST.json"),flush=True)
    return manifest

def evaluate(root):
    """Must not access 2024 outcomes until all 18 weeks are already SHA-locked."""
    root=Path(root)
    manifest_file=root/"FROZEN_MANIFEST.json"
    if not manifest_file.is_file():raise RuntimeError("freeze_before_2024_evaluation")
    manifest=json.loads(manifest_file.read_bytes())
    if (manifest.get("stage")!="frozen_before_2024_outcomes"
        or manifest.get("train_max_allowed_exclusive")!=SOURCE_CUTOFF
        or manifest.get("number_of_weeks")!=18
        or not manifest.get("no_2024_outcomes_accessed")):
        raise RuntimeError("no_verified_pre2024_freeze")
    forecasts=[]
    for week in range(1,19):
        path=root/f"FROZEN/2024_week_{week:02d}.json"
        if sha(path)!=manifest["week_hashes"][str(week)]:
            raise RuntimeError("frozen_2024_forecast_sha_mismatch")
        p=json.loads(path.read_bytes())
        if not p["outcomes_exposed"] is False:
            raise RuntimeError("forecast_packet_accessed_outcomes")
        if any(row["model_asof"]!=SOURCE_CUTOFF for row in p["predictions"]):
            raise RuntimeError("2024_feature_date_violation")
        forecasts.extend(p["predictions"])
    if len(forecasts)!=manifest["forecasted"]:
        raise RuntimeError("incomplete_18_week_frozen_2024")
    print("2024_EVALUATION_OUTCOMES_UNLOCKED_AFTER_18_SHA_LOCKS",len(forecasts),flush=True)
    # First and ONLY access to 2024 player result data occurs below.
    a,b,c=fetch_season(2024)
    observed,coverage=normalize_season(a,b,c,2024,cutoff="2025-03-01")
    labels={(r["game_id"],str(r["player_id"]),r["stat"]):float(r["value"]) for r in observed
         if r["stat"] in xgbm.MARKETS}
    if len(labels)!=sum(r["stat"] in xgbm.MARKETS for r in observed):
        raise RuntimeError("duplicate_2024_settlement_label")
    scored=[]
    for row in forecasts:
        out=dict(row)
        label=labels.get((row["game_id"],row["player_id"],row["stat"]))
        out["result"]=label
        if label is None:
            out["graded"]=False
        else:
            over=int(label>row["line"])
            out["graded"]=True
            out["actual_over"]=over
            for name in ("xgboost","player_only","pbp_team"):
                p=row["p_over_"+name]
                out["hit_"+name]=int((p>=.5)==bool(over))
                out["brier_"+name]=(p-over)**2
                out["logloss_"+name]=-(over*math.log(max(1e-12,p))+
                                 (1-over)*math.log(max(1e-12,1.-p)))
        scored.append(out)
    scored_file=root/"EVALUATION/2024_settled_frozen_forecasts.json"
    atomic_new(scored_file,scored)
    report={}
    for wk in range(1,19):
        for market in (*xgbm.MARKETS,"ALL"):
            z=[r for r in scored if r["week"]==wk and
              (market=="ALL" or r["stat"]==market)]
            ok=[r for r in z if r["graded"]]
            entry={"week":wk,"market":market,
                   "forecasted":len(z),"graded":len(ok),
                   "unmatched":len(z)-len(ok)}
            for name in ("xgboost","player_only","pbp_team"):
                entry[name+"_accuracy"]=(
                   sum(r["hit_"+name] for r in ok)/len(ok) if ok else None)
                entry[name+"_brier"]=(
                   sum(r["brier_"+name] for r in ok)/len(ok) if ok else None)
                entry[name+"_logloss"]=(
                   sum(r["logloss_"+name] for r in ok)/len(ok) if ok else None)
            report[(wk,market)]=entry
    counts={}
    for name in ("xgboost","player_only","pbp_team"):
        ok=[r for r in scored if r["graded"]]
        counts[name]={
          "accuracy":sum(r["hit_"+name] for r in ok)/len(ok) if ok else None,
          "brier":sum(r["brier_"+name] for r in ok)/len(ok) if ok else None,
          "logloss":sum(r["logloss_"+name] for r in ok)/len(ok) if ok else None,
          "under_share":sum(r["p_over_"+name]<.5 for r in ok)/len(ok) if ok else None}
    weekly=[report[(w,"ALL")] for w in range(1,19)]
    per_market=[]
    for market in xgbm.MARKETS:
        z=[r for r in scored if r["stat"]==market]
        ok=[r for r in z if r["graded"]]
        item=dict(market=market,forecasted=len(z),graded=len(ok),
                  unmatched=len(z)-len(ok))
        for name in counts:
            item[name+"_accuracy"]=sum(r["hit_"+name] for r in ok)/len(ok) if ok else None
            item[name+"_brier"]=sum(r["brier_"+name] for r in ok)/len(ok) if ok else None
        per_market.append(item)
    summary=dict(schema=VERSION,stage="2024_scored_only_after_lock",
        frozen_manifest_sha256=sha(manifest_file),
        full_forecast_hashes_validated=18,
        outcomes_loaded_only_after_frozen_forecast_verification=True,
        forecasted=len(scored),graded=sum(x["graded"] for x in scored),
        unmatched=sum(not x["graded"] for x in scored),
        models=counts,weekly=weekly,per_market=per_market,
        training_cutoff=SOURCE_CUTOFF,training_2024_outcomes=0,
        no_2024_retraining=True,
        caveats=["No genuine 2024 bookmaker lines","2024 player active roster unverified",
                 "Pregame candidate eligibility inferred from December 2023 only",
                 "FTN 2022-23 download provenance postdates 2023 and was excluded",
                 "Do not interpret unmatched as DNP or as actual losses",
                 "Fixed model cannot show within-2024 training progression"])
    atomic_new(root/"EVALUATION/SUMMARY.json",summary)
    print("PRE2024_XGB_FROZEN_EVALUATION_DONE",json.dumps({
        "forecasted":summary["forecasted"],"graded":summary["graded"],
        "unmatched":summary["unmatched"],"models":counts,
        "weekly":weekly}),flush=True)
    return summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument("stage",choices=("freeze","evaluate"))
    p.add_argument("--root",required=True)
    p.add_argument("--trials",type=int,default=8)
    args=p.parse_args()
    if args.stage=="freeze":freeze(args.root,trials=args.trials)
    else:evaluate(args.root)

if __name__=="__main__":main()
