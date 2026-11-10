#!/usr/bin/env python3
"""2024 NFL prequential confidence repair, fully frozen as-of child processes.

Research-only; 2024 was previously inspected and is NOT untouched model
validation. No sources for true current-game routes or verified active roster.
No live props, market value, payouts or Tier authority.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, Counter
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time

import numpy as np

from v25_phase2_target_only_2024_replay import (
    H,fail,normalise_pre2024,load_2024_oracle,frozen_lines,crps
)
from v25_phase2_participation_source_bridge import collect_nfl_source_context, build_asof_context

SCRIPT = Path(__file__).resolve().parent
FORECASTER = SCRIPT / "v25_phase2_participation_snap_forecast.py"
CALIBRATOR = SCRIPT / "v25_phase2_online_probability_calibration.py"
MODELS=("updated","no_refit","independent_poisson","participation_snap","participation_no_hurdle")
CALIBRATABLE=("updated","participation_snap","participation_no_hurdle")
CALMODES=("raw","global_platt","role_platt")
THRESHOLDS=(.7,.8,.9,.95)


def mean(s):
    return statistics.fmean(s) if s else None


def _metric(rows):
    if not rows:return {"n":0}
    return {
      "n":len(rows),
      "crps":mean([z["crps"] for z in rows if "crps" in z]),
      "mae":mean([z["mae"] for z in rows if "mae" in z]),
      "brier":mean([z["brier"] for z in rows if "brier" in z]),
      "log_loss":mean([z["log_loss"] for z in rows if "log_loss" in z]),
      "mean_targets_predicted":mean([z["mean_predicted"] for z in rows if "mean_predicted" in z]),
      "mean_targets_actual":mean([z["actual"] for z in rows if "actual" in z]),
      "signed_target_bias_pred_minus_actual":mean([
          z["mean_predicted"]-z["actual"] for z in rows
          if "mean_predicted" in z and "actual" in z]),
    }


def _confidence(rows, cutoff):
    eligible=[x for x in rows if x.get("probability") is not None
              and x.get("actual_over") is not None
              and x.get("probability")!=.5]
    chosen=[x for x in eligible if max(x["probability"],
            1.-x["probability"])>=cutoff]
    n=len(chosen)
    return {"n":n,
      "n_over":sum(r["probability"]>.5 for r in chosen),
      "n_under":sum(r["probability"]<.5 for r in chosen),
      "hit_rate":mean([int((r["probability"]>.5)==bool(r["actual_over"]))
                       for r in chosen]),
      "mean_claimed_confidence":mean([max(r["probability"],
                                   1.-r["probability"]) for r in chosen]),
      "mean_predicted_targets":mean([r["mean_predicted"] for r in chosen]),
      "mean_actual_targets":mean([r["actual"] for r in chosen]),
    }


def _paired(new,old,measure,seed,clusters=18):
    key=lambda r:(r["week"],r["event_id"],r["team"],r["player_id"])
    left={key(r):r for r in new if r.get(measure) is not None}
    right={key(r):r for r in old if r.get(measure) is not None}
    both=sorted(set(left)&set(right))
    by_week=defaultdict(list)
    for k in both:
        by_week[k[0]].append(left[k][measure]-right[k][measure])
    differences=[v for w in by_week.values() for v in w]
    out={
      "n":len(both),
      "new_minus_reference":mean(differences),
      "weeks_with_improvement":sum(mean(v)<0 for v in by_week.values()),
      "n_week_clusters":len(by_week),
      "descriptive_only":True,
    }
    if len(by_week)==18:
        rng=random.Random(seed)
        actual_week_ids=sorted(by_week)
        boot=[]
        for rep in range(1500):
            selected=rng.choices(actual_week_ids,k=clusters)
            x=[d for w in selected for d in by_week[w]]
            boot.append(mean(x))
        boot.sort()
        out["week_cluster_95"]=[boot[37],boot[1462]]
    else:
        out["week_cluster_95"]=None
    return out


def _score_binary(p,y):
    if not 0<=p<=1 or y not in (0,1):fail("invalid_binary_score_input")
    return {
      "brier":(p-y)**2,
      "log_loss":-y*math.log(max(1e-9,p))-(1-y)*math.log(max(1e-9,1-p)),
      "probability":p,
    }


def _write_once(file,obj):
    with file.open("x",encoding="utf8") as f:
        json.dump(obj,f,sort_keys=True,separators=(",",":"),allow_nan=False)
    return hashlib.sha256(file.read_bytes()).hexdigest()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--samples",type=int,default=512)
    parser.add_argument("--seed",type=int,default=20261110)
    args=parser.parse_args(argv)
    if args.output_dir.exists():parser.error("immutable_repair_output_dir_already_exists")
    import nflreadpy
    pre,coverage=normalise_pre2024(nflreadpy)
    sources=collect_nfl_source_context(nflreadpy)
    print("ASOF_SOURCE_INPUT_COUNTS",json.dumps(sources["counts"],sort_keys=True),flush=True)
    oracle,schedules,oracle_sha=load_2024_oracle(args.root)
    lines,universe,orig_sha=frozen_lines(args.root)
    args.output_dir.mkdir(parents=True)
    past=list(pre)
    calib_hist={model:[] for model in CALIBRATABLE}
    scored={model:[] for model in MODELS}
    calibrated={model:{cal:[] for cal in CALMODES}
                for model in CALIBRATABLE}
    weekly=[];receipts=[];numerics=Counter()
    for week in range(1,19):
        if max((x["week"] for x in past if x["season"]==2024),default=0)!=week-1:
            fail("prequential_training_history_cutoff_wrong")
        # The only fields passed to a forecasting process are the BEFORE-week
        # historical observations and the outcome-free current schedule.
        inp={"schema":"v25-p2-target-only-asof-week-v1","week":week,
             "history":past,"schedule":schedules[week],
             **build_asof_context(sources,week,schedules[week])}
        if any(x["season"]==2024 and x["week"]>=week for x in inp["history"]):
            fail("future_training_outcome_during_week_forecast")
        if any(set(x)!={"event_id","team","opponent","week"}
               for x in inp["schedule"]):
            fail("outcome_in_child_schedule")
        input_file=args.output_dir/f"week_{week:02}_asof_model_input.json"
        forecast_file=args.output_dir/f"week_{week:02}_frozen_model.json"
        asof_sha=_write_once(input_file,inp)
        completed=subprocess.run([sys.executable,str(FORECASTER),
            "--input",str(input_file),"--output",str(forecast_file),
            "--seed",str(args.seed),"--samples",str(args.samples)],
            capture_output=True,text=True,timeout=480)
        if completed.returncode:
            fail("forecast_subprocess_week_"+str(week)+":"+
                 completed.stderr[-2200:])
        prediction=json.loads(forecast_file.read_bytes())
        if (prediction["train_2024_max_week"]!=week-1
                or prediction["current_or_future_game_stats_exposed"] is not False
                or prediction["original_file_bytes_sha256"]!=asof_sha):
            fail("frozen_prediction_input_or_time_mismatch")
        frozen_digest=hashlib.sha256(forecast_file.read_bytes()).hexdigest()
        # All current diagnostic lines are inherited from the OLDER frozen
        # weekly quote universe. They are not sportsbook quotes. They are
        # available to the calibrator but never to the target generator.
        offers={model:[] for model in CALIBRATABLE}
        scenario_index={}
        feature_roles={}
        for team in prediction["forecasts"]:
            identity=(team["event_id"],team["team"])
            for model in MODELS:
                key=("updated" if model=="independent_poisson" else model)
                obj=team["models"][key]
                if obj["status"] not in (
                   "shadow_target_allocation_without_routes",
                   "retrospective_participation_snap_challenger_not_certified"):
                    continue
                if model in ("updated","no_refit","independent_poisson"):
                    forecast_player=("independent_poisson_targets"
                                     if model=="independent_poisson" else "player_targets")
                else:
                    forecast_player="player_targets"
                targets=obj[forecast_player]
                asof_roles=team["models"]["participation_snap"].get("player_roles",{})
                for pid,arr in targets.items():
                    scenario_index[(model,*identity,pid)]=arr
                    if pid in asof_roles:
                        feature_roles[(model,*identity,pid)]=asof_roles[pid]
            for (event,tm,pid),line in lines[week].items():
                if (event,tm)!=identity:continue
                for model in CALIBRATABLE:
                    key=(model,event,tm,pid)
                    if key not in scenario_index:continue
                    role=feature_roles.get(key)
                    if role not in ("WR","RB","TE"):continue
                    arr=scenario_index[key]
                    over=sum(v>line for v in arr)
                    under=sum(v<line for v in arr)
                    if not over+under:
                        numerics["all_push_prediction_not_calibratable"]+=1
                        continue
                    offers[model].append({
                        "event_id":event,"team":tm,"player_id":pid,
                        "role":role,"raw_over":over/(over+under)})
        calib_input={
            "schema":"v25-p2-calibration-asof-input-v1","week":week,
            "history":calib_hist,"offers":offers,
        }
        # Every historical calibration row must be from a PREVIOUS week and
        # current offers must never contain settlement labels.
        for rows in calib_input["history"].values():
            if any(x["week"]>=week for x in rows):
                fail("calibration_future_outcome_leak")
        if any("actual_over" in x for rows in calib_input["offers"].values() for x in rows):
            fail("current_outcome_entered_calibration_input")
        cal_in=args.output_dir/f"week_{week:02}_asof_calibrator_input.json"
        cal_out=args.output_dir/f"week_{week:02}_frozen_calibration.json"
        cal_in_sha=_write_once(cal_in,calib_input)
        proc=subprocess.run([sys.executable,str(CALIBRATOR),
            "--input",str(cal_in),"--output",str(cal_out)],
            capture_output=True,text=True,timeout=240)
        if proc.returncode:
            fail("calibration_subprocess_week_"+str(week)+":"+proc.stderr[-2100:])
        receipt=json.loads(cal_out.read_bytes())
        if receipt["original_calibrator_input_sha256"]!=cal_in_sha:
            fail("frozen_calibrator_input_hash_mismatch")
        for model,by_method in receipt["models"].items():
            for cal,block in by_method.items():
                if block["trained_on_latest_week"]>=week:
                    fail("calibrator_trained_on_future_label")
        calib_result_sha=hashlib.sha256(cal_out.read_bytes()).hexdigest()
        qindex={}
        for model,methods in receipt["models"].items():
            for cal,v in methods.items():
                for offer in v["probabilities"]:
                    k=(model,cal,offer["event_id"],offer["team"],offer["player_id"])
                    qindex[k]=offer["calibrated_over"]
        # Reveal CURRENT week only AFTER both prediction and calibration
        # are complete, frozen and hashed. This result is never used inside
        # either child process.
        reveal={(r["event_id"],r["team"]):r for r in oracle[week]}
        current_score={model:[] for model in MODELS}
        current_cal={model:{mode:[] for mode in CALMODES}
                     for model in CALIBRATABLE}
        for (model,event,team,pid),draws in scenario_index.items():
            key=(event,team,pid)
            line=lines[week].get(key)
            if line is None:continue
            game=reveal.get((event,team))
            if game is None:fail("missing_actual_team_game_after_freeze")
            if pid not in game["players"]:
                numerics["candidate_without_settled_target_record"]+=1
                continue
            truth=game["players"][pid]["targets"]
            n=len(draws)
            crps_score=crps(draws,truth)
            row={"week":week,"event_id":event,"team":team,
                 "player_id":pid,"actual":truth,"line":line,
                 "mean_predicted":sum(draws)/n,
                 "crps":crps_score,"mae":abs(sum(draws)/n-truth)}
            over=sum(v>line for v in draws)
            under=sum(v<line for v in draws)
            if truth!=line and over+under:
                p=over/(over+under)
                row["actual_over"]=int(truth>line)
                row.update(_score_binary(p,row["actual_over"]))
            current_score[model].append(row)
            if model in CALIBRATABLE and "actual_over" in row:
                role=feature_roles.get((model,event,team,pid))
                if role not in ("WR","RB","TE"):
                    if model=="updated":
                        # Old model may include players absent from the
                        # newer lagged-roster research cohort. Keep them in
                        # old-model full-universe scores, but do NOT forge
                        # a role or synthesize a calibrated comparison.
                        numerics["baseline_player_not_in_asof_roster_calibration_abstains"]+=1
                        continue
                    fail("current_calibration_role_missing_from_prior")
                for cal in CALMODES:
                    q=qindex.get((model,cal,event,team,pid))
                    if q is None:fail("current_probability_unfrozen")
                    other={**row,**_score_binary(q,row["actual_over"])}
                    current_cal[model][cal].append(other)
                # Update prior WEEK history only now; no re-estimation
                # within a current week.
                calib_hist[model].append({
                  "week":week,"event_id":event,"team":team,
                  "player_id":pid,"role":role,
                  "raw_over":row["probability"],
                  "actual_over":row["actual_over"],
                })
        for model in MODELS:scored[model].extend(current_score[model])
        for model in CALIBRATABLE:
            for cal in CALMODES:
                calibrated[model][cal].extend(current_cal[model][cal])
        weekly.append({
          "week":week,"all_original_candidate_targets":universe[week],
          "scored_targets":{m:_metric(current_score[m]) for m in MODELS},
          "calibrated_targets":{m:{
              c:_metric(current_cal[m][c]) for c in CALMODES}
              for m in CALIBRATABLE},
          "confidence":{m:{c:{
              str(int(t*100)):_confidence(current_cal[m][c],t)
              for t in THRESHOLDS} for c in CALMODES}
              for m in CALIBRATABLE},
          "calibration_sample_count_previous_weeks":{
              m:len(calib_input["history"][m]) for m in CALIBRATABLE},
          "asof_forecast_sha256":frozen_digest,
          "asof_calibration_sha256":calib_result_sha,
          "latest_disclosed_2024_week":week-1,
        })
        receipts.append({
          "week":week,"asof_training_sha256":asof_sha,
          "frozen_forecast_sha256":frozen_digest,
          "calibration_input_sha256":cal_in_sha,
          "frozen_calibration_sha256":calib_result_sha,
          "historical_original_frozen_research_sha256":orig_sha[week],
          "no_current_game_training_labels":True,
          "calibrator_trained_through_week":week-1,
        })
        past.extend(oracle[week])
        print("WEEK_FROZEN_REVEALED",json.dumps({
           "week":week,
           "target_n_original":len(current_score["updated"]),
           "target_n_repaired":len(current_score["participation_snap"]),
           "target_crps_original":_metric(current_score["updated"])["crps"],
           "target_crps_repaired":_metric(current_score["participation_snap"])["crps"],
           "brier_role_raw":_metric(current_cal["participation_snap"]["raw"])["brier"],
           "brier_role_calibrated":_metric(
               current_cal["participation_snap"]["role_platt"])["brier"],
           "historical_calibrator_rows":len(calib_input["history"]["participation_snap"]),
        },sort_keys=True),flush=True)
    overall={
       "baseline_targets":{m:_metric(scored[m]) for m in MODELS},
       "calibrated_binary":{m:{c:_metric(calibrated[m][c])
                                 for c in CALMODES} for m in CALIBRATABLE},
       "confidence":{m:{c:{
         str(int(t*100)):_confidence(calibrated[m][c],t)
         for t in THRESHOLDS} for c in CALMODES}
         for m in CALIBRATABLE},
       "paired_repaired_vs_original":{
         metric:_paired(scored["participation_snap"],scored["updated"],metric,args.seed)
         for metric in ("crps","brier","log_loss")},
       "paired_repaired_vs_poisson":{
         metric:_paired(scored["participation_snap"],
                        scored["independent_poisson"],metric,args.seed)
         for metric in ("crps","brier","log_loss")},
       "paired_repaired_calibration_vs_raw":{
         metric:_paired(calibrated["participation_snap"]["role_platt"],
                        calibrated["participation_snap"]["raw"],metric,args.seed)
         for metric in ("brier","log_loss")},
       "paired_repaired_platt_vs_original_platt":{
         metric:_paired(calibrated["participation_snap"]["role_platt"],
                        calibrated["updated"]["role_platt"],metric,args.seed)
         for metric in ("brier","log_loss")},
    }
    report={
      "schema":"v25-p2-participation-calibration-retrospective-2024-v1",
      "study_status":"EXPLORATORY_2024_ALREADY_INSPECTED_NO_UNTOUCHED_HOLDOUT",
      "research_only":True,"promotion_authorized":False,
      "code_package_version":"v25-phase2-participation-snap-shadow-20261110",
      "original_oracle_sha256":oracle_sha,
      "initial_training":coverage,
      "weeks":18,"samples":args.samples,"seed":args.seed,
      "uses_true_pregame_roster":False,
      "source_coverage":sources["counts"],
      "true_original_pregame_capture_verified":False,
      "snap_exposure_is_not_routes":True,
      "uses_actual_receiver_routes":False,
      "future_or_current_games_seen_by_forecaster":False,
      "calendar_week_boundary_only_2024":True,
      "calibrator_uses_only_prior_reveals":True,
      "all_candidate_target_research_lines":sum(universe.values()),
      "results":overall,"weekly":weekly,
      "freeze_manifest":receipts,
      "limitations":[
         "2024 already used in model development; no untouched external generalization claim",
         "Original synthetic target lines and incomplete candidate universe, not bookmaker prices",
         "Historical target rows do not prove active roster, routes or injury status",
         "Do not compare unpaired raw model cohorts to infer accuracy improvement",
         "No heavy NUTS training, promotion, Tier or production ranking",
      ],
    }
    report["receipt_sha256"]=H(report)
    _write_once(args.output_dir/"FINAL_ROLE_REPAIR_CALIBRATION_REPORT.json",report)
    print("PHASE2_ROLE_CALIBRATION_FINAL",json.dumps({
      "receipt_sha256":report["receipt_sha256"],
      "initial_training":coverage,
      "original_scored":overall["baseline_targets"]["updated"],
      "repaired_scored":overall["baseline_targets"]["participation_snap"],
      "no_hurdle_scored":overall["baseline_targets"]["participation_no_hurdle"],
      "poisson_scored":overall["baseline_targets"]["independent_poisson"],
      "overall_calibrated":overall["calibrated_binary"],
      "confidence":overall["confidence"],
      "paired_vs_original":overall["paired_repaired_vs_original"],
      "paired_vs_poisson":overall["paired_repaired_vs_poisson"],
      "paired_calibration":overall["paired_repaired_calibration_vs_raw"],
    },sort_keys=True),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
