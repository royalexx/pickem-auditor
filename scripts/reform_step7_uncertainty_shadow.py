"""Step 7: original full-universe selection vs fixed, uncertainty-proxy shadows.

Read-only, non-promotable research. Inter-engine disagreement is NOT a
calibrated standard error, and missing Engine B relative_se MUST NOT be
fabricated. The frozen ranking weights and eligibility are unchanged.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import random

from reform_phase4_scorecard import load_nfl_slate, read_json, contract_key
from reform_phase5_selection_audit import (
    rebuild_pool,reconstructed_ranks,identity,SPORTS,SelectionAuditError,
    score_observations,
)

LAMBDAS=(0.0,0.5,1.0,1.5)
SEED=20261108


def clip(x,lo=0.,hi=1.):
    return max(lo,min(hi,x))


def candidate_profile(item):
    row=item["row"]
    v=[row.get(k) for k in ("Engine_A","Engine_B","Bayesian_A","Bayesian_B")
       if row.get(k) is not None]
    if len(v)<2 or not all(type(x) in (float,int) and 0<=x<=1 and math.isfinite(x) for x in v):
        raise SelectionAuditError("missing_original_engine_disagreement_inputs")
    engine_b=(row.get("models") or {}).get("Engine_B") or {}
    value=engine_b.get("relative_se")
    relative_se=None
    if value is not None:
        if type(value) not in (float,int) or not math.isfinite(value) or value<0:
            raise SelectionAuditError("invalid_engine_b_relative_se")
        relative_se=float(value)
    return {"spread":max(v)-min(v),"n_models":len(v),"relative_se":relative_se,
            "uncertainty_kind":"intermodel_disagreement_proxy_not_probability_standard_error"}


def shadow_score(item, *, penalty_pp, strength=1.0):
    if strength<0 or not math.isfinite(strength):
        raise SelectionAuditError("invalid_uncertainty_strength")
    # Only perturb the original 25-point market-edge component. Every other
    # original score component, market, side, line, and source stays frozen.
    original_component=25*clip(item["edge_pp"]/25)
    remaining=max(0.,item["edge_pp"]-strength*penalty_pp)
    shadow_component=25*clip(remaining/25)
    return round(item["score"]-original_component+shadow_component,6)


def rank_with_original_caps(pool, *, score_key="shadow_score"):
    by_sport={}
    order=sorted(pool,key=lambda x:(
        -x[score_key],-x["floor"],-x["edge_pp"],
        x["row"]["sport"],x["row"]["player"],
        x["row"]["stat"],x["row"]["side"]))
    for sport in SPORTS:
        selected=[];players=Counter();fixtures=Counter();seen=set()
        for item in order:
            row=item["row"]
            if row["sport"]!=sport:continue
            fixture=tuple(sorted((str(row["team"]),str(row["opponent"]))))
            who=str(row.get("player_id") or row["player"])
            key=(who,row["stat"],row["line"])
            if key in seen or players[who]>=2 or fixtures[fixture]>=4:
                continue
            selected.append(item)
            seen.add(key);players[who]+=1;fixtures[fixture]+=1
            if len(selected)==10:break
        by_sport[sport]=selected
    return by_sport


def serialize_ranked(rows):
    return [{"rank":index,"player":x["row"]["player"],
             "sport":x["row"]["sport"],"stat":x["row"]["stat"],
             "side":x["row"]["side"],"line":x["row"]["line"],
             "identity":list(x["identity"]),
             "model_consensus":x["row"]["Consensus"],
             "market":x["row"]["Market"],
             "original_score":x["score"],
             "shadow_score":x.get("shadow_score"),
             "frozen_edge_pp":x["edge_pp"],
             "uncertainty_proxy_spread_pp":100*x["profile"]["spread"],
             "uncertainty_penalty_pp":x.get("uncertainty_penalty_pp"),
             "engine_b_relative_se":x["profile"]["relative_se"]}
            for index,x in enumerate(rows,1)]


def audit(frozen,review,board, *, settlement=None,pinned=None):
    pool,excluded,total=rebuild_pool(frozen,review)
    archive,board_hash=read_json(board)
    source,_=read_json(frozen)
    if (archive.get("schema")!="slate-evidence-priority-v1"
            or archive.get("date")!=source.get("metadata",{}).get("day")
            or archive.get("candidate_pool_count")!=len(pool)
            or archive.get("full_universe_evaluated")!=total
            or archive.get("excluded")!=excluded):
        raise SelectionAuditError("historical_rank_provenance_mismatch")
    original=reconstructed_ranks(pool,archive)
    profiles={x["identity"]:candidate_profile(x) for x in pool}
    original_keys={sport:[x["identity"] for x in ranked] for sport,ranked in original.items()}
    variants={}
    for strength in LAMBDAS:
        enriched=[]
        for item in pool:
            profile=profiles[item["identity"]]
            penalty_pp=50*profile["spread"]
            enriched.append({**item,"profile":profile,
                             "uncertainty_penalty_pp":penalty_pp,
                             "shadow_score":shadow_score(item,penalty_pp=penalty_pp,strength=strength)})
        ranked=rank_with_original_caps(enriched)
        if strength==0 and any([x["identity"] for x in ranked[s]]!=original_keys[s] for s in SPORTS):
            raise SelectionAuditError("unadjusted_shadow_does_not_reproduce_original")
        variants[str(strength)]={
            "strength":strength,
            "per_sport":{
                sport:{"original_overlap_top10":len(set(original_keys[sport]) &
                              {x["identity"] for x in ranked[sport]}),
                       "original_overlap_top5":len(set(original_keys[sport][:5]) &
                              {x["identity"] for x in ranked[sport][:5]}),
                       "ranked":serialize_ranked(ranked[sport])}
                for sport in SPORTS}}
    # Negative control: permute spread estimates *within* sports, retaining
    # identical eligible candidates and original probability/market signals.
    rng=random.Random(SEED)
    randomized={}
    for sport in SPORTS:
        entries=[x for x in pool if x["row"]["sport"]==sport]
        penalties=[50*profiles[x["identity"]]["spread"] for x in entries]
        rng.shuffle(penalties)
        randomized.update({x["identity"]:penalty for x,penalty in zip(entries,penalties)})
    shuffled=[{**x,"profile":profiles[x["identity"]],
                "uncertainty_penalty_pp":randomized[x["identity"]],
                "shadow_score":shadow_score(x,penalty_pp=randomized[x["identity"]],strength=1.)}
              for x in pool]
    shuffled_ranks=rank_with_original_caps(shuffled)
    selection={
        "schema":"pickem-reform-step7-shadow-rank-v1",
        "state":"research_only_not_probabilistically_calibrated",
        "training_started":False,"production_modified":False,
        "rank_formula_deployed":False,
        "original_full_universe_rows":total,"original_eligible_candidates":len(pool),
        "original_30_top10_reproduced":True,
        "source_sha256":{"frozen":read_json(frozen)[1],
                         "review":read_json(review)[1],"board":board_hash},
        "uncertainty_available":{
            "engine_b_relative_se_usable":sum(p["relative_se"] is not None for p in profiles.values()),
            "candidates":len(profiles),
            "missing_relative_se":sum(p["relative_se"] is None for p in profiles.values()),
            "disagreement_is_not_epistemic_standard_error":True},
        "formula":"original_score minus original_edge_component plus clipped_edge_minus_lambda_half_range",
        "weights_original_unchanged":True,
        "negative_control":"within_sport_shuffled_intermodel_spread_penalty",
        "negative_control_top10_overlap":{
            sport:len(set(original_keys[sport]) &
                      {x["identity"] for x in shuffled_ranks[sport]})
            for sport in SPORTS},
        "variants":variants,
        "limits":[
            "Published NUTS numerical_mc_se is numerical integration error, not predictive uncertainty",
            "Inter-engine spread mixes bias, shared information and epistemic disagreement; not a calibrated SE",
            "Engine B relative_se absent in original frozen archive; do not impute it",
            "A one-slate ranking-churn analysis cannot establish optimizer's curse or portfolio profit",
            "The original rank is a research priority, not a model probability",
            "No calibrated edge shrinkage or new eligibility threshold is authorized"]}
    if settlement is not None or pinned is not None:
        if settlement is None or pinned is None:
            raise SelectionAuditError("settlement_and_pinned_must_be_supplied_together")
        graded,_=load_nfl_slate(frozen,settlement,pinned)
        by_contract={r["contract"]:r for r in graded}
        existing=set()
        for key,variant in variants.items():
            if key not in ("0.0","1.0"):
                continue
            scores={}
            for sport,data in variant["per_sport"].items():
                if sport!="NFL":continue
                included=[]
                for record in data["ranked"]:
                    item=next(x for x in pool if list(x["identity"])==record["identity"])
                    row=item["row"]
                    if row.get("event_start")!="2026-11-08T18:00:00Z":continue
                    match=by_contract.get(contract_key(row))
                    if match is None:continue
                    included.append({"consensus":row["Consensus"],
                                    "market":row["Market"],
                                    "hit":int(row["side"]==match["outcome"]),
                                    "game_id":match["game_id"],"stat":row["stat"],
                                    "side":row["side"]})
                scores[sport]=score_observations(included)
            selection["variants"][key]["selected_1pm_official_outcomes"]=scores
        selection["outcome_scope_warning"]="Only original NFL 1 PM graded window; do not evaluate other sports or start times as losses"
    return selection


def main(argv=None):
    p=argparse.ArgumentParser()
    for key in ("frozen","review","board"):
        p.add_argument("--"+key,type=Path,required=True)
    p.add_argument("--settlement",type=Path)
    p.add_argument("--pinned",type=Path)
    p.add_argument("--out",type=Path)
    a=p.parse_args(argv)
    result=audit(a.frozen,a.review,a.board,settlement=a.settlement,pinned=a.pinned)
    data=json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n"
    if a.out:
        if a.out.exists() and a.out.read_text()!=data:
            raise SelectionAuditError("would_overwrite_original_result")
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(data)
    print(json.dumps({"state":result["state"],"eligible":result["original_eligible_candidates"],
                      "uncertainty":result["uncertainty_available"],
                      "top10_overlap":{k:{s:v["original_overlap_top10"]
                        for s,v in e["per_sport"].items()} for k,e in result["variants"].items()},
                      "negative_control":result["negative_control_top10_overlap"]},sort_keys=True))


if __name__=="__main__":
    main()
