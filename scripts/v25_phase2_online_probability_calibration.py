"""Phase 2 point-in-time binary probability recalibration research.

Learns exclusively from PREVIOUSLY REVEALED weekly forecast/settlement
pairs, never on the current or later week. Does not alter underlying count
distributions or their CRPS; intercept/slope and role residuals are side
neutral transformations of P(Over) to prevent cosmetic Under favoritism.
"""
from __future__ import annotations

import hashlib
import json
import math
import numpy as np


def fail(reason):
    raise ValueError("PHASE2_CALIBRATION_ASOF_REJECTED:"+reason)


def _logit(p):
    x=max(0.0005,min(0.9995,float(p)))
    return math.log(x/(1.-x))


def _sigmoid(t):
    return 1.0/(1.0+math.exp(-max(-30.,min(30.,float(t)))))


def _solve_global(history):
    # Logistic ridge MAP shrink to IDENTITY p_calibrated=p_raw until there
    # are enough prior-week labels; the prior itself is pre-registered.
    x=np.array([_logit(z["raw_over"]) for z in history],dtype=float)
    y=np.array([z["actual_over"] for z in history],dtype=float)
    params=np.array([0.,1.],dtype=float)
    lam=np.array([8.,14.],dtype=float)
    for i in range(80):
        z=params[0]+params[1]*x
        p=1./(1.+np.exp(-np.clip(z,-30,30)))
        w=p*(1-p)
        gradient=np.array([
            float(np.sum(p-y))+lam[0]*params[0],
            float(np.sum((p-y)*x))+lam[1]*(params[1]-1.),
        ])
        hess=np.array([
            [float(np.sum(w))+lam[0],
             float(np.sum(w*x))],
            [float(np.sum(w*x)),
             float(np.sum(w*x*x))+lam[1]]
        ])
        step=np.linalg.solve(hess,gradient)
        proposed=params-step
        proposed[0]=np.clip(proposed[0],-4.5,4.5)
        proposed[1]=np.clip(proposed[1],0.05,1.8)
        if np.max(abs(proposed-params))<1e-8:
            params=proposed
            break
        params=proposed
    return float(params[0]),float(params[1])


def _role_offsets(history,a,b):
    # Partial pooling via penalized intercepts AFTER global map. Distinct
    # from fitting current-week outcomes, with strict minimum history.
    result={}
    roles=("WR","RB","TE")
    for role in roles:
        subset=[r for r in history if r["role"]==role]
        if len(subset)<40:
            result[role]={"offset":0.,"n":len(subset),"status":"insufficient_prior_label_rows"}
            continue
        x=np.array([_logit(r["raw_over"]) for r in subset],dtype=float)
        y=np.array([r["actual_over"] for r in subset],dtype=float)
        offset=0.
        for i in range(50):
            p=1./(1.+np.exp(-np.clip(a+b*x+offset,-30,30)))
            gradient=float(np.sum(p-y)+25.*offset)
            hess=float(np.sum(p*(1.-p))+25.)
            nxt=max(-2.0,min(2.0,offset-gradient/hess))
            if abs(nxt-offset)<1e-9:
                offset=nxt
                break
            offset=nxt
        result[role]={"offset":offset,"n":len(subset),"status":"fit_from_earlier_weeks"}
    return result


def calibrate_asof(history,offers,*,week,mode="global_platt"):
    if type(week) is not int or not 1<=week<=18:
        fail("invalid_week")
    if mode not in ("global_platt","role_platt","raw"):
        fail("unsupported_calibration_method")
    if not isinstance(history,list) or not isinstance(offers,list):
        fail("invalid_history_or_offers")
    allowed={"week","event_id","team","player_id","role","raw_over","actual_over"}
    for r in history:
        if not isinstance(r,dict) or set(r)!=allowed:
            fail("invalid_past_label_schema")
        if type(r["week"]) is not int or not 1<=r["week"]<week:
            fail("current_or_future_label_in_calibrator")
        if r["role"] not in ("WR","RB","TE"):
            fail("unrecognized_history_role")
        if r["actual_over"] not in (0,1):
            fail("invalid_prior_week_binary_label")
        if not isinstance(r["raw_over"],(float,int)) or not 0<=r["raw_over"]<=1:
            fail("invalid_past_probability")
    allowed_offer={"event_id","team","player_id","role","raw_over"}
    for r in offers:
        if not isinstance(r,dict) or set(r)!=allowed_offer:
            fail("current_offer_has_actual_or_outcome_field")
        if r["role"] not in ("WR","RB","TE"):
            fail("invalid_current_role")
        if not isinstance(r["raw_over"],(int,float)) or not 0<=r["raw_over"]<=1:
            fail("invalid_current_probability")
    key=lambda r:(r["event_id"],r["team"],r["player_id"])
    if len(set(map(key,offers)))!=len(offers):
        fail("duplicate_current_offer")
    # For duplicates in past history, same player/game forecast must be
    # counted ONCE; another model's rows must remain isolated by model.
    if len(set((r["week"],*key(r)) for r in history))!=len(history):
        fail("duplicate_historical_offer_or_player")
    if mode=="raw" or len(history)<80:
        a,b=0.,1.
        offsets={r:{"offset":0.,"n":0,"status":"identity"} for r in ("WR","RB","TE")}
        status="identity_no_history" if not history else (
            "identity_insufficient_80_prior_rows" if mode!="raw" else "identity_requested")
    else:
        a,b=_solve_global(history)
        offsets=_role_offsets(history,a,b) if mode=="role_platt" else {
            r:{"offset":0.,"n":sum(z["role"]==r for z in history),"status":"global_only"}
            for r in ("WR","RB","TE")}
        status="fit_from_earlier_weeks_only"
    out=[]
    for offer in offers:
        q=offer["raw_over"]
        z=a+b*_logit(q)+offsets[offer["role"]]["offset"]
        calibrated=_sigmoid(z)
        out.append({**offer,"calibrated_over":calibrated,
            "calibrated_under":1.-calibrated})
    report={
       "schema":"v25-p2-prequential-calibrator-v1",
       "week":week,"trained_on_latest_week":max(
           [x["week"] for x in history],default=0),
       "fit_count":len(history),
       "status":status,"method":mode,
       "a_intercept":a,"b_slope":b,"role_offsets":offsets,
       "future_labels_read":False,
       "calibration_is_point_in_time":True,
       "probabilities":out,
    }
    report["sha256"]=hashlib.sha256(json.dumps(
        report,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return report
