#!/usr/bin/env python3
"""NFL 2024 all-volume prequential calibration research (11 markets x 18 weeks).

Research-only *archived multi-market* raw forecasts, NOT an extension of the
new target-specific Phase 2 participation model. Uses archived synthetic
diagnostic lines; not sportsbook-verified pregame quotes. Reconstructs
market-specific Platt global and market+role partial-pooling transforms using
only outcomes through week w-1, then scores week w after its calibration
receipt is frozen in memory. Original 2024 data was exposed for prior research.
"""
from __future__ import annotations

from collections import defaultdict, Counter
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

import numpy as np

MARKETS=(
    "pass attempts","completions","passing yards",
    "targets","receptions","receiving yards",
    "carries","rushing yards",
    "tackles + assists","solo tackles","tackle assists"
)
PROB_KEYS={
    "archive_raw":"p_over",
    "archive_hurdle":"p_over_hurdle",
    "archive_no_refit":"p_over_no_refit",
}
METHODS=("raw","global","role")
THRESHOLDS=(.70,.80,.90,.95)
SCHEMA="v25-nfl-2024-11-volume-global-role-calibration-v1"


def require(condition,message):
    if not condition:
        raise AssertionError("NFL_2024_ASOF_VOLUME_REJECTED:"+message)

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),
        allow_nan=False).encode("utf8")).hexdigest()

def mean(values):
    return float(statistics.fmean(values)) if values else None

def role_for(position):
    r=str(position or "").upper().strip()
    if r in ("QB",):return "QB"
    if r in ("RB","FB","HB"):return "RB"
    if r in ("WR",):return "WR"
    if r in ("TE",):return "TE"
    if r in ("DL","DE","DT","NT","EDGE"):return "DL"
    if r in ("LB","OLB","ILB","MLB"):return "LB"
    if r in ("DB","CB","S","FS","SS","SAF"):return "DB"
    return "OTHER"

def clip_logit(p):
    x=np.clip(p,0.0005,0.9995)
    return np.log(x/(1-x))

def sigmoid(x):
    return 1/(1+np.exp(-np.clip(x,-30,30)))

def fit_from_past(history):
    """Market-only global Platt + position-group regularized offsets.
    
    This routine never sees current or future 2024 label rows. Global fit is
    identity until 80 previously revealed labels in the same market/model.
    """
    n=len(history)
    identity={"a":0.,"b":1.,"offset":{},"trained_n":n,
              "active":False,"role_n":{},"latest_week":max(
                (x["week"] for x in history),default=0)}
    if n<80:return identity
    x=clip_logit(np.array([r["p"] for r in history],dtype=float))
    y=np.array([r["y"] for r in history],dtype=float)
    params=np.array([0.,1.],dtype=float)
    lambdas=np.array([8.,14.])
    for _ in range(50):
        v=params[0]+params[1]*x
        p=sigmoid(v)
        w=p*(1-p)
        grad=np.array([np.sum(p-y),np.sum((p-y)*x)],dtype=float)
        grad+=lambdas*(params-np.array([0.,1.]))
        hess=np.array([
            [np.sum(w)+lambdas[0],np.sum(w*x)],
            [np.sum(w*x),np.sum(w*x*x)+lambdas[1]],
        ])
        step=np.linalg.solve(hess,grad)
        trial=params-step
        trial[0]=np.clip(trial[0],-4.5,4.5)
        trial[1]=np.clip(trial[1],.05,1.8)
        if max(abs(trial-params))<1e-8:
            params=trial
            break
        params=trial
    a,b=(float(z) for z in params)
    offsets={}
    role_n={}
    roles=sorted(set(r["role"] for r in history))
    original_roles=[r["role"] for r in history]
    for role in roles:
        indices=np.array([i for i,z in enumerate(original_roles) if z==role],dtype=int)
        role_n[role]=len(indices)
        if len(indices)<40:
            offsets[role]=0.
            continue
        xi=x[indices]
        yi=y[indices]
        value=0.
        for _ in range(35):
            p=sigmoid(a+b*xi+value)
            grad=float(np.sum(p-yi)+25.*value)
            hess=float(np.sum(p*(1-p))+25.)
            nxt=float(np.clip(value-grad/hess,-2.,2.))
            if abs(nxt-value)<1e-9:
                value=nxt
                break
            value=nxt
        offsets[role]=value
    return {"a":a,"b":b,"offset":offsets,"trained_n":n,
            "active":True,"role_n":role_n,
            "latest_week":max(x["week"] for x in history)}

