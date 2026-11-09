#!/usr/bin/env python3
"""NFL 2024 chronological walk-forward, research-only.

Each week: (1) make and SHA-lock the whole week's predictions; (2) reveal
only that week's outcomes through a distinct subprocess; (3) settle; (4)
incorporate observed positive-snap player rows and team PBP; (5) refit two
team XGBoost models and the active-zero classifier using only revealed weeks.

Initially only 2021-23 information and a 2024 game fixture calendar enter
the forecaster. The oracle cache is created *after* Week 1 is locked, and
is accessed only through the oracle_reveal subprocess after each weekly
forecast lock. This is an auditable software firewall, not cryptographic
blindness: the public 2024 dataset already exists. Original 2024 audit
artifacts remain untouched; the new run has a clean directory.

Not sportsbook backtesting. Lines are synthetic, active rosters and bookmaker
quotes are unverified. No 2024 hyperparameter search. No production promotion.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import nfl_pre2024_xgb_replay as common
import nfl_pre2024_hybrid_bayesian_mc as hybrid
import nfl_pre2024_team_defense_challenger as priors
import nfl_pre2024_team_volume_xgb as teamxgb
import nfl_pre2024_active_zero_hurdle as zero
from population_nfl import fetch_season, normalize_season

SCHEMA = "nfl_2024_weekly_expanding_training_after_results_v1"
TRAIN_END = "2024-01-01"
EXTENDED_BOUNDARY = date(2025, 2, 1)
BASE = "pickem_runs/2024_hybrid_activezero_pre2024_numpy2_clean_v3"
MARKETS = ("p_over", "p_over_hurdle", "p_over_player_prior", "p_over_static_player")
MODEL_FILES = {
    "pass_attempts": "pass_attempts.ubj",
    "rush_attempts": "rush_attempts.ubj",
    "active_zero_hurdle": "active_zero_hurdle.ubj",
    "active_zero_platt_calibration": "active_zero_platt_calibration.json",
}


def day(x):
    return date.fromisoformat(str(x)[:10])


def reject_future(rows, boundary, *, key="game_date"):
    """Guard before fitting, scoring features, or appending a new week."""
    b = day(boundary)
    for r in rows:
        if day(r[key]) >= b:
            raise RuntimeError("future_week_label_or_feature_in_model_state")
    return True


def calendar_week(fixtures):
    by = collections.defaultdict(list)
    for fixture in fixtures:
        by[int(fixture["week"])].append(fixture)
    if set(by) != set(range(1, 19)):
        raise RuntimeError("incomplete_18_week_schedule")
    for w in by:
        by[w].sort(key=lambda r: r["game_id"])
    return by


def lock_sha(root, week):
    path = root / "FROZEN" / ("week_%02d.json" % week)
    if not path.is_file():
        raise RuntimeError("oracle_reveal_before_forecast_lock")
    locked = json.loads(path.read_bytes())
    if locked["week"] != week or locked.get("stage") != "before_week_outcomes":
        raise RuntimeError("invalid_frozen_forecast_before_reveal")
    return common.sha(path)


def oracle_prepare(root, vault):
    """Privileged stage, never imported/called from the forecasting model."""
    if not lock_sha(root, 1):
        raise RuntimeError("must_lock_week1_before_2024_label_download")
    if vault.exists():
        raise RuntimeError("oracle_vault_exists_refuse_overwrite")
    import nflreadpy
    import nfl_pre2024_pbp_ngs_sources as pbp_utils

    fixtures = common.frozen_2024_schedule_only()
    allowed = {str(f["game_id"]): str(f["gameday"]) for f in fixtures}
    stats, snaps, schedule = fetch_season(2024)
    observed, cov = normalize_season(stats, snaps, schedule, 2024, cutoff="2025-02-01")
    obs = [r for r in observed if r["game_id"] in allowed and r["stat"] in priors.VOLUME_MARKETS]
    df = nflreadpy.load_pbp(seasons=[2024])
    missing = set(common.PBP_COLUMNS) - set(df.columns)
    if missing:
        raise RuntimeError("oracle_2024_pbp_columns_missing:" + str(sorted(missing)))
    slim = df.select(list(common.PBP_COLUMNS)).to_dicts()
    del df
    pbp_utils.CUTOFF = EXTENDED_BOUNDARY
    pbp_utils.TRAINING_SEASONS = (2024,)
    positions = {str(r["player_id"]): str(r["position"])
                 for r in obs if r["stat"] == "targets"}
    team_games, pbp_coverage = pbp_utils.aggregate_games(
        slim, allowed, player_position=positions, ftn_rows=())
    byweek = collections.defaultdict(lambda: {"players": [], "team_games": []})
    gid_week = {f["game_id"]: int(f["week"]) for f in fixtures}
    for r in obs:
        byweek[gid_week[r["game_id"]]]["players"].append(r)
    for r in team_games:
        byweek[int(r["week"])]["team_games"].append(r)
    if any(w not in byweek for w in range(1, 19)):
        raise RuntimeError("oracle_2024_missing_week")
    out = {
        "schema": SCHEMA + "_private_oracle",
        "created_only_after_week1_frozen_sha": lock_sha(root, 1),
        "data_from": "nflreadpy player_stats/snaps/PBP weekly player and team aggregates",
        "play_by_play_coverage": pbp_coverage,
        "player_normalization_coverage": cov,
        "weeks": {str(w): byweek[w] for w in range(1, 19)},
    }
    vault.mkdir(parents=True, exist_ok=False)
    common.atomic_new(vault / "oracle_2024.json", out)
    print("ORACLE_PREPARED_AFTER_WEEK1_LOCK",
          json.dumps({"players":len(obs),"team_games":len(team_games),
                      "weeks":18,"frozen_sha":lock_sha(root, 1)}), flush=True)


def oracle_reveal(root, vault, week):
    """Output ONLY the explicitly locked week's stats; other weeks stay sealed."""
    locked_sha = lock_sha(root, week)
    if (root / "REVEALED" / ("week_%02d.json" % week)).exists():
        raise RuntimeError("reveal_not_idempotent_repeated_week")
    raw = json.loads((vault / "oracle_2024.json").read_bytes())
    if raw["schema"] != SCHEMA + "_private_oracle":
        raise RuntimeError("unregistered_outcome_vault")
    payload = raw["weeks"][str(week)]
    if any(int(r["season"]) != 2024 or
           int(str(r["game_id"]).split("_")[1]) != week
           for r in payload["players"]):
        raise RuntimeError("oracle_player_week_cross_contamination")
    if any(int(r["season"]) != 2024 or int(r["week"]) != week
           for r in payload["team_games"]):
        raise RuntimeError("oracle_pbp_week_cross_contamination")
    print(common.canonical({
        "week": week, "frozen_sha": locked_sha, "players":payload["players"],
        "team_games":payload["team_games"]}).decode())


