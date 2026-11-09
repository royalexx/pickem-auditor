#!/usr/bin/env python3
"""Strict pre-2024 XGBoost-team + Bayesian-allocation Monte Carlo challenger.

freeze: load/train/tune ONLY on 2021–2023 dates before Jan 1 2024. A 2024
game SCHEDULE is permitted solely to define matchups. Lock all 18 weeks'
synthetic research forecasts before any 2024 player outcomes are requested.
evaluate: verify immutable manifest and 18 SHA locks, then load 2024 results
only for scoring. No 2024 updates, hyperparameter tuning or model choices.

Player roster carried forward from 2023 is not verified for 2024. FTN records
pulled in September 2024 are excluded. No production/pick ranking changes.
"""
from __future__ import annotations
import argparse,json,math,hashlib
from collections import defaultdict
from pathlib import Path

import nfl_pre2024_xgb_replay as common
import nfl_pre2024_team_volume_xgb as teamxgb
import nfl_pre2024_team_defense_challenger as priors
import nfl_pre2024_hybrid_bayesian_mc as hybrid
import nfl_pre2024_active_zero_hurdle as active_zero
import nflverse_pre2024_hurdle_gateway as gateway
from population_nfl import fetch_season,normalize_season

SCHEMA="nfl_pre2024_team_xgb_hierarchical_mc_activezero_frozen_2024_v2"
TRAIN_END_EXCLUSIVE="2024-01-01"

