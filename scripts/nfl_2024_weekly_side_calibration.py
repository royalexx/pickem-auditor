#!/usr/bin/env python3
"""Chronological, side- and market-specific calibration of the 2024 challenger.

Research-only: no changes to frozen forecasts, no model refits, no promotion.
Each Week W uses settlement weeks strictly < W to fit its calibrator.
The dependent variable is whether the model's chosen raw side wins, with
the chosen side determined from a FROZEN prediction. Over and Under receive
SEPARATE calibrators; markets partially pool to each side's population fit.

This is binary non-push calibration for 2024 synthetic half-integer lines,
NOT bookmaker calibration. No verified NFL odds, injuries, or void events.
"""
from __future__ import annotations

from collections import defaultdict
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

SCHEMA="nfl_2024_nfl_challenger_market_side_chrono_calibration_v1"
RAW_FIELD="p_over_hurdle"
MIN_EVAL_WEEK=5
MIN_GLOBAL=180
MIN_MARKET=100
MIN_CLASS=10
GLOBAL_L2=90.
MARKET_L2=110.
EPS=1e-5


def clip(p):
    if type(p) not in (float,int) or not math.isfinite(p) or not 0<=p<=1:
        raise ValueError("invalid_raw_probability")
    return max(EPS,min(1-EPS,float(p)))


def logit(p):
    q=clip(p)
    return math.log(q/(1-q))


def sigmoid(z):
    if z>=0:return 1/(1+math.exp(-z))
    e=math.exp(z)
    return e/(1+e)


def choice(r):
    p=clip(r[RAW_FIELD])
    outcome=float(r["actual_stat"])
    line=float(r["research_line"])
    if outcome==line:
        return None
    over=p>=.5
    return {"week":int(r["week"]),"market":str(r["market"]),
        "side":"over" if over else "under",
        "q":p if over else 1-p,
        "win":int(outcome>line if over else outcome<line)}


def fit(rows,*,prior=(0.,1.),penalty=GLOBAL_L2):
    """Regularized selected-side Platt calibration, monotone slope >0."""
    if not rows:return None
    xs=np.asarray([logit(r["q"]) for r in rows],dtype=np.float64)
    ys=np.asarray([r["win"] for r in rows],dtype=np.float64)
    if len(set(ys.tolist()))<2:return None
    a0,b0=map(float,prior)
    def obj(z):
        a,b=z
        eta=a+b*xs
        nll=np.logaddexp(0.,eta).sum()-np.dot(ys,eta)
        return float(nll + .5*penalty*((a-a0)**2+.30*(b-b0)**2))
    r=minimize(obj,np.asarray([a0,b0]),method="L-BFGS-B",
              bounds=((-7.,7.),(.025,2.5)),options={"maxiter":300})
    if not r.success or not np.isfinite(r.x).all():
        raise RuntimeError("calibration_failed_to_converge")
    return {"a":float(r.x[0]),"b":float(r.x[1]),"n":len(rows)}


def fit_prior_weeks(history,week):
    if week<2 or any(int(r["week"])>=week for r in history):
        raise RuntimeError("current_or_future_week_calibration_leak")
    groups=defaultdict(list)
    for r in history:
        c=choice(r)
        if c is None:continue
        groups[(c["side"],None)].append(c)
        groups[(c["side"],c["market"])].append(c)
    pool={};markets={}
    for side in ("under","over"):
        rows=groups[(side,None)]
        positives=sum(r["win"] for r in rows)
        if len(rows)>=MIN_GLOBAL and min(positives,len(rows)-positives)>=MIN_CLASS:
            pool[side]=fit(rows)
        else:pool[side]=None
    for (side,market),rows in groups.items():
        if market is None:continue
        base=pool[side]
        positives=sum(r["win"] for r in rows)
        if (base is not None and len(rows)>=MIN_MARKET and
                min(positives,len(rows)-positives)>=MIN_CLASS):
            markets[(side,market)]=fit(rows,
                prior=(base["a"],base["b"]),penalty=MARKET_L2)
    return {"trained_through_week":week-1,"pool":pool,
            "markets":markets,
            "global_training_n":{s:len(groups[(s,None)]) for s in ("under","over")}}


def predict(r,cal):
    if cal["trained_through_week"]>=int(r["week"]):
        raise RuntimeError("calibration_trained_on_this_or_future_week")
    p=clip(r[RAW_FIELD])
    side="over" if p>=.5 else "under"
    params=cal["markets"].get((side,r["market"]))
    scope="market_side" if params is not None else "pooled_side"
    if params is None:params=cal["pool"].get(side)
    if params is None:
        return {"p_over_calibrated":None,"scope":"insufficient_past_data"}
    selected=sigmoid(params["a"]+params["b"]*logit(p if side=="over" else 1-p))
    return {"p_over_calibrated":selected if side=="over" else 1-selected,
        "scope":scope,"fit_through_week":cal["trained_through_week"],
        "fit_training_n":params["n"]}