def oracle_get_one_week(root, vault, week):
    """Only this child process is permitted to read the sealed future results."""
    proc = subprocess.run(
        [sys.executable, "-u", str(Path(__file__).resolve()), "oracle_reveal",
         "--root",str(root),"--vault",str(vault),"--week",str(week)],
        capture_output=True,text=True,check=True,timeout=180)
    payload = json.loads(proc.stdout)
    if payload["week"] != week or payload["frozen_sha"] != lock_sha(root,week):
        raise RuntimeError("oracle_reveal_not_matching_week_frozen_sha")
    return payload


def online_roster(state, teams):
    """Use last observed 2024 positive-snap appearance; 2023 ONLY in Week 1."""
    asof = hybrid.CUTOFF
    out = {t: [] for t in teams}
    has_2024 = any(r["season"] == 2024 and day(r["gameday"]) < asof
                   for r in state["latest_by_player"].values())
    for pid, r in state["latest_by_player"].items():
        if r["team"] not in out or day(r["gameday"]) >= asof:
            continue
        age = (asof - day(r["gameday"])).days
        if r["season"] == 2024:
            if age <= 75:
                out[r["team"]].append((str(pid),r["position"]))
        elif not has_2024 and r["season"] == 2023 and age <= 420:
            out[r["team"]].append((str(pid),r["position"]))
    for team in out:
        out[team].sort()
    return out