def freeze(root,*,trials=8,draws=2000):
    root=Path(root)
    if root.exists():raise RuntimeError("immutable_hybrid_run_directory_exists")
    root.mkdir(parents=True,exist_ok=False)
    rows,team_games,ngs,source_receipt=common.pre2024_sources()
    if source_receipt["cutoff"]!=TRAIN_END_EXCLUSIVE:
        raise RuntimeError("pre2024_source_cutoff_mismatch")
    if any(r["game_date"]>=TRAIN_END_EXCLUSIVE for r in rows):
        raise RuntimeError("future_player_training_row")
    if any(r["gameday"]>=TRAIN_END_EXCLUSIVE for r in team_games):
        raise RuntimeError("future_pbp_training_row")
    if any(r["gameday"]>=TRAIN_END_EXCLUSIVE for v in ngs.values() for r in v):
        raise RuntimeError("future_ngs_training_row")
    if source_receipt["ftn_records_admitted"]!=0:
        raise RuntimeError("post_cutoff_ftn_was_admitted")
    print("HYBRID_PRE2024_SOURCES",json.dumps({
        "player_rows":len(rows),"team_games":len(team_games),
        "ngs_rows":{k:len(v) for k,v in ngs.items()},
        "ftn_rows":0}),flush=True)
    state=priors.historical_sources(rows,team_games,ngs)
    # No 2024 game observations, no 2023 FTN postseason participation.
    context=gateway.load_nflreadpy_strict_pre2024_context(
       include_participation=True,include_injuries=True)
    if context["cutoff_exclusive"]!=TRAIN_END_EXCLUSIVE or context["ftn_participation_2023_plus"]:
        raise RuntimeError("hurdle_context_breaks_asof_cutoff")
    active_zero_fit,zero_receipt=active_zero.train(state,context,rows,trials=trials)
    if active_zero_fit is not None:
        mpath=root/"MODELS"/"active_zero_hurdle.ubj"
        mpath.parent.mkdir(parents=True,exist_ok=True)
        active_zero_fit[0].save_model(str(mpath))
        if active_zero_fit[1] is not None:
            cal=active_zero_fit[1]
            common.atomic_new(root/"MODELS"/"active_zero_platt_calibration.json",
               {"coef":cal.coef_.tolist(),"intercept":cal.intercept_.tolist(),
                "classes":cal.classes_.tolist(),
                "fit_cutoff_exclusive":TRAIN_END_EXCLUSIVE,
                "method":"pre2024_oof_platt_logit"})
        print("HURDLE_PRE2024_FIT",json.dumps(zero_receipt,sort_keys=True)[:2500],flush=True)
    else:
        print("HURDLE_PRE2024_ABSTAIN",zero_receipt,flush=True)
    index=teamxgb.build_index(team_games,ngs)
    # Team totals, NOT individual player props, are the two XGBoost labels.
    fitted,fit_receipts=teamxgb.train(team_games,index,trials=trials)
    for market,mdl in fitted.items():
        path=root/"MODELS"/(market+".ubj")
        path.parent.mkdir(parents=True,exist_ok=True)
        mdl.save_model(str(path))
        print("HYBRID_TEAM_XGB_FIT",market,json.dumps(fit_receipts[market],
               sort_keys=True)[:1100],flush=True)
    schedule=common.frozen_2024_schedule_only()
    byweek=defaultdict(list)
    for fixture in schedule:
        home=fixture["home_team"];away=fixture["away_team"]
        means={
            home:teamxgb.project(fitted,index,home,away,home=True,
                                  week=fixture["week"]),
            away:teamxgb.project(fitted,index,away,home,home=False,
                                  week=fixture["week"])}
        dispersion={t:{m:fit_receipts[m]["dispersion"] for m in teamxgb.TARGETS}
                    for t in (home,away)}
        forecasts,meta=hybrid.summarize_game(state,fixture,means,dispersion,
                                              draws=draws)
        # Paired forecast from EXACT same pre2024 state and same game.
        if active_zero_fit is not None:
            new,hr=hybrid.summarize_game(
                state,fixture,means,dispersion,draws=draws,
                active_zero_model=active_zero_fit,hurdle_context=context)
            byid={(p["game_id"],p["player_id"],p["market"]):p for p in new}
            if len(byid)!=len(forecasts):
                raise RuntimeError("hurdle_candidate_universe_changed")
            for p in forecasts:
                ident=(p["game_id"],p["player_id"],p["market"])
                if ident not in byid:raise RuntimeError("hurdle_identity_mismatch")
                h=byid[ident]
                p["p_over_hurdle"]=h["p_over"]
                p["p_zero_active_hurdle_simulated"]=h["p_zero_active_simulated"]
        else:
            for p in forecasts:
                p["p_over_hurdle"]=None
                p["p_zero_active_hurdle_simulated"]=None
        for pred in forecasts:
            # Comparator is the last-five player prior, also pre2024 only.
            ref,ev=priors.predict(state,stat=pred["market"],
              player_id=pred["player_id"],position=pred["position"],
              team=pred["team"],
              opponent=(away if pred["team"]==home else home),
              asof=TRAIN_END_EXCLUSIVE,variant="player_only")
            pred["p_over_player_prior"]=(
                priors.prob_over(ref,pred["research_line"],pred["market"])
                if ref is not None else None)
            pred["team_pass_xgb"]=means[pred["team"]]["pass_attempts"]
            pred["team_rush_xgb"]=means[pred["team"]]["rush_attempts"]
            pred["comparison_fitted_before_2024"]=True
            if pred["model_asof"]!=TRAIN_END_EXCLUSIVE or pred["training_data_from_2024"]:
                raise RuntimeError("future_training_data_in_hybrid_forecast")
        byweek[int(fixture["week"])].extend(forecasts)
    if set(byweek)!=set(range(1,19)):
        raise RuntimeError("no_frozen_18_week_calendar")
    hashes={};week_counts={}
    for week in range(1,19):
        row=sorted(byweek[week],key=lambda r:(r["game_id"],r["player_id"],r["market"]))
        ident=[(r["game_id"],r["player_id"],r["market"]) for r in row]
        if len(ident)!=len(set(ident)):
            raise RuntimeError("duplicate_hybrid_prop_per_game")
        week_file=root/f"FROZEN/2024_week_{week:02d}.json"
        hashes[str(week)]=common.atomic_new(week_file,
             {"week":week,"year":2024,"stage":"frozen_pre2024",
              "2024_player_results_accessed":False,
              "research_only":True,"predictions":row})
        week_counts[str(week)]=len(row)
    manifest=dict(schema=SCHEMA,stage="all_18_weeks_frozen",
        training_cutoff_exclusive=TRAIN_END_EXCLUSIVE,
        fit_and_hyperparameter_selection_use_only_pre2024=True,
        feature_source="PBP_2021_2023_and_NGS_2021_2023",
        rb_target_receiver_position_scope="same_game_only_no_future_season_backfill",
        ftndata_used=False,
        ftndata_quarantine_reason="FTN_2022_2023_archive_pulled_2024_09",
        model_mode="XGB_team_pass_rush_Dirichlet_Beta_Binomial_MC_active_zero_hurdle",
        hurdle_fit_receipt=zero_receipt,
        hurdle_source_provenance={"nflreadpy_standardized":True,
          "2023_ftn_participation_quarantined":True,
          "2021_22_dropback_presence_is_not_routes_run":True,
          "active_only_confirmed_snap_training_labels":True,
          "2024_pregame_injury_report_unavailable_by_design":True,
          "no_emergency_only_imputation":True},
        previous_2024_weeks_train_model=False,
        source_receipt=source_receipt,
        team_xgboost_fit_receipts=fit_receipts,
        model_file_hashes={
           **{m:common.sha(root/"MODELS"/(m+".ubj")) for m in fitted},
           **({"active_zero_hurdle":common.sha(root/"MODELS"/"active_zero_hurdle.ubj")}
              if active_zero_fit is not None else {}),
           **({"active_zero_platt_calibration":common.sha(
                root/"MODELS"/"active_zero_platt_calibration.json")}
              if active_zero_fit is not None and active_zero_fit[1] is not None else {})},
        week_hashes=hashes,week_counts=week_counts,
        forecasted=sum(week_counts.values()),draws=int(draws),
        all_18_weeks_frozen_before_scoring=True,
        no_2024_player_stats_pbp_ngs_loaded=True,
        roster_2024_verified=False,
        bookmaker_2024_lines_verified=False,
        production_eligible=False)
    common.atomic_new(root/"FROZEN_MANIFEST.json",manifest)
    print("HYBRID_FROZEN_18_WEEK_LOCK",json.dumps({
         "predictions":manifest["forecasted"],"counts":week_counts,
         "model_hashes":manifest["model_file_hashes"],
         "manifest_sha":common.sha(root/"FROZEN_MANIFEST.json")}),flush=True)
    return manifest

