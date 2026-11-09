#!/usr/bin/env python3
"""Research-only, causal weekly calibration of 2024 NFL chosen-side probabilities.

Over and Under have separate partial-pooling Platt calibrators, and each
market is fitted separately with shrinkage to its own SIDE-wide calibrator.
Only *previously settled* weeks may enter a calibration fit. Week 1 remains
unfitted. Calibrated risk score is P(chosen side correct), NOT a normalized
Over/Under joint distribution. No retrospective direction flip, deployment,
or confidence-tier authorization. Synthetic props; unverified rosters.

2024 data has already been used in prior analyses; this is a diagnostic
chronological walk-forward, NOT pristine independent holdout selection.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import mean

SCHEMA = "nfl_2024_separate_side_market_walkforward_calibrator_v1"
SOURCE = "p_over_hurdle"
SIDE_MIN = 160
MARKET_MIN = 80
MARKET_PSEUDO = 300.0
REGULARIZATION_C = .3
EPS = 1e-5


def logit(p):
    p=max(EPS,min(1.-EPS,float(p)))
    return math.log(p/(1.-p))


def sigmoid(v):
    return 1./(1.+math.exp(-max(-45.,min(45.,v))))


def normalize(row):
    p=float(row[SOURCE])
    if not math.isfinite(p) or not 0<=p<=1:
        raise ValueError("invalid_forecast_probability")
    side="Over" if p>=.5 else "Under"
    return {"week":int(row["week"]),"game_id":row["game_id"],
            "player_id":row["player_id"],"market":row["market"],
            "side":side,"raw":p if side=="Over" else 1.-p,
            "win":int((p>=.5)==bool(row["actual_over"]))}


def load_week(root,week):
    f=Path(root)/"FROZEN"/("week_%02d.json"%week)
    r=Path(root)/"REVEALED"/("week_%02d.json"%week)
    full=json.loads(r.read_bytes())
    frozen=json.loads(f.read_bytes())
    if full["frozen_sha"]!=sha256(f.read_bytes()).hexdigest():
        raise RuntimeError("weekly_forecast_hash_mismatch")
    if frozen["latest_revealed_week"]!=week-1:
        raise RuntimeError("incorrect_frozen_training_week")
    rows=[normalize(row) for row in full["full_research_rows"] if row.get("graded")]
    if any(row["week"]!=week for row in rows):
        raise RuntimeError("cross_week_grading_record")
    if len(rows)!=full["score"]["graded"]:
        raise RuntimeError("incorrect_weekly_grading_n")
    return rows


def fit_platt(rows,min_n):
    if len(rows)<min_n or len({r["win"] for r in rows})<2:
        return None
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    X=np.asarray([logit(r["raw"]) for r in rows],dtype=float).reshape(-1,1)
    y=np.asarray([r["win"] for r in rows],dtype=int)
    mdl=LogisticRegression(C=REGULARIZATION_C,solver="lbfgs",max_iter=200)
    mdl.fit(X,y)
    slope=max(0.,float(mdl.coef_[0,0]))
    intercept=float(mdl.intercept_[0])
    return {"slope":slope,"intercept":intercept,"n":len(rows)}


def map_probability(p,fit):
    return sigmoid(fit["intercept"]+fit["slope"]*logit(p))


def fit_for_week(previous, week):
    """Explicit precondition prevents full-season calibration leakage."""
    if any(row["week"]>=week for row in previous):
        raise RuntimeError("future_week_or_same_week_in_calibrator_fit")
    sided=defaultdict(list)
    for r in previous:sided[r["side"]].append(r)
    result={"week":week,"max_seen_week":max((r["week"] for r in previous),default=0),
            "side":{},"market":{}}
    for side in ("Over","Under"):
        result["side"][side]=fit_platt(sided[side],SIDE_MIN)
        grouped=defaultdict(list)
        for row in sided[side]:
            grouped[row["market"]].append(row)
        for m,items in grouped.items():
            result["market"][(side,m)]=fit_platt(items,max(MARKET_MIN,2))
    return result


def calibrated(row, fit):
    if row["week"]!=fit["week"] or fit["max_seen_week"]>=row["week"]:
        raise RuntimeError("calibrator_uses_future_labels")
    s=fit["side"][row["side"]]
    if s is None:
        return row["raw"],"unfitted_raw",0.
    p=map_probability(row["raw"],s)
    local=fit["market"].get((row["side"],row["market"]))
    if local is None:
        return p,"side_global",0.
    n=local["n"]
    weight=n/(n+MARKET_PSEUDO)
    return (1.-weight)*p+weight*map_probability(row["raw"],local), "side_market_partial_pool",weight


def measure(rows,key):
    if not rows:return {"n":0}
    n=len(rows)
    p=[r[key] for r in rows]
    y=[r["win"] for r in rows]
    return {"n":n,"brier":sum((a-b)**2 for a,b in zip(p,y))/n,
            "logloss":-sum(b*math.log(max(EPS,min(1.-EPS,a)))+
                      (1-b)*math.log(max(EPS,min(1.-EPS,1.-a)))
                      for a,b in zip(p,y))/n,
            "mean_confidence":mean(p),
            "hit_rate":mean(y),
            "overconfidence_pp":100.*(mean(p)-mean(y)),
            "selected_ge80":sum(a>=.8 for a in p),
            "selected_ge90":sum(a>=.9 for a in p),
            "selected_ge95":sum(a>=.95 for a in p)}


def audit(root, *, out=None):
    root=Path(root)
    if not (root/"FINAL_SUMMARY.json").is_file():
        raise RuntimeError("replay_not_complete")
    hist=[];scored=[];fits=[]
    for w in range(1,19):
        fresh=load_week(root,w)
        fit=fit_for_week(hist,w)
        fits.append({"week":w,"training_last_week":fit["max_seen_week"],
                     "prior_scored":len(hist),
                     "over_side_fitted":fit["side"]["Over"] is not None,
                     "under_side_fitted":fit["side"]["Under"] is not None,
                     "market_side_groups_fitted":sum(v is not None for v in fit["market"].values())})
        for r in fresh:
            confidence,source,weight=calibrated(r,fit)
            scored.append({**r,"calibrated":confidence,
                    "calibration_source":source,"market_weight":weight})
        hist.extend(fresh)
    if len(scored)!=38832:
        raise RuntimeError("unexpected_2024_graded_sample_count")
    eligible=[r for r in scored if r["week"]>1]
    by_market=defaultdict(list);by_side=defaultdict(list);by_week=defaultdict(list)
    for r in eligible:
        by_market[(r["side"],r["market"])].append(r)
        by_side[r["side"]].append(r)
        by_week[str(r["week"])].append(r)
    out_report={"schema":SCHEMA,"production_eligible":False,
        "leakage_guard":"no fit can contain same/future week labels",
        "training_and_eval_temporal_protocol":"fit prior weeks, score new week, append outcomes",
        "out_of_sample_claim":"chronological relative to weekly fits but 2024 already inspected",
        "source_lines":"synthetic_not_bookmaker",
        "risk_score_not_normalized_over_under_distribution":True,
        "first_week_unfitted":True,
        "all_grades":len(scored),"evaluation_weeks":"2-18",
        "fits":fits,
        "overall":{"raw":measure(eligible,"raw"),"calibrated":measure(eligible,"calibrated")},
        "by_side":{side:{"raw":measure(rr,"raw"),"calibrated":measure(rr,"calibrated")} for side,rr in by_side.items()},
        "by_side_market":{side+"|"+m:{"raw":measure(rr,"raw"),"calibrated":measure(rr,"calibrated")}
             for (side,m),rr in sorted(by_market.items())},
        "by_week":{w:{"raw":measure(rr,"raw"),"calibrated":measure(rr,"calibrated")}
            for w,rr in sorted(by_week.items(),key=lambda x:int(x[0]))},
        "high_confidence":{
          str(t):{key:measure([r for r in eligible if r[key]>=t],key)
                  for key in ("raw","calibrated")}
            for t in (.8,.9,.95)},
        "calibration_methods":dict(
          side_min=SIDE_MIN,market_min=MARKET_MIN,
          market_pseudocount=MARKET_PSEUDO,regularization_c=REGULARIZATION_C),
        "model_tiers_suspended":True}
    if out is not None:
        p=Path(out)
        p.parent.mkdir(parents=True,exist_ok=True)
        if p.exists():raise RuntimeError("would_overwrite_existing_calibration_audit")
        p.write_text(json.dumps(out_report,sort_keys=True,indent=2)+"\n")
    print("CALIBRATION_2024_OVERALL",json.dumps(out_report["overall"]),flush=True)
    for side,s in out_report["by_side"].items():
        print("CALIBRATION_SIDE",side,json.dumps(s),flush=True)
    for market,s in out_report["by_side_market"].items():
        print("CALIBRATION_MARKET",market,json.dumps(s),flush=True)
    print("CALIBRATION_HIGH",json.dumps(out_report["high_confidence"]),flush=True)
    print("CALIBRATION_STATUS",json.dumps(dict(production_eligible=False,
        chronological_heldout_week_count=17,
        fitted_weeks=sum(f["under_side_fitted"] and f["over_side_fitted"] for f in fits))),flush=True)
    return out_report


if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",required=True,type=Path)
    ap.add_argument("--out",type=Path)
    args=ap.parse_args()
    audit(args.root,out=args.out)