def assert_player_state_past(state):
    boundary = hybrid.CUTOFF
    for key in ("player","role","team_offense","opponent_allowed",
                "league_offense","ngs"):
        for bucket in state[key].values():
            for row in bucket:
                if day(row["gameday"]) >= boundary:
                    raise RuntimeError("unrevealed_or_same_week_history_in_model")
                if row.get("season",2023) > 2024:
                    raise RuntimeError("invalid_posterior_season")
    return True


def set_forecast_asof(week_start):
    """Use a single snapshot before the *first* fixture of the slate."""
    global dynamic_week
    dynamic_week = day(week_start)
    hybrid.CUTOFF = dynamic_week
    priors.CUTOFF = dynamic_week
    zero.CUTOFF = dynamic_week
    teamxgb.CUTOFF = EXTENDED_BOUNDARY
    hybrid._pre2024_only = assert_player_state_past
    hybrid.previous_roster = online_roster


def append_player_team_week(state,players,teams):
    """Append only observed, positive-snap normalized rows after week settlement."""
    existing = set()
    for r in players:
        if r["stat"] not in priors.VOLUME_MARKETS:
            continue
        if r["position"] not in priors.ROLE_POS[r["stat"]]:
            continue
        if float(r.get("workload",0)) < 1:
            continue
        pid = str(r["player_id"])
        key=(r["game_id"],pid,r["stat"])
        if key in existing:
            raise RuntimeError("duplicate_revealed_player_stat")
        existing.add(key)
        x={"gameday":str(r["game_date"]),"game_date":str(r["game_date"]),
           "value":float(r["value"]),"workload":float(r["workload"]),
           "position":r["position"],"team":r["team"],"season":2024}
        state["player"][(r["stat"],pid)].append(x)
        state["role"][(r["stat"],r["position"])].append(x)
        prev=state["latest_by_player"].get(pid)
        if prev is None or str(r["game_date"])>prev["gameday"]:
            state["latest_by_player"][pid]={
              "gameday":str(r["game_date"]),"team":r["team"],
              "position":r["position"],"season":2024}
    for row in teams:
        team,opp,dt=row["team"],row["opponent"],str(row["gameday"])
        for metric in set(priors.MARKET_TEAM_METRIC.values()) | {
            "short_pass_attempts","short_rb_targets","neutral_passes",
            "neutral_rushes","pass_completions","qb_hits","charted_checkdowns",
            "charted_dropbacks","passing_yards","rushing_yards"}:
            item={"gameday":dt,"value":float(row.get(metric,0.))}
            state["team_offense"][(metric,team)].append(item)
            state["opponent_allowed"][(metric,opp)].append(item)
            state["league_offense"][metric].append(item)
    state["team_games"]+=len(teams)
    return len(existing)


def zero_new_rows_before_reveal_update(state,context,players,week):
    """Build Week-N train features using *only* data through Week N-1."""
    out=[]
    seen=set()
    for r in players:
        stat=r["stat"]
        if stat not in zero.MARKETS or r["position"] not in zero.POSITION_ID:
            continue
        if float(r.get("workload",0))<1:
            continue
        pid=str(r["player_id"])
        k=(r["game_id"],pid,stat)
        if k in seen: raise RuntimeError("duplicate_2024_zero_label")
        seen.add(k)
        if float(r["value"])<0 or not float(r["value"]).is_integer():
            raise RuntimeError("invalid_hurdle_week_label")
        x=zero.features(state,context,market=stat,pid=pid,
            position=r["position"],team=r["team"],opponent=r["opponent"],
            asof=r["game_date"],season=2024,week=week)
        if x is None:continue
        out.append({"x":x.tolist(),"y":int(float(r["value"])==0),
                    "gameday":str(r["game_date"]),"week":week})
    return out