def evaluate(root):
    root=Path(root);mf=root/"FROZEN_MANIFEST.json"
    if not mf.is_file():raise RuntimeError("must_freeze_before_evaluate")
    original=json.loads(mf.read_bytes())
    if (original.get("schema")!=SCHEMA
         or original.get("stage")!="all_18_weeks_frozen"
         or original.get("training_cutoff_exclusive")!=TRAIN_END_EXCLUSIVE
         or not original.get("fit_and_hyperparameter_selection_use_only_pre2024")
         or not original.get("all_18_weeks_frozen_before_scoring")
         or original.get("ftndata_used")):
        raise RuntimeError("invalid_strict_cutoff_manifest")
    # Calibrator is saved as JSON, while XGBoost boosters are .ubj.
    # Resolve each frozen artifact to its registered exact filename.
    # Never modify an artifact or silently skip its hash check.
    model_artifacts={
        "pass_attempts":"pass_attempts.ubj",
        "rush_attempts":"rush_attempts.ubj",
        "active_zero_hurdle":"active_zero_hurdle.ubj",
        "active_zero_platt_calibration":"active_zero_platt_calibration.json",
    }
    for market,h in original["model_file_hashes"].items():
        if market not in model_artifacts:
            raise RuntimeError("unrecognized_frozen_model_artifact:"+market)
        path=root/"MODELS"/model_artifacts[market]
        if common.sha(path)!=h:
            raise RuntimeError("frozen_model_changed_after_forecast_lock:"+market)
    rows=[]
    for week in range(1,19):
        path=root/f"FROZEN/2024_week_{week:02d}.json"
        if common.sha(path)!=original["week_hashes"][str(week)]:
            raise RuntimeError("weekly_hybrid_forecast_sha_modified")
        frozen=json.loads(path.read_bytes())
        if frozen["2024_player_results_accessed"] is not False:
            raise RuntimeError("2024_outcomes_accessed_before_freeze")
        if frozen["week"]!=week:raise RuntimeError("week_misassigned")
        for p in frozen["predictions"]:
            if p["model_asof"]!=TRAIN_END_EXCLUSIVE:
                raise RuntimeError("2024_feature_date_in_frozen_forecast")
        rows.extend(frozen["predictions"])
    if len(rows)!=original["forecasted"]:
        raise RuntimeError("incomplete_frozen_forecast_ledger")
    print("HYBRID_ALL_18_WEEK_FORECASTS_LOCKED_BEFORE_2024_LABEL_LOAD",
          len(rows),flush=True)
    # First time 2024 player stats/snap labels can enter this workflow.
    stats,snaps,schedule=fetch_season(2024)
    observed,cov=normalize_season(stats,snaps,schedule,2024,
                                  cutoff="2025-03-01")
    labels={(r["game_id"],str(r["player_id"]),r["stat"]):float(r["value"])
            for r in observed if r["stat"] in priors.VOLUME_MARKETS}
    if len(labels)!=sum(r["stat"] in priors.VOLUME_MARKETS for r in observed):
        raise RuntimeError("duplicate_2024_graded_label")
    result=[]
    for p in rows:
        q=dict(p)
        actual=labels.get((p["game_id"],p["player_id"],p["market"]))
        q["actual_stat"]=actual
        q["graded"]=actual is not None
        if actual is not None:
            # All research lines are half-points; no artificial push logic.
            over=int(actual>p["research_line"])
            q["actual_over"]=over
            for name in ("p_over","p_over_hurdle","p_over_player_prior"):
                pro=p.get(name)
                if pro is None:
                    q[name+"_brier"]=None;q[name+"_hit"]=None
                else:
                    if not 0<=pro<=1:raise RuntimeError("impossible_probability")
                    q[name+"_brier"]=(pro-over)**2
                    q[name+"_hit"]=int((pro>=.5)==bool(over))
        result.append(q)
    common.atomic_new(root/"EVALUATION/all_props.json",result)
    metrics=[]
    for wk in range(1,19):
        for market in (None,*priors.VOLUME_MARKETS):
            candidates=[r for r in result if r["week"]==wk and
                         (market is None or r["market"]==market)]
            matched=[r for r in candidates if r["graded"]]
            m={"week":wk,"market":market or "ALL",
               "forecasted":len(candidates),"graded":len(matched),
               "unmatched":len(candidates)-len(matched)}
            for probname in ("p_over","p_over_hurdle","p_over_player_prior"):
                subset=[r for r in matched if r.get(probname+"_hit") is not None]
                m[probname+"_accuracy"]=(sum(x[probname+"_hit"] for x in subset)/
                       len(subset) if subset else None)
                m[probname+"_brier"]=(sum(x[probname+"_brier"] for x in subset)/
                       len(subset) if subset else None)
                m[probname+"_under_share"]=(sum(x[probname]<.5 for x in subset)/
                       len(subset) if subset else None)
            metrics.append(m)
    graded=[r for r in result if r["graded"]]
    def agg(name):
        chosen=[r for r in graded if r.get(name+"_hit") is not None]
        return {"n":len(chosen),
           "accuracy":sum(r[name+"_hit"] for r in chosen)/len(chosen) if chosen else None,
           "brier":sum(r[name+"_brier"] for r in chosen)/len(chosen) if chosen else None,
           "under_share":sum(r[name]<.5 for r in chosen)/len(chosen) if chosen else None}
    report={"schema":SCHEMA,"training_cutoff_exclusive":TRAIN_END_EXCLUSIVE,
        "active_zero_hurdle_fitted_pre2024":original.get("hurdle_fit_receipt",{}).get("status")=="fitted_pre2024_only",
        "model_was_frozen_before_2024_labels":True,
        "forecasts":len(result),"graded":len(graded),
        "unmatched":len(result)-len(graded),
        "hybrid":agg("p_over"),
        "hybrid_active_zero_hurdle":agg("p_over_hurdle"),
        "player_prior":agg("p_over_player_prior"),
        "always_under_on_graded":sum(r["actual_over"]==0 for r in graded)/
                                    len(graded) if graded else None,
        "weekly_and_market_metrics":metrics,
        "roster_2024_verified":False,"bookmaker_2024_lines_verified":False,
        "research_only_no_production_promotion":True}
    common.atomic_new(root/"EVALUATION/SUMMARY.json",report)
    print("HYBRID_2024_HOLDOUT_SCORE",json.dumps({
      k:v for k,v in report.items() if k!="weekly_and_market_metrics"},
      sort_keys=True),flush=True)
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("stage",choices=("freeze","evaluate"))
    p.add_argument("--root",required=True)
    p.add_argument("--trials",type=int,default=8)
    p.add_argument("--draws",type=int,default=2000)
    a=p.parse_args()
    if a.stage=="freeze":freeze(a.root,trials=a.trials,draws=a.draws)
    else:evaluate(a.root)

if __name__=="__main__":main()