def _score(rows,pname):
    subset=[r for r in rows if r.get(pname) is not None]
    if not subset:return {"n":0}
    n=len(subset)
    return {"n":n,
        "brier":sum((r[pname]-r["y_over"])**2 for r in subset)/n,
        "logloss":sum(-r["y_over"]*math.log(clip(r[pname])) -
                  (1-r["y_over"])*math.log(1-clip(r[pname])) for r in subset)/n,
        "accuracy":sum((r[pname]>=.5)==bool(r["y_over"]) for r in subset)/n,
        "predicted_under_share":sum(r[pname]<.5 for r in subset)/n}


def read_week(root,week):
    frozen=root/"FROZEN"/("week_%02d.json"%week)
    revealed=root/"REVEALED"/("week_%02d.json"%week)
    locked=json.loads(frozen.read_bytes())
    settled=json.loads(revealed.read_bytes())
    if (locked.get("week")!=week or
            locked.get("latest_revealed_week")!=week-1 or
            settled.get("week")!=week or
            settled.get("frozen_sha")!=hashlib.sha256(frozen.read_bytes()).hexdigest()):
        raise RuntimeError("tampered_unfrozen_or_nonchronological_week")
    rows=[r for r in settled["full_research_rows"] if r["graded"] is True]
    if len(rows)!=settled["score"]["graded"]:raise RuntimeError("graded_count_mismatch")
    if any(int(r["week"])!=week or
           int(r["training_last_revealed_week"])!=week-1 for r in rows):
        raise RuntimeError("future_training_week_entered_prediction")
    return rows


def audit(root):
    root=Path(root)
    history=[];evaluated=[];byweek=[]
    for week in range(1,19):
        observations=read_week(root,week)
        if week>=MIN_EVAL_WEEK:
            calibrator=fit_prior_weeks(history,week)
            now=[]
            for r in observations:
                if float(r["actual_stat"])==float(r["research_line"]):
                    continue
                transformed=predict(r,calibrator)
                if transformed["p_over_calibrated"] is None:continue
                x={"week":week,"market":r["market"],"game_id":r["game_id"],
                   "y_over":int(float(r["actual_stat"])>float(r["research_line"])),
                   "p_raw":clip(r[RAW_FIELD]),
                   "p_calibrated":transformed["p_over_calibrated"],
                   "fit_through_week":transformed["fit_through_week"],
                   "side":"over" if r[RAW_FIELD]>=.5 else "under",
                   "scope":transformed["scope"]}
                if x["fit_through_week"]>=week:
                    raise RuntimeError("future_labels_in_calibration")
                now.append(x)
            byweek.append({"week":week,"forecasted_graded":len(observations),
                           "calibrated_n":len(now),
                           "raw":_score(now,"p_raw"),
                           "calibrated":_score(now,"p_calibrated"),
                           "training_counts":calibrator["global_training_n"],
                           "used_market_fit_n":sum(r["scope"]=="market_side" for r in now)})
            evaluated.extend(now)
        # Only AFTER calculating this week's predictions does its outcome
        # enter the fitting pool for the next week.
        history.extend(observations)
    overall={"raw":_score(evaluated,"p_raw"),
             "calibrated":_score(evaluated,"p_calibrated")}
    by_market={}
    for market in sorted({r["market"] for r in evaluated}):
        sub=[r for r in evaluated if r["market"]==market]
        by_market[market]={"raw":_score(sub,"p_raw"),
                           "calibrated":_score(sub,"p_calibrated")}
    by_side={}
    for side in ("over","under"):
        sub=[r for r in evaluated if r["side"]==side]
        by_side[side]={"raw":_score(sub,"p_raw"),
                       "calibrated":_score(sub,"p_calibrated")}
    result={"schema":SCHEMA,"research_only":True,"no_2024_future_week_fit":True,
            "min_week_evaluated":MIN_EVAL_WEEK,
            "calibration_is_market_and_side_specific":True,
            "frozen_forecasts_modified":False,
            "production_promotion_allowed":False,
            "tier1_2_challenger_still_suspended":True,
            "source_is_synthetic_lines_not_bookmaker":True,
            "overall":overall,"weekly":byweek,"by_side":by_side,
            "by_market":by_market}
    target=root/"AUDIT"/"SIDE_MARKET_CALIBRATION_RESEARCH.json"
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():raise RuntimeError("calibration_audit_already_exists_refuse_overwrite")
    target.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print("MARKET_SIDE_CALIBRATION_COMPLETE",
          json.dumps({"overall":overall,"by_side":by_side,"by_market":by_market}),flush=True)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    args=p.parse_args()
    audit(Path(args.root))


if __name__=="__main__":
    main()