def load_base(root):
    # The old immutable run supplies ONLY models fitted on pre2024 data.
    base = root.parent / Path(BASE).name
    manifest = json.loads((base / "FROZEN_MANIFEST.json").read_bytes())
    if manifest["training_cutoff_exclusive"] != TRAIN_END:
        raise RuntimeError("base_model_contains_post2023_training")
    if not manifest["fit_and_hyperparameter_selection_use_only_pre2024"]:
        raise RuntimeError("base_parameters_not_pre2024_only")
    for key,filename in MODEL_FILES.items():
        expected=manifest["model_file_hashes"].get(key)
        if expected is None or common.sha(base / "MODELS" / filename)!=expected:
            raise RuntimeError("base_model_sha_mismatch:"+key)
    import xgboost as xgb
    from sklearn.linear_model import LogisticRegression
    fitted = {}
    for key in teamxgb.TARGETS:
        mdl=teamxgb._model(manifest["team_xgboost_fit_receipts"][key]["best_params"])
        mdl.load_model(str(base / "MODELS" / MODEL_FILES[key]))
        fitted[key]=mdl
    z=xgb.XGBClassifier()
    z.load_model(str(base / "MODELS" / "active_zero_hurdle.ubj"))
    dat=json.loads((base / "MODELS" / "active_zero_platt_calibration.json").read_bytes())
    cal=LogisticRegression()
    cal.classes_=np.asarray(dat["classes"])
    cal.coef_=np.asarray(dat["coef"],dtype=float)
    cal.intercept_=np.asarray(dat["intercept"],dtype=float)
    cal.n_features_in_=1
    cal.n_iter_=np.asarray([1],dtype=np.int32)
    return manifest,fitted,(z,cal),base


def score(rows,labels):
    lookup={(r["game_id"],str(r["player_id"]),r["stat"]):float(r["value"])
            for r in labels if r["stat"] in priors.VOLUME_MARKETS}
    graded=[]
    results=[]
    for p in rows:
        q=dict(p)
        true=lookup.get((p["game_id"],p["player_id"],p["market"]))
        q["actual_stat"]=true
        q["graded"]=true is not None
        if true is not None:
            q["actual_over"]=int(true>p["research_line"])
            graded.append(q)
        results.append(q)
    return results,graded


def metrics(rows):
    result={"graded":len(rows)}
    if not rows:
        return result
    result["always_under"]=sum(not r["actual_over"] for r in rows)/len(rows)
    for key in MARKETS:
        sub=[r for r in rows if r.get(key) is not None]
        if sub:
            result[key]={"n":len(sub),
                "accuracy":sum((r[key]>=.5)==bool(r["actual_over"]) for r in sub)/len(sub),
                "brier":sum((r[key]-r["actual_over"])**2 for r in sub)/len(sub),
                "under_share":sum(r[key]<.5 for r in sub)/len(sub)}
    return result


def dynamic_model_hashes(model_paths):
    return {name:common.sha(path) for name,path in model_paths.items()}


def refit_with_prior_params(manifest,team_games,ngs,historical_zero,weekly_zero):
    """Refit actual XGBoost parameters weekly; don't retune against 2024."""
    import xgboost as xgb
    teamxgb.CUTOFF=EXTENDED_BOUNDARY
    index=teamxgb.build_index(team_games,ngs)
    train=teamxgb.training_rows(team_games,index)
    fitted={}
    for market in teamxgb.TARGETS:
        params=manifest["team_xgboost_fit_receipts"][market]["best_params"]
        X=np.asarray([r["x"] for r in train[market]],dtype=np.float32)
        y=np.asarray([r["y"] for r in train[market]],dtype=np.float32)
        if len(y)<1598:
            raise RuntimeError("unexpected_team_training_size")
        model=teamxgb._model(params)
        model.fit(X,y)
        fitted[market]=model
    # Historical out-of-fold Platt calibrator stays frozen and is not
    # refit on same-week labels (which would contaminate later calibration).
    params=manifest["hurdle_fit_receipt"]["best_params"]
    z=xgb.XGBClassifier(objective="binary:logistic",tree_method="hist",
                        random_state=zero.SEED,n_jobs=2,verbosity=0,
                        eval_metric="logloss",**params)
    samples=historical_zero+weekly_zero
    X=np.asarray([s["x"] for s in samples],dtype=np.float32)
    y=np.asarray([s["y"] for s in samples],dtype=np.int32)
    if len(y)<70000 or len(set(y.tolist()))!=2:
        raise RuntimeError("invalid_expanding_hurdle_training_population")
    z.fit(X,y)
    return fitted,z,{"team_rows":len(train["pass_attempts"]),
                      "zero_rows":len(samples),"zero_2024_rows":len(weekly_zero),
                      "team_2024_rows":sum(int(r["season"])==2024 for r in team_games)}


