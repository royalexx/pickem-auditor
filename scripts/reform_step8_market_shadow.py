"""Step 8: matched same-contract market logit blend shadow.

Never train M2/M3 on 1-4 dates. Existing fit_blend.py M2/M3 are eligible
only after fully archived pregame sources, sufficient independent training
dates/rows, and heldout date-block uncertainty. A fixed equal-logit market
mix is a clearly labeled untrained descriptive scenario, not fitted weights.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path

from reform_phase4_scorecard import load_nfl_slate, load_historical, read_json

MIN_TRAIN_ROWS=300
MIN_TRAIN_DATES=20
MIN_EVAL_ROWS=100
MIN_EVAL_DATES=20


class MarketBlendError(ValueError):
    pass


def proper_pair(value, *, tolerance=1e-8):
    if value is None or not isinstance(value,dict):
        return False
    a,b=value.get("over"),value.get("under")
    return (type(a) in (int,float) and type(b) in (int,float)
            and math.isfinite(a) and math.isfinite(b)
            and 0<=a<=1 and 0<=b<=1
            and abs(a+b-1.)<=tolerance)


def sigmoid(x):
    if x>=0:return 1/(1+math.exp(-x))
    value=math.exp(x)
    return value/(1+value)


def logit(p):
    value=min(1-1e-9,max(1e-9,p))
    return math.log(value/(1-value))


def equal_logit_over(model,market):
    if not proper_pair(model) or not proper_pair(market):
        raise MarketBlendError("unverified_or_noncomplementary_two_way_forecast")
    # Equal coefficients declared before looking at any settlement. This
    # is NOT a fitted market-inclusive M2 or M3 logistic meta-model.
    return sigmoid(.5*logit(model["over"])+.5*logit(market["over"]))


def choose_over_probability(p_over, outcome):
    if outcome not in ("over","under") or not (0<=p_over<=1 and math.isfinite(p_over)):
        raise MarketBlendError("invalid_binary_outcome_or_probability")
    if abs(p_over-.5)<1e-12:
        return None
    chosen="over" if p_over>.5 else "under"
    p=max(p_over,1-p_over)
    return {"side":chosen,"p":p,"hit":int(chosen==outcome),
            "winner":outcome,"over":p_over,"under":1-p_over,
            "side_sum":1.}


def metrics(values):
    n=len(values)
    if not n:return {"n":0}
    hits=sum(x["hit"] for x in values)
    def loss(x):
        p=min(1-1e-12,max(1e-12,x["p"]))
        return -x["hit"]*math.log(p)-(1-x["hit"])*math.log1p(-p)
    return {"n":n,"hits":hits,"directional_accuracy":hits/n,
            "mean_selected_probability":sum(x["p"] for x in values)/n,
            "brier":sum((x["p"]-x["hit"])**2 for x in values)/n,
            "log_loss":sum(loss(x) for x in values)/n,
            "selected_over_share":sum(x["side"]=="over" for x in values)/n}


def same_contract_scenario(rows, *, model):
    tally=Counter()
    forecasts=[]
    for r in rows:
        m=(r.get("models") or {}).get(model)
        market=(r.get("models") or {}).get("Market")
        if m is None or market is None:
            tally["model_or_market_unavailable"]+=1
            continue
        if not proper_pair(m) or not proper_pair(market):
            tally["nonunit_two_way_forecast"]+=1
            continue
        p_model=m["over"]
        p_market=market["over"]
        p_mix=equal_logit_over(m,market)
        same={"model":choose_over_probability(p_model,r["outcome"]),
              "market":choose_over_probability(p_market,r["outcome"]),
              "fixed_equal_logit_market_mix":choose_over_probability(p_mix,r["outcome"])}
        if any(x is None for x in same.values()):
            tally["ties_no_direction"]+=1
            continue
        forecasts.append((r,same))
    slices={}
    for name in ("model","market","fixed_equal_logit_market_mix"):
        slices[name]=metrics([f[name] for _,f in forecasts])
    tally["same_contract_compared"]=len(forecasts)
    unique_dates=sorted({r["date"] for r,_ in forecasts})
    unique_games=sorted({str(r["game_id"]) for r,_ in forecasts})
    return {"source_model":model,
            "scenario":"fixed_equal_weights_in_log_odds_NOT_fitted_M2_M3",
            "coverage":dict(tally),
            "unique_dates":len(unique_dates),"unique_games":len(unique_games),
            "same_contract_metrics":slices,
            "promotion_allowed":False}


def oos_gates(rows, *, independent_source_archive_verified):
    # This diagnostic counts only rows; it NEVER fits or turns an estimate
    # into a real-time forecast. Dates and archive provenance must both pass.
    dates={r["date"] for r in rows}
    c=Counter()
    for r in rows:
        p=r["models"]
        for name in ("Engine_A","Engine_B","Market"):
            if proper_pair(p.get(name)):c[name]+=1
        if all(proper_pair(p.get(k)) for k in ("Engine_A","Market")):
            c["M2_complete_paired_inputs"]+=1
        if all(proper_pair(p.get(k)) for k in ("Engine_A","Engine_B","Market")):
            c["M3_complete_paired_inputs"]+=1
    reasons=[]
    if not independent_source_archive_verified:
        reasons.append("original_pregame_feature_source_archive_incomplete")
    if len(dates)<MIN_TRAIN_DATES+MIN_EVAL_DATES:
        reasons.append("fewer_than_40_training_plus_evaluation_dates")
    if c["M3_complete_paired_inputs"]<MIN_TRAIN_ROWS+MIN_EVAL_ROWS:
        reasons.append("fewer_than_400_matched_M3_training_plus_evaluation_contracts")
    return {"contract_count":len(rows),"independent_dates":len(dates),
            "complete_input_counts":dict(c),
            "requirements":{"train_rows":MIN_TRAIN_ROWS,"train_dates":MIN_TRAIN_DATES,
                            "eval_rows":MIN_EVAL_ROWS,"eval_dates":MIN_EVAL_DATES},
            "source_provenance_verified":bool(independent_source_archive_verified),
            "M2_M3_fitted":False,"weights_emitted":False,
            "fitting_authorized":not reasons,
            "blocking_reasons":reasons}


def audit(*,frozen,settlement,pinned,historical,archive_root):
    current,cr=load_nfl_slate(frozen,settlement,pinned)
    prior,hr=load_historical(historical,archive_root)
    # Old 70/30 research cohort is NEVER pooled with Nov 8 60/40 production.
    current_scenario=same_contract_scenario(current,model="Consensus")
    historical_scenario=same_contract_scenario(prior,model="Engine_A")
    current_gate=oos_gates(current,independent_source_archive_verified=False)
    past_gate=oos_gates(prior,independent_source_archive_verified=False)
    combined_dates={r["date"] for r in current+prior}
    return {
        "schema":"pickem_reform_step8_market_shadow_v1",
        "status":"M2_M3_not_fitted_and_not_promotable",
        "training_started":False,"production_modified":False,
        "original_source_receipts":{"current":cr,"retrospective":hr},
        "immutable_sha256":{"frozen":read_json(frozen)[1],
                            "settlement":read_json(settlement)[1],
                            "pinned":read_json(pinned)[1],
                            "historical":read_json(historical)[1]},
        "current_nov8_60_40_cohort":{
            "model":"Consensus","scenario":current_scenario,
            "fit_eligibility":current_gate},
        "older_nov5_7_research_cohort":{
            "model":"Engine_A","scenario":historical_scenario,
            "fit_eligibility":past_gate},
        "date_coverage_combined_but_not_pooled":len(combined_dates),
        "production_weight_changes_forbidden":True,
        "limitations":[
            "Only Nov 8 current production day and three older research dates are archived",
            "Original source feature publication/bytes incomplete; time-of-collection approximations are not certified historical pregame evidence",
            "The original historical market side pair is frequently not complementary; its rows fail closed instead of being silently de-vigged",
            "A fixed 50/50 log-odds blend is a sensitivity scenario, NOT a fitted M2 or M3 logistic meta-model",
            "Game/date correlation prevents treating overlapping props as independent",
            "A single slate may improve or worsen either model by chance",
            "No learned coefficients, backfilled probabilities, or production market corrections are authorized"]}


def main(argv=None):
    p=argparse.ArgumentParser()
    for k in ("frozen","settlement","pinned","historical","archive_root"):
        p.add_argument("--"+k.replace("_","-"),type=Path,required=True)
    p.add_argument("--out",type=Path)
    a=p.parse_args(argv)
    result=audit(frozen=a.frozen,settlement=a.settlement,pinned=a.pinned,
                 historical=a.historical,archive_root=a.archive_root)
    serialized=json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n"
    if a.out:
        if a.out.exists() and a.out.read_text()!=serialized:
            raise MarketBlendError("would_overwrite_different_market_shadow_receipt")
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(serialized)
    print(json.dumps({"state":result["status"],
                      "current":result["current_nov8_60_40_cohort"],
                      "historical":result["older_nov5_7_research_cohort"],
                      "combined_dates_not_pooled":result["date_coverage_combined_but_not_pooled"]},
                     sort_keys=True))


if __name__=="__main__":
    main()
