"""Replay *original* full-slate top-k selection without refitting or look-ahead.

The historical November 8 comparison and full-universe research receipts
contain enough frozen pregame information to reproduce 160 eligible candidates
and the exact 10 research priorities per sport. Actual outcomes are joined
only after that replay is verified, and only for the independently graded
NFL 1 PM games. Do not infer optimizer's curse from one slate.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

from reform_phase4_scorecard import load_nfl_slate, read_json, contract_key

REASONS={"STATUS_NOT_VERIFIED","VENUE_OR_FORECAST_UNVERIFIED",
         "CONTEXT_UNRESOLVED","RESEARCH_UNVERIFIED",
         "POST_SHADOW_PRODUCTION_PENDING"}
MODEL_NAMES=("Engine_A","Engine_B","Bayesian_A","Bayesian_B")
SPORTS=("NBA","NHL","NFL")


class SelectionAuditError(ValueError):
    pass


def identity(row):
    line=row.get("line",row.get("reference_line"))
    if type(line) not in (int,float) or not math.isfinite(line):
        raise SelectionAuditError("missing_or_invalid_line")
    keys=("run_id","forecast_at","sport","player_id",
          "team","opponent","stat","side")
    return tuple(str(row.get(k)) for k in keys)+(format(float(line),".15g"),)


def good_prob(x):
    return type(x) in (int,float) and math.isfinite(x) and 0<=x<=1


def rebuild_pool(frozen, reviews):
    comparison, _=read_json(frozen)
    evidence, _=read_json(reviews)
    if (comparison.get("schema")!="slate-model-comparison-v1"
            or evidence.get("schema")!="slate-full-universe-research-v1"):
        raise SelectionAuditError("wrong_immutable_comparison_or_review_schema")
    records=comparison["picks"]
    evidence_rows=evidence["reviews"]
    if len(records)!=len(evidence_rows) or evidence.get("contracts_reviewed")!=len(records):
        raise SelectionAuditError("full_universe_review_count_mismatch")
    by_id={}
    for r in evidence_rows:
        ident=identity(r)
        if ident in by_id:raise SelectionAuditError("duplicate_universe_review")
        by_id[ident]=r
    audit=Counter()
    candidates=[]
    for r in records:
        ident=identity(r)
        v=by_id.pop(ident,None)
        if v is None or r.get("block_reason")!=v.get("original_block_reason"):
            raise SelectionAuditError("unmatched_frozen_review_identity")
        models=r.get("models") or {}
        a=models.get("Engine_A") or {}
        b=models.get("Engine_B") or {}
        market=models.get("Market") or {}
        if (r.get("production_consensus_available") is not True
                or r.get("block_reason") not in REASONS
                or a.get("reliable") is not True or b.get("reliable") is not True):
            audit["production_or_primary_research_gate"]+=1
            continue
        if market.get("status")!="forecast" or len(market.get("books") or [])<2:
            audit["fewer_than_two_matched_frozen_books"]+=1
            continue
        values={m:r.get(m) for m in MODEL_NAMES}
        cons,price=r.get("Consensus"),r.get("Market")
        if not all(good_prob(x) for x in (cons,price,values["Engine_A"],values["Engine_B"])) or any(
                x is not None and not good_prob(x) for x in values.values()):
            audit["invalid_probability_or_provenance"]+=1
            continue
        if cons<.58:
            audit["below_consensus_watch_floor"]+=1
            continue
        edge=100*(cons-price)
        if edge<3:
            audit["below_market_edge_watch_floor"]+=1
            continue
        observed=[x for x in values.values() if x is not None]
        floor=min(observed)
        spread=max(observed)-floor
        history=v.get("player_tendency") or {}
        opportunity=history.get("opportunity")
        evidence_ok=(history.get("status")=="verified_historical"
                     and isinstance(opportunity,dict)
                     and opportunity.get("last_5_mean") is not None)
        score=round(
            40*cons +25*floor +25*max(0,min(edge/25,1))
            +5*(1-min(spread/.30,1)) +5*int(evidence_ok),3)
        candidates.append({"score":score,"floor":floor,"edge_pp":edge,
                           "row":r,"review":v,"identity":ident})
    if by_id:raise SelectionAuditError("orphaned_full_universe_review")
    return candidates, dict(audit),len(records)


def reconstructed_ranks(candidates,board):
    sorted_pool=sorted(candidates,key=lambda x:(
        -x["score"],-x["floor"],-x["edge_pp"],
        x["row"]["sport"],x["row"]["player"],
        x["row"]["stat"],x["row"]["side"]))
    result={}
    for sport in SPORTS:
        chosen=[];players=Counter();fixtures=Counter();identities=set()
        for item in sorted_pool:
            r=item["row"]
            if r["sport"]!=sport:continue
            fixture=tuple(sorted((str(r["team"]),str(r["opponent"]))))
            who=str(r.get("player_id") or r["player"])
            ident=(who,r["stat"],r["line"])
            if ident in identities or players[who]>=2 or fixtures[fixture]>=4:continue
            chosen.append(item)
            identities.add(ident)
            players[who]+=1
            fixtures[fixture]+=1
            if len(chosen)==10:break
        result[sport]=chosen
        recorded=board["top_10_by_sport"][sport]
        if len(recorded)!=len(chosen) or len(recorded)!=board["top_counts"][sport]:
            raise SelectionAuditError("recorded_rank_count_mismatch")
        for index,(frozen,origin) in enumerate(zip(chosen,recorded),1):
            if (frozen["identity"]!=identity(origin)
                    or origin.get("sport_rank")!=index
                    or not math.isclose(origin["research_priority_score"],frozen["score"],abs_tol=.00051)):
                raise SelectionAuditError("original_top10_selection_not_reproducible")
    return result


def score_observations(items):
    n=len(items)
    if not n:return {"n":0}
    def ll(p,y):
        p=min(1-1e-12,max(1e-12,p))
        return -y*math.log(p)-(1-y)*math.log1p(-p)
    def brier(column):return sum((x[column]-x["hit"])**2 for x in items)/n
    return {"n":n,
            "hits":sum(r["hit"] for r in items),
            "hit_rate":sum(r["hit"] for r in items)/n,
            "mean_consensus_probability":sum(r["consensus"] for r in items)/n,
            "mean_model_minus_market_pp":100*sum(r["consensus"]-r["market"] for r in items)/n,
            "mean_confidence_minus_hit_pp":100*sum(r["consensus"]-r["hit"] for r in items)/n,
            "consensus_brier":brier("consensus"),
            "market_same_side_brier":brier("market"),
            "consensus_log_loss":sum(ll(x["consensus"],x["hit"]) for x in items)/n,
            "market_same_side_log_loss":sum(ll(x["market"],x["hit"]) for x in items)/n,
            "distinct_games":len({x["game_id"] for x in items}),
            "distinct_stats":len({x["stat"] for x in items}),
            "selected_unders":sum(x["side"]=="under" for x in items)}


def audit(*,frozen,review,board,settlement,pinned):
    candidate_pool,excluded,total=rebuild_pool(frozen,review)
    original,board_sha=read_json(board)
    if (original.get("schema")!="slate-evidence-priority-v1"
            or original.get("full_universe_before_top10") is not True
            or original.get("ranking_not_a_probability") is not True
            or original.get("original_forecasts_unchanged") is not True
            or original.get("candidate_pool_count")!=len(candidate_pool)
            or original.get("full_universe_evaluated")!=total
            or original.get("excluded")!=excluded):
        raise SelectionAuditError("ranked_board_not_replayable_from_original_universe")
    ranked=reconstructed_ranks(candidate_pool,original)
    selected={x["identity"]:(sport,i)
              for sport,group in ranked.items()
              for i,x in enumerate(group,1)}
    graded,provenance=load_nfl_slate(frozen,settlement,pinned)
    verified={r["contract"]:r for r in graded}
    scored=[];seen=set();coverage=Counter()
    for item in candidate_pool:
        r=item["row"]
        if r["sport"]!="NFL":continue
        coverage["eligible_full_slate"]+=1
        if item["identity"] in selected:
            coverage["selected_full_slate_top10"]+=1
        if r.get("event_start")!="2026-11-08T18:00:00Z":
            coverage["not_in_officially_settled_1pm_window"]+=1
            continue
        coverage["eligible_1pm_original"]+=1
        key=contract_key(r)
        actual=verified.get(key)
        if actual is None:
            coverage["excluded_officially_unverified_or_push"]+=1
            continue
        if key in seen:
            raise SelectionAuditError("both_sides_eligible_for_same_contract")
        seen.add(key)
        hit=int(actual["outcome"]==r["side"])
        selected_rank=selected.get(item["identity"])
        scored.append({
            "identity":item["identity"],
            "contract":key,
            "player":r["player"],"stat":r["stat"],
            "side":r["side"],"game_id":actual["game_id"],
            "score":item["score"],"consensus":r["Consensus"],
            "market":r["Market"],"hit":hit,
            "selected_top5":bool(selected_rank and selected_rank[1]<=5),
            "selected_top10":bool(selected_rank),
            "sport_rank":selected_rank[1] if selected_rank else None})
    subsets={
        "eligible_scored_1pm":scored,
        "selected_original_top5": [x for x in scored if x["selected_top5"]],
        "selected_original_top10":[x for x in scored if x["selected_top10"]],
        "eligible_not_selected_top10":[x for x in scored if not x["selected_top10"]]}
    scores={k:score_observations(v) for k,v in subsets.items()}
    # Require overlap on both rank status and pregame market/stat bins before
    # claiming a matched selection comparison. This is NOT a fitted correction.
    strata=defaultdict(lambda:{"selected":[],"unselected":[]})
    for x in scored:
        stat=x["stat"]
        band=int(x["consensus"]*10)
        edge_band=int(100*(x["consensus"]-x["market"])//5)
        group=(stat,band,edge_band)
        strata[group]["selected" if x["selected_top10"] else "unselected"].append(x)
    matched=[v for v in strata.values() if v["selected"] and v["unselected"]]
    return {"schema":"pickem_reform_phase5_topk_selection_audit_v1",
            "status":"read_only_replay_no_promotion",
            "production_changed":False,"training_started":False,
            "source_hashes_sha256":{
                "frozen_comparison":read_json(frozen)[1],
                "full_universe_reviews":read_json(review)[1],
                "original_top10_board":board_sha,
                "official_settlement":read_json(settlement)[1]},
            "reproduction":{
                "full_universe_rows":total,
                "original_eligible_pool":len(candidate_pool),
                "replay_matches_all_original_top30":True,
                "original_exclusions":excluded,
                "original_top_counts":original["top_counts"],
                "top_replayed_per_sport":{s:len(v) for s,v in ranked.items()}},
            "outcome_scope":{
                "sport":"NFL","event_start":"2026-11-08T18:00:00Z",
                "official_contracts":len(graded),
                "full_slate_nfl_eligible":coverage["eligible_full_slate"],
                "full_slate_nfl_top10":coverage["selected_full_slate_top10"],
                "eligible_1pm":coverage["eligible_1pm_original"],
                "eligible_1pm_scored":len(scored),
                "eligible_1pm_unverified_or_push":coverage["excluded_officially_unverified_or_push"],
                "selected_1pm_top10_scored":len(subsets["selected_original_top10"]),
                "ranked_outside_1pm_or_unsettled":coverage["selected_full_slate_top10"]-len(subsets["selected_original_top10"])},
            "scores":scores,
            "selected_1pm_details":[{k:v for k,v in x.items() if k not in ("contract","identity")}
                for x in subsets["selected_original_top10"]],
            "stratified_selection_support":{
                "stat_confidence_edge_strata_with_both_selected_and_unselected":len(matched),
                "selected_cases_in_overlapping_strata":sum(len(v["selected"]) for v in matched),
                "unselected_cases_in_overlapping_strata":sum(len(v["unselected"]) for v in matched),
                "method":"exact_stat_x_10pp_consensus_band_x_5pp_model_market_gap_band"},
            "evidence_sufficient_to_infer_optimizers_curse":False,
            "limitations":[
                "Top-ten research candidates are never verified wagers or approved Tiers",
                "The original 30 selected picks were ranked over all three sports and all start windows; only NFL 1 PM has pinned independently graded settlement",
                "Selection, stat, confidence, market edge, and game context are confounded",
                "One slate and extremely few originally selected settled top-10 entries cannot identify winner's curse",
                "Full frozen source features and Engine B uncertainty receipts were not independently archived for all original comparisons",
                "No shrinkage, calibration or market-informed deployment authorized"]}


def main(argv=None):
    p=argparse.ArgumentParser()
    for k in ("frozen","review","board","settlement","pinned"):
        p.add_argument("--"+k,type=Path,required=True)
    p.add_argument("--out",type=Path)
    a=p.parse_args(argv)
    result=audit(frozen=a.frozen,review=a.review,board=a.board,
                 settlement=a.settlement,pinned=a.pinned)
    data=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n"
    if a.out:
        if a.out.exists() and a.out.read_text()!=data:
            raise SelectionAuditError("would_replace_original_receipt")
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(data)
    print(json.dumps({"status":result["status"],"reproduction":result["reproduction"],
                      "scope":result["outcome_scope"],"scores":result["scores"],
                      "strata":result["stratified_selection_support"]},sort_keys=True))


if __name__=="__main__":
    main()