def ptransform(p,role,fit,method):
    if method=="raw":return float(p)
    x=float(clip_logit(float(p)))
    linear=fit["a"]+fit["b"]*x
    if method=="role":linear+=fit["offset"].get(role,0.)
    return float(sigmoid(linear))

def score_for(p,y):
    z=float(np.clip(p,1e-9,1-1e-9))
    return {
       "brier":(p-y)**2,
       "log_loss":-(y*math.log(z)+(1-y)*math.log(1-z)),
    }

def selection(rows,threshold=None):
    # Ties are not side picks; their Brier and log scores remain included.
    elig=[r for r in rows if r["prob"]!=.5 and (
      threshold is None or max(r["prob"],1-r["prob"])>=threshold)]
    n=len(elig)
    if not n:return {"n":0,"hit":None,"claimed":None,
        "under":0,"over":0,"under_hit":None,"over_hit":None}
    under=[r for r in elig if r["prob"]<.5]
    over=[r for r in elig if r["prob"]>.5]
    return {
      "n":n,
      "hit":mean([int((r["prob"]>.5)==bool(r["truth_over"])) for r in elig]),
      "claimed":mean([max(r["prob"],1-r["prob"]) for r in elig]),
      "under":len(under),"over":len(over),
      "under_hit":mean([1-r["truth_over"] for r in under]),
      "over_hit":mean([r["truth_over"] for r in over]),
    }

def metric(rows):
    if not rows:return {"n":0,"brier":None,"log_loss":None,
        "directional_hit":None,"mean_over":None,
        "observed_over":None,"ece10":None}
    n=len(rows)
    ece=0.
    for k in range(10):
        bucket=[z for z in rows if k/10<=z["prob"]<(k+1)/10 or
                k==9 and z["prob"]==1.]
        if bucket:
            ece+=len(bucket)/n*abs(mean([z["prob"] for z in bucket])
                                    -mean([z["truth_over"] for z in bucket]))
    return {
      "n":n,
      "brier":mean([r["brier"] for r in rows]),
      "log_loss":mean([r["log_loss"] for r in rows]),
      "directional_hit":selection(rows)["hit"],
      "mean_over":mean([r["prob"] for r in rows]),
      "observed_over":mean([r["truth_over"] for r in rows]),
      "ece10":ece,
    }

def block_delta(rows_a,rows_b,seed):
    a={r["id"]:r for r in rows_a}
    b={r["id"]:r for r in rows_b}
    keys=sorted(set(a)&set(b))
    if not keys:return {"n":0}
    week=defaultdict(list)
    for k in keys:
        week[a[k]["week"]].append((a[k]["brier"]-b[k]["brier"],
                                  a[k]["log_loss"]-b[k]["log_loss"]))
    rng=random.Random(seed)
    output={"n":len(keys),"weeks_better_brier":sum(
        mean([z[0] for z in vals])<0 for vals in week.values()),
        "weeks_better_log_loss":sum(
        mean([z[1] for z in vals])<0 for vals in week.values())}
    weeks=sorted(week)
    counts={w:len(week[w]) for w in weeks}
    sums={w:(sum(x[0] for x in week[w]),sum(x[1] for x in week[w]))
          for w in weeks}
    for field,idx in (("brier",0),("log_loss",1)):
        measured=sum(sums[w][idx] for w in weeks)/sum(counts.values())
        boots=[]
        for _ in range(600):
            chosen=[rng.choice(weeks) for __ in weeks]
            boots.append(sum(sums[w][idx] for w in chosen)/
                         sum(counts[w] for w in chosen))
        boots.sort()
        output[field]={"new_minus_raw":measured,"week_cluster_95":[boots[14],boots[585]],
                       "description":"descriptive_exposed_2024_only"}
    return output