def forecast_one_week(state,static_state,context,index,base_index,
                      fitted,frozen_fitted,zhurdle,static_hurdle,
                      manifest,fixtures,draws,week_start):
    pred=[]
    dispersions={m:manifest["team_xgboost_fit_receipts"][m]["dispersion"]
                 for m in teamxgb.TARGETS}
    set_forecast_asof(week_start)
    for fixture in fixtures:
        home,away=fixture["home_team"],fixture["away_team"]
        means={t:teamxgb.project(fitted,index,t,opp,home=(t==home),week=int(fixture["week"]))
               for t,opp in ((home,away),(away,home))}
        frozen_means={t:teamxgb.project(frozen_fitted,base_index,t,opp,
                 home=(t==home),week=int(fixture["week"]))
               for t,opp in ((home,away),(away,home))}
        k={t:dispersions for t in (home,away)}
        pure,_=hybrid.summarize_game(state,fixture,means,k,draws=draws)
        h,_=hybrid.summarize_game(state,fixture,means,k,draws=draws,
                 active_zero_model=zhurdle,hurdle_context=context)
        by={(r["player_id"],r["market"]):r for r in h}
        if len(by)!=len(pure):
            raise RuntimeError("weekly_hurdle_candidate_universe_mismatch")
        for q in pure:
            ident=(q["player_id"],q["market"])
            if ident not in by:
                raise RuntimeError("weekly_hurdle_prop_mismatch")
            q["p_over_hurdle"]=by[ident]["p_over"]
            q["p_zero_active_hurdle_simulated"]=by[ident]["p_zero_active_simulated"]
            # Non-updating 2023 player prior on exactly the SAME week's
            # synthetic line. Missing static player means abstention.
            ref,ev=priors.predict(static_state,stat=q["market"],
                  player_id=q["player_id"],position=q["position"],
                  team=q["team"],
                  opponent=(away if q["team"]==home else home),
                  asof=TRAIN_END,variant="player_only")
            q["p_over_static_player"]=(priors.prob_over(ref,q["research_line"],q["market"])
                                       if ref is not None else None)
            mean,evi=priors.predict(state,stat=q["market"],
                   player_id=q["player_id"],position=q["position"],
                   team=q["team"],
                   opponent=(away if q["team"]==home else home),
                   asof=week_start,variant="player_only")
            q["p_over_player_prior"]=(
                priors.prob_over(mean,q["research_line"],q["market"])
                if mean is not None else None)
            q["model_asof"]=week_start
            q["forecast_week"]=int(fixture["week"])
            q["training_last_revealed_week"]=int(fixture["week"])-1
            q["training_data_from_2024"]=int(fixture["week"])>1
            q["roster_2024_verified"]=False
            q["bookmaker_quote_verified"]=False
            q["team_xgb_pass_mean"]=means[q["team"]]["pass_attempts"]
            q["team_xgb_rush_mean"]=means[q["team"]]["rush_attempts"]
        pred.extend(pure)
    pred.sort(key=lambda p:(p["game_id"],p["player_id"],p["market"]))
    keys=[(r["game_id"],r["player_id"],r["market"]) for r in pred]
    if len(keys)!=len(set(keys)):
        raise RuntimeError("duplicate_weekly_synthetic_contract")
    return pred


