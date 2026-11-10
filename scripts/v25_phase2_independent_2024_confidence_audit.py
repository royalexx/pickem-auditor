#!/usr/bin/env python3
"""Independent 2024 Phase 2 participation confidence + as-of receipt audit.

This scores *original frozen model and calibration files* without training.
Reports conditional Brier/log loss, target CRPS cohort, role/side reliability,
count support, prediction interval coverage, new-player availability,
stale-source counts and week-specific refusal reasons. 2024 is research-exposed.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, Counter
import hashlib
import json
import math
from pathlib import Path
import statistics

METHODS=("updated","no_refit","independent_poisson",
         "participation_snap","participation_no_hurdle")
CALIBRATED=("updated","participation_snap","participation_no_hurdle")
CAL_TYPES=("raw","global_platt","role_platt")

def avg(values):
    return statistics.fmean(values) if values else None
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def probscore(p,y):
    if not (0<=p<=1 and y in (0,1)):
        raise AssertionError("bad_probability_or_outcome")
    return {"brier":(p-y)**2,
            "log_loss":-y*math.log(max(1e-9,p))-(1-y)*math.log(max(1e-9,1-p))}
def crps(values,actual):
    x=sorted(values);m=len(x)
    return (sum(abs(v-actual) for v in x)/m
            -sum((2*i-m+1)*v for i,v in enumerate(x))/(m*m))

def summary(rows,score="brier"):
    valid=[r for r in rows if r.get(score) is not None]
    if not valid:return {"n":0}
    out={"n":len(valid),"mean_"+score:avg([r[score] for r in valid])}
    if score=="brier":
        out["equality_tie_share"]=sum(r["q"]==.5 for r in valid)/len(valid)
        out["mean_p_over"]=avg([r["q"] for r in valid])
        out["over_actual_rate"]=avg([r["actual_over"] for r in valid])
        out["ece_10_equal_width"]=sum(
            len(cell)/len(valid)*abs(
              avg([r["q"] for r in cell])-avg([r["actual_over"] for r in cell]))
            for b in range(10) if (cell:=[r for r in valid if (
                (b/10)<=r["q"]<((b+1)/10) or
                b==9 and r["q"]==1.)])
        )
    return out

def confidence(rows,minimum):
    chosen=[r for r in rows if r["q"]!=.5 and
            max(r["q"],1-r["q"])>=minimum]
    if not chosen:return {"n":0}
    return {
      "n":len(chosen),
      "under_n":sum(x["q"]<.5 for x in chosen),
      "over_n":sum(x["q"]>.5 for x in chosen),
      "mean_claimed":avg([max(x["q"],1-x["q"]) for x in chosen]),
      "accuracy":avg([int((x["q"]>.5)==(x["actual_over"]==1)) for x in chosen]),
      "over_accuracy":avg([int(x["actual_over"]==1) for x in chosen if x["q"]>.5]),
      "under_accuracy":avg([int(x["actual_over"]==0) for x in chosen if x["q"]<.5]),
    }

def paired(a,b,metric):
    indexed=lambda rows:{(r["week"],r["event_id"],r["team"],r["player_id"]):r
                         for r in rows if r.get(metric) is not None}
    left=indexed(a);right=indexed(b)
    keys=set(left)&set(right)
    return {
      "n":len(keys),
      "mean_new_minus_reference":avg([left[k][metric]-right[k][metric]
                                      for k in keys]),
      "positive_improvement_fraction":avg([int(left[k][metric]<right[k][metric])
                                           for k in keys]),
      "n_distinct_event_clusters":len({k[1] for k in keys}),
    }

def run(direct,original):
    reportfile=direct/"FINAL_ROLE_REPAIR_CALIBRATION_REPORT.json"
    if not reportfile.exists():raise AssertionError("final_experiment_receipt_missing")
    report=json.loads(reportfile.read_text())
    if report["weeks"]!=18 or not report["calibrator_uses_only_prior_reveals"]:
        raise AssertionError("incorrect_experiment_span_or_calendar_cutoff")
    with (original/"2024_walkforward_expanding_online_v2__PRIVATE_2024_ORACLE"/
          "oracle_2024.json").open() as f:
        oracle=json.load(f)
    lines={}
    for w in range(1,19):
        source=original/"2024_walkforward_expanding_online_v2"/"FROZEN"/f"week_{w:02d}.json"
        frozen=json.loads(source.read_bytes())
        lines[w]={ (x["game_id"],x["team"],x["player_id"]):float(x["research_line"])
                   for x in frozen["predictions"] if x["market"]=="targets" }
    ledger=defaultdict(list)
    reliability=defaultdict(list)
    week_summary=[]
    bad=Counter()
    coverage=Counter()
    for w in range(1,19):
        pre=direct/f"week_{w:02}_asof_model_input.json"
        frozen=direct/f"week_{w:02}_frozen_model.json"
        cinput=direct/f"week_{w:02}_asof_calibrator_input.json"
        coutput=direct/f"week_{w:02}_frozen_calibration.json"
        packet=json.loads(pre.read_bytes())
        forecast=json.loads(frozen.read_bytes())
        calin=json.loads(cinput.read_bytes())
        calout=json.loads(coutput.read_bytes())
        receipt=report["freeze_manifest"][w-1]
        for file,field in ((pre,"asof_training_sha256"),
                           (frozen,"frozen_forecast_sha256"),
                           (cinput,"calibration_input_sha256"),
                           (coutput,"frozen_calibration_sha256")):
            if digest(file)!=receipt[field]:
                bad["receipt_hash_mismatch"]+=1
        if (forecast["train_2024_max_week"]!=w-1
                or packet["week"]!=w
                or forecast["current_or_future_game_stats_exposed"]):
            bad["incorrect_training_cutoff"]+=1
        if any(r["season"]==2024 and r["week"]>=w
               for r in packet["history"]):
            bad["future_2024_stat_label"]+=1
        if any(r["season"]==2024 and r["week"]>=w
               for k in ("lagged_roster_context","lagged_snap_context")
               for r in packet[k]):
            bad["future_2024_participation_label"]+=1
        if any(r["source_claim"]!="retrospectively_retrieved_dated_report_not_original_capture"
               or r["date_modified"]>r["freeze_at"]
               for r in packet["dated_pregame_injury_context"]):
            bad["injury_source_future_or_certification"]+=1
        if any("actual_over" in r for rows in calin["offers"].values()
               for r in rows):
            bad["current_week_outcome_to_calibrator"]+=1
        if any(r["week"]>=w for rows in calin["history"].values()
               for r in rows):
            bad["future_outcome_to_calibrator"]+=1
        if calout["week"]!=w or calout["current_and_future_game_outcomes_accessed"]:
            bad["calibrator_receipt_failure"]+=1
        current=oracle["weeks"][str(w)]
        outcome={(x["game_id"],x["team"],x["player_id"]):x["value"]
                  for x in current["players"] if x["stat"]=="targets"
                  and x.get("position") in ("WR","RB","TE")}
        team_actual={(x["game_id"],x["team"]):x["pass_attempts"]
                      for x in current["team_games"]}
        calibration_lookup={}
        for model,methods in calout["models"].items():
            for method,entry in methods.items():
                if entry["trained_on_latest_week"]>=w:
                    bad["calibrator_fitted_on_same_or_future_week"]+=1
                for q in entry["probabilities"]:
                    calibration_lookup[(model,method,q["event_id"],
                       q["team"],q["player_id"])]=q["calibrated_over"]
        scoring_counts=Counter()
        for team in forecast["forecasts"]:
            k=(team["event_id"],team["team"])
            y_attempt=team_actual[k]
            for model in METHODS:
                key="updated" if model=="independent_poisson" else model
                mod=team["models"][key]
                if mod["status"] not in ("shadow_target_allocation_without_routes",
                        "retrospective_participation_snap_challenger_not_certified"):
                    continue
                if model.startswith("participation"):
                    for j,attempts in enumerate(mod["pass_attempts"]):
                        if (sum(x[j] for x in mod["player_targets"].values())
                           +mod["unknown_receiver_targets"][j]
                           +mod["non_target_attempts"][j]!=attempts):
                            bad["illegal_target_sum"]+=1
                drawn=mod["independent_poisson_targets"] if model=="independent_poisson" else mod["player_targets"]
                for player,samples in drawn.items():
                    identity=(team["event_id"],team["team"],player)
                    if identity not in lines[w]:
                        continue
                    coverage[(model,"has_saved_line")]+=1
                    if identity not in outcome:
                        coverage[(model,"no_settlement")]+=1
                        continue
                    y=outcome[identity];line=lines[w][identity]
                    score={
                       "week":w,"event_id":identity[0],"team":identity[1],
                       "player_id":player,
                       "crps":crps(samples,y),
                       "mae":abs(avg(samples)-y),
                       "mean_predicted":avg(samples),
                       "actual":y,
                    }
                    ledger[model].append(score)
                    scoring_counts[model]+=1
                    if y==line:
                        coverage[(model,"push")]+=1
                        continue
                    over=sum(s>line for s in samples)
                    under=sum(s<line for s in samples)
                    if over+under==0:continue
                    p=over/(over+under)
                    evaluated={**score,"q":p,"actual_over":int(y>line),
                                **probscore(p,int(y>line))}
                    reliability[(model,"raw")].append(evaluated)
                    if model in CALIBRATED:
                        for method in ("global_platt","role_platt"):
                            v=calibration_lookup.get((model,method,*identity))
                            if v is None:
                                # Baseline preserves its full forecast cohort,
                                # including players omitted by the new lagged
                                # roster. The separate calibration runner
                                # properly abstains for such unverified roles.
                                # This is an explicit loss of calibration
                                # coverage, NOT an invented player role.
                                if model=="updated":
                                    coverage[(model,"no_asof_role_for_calibration")]+=1
                                    continue
                                bad["missing_current_calibrated_probability"]+=1
                                continue
                            reliability[(model,method)].append({
                                **score,"q":v,"actual_over":int(y>line),
                                **probscore(v,int(y>line))})
        week_summary.append({
          "week":w,
          "scored":dict(scoring_counts),
          "raw_high80":{
             model:confidence([x for x in reliability[(model,"raw")] if x["week"]==w],.8)
             for model in ( "updated","participation_snap","participation_no_hurdle") },
          "cal_high80":{
             model:confidence([x for x in reliability[(model,"role_platt")] if x["week"]==w],.8)
             for model in ("updated","participation_snap","participation_no_hurdle")},
        })
    if bad:raise AssertionError("INDEPENDENT_AUDIT_FAILED:"+str(dict(bad)))
    out={
      "schema":"v25-phase2-independent-2024-confidence-audit-v1",
      "source_report_sha256":report["receipt_sha256"],
      "week_count":len(week_summary),
      "asof_history_verified":True,
      "original_provider_publication_independently_verified":False,
      "actual_receiver_routes_not_reconstructed":True,
      "real_market_quotes_not_used":True,
      "coverage":{
        "original_research_candidate_lines":sum(len(lines[w]) for w in lines),
        "player_target_scored":{m:len(ledger[m]) for m in METHODS},
        "reasons":{f"{a}:{b}":n for (a,b),n in coverage.items()},
      },
      "distribution_metrics":{m:summary(ledger[m],"crps") for m in METHODS},
      "probability_metrics":{f"{m}|{c}":summary(rows)
                            for (m,c),rows in reliability.items()},
      "selective_reliability":{
        f"{m}|{c}":{str(int(100*t)):confidence(rows,t)
                  for t in (.7,.8,.9,.95)}
        for (m,c),rows in reliability.items()},
      "paired_raw_vs_original":{
          m:{measure:paired(reliability[(m,"raw")],
                        reliability[("updated","raw")],measure)
             for measure in ("brier","log_loss")}
          for m in ("participation_snap","participation_no_hurdle")},
      "paired_calibration_vs_raw":{
          m:{measure:paired(reliability[(m,"role_platt")],
                        reliability[(m,"raw")],measure)
            for measure in ("brier","log_loss")}
          for m in CALIBRATED},
      "paired_model_vs_baseline_crps":{
        m:paired(ledger[m],ledger["updated"],"crps")
          for m in ("participation_snap","participation_no_hurdle",
                    "independent_poisson")},
      "week_by_week":week_summary,
    }
    out["audit_sha256"]=hashlib.sha256(json.dumps(
        out,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return out

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--frozen-dir",required=True,type=Path)
    parser.add_argument("--original-run-root",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    a=parser.parse_args()
    if a.output.exists():parser.error("immutable_audit_output_exists")
    report=run(a.frozen_dir,a.original_run_root)
    with a.output.open("x",encoding="utf8") as f:
        json.dump(report,f,sort_keys=True,indent=2,allow_nan=False)
        f.write("\n")
    print("INDEPENDENT_PHASE2_AUDIT",json.dumps({
      "audit_sha256":report["audit_sha256"],
      "coverage":report["coverage"],
      "paired_crps":report["paired_model_vs_baseline_crps"],
      "paired_confidence":report["paired_calibration_vs_raw"],
      "selective":{k:v["80"] for k,v in
                   report["selective_reliability"].items()},
    },sort_keys=True),flush=True)

if __name__=="__main__":
    main()