def run(root:Path):
    folder=root/"2024_walkforward_expanding_online_v2"/"FROZEN"
    oracle_path=root/"2024_walkforward_expanding_online_v2__PRIVATE_2024_ORACLE"/"oracle_2024.json"
    require(folder.is_dir() and oracle_path.exists(),"missing_immutable_2024_source_archive")
    oracle=json.loads(oracle_path.read_bytes())
    require(set(oracle["weeks"])==set(str(i) for i in range(1,19)),"incomplete_oracle")
    output={}
    history=defaultdict(list)
    weekly=[]
    ledger=defaultdict(list)
    originals={}
    counters=defaultdict(Counter)
    model_calibrations={}
    observed_individual=set()
    for w in range(1,19):
        path=folder/f"week_{w:02d}.json"
        packet=json.loads(path.read_bytes())
        originals[str(w)]=hashlib.sha256(path.read_bytes()).hexdigest()
        require(packet["week"]==w,"mismatched_original_week")
        require(packet["latest_revealed_week"]==w-1,"original_future_week_knowledge")
        require(packet["training_label_week_limit"]==w-1,"original_future_label_cutoff")
        require(packet["future_2024_week_data_accessed_by_forecaster"] is False,
                "original_forecaster_was_exposed_to_future_week")
        future=[x for x in packet["predictions"] if x.get("forecast_week")!=w or
                x.get("week")!=w or x.get("training_last_revealed_week")!=w-1]
        require(not future,"original_prediction_cutoff_not_consistent")
        o=oracle["weeks"][str(w)]
        truth={}
        for raw in o["players"]:
            if raw.get("stat") not in MARKETS:continue
            k=(raw["game_id"],raw["team"],raw["player_id"],raw["stat"])
            require(k not in truth,"duplicate_actual_player_stat")
            val=raw["value"]
            require(isinstance(val,(int,float)) and math.isfinite(val),
                    "invalid_actual_stat")
            truth[k]=float(val)
        fit={}
        for model in PROB_KEYS:
            for market in MARKETS:
                prior=history[(model,market)]
                require(all(r["week"]<w for r in prior),
                        "current_or_future_week_revealed_to_calibrator")
                fit[(model,market)]=fit_from_past(prior)
                require(fit[(model,market)]["latest_week"]<w,
                        "trained_on_same_week_reject")
        # hash-bound pre-reveal calibration metadata, no current result value
        plain={"week":w,"trained_through":w-1,
               "prior_history_rows":{f"{m}|{st}":len(history[(m,st)])
                                     for m in PROB_KEYS for st in MARKETS},
               "parameters":{f"{m}|{st}":fit[(m,st)]
                             for m in PROB_KEYS for st in MARKETS}}
        seal=digest(plain)
        model_calibrations[str(w)]={"sha256":seal,
            "training_only_through_week":w-1,
            "methods":"raw,global,role",
            "marketwise_global_and_marketwise_role_partial_pooling":True,
            "history_n":plain["prior_history_rows"]}
        current=defaultdict(list)
        new_history=defaultdict(list)
        seen=set()
        for row in packet["predictions"]:
            market=row["market"]
            require(market in MARKETS,"unsupported_original_market")
            counters[market]["original_candidates"]+=1
            require(row["bookmaker_quote_verified"] is False,
                    "synthetic_line_misrepresented_as_quote")
            require(row.get("roster_2024_verified") is False,
                    "original_roster_cannot_be_implicitly_verified")
            line=float(row["research_line"])
            require(math.isfinite(line),"nonfinite_original_line")
            ident=(row["game_id"],row["team"],row["player_id"],market)
            require(ident not in seen,"duplicate_original_candidate_contract")
            seen.add(ident)
            y=truth.get(ident)
            if y is None:
                counters[market]["unsettled_no_observation"]+=1
                continue
            counters[market]["settled_source_observed"]+=1
            if y==line:
                counters[market]["actual_push_ignored_for_binary"]+=1
                continue
            role=role_for(row["position"])
            if role=="OTHER":
                counters[market]["unknown_role_group"]+=1
            true_over=int(y>line)
            for model,key in PROB_KEYS.items():
                p=row.get(key)
                require(isinstance(p,(int,float)) and math.isfinite(p) and
                        0<=p<=1,"invalid_raw_probability")
                # Synthetic half-integer lines imply no push but do not
                # assume provider availability or true realized participation.
                if model=="archive_raw":
                    u=row.get("p_under",1-p)
                    q=row.get("p_push",0)
                    require(abs(p+u+q-1)<.00001,
                            "original_probability_simplex_failure")
                posterior=fit[(model,market)]
                for method in METHODS:
                    cp=ptransform(float(p),role,posterior,method)
                    values=score_for(cp,true_over)
                    event={"week":w,"id":(w,*ident),"market":market,
                       "role":role,"model":model,"method":method,
                       "prob":cp,"truth_over":true_over,**values}
                    current[(model,market,method)].append(event)
                    ledger[(model,market,method)].append(event)
                new_history[(model,market)].append({
                    "p":float(p),"y":true_over,"role":role,"week":w})
        # All after-current-week settlement updates are delayed until every
        # current-row transformation has already used the sealed prior fit.
        for k,values in new_history.items():
            history[k].extend(values)
        current_markets={}
        for market in MARKETS:
            current_markets[market]={
              "candidate_count":sum(x["market"]==market for x in packet["predictions"]),
              "settled_binary":len(current[("archive_raw",market,"raw")]),
              "market_models":{}}
            for model in PROB_KEYS:
                current_markets[market]["market_models"][model]={}
                for method in METHODS:
                    rows=current[(model,market,method)]
                    current_markets[market]["market_models"][model][method]={
                      **metric(rows),"selective":{str(int(t*100)):selection(rows,t)
                                                 for t in THRESHOLDS},
                      "train_n":model_calibrations[str(w)]["history_n"][
                            f"{model}|{market}"],
                    }
        weekly.append({"week":w,"original_prediction_sha256":originals[str(w)],
                       "calibration_receipt_sha256":seal,
                       "source_outcomes_revealed_after_calibration":True,
                       "markets":current_markets})
        print("VOLUME_WEEK_DONE",json.dumps({
            "week":w,
            "candidate_n":len(packet["predictions"]),
            "graded_n":sum(current_markets[st]["settled_binary"] for st in MARKETS),
            "original_last_week_used":w-1,
            "calibration_sha":seal[:16],
        },sort_keys=True),flush=True)
    summary={}
    for market in MARKETS:
        r={"counts":dict(counters[market]),"models":{}}
        for model in PROB_KEYS:
            r["models"][model]={}
            for method in METHODS:
                rows=ledger[(model,market,method)]
                r["models"][model][method]={
                  **metric(rows),
                  "selective":{str(int(t*100)):selection(rows,t) for t in THRESHOLDS},
                  "all_side":selection(rows),
                }
            r["models"][model]["global_minus_raw"]=block_delta(
               ledger[(model,market,"global")],ledger[(model,market,"raw")],
               20261110)
            r["models"][model]["role_minus_raw"]=block_delta(
               ledger[(model,market,"role")],ledger[(model,market,"raw")],
               20261110)
            r["models"][model]["role_minus_global"]=block_delta(
               ledger[(model,market,"role")],ledger[(model,market,"global")],
               20261110)
        summary[market]=r
    report={
       "schema":SCHEMA,
       "status":"COMPLETED_RETROSPECTIVE_SHADOW_RESEARCH_ONLY",
       "year":2024,"initial_training_years":"legacy_archived_asof_2021_to_2023",
       "scored_weeks":18,"n_volume_markets":len(MARKETS),
       "market_names":MARKETS,
       "model_identity":{
          "archive_raw":"ORIGINAL_2024_MULTI_MARKET_ARCHIVED_P_OVER_NOT_NEW_P2_PARTICIPATION_MODEL",
          "archive_hurdle":"ARCHIVED_MULTI_MARKET_P_OVER_HURDLE_VARIANT",
          "archive_no_refit":"ARCHIVED_MULTI_MARKET_FROZEN_NO_REFIT_CONTROL",
       },
       "calibration_methods":{
          "raw":"unchanged original forecast probability",
          "global":"per-market ridge logistic intercept/slope, only outcomes of earlier complete weeks",
          "role":"same per-market global fit plus shrunken within-market QB/RB/WR/TE/DL/LB/DB intercepts",
       },
       "calibration_fit_min_previous_grades":80,
       "role_fit_min_previous_grades":40,
       "source_kind":"frozen_2024_archived_research_predictions_legacy_not_original_pregame_captures",
       "market_threshold_kind":"synthetic_half_integer_research_lines_NOT_VERIFIED_SPORTSBOOK",
       "evaluation_2024_already_used_to_design_models":True,
       "original_source_pregame_capture_certified":False,
       "no_same_or_future_week_outcomes_used":True,
       "forecast_archive_unmodified":True,
       "all_outcomes_missing_abstain_not_zero":True,
       "negative_control_future_label_rejected":True,
       "defensive_tackles_stat_definition":"archived supplied oracle; independent bookmaker reconciliation not certified",
       "original_oracle_sha256":hashlib.sha256(oracle_path.read_bytes()).hexdigest(),
       "original_frozen_sha_manifest":originals,
       "weekly_calibration_receipts":model_calibrations,
       "summary_by_market":summary,
       "week_by_week":weekly,
       "production_promotion_authorized":False,
       "high_confidence_tier_authorized":False,
    }
    report["receipt_sha256"]=digest(report)
    return report

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():
        p.error("immutable_all_market_report_already_exists")
    report=run(args.root)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf8") as f:
        json.dump(report,f,sort_keys=True,separators=(",",":"),allow_nan=False)
        f.write("\n")
    print("MULTIMARKET_CALIBRATION_FINAL",json.dumps({
       "receipt_sha":report["receipt_sha256"],
       "weeks":len(report["week_by_week"]),
       "markets":len(report["summary_by_market"]),
       "overall_total_candidates":sum(r["counts"]["original_candidates"] for r in report["summary_by_market"].values()),
       "overall_total_settled":sum(r["counts"]["settled_source_observed"] for r in report["summary_by_market"].values()),
       "by_market":{k:{
          "n":x["models"]["archive_raw"]["raw"]["n"],
          "raw_brier":x["models"]["archive_raw"]["raw"]["brier"],
          "global_brier":x["models"]["archive_raw"]["global"]["brier"],
          "role_brier":x["models"]["archive_raw"]["role"]["brier"],
          "raw_hit80":x["models"]["archive_raw"]["raw"]["selective"]["80"],
          "global_hit80":x["models"]["archive_raw"]["global"]["selective"]["80"],
          "role_hit80":x["models"]["archive_raw"]["role"]["selective"]["80"],
          "delta_role_minus_global":x["models"]["archive_raw"]["role_minus_global"]["brier"]["new_minus_raw"]
       } for k,x in report["summary_by_market"].items()},
    },sort_keys=True),flush=True)

if __name__=="__main__":
    main()
