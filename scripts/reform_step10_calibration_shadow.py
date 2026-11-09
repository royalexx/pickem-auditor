"""Step 10: identity-preserving Beta calibration and global market stacking.

A read-only model research harness. It has no production writer and refuses
to fit from incomplete source archives. No sport/position/market segmented
fitting: both candidate families use globally pooled, regularized parameters.
All heldout probabilities compare on the same chronological exact-contract
nonpush binary outcomes with date-block intervals.

For count-line pushes this models P(over | no push); no push-rate calibration
or entry probability is asserted.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import random

from fit_blend import fit_logistic, predict_logistic
from reform_phase4_scorecard import load_nfl_slate, read_json
from reform_step8_market_shadow import proper_pair, logit, sigmoid

VERSION="pickem-reform-step10-calibration-shadow-v1"
EPS=1e-8
L2=20.0
MIN_TRAIN=300
MIN_EVAL=100
MIN_TRAIN_DATES=20
MIN_EVAL_DATES=20
BOOTSTRAPS=600
SEED=20261109
CANDIDATES=("beta_consensus","global_stack_market")
BASELINES=("original_consensus","market")


class CalibrationError(ValueError):
    pass


def finite_probability(p):
    return type(p) in (int,float) and math.isfinite(p) and 0<=p<=1


def betafeatures(p):
    """Identity is EXACTLY a=b=1, c=0: logit(p)=log(p)-log(1-p)."""
    if not finite_probability(p):
        raise CalibrationError("invalid_calibration_probability")
    safe=min(1-EPS,max(EPS,p))
    return {"log_p":math.log(safe),"neg_log1m_p":-math.log1p(-safe)}


def beta_map(p, params):
    a,b,c=(params[k] for k in ("a","b","c"))
    if any(type(v) not in (int,float) or not math.isfinite(v)
           for v in (a,b,c)) or a<0 or b<0:
        raise CalibrationError("invalid_or_nonmonotone_beta_coefficients")
    feature=betafeatures(p)
    return sigmoid(c+a*feature["log_p"]+b*feature["neg_log1m_p"])


def stack_map(model_p,market_p,params):
    if not finite_probability(model_p) or not finite_probability(market_p):
        raise CalibrationError("invalid_global_stack_probabilities")
    if any(type(v) not in (float,int) or not math.isfinite(v)
           for v in params.values()):
        raise CalibrationError("nonfinite_stack_weights")
    return sigmoid(params["intercept"]+
                   params["logit_model"]*logit(model_p)+
                   params["logit_market"]*logit(market_p))


def normalize(rows):
    """One contract, one binary outcome, both pregame 2-way pairs coherent."""
    seen=set()
    good=[]
    excluded=defaultdict(int)
    for row in rows:
        if row.get("outcome") not in ("over","under"):
            excluded["push_unverified_or_other_outcome"]+=1
            continue
        model=(row.get("models") or {}).get("Consensus")
        market=(row.get("models") or {}).get("Market")
        if not proper_pair(model) or not proper_pair(market):
            excluded["noncomplementary_or_missing_paired_input"]+=1
            continue
        date=row.get("date")
        game=row.get("game_id")
        contract=row.get("contract")
        if (not isinstance(date,str) or not date or not game or
                not isinstance(contract,tuple) or not contract):
            raise CalibrationError("missing_original_game_date_or_contract")
        from datetime import date as Date
        try:Date.fromisoformat(date)
        except ValueError as e:raise CalibrationError("invalid_original_date") from e
        key=(date,tuple(contract))
        if key in seen:raise CalibrationError("duplicate_original_settled_contract")
        seen.add(key)
        good.append({"date":date,"game_id":str(game),
                     "contract":tuple(contract),
                     "p_model":float(model["over"]),
                     "p_market":float(market["over"]),
                     "y":int(row["outcome"]=="over")})
    good.sort(key=lambda r:(r["date"],repr(r["contract"])))
    return good,dict(excluded)


def split_dates(rows):
    dates=sorted({r["date"] for r in rows})
    by=defaultdict(list)
    for r in rows:by[r["date"]].append(r)
    total=len(rows)
    cumulative=0
    for i,date in enumerate(dates):
        if (i>=MIN_TRAIN_DATES and len(dates)-i>=MIN_EVAL_DATES
                and cumulative>=MIN_TRAIN and
                total-cumulative>=MIN_EVAL):
            before=[r for d in dates[:i] for r in by[d]]
            after=[r for d in dates[i:] for r in by[d]]
            if not before or not after or before[-1]["date"]>=after[0]["date"]:
                raise CalibrationError("nonchronological_calibration_fold")
            return before,after,{"first_holdout_date":date,
                    "train_n":len(before),"holdout_n":len(after),
                    "train_dates":i,"holdout_dates":len(dates)-i}
        cumulative+=len(by[date])
    return None,None,{"available_n":len(rows),"available_dates":len(dates),
            "reason":"no_verified_300_100_rows_and_20_20_dates_chronological_split"}


def fit_beta(training):
    design=[{"features":betafeatures(x["p_model"]),"label":x["y"]} for x in training]
    priors={"intercept":0.0,"log_p":1.0,"neg_log1m_p":1.0}
    fit=fit_logistic(design,["log_p","neg_log1m_p"],priors,L2)
    params={"a":fit["log_p"],"b":fit["neg_log1m_p"],
            "c":fit["intercept"]}
    if params["a"]<0 or params["b"]<0:
        raise CalibrationError("beta_fit_nonmonotone_abstain")
    return params


def fit_stack(training):
    design=[{"features":{"logit_model":logit(r["p_model"]),
                         "logit_market":logit(r["p_market"])},
             "label":r["y"]} for r in training]
    # Partial pooling toward balanced global information, not top-k selected.
    priors={"intercept":0.,"logit_model":.5,"logit_market":.5}
    return fit_logistic(design,["logit_model","logit_market"],priors,L2)


def logloss(p,y):
    p=min(1-1e-12,max(1e-12,p))
    return -y*math.log(p)-(1-y)*math.log1p(-p)


def evaluate_predictions(test, beta,stack):
    rows=[]
    for r in test:
        preds={
            "original_consensus":r["p_model"],
            "market":r["p_market"],
            "beta_consensus":beta_map(r["p_model"],beta),
            "global_stack_market":stack_map(r["p_model"],r["p_market"],stack),
        }
        if not all(finite_probability(p) for p in preds.values()):
            raise CalibrationError("invalid_evaluation_probability")
        rows.append({"date":r["date"],"game_id":r["game_id"],
                     "contract":r["contract"],"y":r["y"],"predictions":preds})
    return rows


def metric(rows, model):
    if not rows:return {"n":0}
    n=len(rows)
    return {"n":n,"brier":sum((r["predictions"][model]-r["y"])**2
                              for r in rows)/n,
            "log_loss":sum(logloss(r["predictions"][model],r["y"])
                           for r in rows)/n,
            "over_predicted":sum(r["predictions"][model] for r in rows)/n,
            "over_realized":sum(r["y"] for r in rows)/n,
            "directional_accuracy":sum(
                (r["predictions"][model]>.5)==bool(r["y"])
                for r in rows)/n}


def interval(rows,candidate,baseline,*,metric_name,draws=BOOTSTRAPS,seed=SEED):
    dates=defaultdict(list)
    for r in rows:dates[r["date"]].append(r)
    if len(dates)<MIN_EVAL_DATES or len(rows)<MIN_EVAL:
        return {"status":"insufficient_independent_holdout",
                "interval_95":None,"n_dates":len(dates)}
    keys=sorted(dates)
    rng=random.Random(seed)
    values=[]
    for _ in range(draws):
        sample=[r for d in rng.choices(keys,k=len(keys)) for r in dates[d]]
        vals=metric(sample,baseline)[metric_name]-metric(sample,candidate)[metric_name]
        values.append(vals)
    values.sort()
    low=values[int(.025*draws)]
    high=values[int(.975*draws)-1]
    return {"status":"descriptive_date_block_only",
            "baseline_minus_candidate":metric(rows,baseline)[metric_name]-
                                       metric(rows,candidate)[metric_name],
            "interval_95":[low,high],"n_dates":len(dates)}


def research(rows, *, source_pregame_verified, draws=BOOTSTRAPS):
    if type(source_pregame_verified) is not bool:
        raise CalibrationError("source_verification_must_be_boolean")
    if draws<100 or draws>5000:raise CalibrationError("invalid_bootstrap_draw_count")
    cohort,excluded=normalize(rows)
    training,test,cut=split_dates(cohort)
    report={
        "schema":VERSION,
        "input_contracts":len(rows),"eligible_coherent_contracts":len(cohort),
        "excluded":excluded,
        "original_source_pregame_verified":source_pregame_verified,
        "split":cut,
        "status":"blocked","no_fitted_parameters_released":True,
        "production_promotion_authorized":False,
        "training_started":False,"production_modified":False,
        "model_scope":"global_binary_nonpush_over_only",
        "excluded_push_mass_modeling":True,
        "requirements":{"train":MIN_TRAIN,"evaluation":MIN_EVAL,
                       "train_dates":MIN_TRAIN_DATES,"evaluation_dates":MIN_EVAL_DATES},
    }
    if not source_pregame_verified:
        report["block_reason"]="original_point_in_time_source_archives_not_verified"
        return report
    if training is None:
        report["block_reason"]=cut["reason"]
        return report
    beta=fit_beta(training)
    stack=fit_stack(training)
    scored=evaluate_predictions(test,beta,stack)
    comparisons={}
    for candidate in CANDIDATES:
        comparisons[candidate]={}
        for baseline in BASELINES:
            comparisons[candidate][baseline]={
                name:interval(scored,candidate,baseline,metric_name=name,draws=draws)
                for name in ("brier","log_loss")}
    metrics={name:metric(scored,name) for name in BASELINES+CANDIDATES}
    # Even a statistically promising *shadow* experiment is not production.
    passboth=all(
        comparisons[c][b][m]["interval_95"][0]>0
        for c in CANDIDATES for b in BASELINES for m in ("brier","log_loss"))
    report.update({
        "status":"chronological_research_heldout_only",
        "block_reason":"no_external_independent_promotion_or_future_policy_approval",
        "coefficient_status":"internal_research_only_do_not_export",
        "calibration_family_identity_included":True,
        "train_and_test_keys_disjoint":True,
        "same_contract_holdout_metrics":metrics,
        "paired_date_block_baseline_improvements":comparisons,
        "all_candidates_beat_both_baselines":passboth,
        "full_holdout_rows_evaluated":len(scored),
        "trained_coefficients_not_emitted_to_production":True,
    })
    return report


def audit_original(*,frozen,settlement,pinned):
    from reform_phase4_scorecard import load_nfl_slate
    original,receipt=load_nfl_slate(frozen,settlement,pinned)
    # Loader verifies pinned original snapshot and official settlement but
    # explicitly reports source_completeness_verified=False. Do not upgrade
    # that incomplete claim based on hashes of only downstream files.
    full_source=receipt.get("source_completeness_verified") is True
    output=research(original,source_pregame_verified=full_source)
    output.update({"original_sha256":{
        "comparison":read_json(frozen)[1],
        "settlement":read_json(settlement)[1],
        "pinned":read_json(pinned)[1]},
        "official_contracts":len(original),
        "scope":"original_nfl_1pm_2026_11_08_only_no_reconstructed_preds"})
    return output


def main(argv=None):
    p=argparse.ArgumentParser()
    for name in ("frozen","settlement","pinned"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--out",type=Path)
    a=p.parse_args(argv)
    output=audit_original(frozen=a.frozen,settlement=a.settlement,pinned=a.pinned)
    data=json.dumps(output,sort_keys=True,indent=2,allow_nan=False)+"\n"
    if a.out:
        if a.out.exists() and a.out.read_text()!=data:
            raise CalibrationError("would_replace_different_calibration_audit")
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(data)
    print(json.dumps(output,sort_keys=True))


if __name__=="__main__":
    main()