def run(root,*,draws=750):
    if root.exists():
        raise RuntimeError("refuse_existing_walkforward_root_preserve_prior_results")
    vault=root.with_name(root.name+"__PRIVATE_2024_ORACLE")
    if vault.exists():
        raise RuntimeError("refuse_preexisting_2024_oracle_vault")
    root.mkdir(parents=True)
    prior_manifest,base_fitted,original_hurdle,base=load_base(root)
    print("WALKFORWARD_BASE_VERIFIED",json.dumps({
      "cutoff":TRAIN_END,"base_model_hashes":prior_manifest["model_file_hashes"],
      "uses_2024_fitted_parameters":False}),flush=True)

    # The forecaster loads 2021-23 labels only. No 2024 result reader yet.
    rows,team_games,ngs,receipts=common.pre2024_sources()
    static_state=priors.historical_sources(rows,team_games,ngs)
    dynamic_state=priors.historical_sources(rows,team_games,ngs)
    import nflverse_pre2024_hurdle_gateway as gateway
    context=gateway.load_nflreadpy_strict_pre2024_context(
                    include_participation=True,include_injuries=True)
    # Historical hurdle features must be built with the ORIGINAL strict
    # pre2024 cutoff and untouched first, to forbid 2024 outcomes.
    zero.CUTOFF=date(2024,1,1)
    historical_zero_raw=zero.make_training_rows(dynamic_state,context,rows)
    historical_zero=[{"x":r["x"],"y":r["zero"]} for r in historical_zero_raw]
    if len(historical_zero)!=prior_manifest["hurdle_fit_receipt"]["sample_n"]:
        raise RuntimeError("historical_hurdle_feature_universe_changed")
    print("WALKFORWARD_PRE2024_STATE",json.dumps({
        "player_market_rows":len(rows),"team_games":len(team_games),
        "historical_hurdle_rows":len(historical_zero),
        "data_cutoff":"2024-01-01 exclusive"}),flush=True)
    del rows,historical_zero_raw
    schedule=calendar_week(common.frozen_2024_schedule_only())
    weekly_zero=[]
    curr_fitted=dict(base_fitted)
    curr_hurdle=original_hurdle
    base_index=teamxgb.build_index(team_games,ngs)
    index=base_index
    original_model_paths={k:base/"MODELS"/filename for k,filename in MODEL_FILES.items()}
    input_model_paths=original_model_paths
    week_metrics=[]
    all_graded=[]
    for week in range(1,19):
        start=min(x["gameday"] for x in schedule[week])
        end=max(x["gameday"] for x in schedule[week])
        if start < TRAIN_END:
            raise RuntimeError("2024_calendar_before_model_train_cutoff")
        reject_future([{"game_date":r["gameday"]}
              for r in team_games if int(r["season"])==2024],start)
        # Protect against an unordered 2024 calendar; no after-week refits
        # may influence a previous-week simulation.
        set_forecast_asof(start)
        assert_player_state_past(dynamic_state)
        predictions=forecast_one_week(dynamic_state,static_state,context,
            index,base_index,curr_fitted,base_fitted,curr_hurdle,original_hurdle,
            prior_manifest,schedule[week],draws,start)
        hashes=dynamic_model_hashes(input_model_paths)
        frozen_sha=common.atomic_new(
            root/"FROZEN"/("week_%02d.json"%week),
            {"schema":SCHEMA,"stage":"before_week_outcomes","week":week,
             "forecast_asof":start,"latest_revealed_week":week-1,
             "training_label_week_limit":week-1,"predictions":predictions,
             "models_input_sha":hashes,
             "future_2024_week_data_accessed_by_forecaster":False,
             "research_only":True})
        print("WEEK_FROZEN",json.dumps({
            "week":week,"forecasts":len(predictions),"forecast_sha":frozen_sha,
            "training_up_through_week":week-1,"fitted_model_sha":hashes}),flush=True)
        if week==1:
            proc=subprocess.run(
                [sys.executable,"-u",str(Path(__file__).resolve()),
                 "oracle_prepare","--root",str(root),"--vault",str(vault)],
                capture_output=True,text=True,timeout=900)
            print(proc.stdout[-3000:],flush=True)
            if proc.returncode:
                raise RuntimeError("oracle_prepare_failed:"+proc.stderr[-4500:])
        revealed=oracle_get_one_week(root,vault,week)
        observed=revealed["players"]
        team_week=revealed["team_games"]
        if any(r["game_date"] < start or r["game_date"] > end for r in observed):
            raise RuntimeError("weekly_outcome_calendar_mismatch")
        graded_rows,graded=score(predictions,observed)
        s=metrics(graded)
        all_graded.extend(graded)
        receipt=common.atomic_new(
            root/"REVEALED"/("week_%02d.json"%week),
            {"week":week,"frozen_sha":frozen_sha,
             "actuals_revealed_after_sha_lock":True,
             "player_week_rows":len(observed),
             "team_games":len(team_week),"score":s,
             "full_research_rows":graded_rows})
        # Build train features from ONLY past weeks, before adding new
        # observed player rows to historical features. For the final game
        # within a slate the next week is the training boundary.
        zero.CUTOFF=day(end)+timedelta(days=1)
        new_hurdle=zero_new_rows_before_reveal_update(
                      dynamic_state,context,observed,week)
        # Exposure-missing and non-active rows are never synthetic zeros.
        appended=append_player_team_week(dynamic_state,observed,team_week)
        team_games.extend(team_week)
        weekly_zero.extend(new_hurdle)
        fitted_new,model_zero,training=refit_with_prior_params(
                     prior_manifest,team_games,ngs,historical_zero,weekly_zero)
        dest=root/"UPDATED_MODELS"/("after_week_%02d"%week)
        dest.mkdir(parents=True,exist_ok=False)
        input_model_paths={}
        for market,mdl in fitted_new.items():
            path=dest/(market+".ubj")
            mdl.save_model(str(path))
            input_model_paths[market]=path
        zpath=dest/"active_zero_hurdle.ubj"
        model_zero.save_model(str(zpath))
        input_model_paths["active_zero_hurdle"]=zpath
        # frozen pre2024 OOF calibrator remains unchanged
        input_model_paths["active_zero_platt_calibration"] = original_model_paths[
                        "active_zero_platt_calibration"]
        update_sha=common.atomic_new(root/"UPDATES"/("after_week_%02d.json"%week),
            {"schema":SCHEMA,"updated_after_revealed_week":week,
             "locked_forecast_sha":frozen_sha,"revealed_score_sha":receipt,
             "2024_training_seasons_weeks":list(range(1,week+1)),
             "trained_team_records":training["team_rows"],
             "trained_hurdle_records":training["zero_rows"],
             "2024_hurdle_train_records":training["zero_2024_rows"],
             "2024_team_train_records":training["team_2024_rows"],
             "observed_positive_snap_player_stat_rows_appended":appended,
             "model_hashes":dynamic_model_hashes(input_model_paths),
             "hyperparameters_from_2023_frozen_no_2024_tpe":True,
             "calibrator_pre2024_unchanged":True})
        curr_fitted=fitted_new
        curr_hurdle=(model_zero,original_hurdle[1])
        teamxgb.CUTOFF=EXTENDED_BOUNDARY
        index=teamxgb.build_index(team_games,ngs)
        week_score={"week":week,"forecasted":len(predictions),
                    "matched":len(graded),"unmatched":len(predictions)-len(graded),
                    "revealed_rows":len(observed),"update_sha":update_sha,
                    **s}
        week_metrics.append(week_score)
        common.atomic_new(root/"WEEKLY_REPORTS"/("week_%02d.json"%week),week_score)
        print("WEEK_SCORED_AND_TRAINED",json.dumps(week_score),flush=True)
    result={"schema":SCHEMA,"complete":True,"train_initial_before":TRAIN_END,
            "no_future_week_labels_in_fits":True,"weeks":week_metrics,
            "forecasts":sum(r["forecasted"] for r in week_metrics),
            "graded":len(all_graded),"overall":metrics(all_graded),
            "rosters_verified":False,"bookmaker_lines_verified":False,
            "research_only_no_production_promotion":True}
    common.atomic_new(root/"FINAL_SUMMARY.json",result)
    print("WALKFORWARD_2024_COMPLETE",json.dumps({
        k:v for k,v in result.items() if k!="weeks"},sort_keys=True),flush=True)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["run","oracle_prepare","oracle_reveal"])
    parser.add_argument("--root",required=True)
    parser.add_argument("--vault")
    parser.add_argument("--week",type=int)
    parser.add_argument("--draws",type=int,default=750)
    a=parser.parse_args()
    root=Path(a.root).resolve()
    if a.action=="run":
        run(root,draws=a.draws)
    else:
        if not a.vault:raise RuntimeError("private_oracle_vault_path_required")
        vault=Path(a.vault).resolve()
        if a.action=="oracle_prepare":
            oracle_prepare(root,vault)
        else:
            if a.week not in range(1,19):
                raise ValueError("oracle_requested_week_out_of_range")
            oracle_reveal(root,vault,a.week)


if __name__ == "__main__":
    main()
