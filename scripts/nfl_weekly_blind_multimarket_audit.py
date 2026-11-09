"""Independent week-by-week receipt and performance audit.

Reads only already settled weeks and original SHA-locked pregame packets.
No fitting, access to hidden week outcomes or recomputed predictions.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import argparse
import hashlib
import json
import math
from pathlib import Path
import random

from nfl_weekly_blind_multimarket import MARKETS,SCHEMA


class WeeklyAuditError(ValueError):pass


def read_verify(path):
    raw=Path(path).read_bytes()
    return json.loads(raw),hashlib.sha256(raw).hexdigest()


def weighted_metrics(weeks,part):
    samples=[]
    for week in weeks:
        for m in MARKETS if part is None else [part]:
            r=week["by_market"][m]
            n=r["model"]["n"]
            if n<=0:continue
            a=r["model"];b=r["historical_baseline"]
            if b["n"]!=n:raise WeeklyAuditError("unmatched_model_control_cohort")
            samples.append((n,a,b))
    total=sum(n for n,_,_ in samples)
    if not total:return {"n":0}
    metrics=("brier","log_loss","directional_accuracy")
    result={"n":total}
    for name in metrics:
        result["model_"+name]=sum(n*a[name] for n,a,b in samples)/total
        result["baseline_"+name]=sum(n*b[name] for n,a,b in samples)/total
        result["delta_model_minus_baseline_"+name]=(
            result["model_"+name]-result["baseline_"+name])
    return result


def weekly_interval(weeks,market,*,draws=1200,seed=20261109):
    if len(weeks)<5:return None
    rng=random.Random(seed)
    reps={name:[] for name in ("brier","log_loss","directional_accuracy")}
    for _ in range(draws):
        sample=rng.choices(weeks,k=len(weeks))
        stat=weighted_metrics(sample,market)
        if not stat.get("n"):continue
        for key in reps:
            reps[key].append(stat["delta_model_minus_baseline_"+key])
    def ci(items):
        if not items:return None
        items.sort()
        return [items[int(.025*len(items))],items[int(.975*len(items))-1]]
    return {k:ci(v) for k,v in reps.items()}


def audit(root, *, expected_weeks=18, year=2024):
    root=Path(root)
    if not 1<=expected_weeks<=18 or year not in (2024,2025):
        raise WeeklyAuditError("invalid_experiment_year_week_count")
    settlements=[];receipts=[];prior=None
    for week in range(1,expected_weeks+1):
        directory=root/f"{year}_week_{week:02d}"
        packet,p_sha=read_verify(directory/"pregame_packet.json")
        frozen,f_sha=read_verify(directory/"frozen_all_markets.json")
        lock,l_sha=read_verify(directory/"lock.json")
        settled,s_sha=read_verify(directory/"settlement.json")
        cipher=(directory/"encrypted_outcomes.bin").read_bytes()
        cipher_sha=hashlib.sha256(cipher).hexdigest()
        for obj,stage in ((packet,"pregame"),(frozen,"all_markets_frozen"),
                          (lock,"complete_week_market_lock"),
                          (settled,"complete_week_settled")):
            if obj.get("schema")!=SCHEMA or obj.get("stage")!=stage:
                raise WeeklyAuditError("original_week_stage_mismatch")
            if obj.get("week")!=week or obj.get("year")!=year:
                raise WeeklyAuditError("week_identity_mismatch")
        if packet.get("target_week_results_in_packet") is not False:
            raise WeeklyAuditError("target_result_exposure_not_explicitly_blocked")
        if (packet.get("markets")!=list(MARKETS) or
                frozen.get("markets_order")!=list(MARKETS) or
                set(frozen.get("market_results",{}))!=set(MARKETS) or
                set(settled.get("by_market",{}))!=set(MARKETS) or
                lock.get("market_count")!=len(MARKETS)):
            raise WeeklyAuditError("incomplete_required_week_markets")
        if (frozen.get("packet_sha256")!=p_sha or
                lock.get("packet_sha256")!=p_sha or
                lock.get("forecast_sha256")!=f_sha or
                lock.get("encrypted_vault_sha256")!=cipher_sha or
                settled.get("encrypted_vault_sha256")!=cipher_sha or
                settled.get("lock_sha256")!=l_sha or
                settled.get("forecast_sha256")!=f_sha):
            raise WeeklyAuditError("corrupted_frozen_week_receipt")
        if (settled.get("all_markets_frozen_before_any_result") is not True
                or settled.get("trained_only_after_whole_week_revealed") is not True):
            raise WeeklyAuditError("missing_no_partial_week_result_gate")
        if settled.get("markets_scored")!=len(MARKETS):
            raise WeeklyAuditError("missing_graded_market")
        if prior:
            if packet.get("previous_week_settlement_sha256")!=prior["settlement_sha"]:
                raise WeeklyAuditError("week_chain_not_same_original_receipt")
            for m in MARKETS:
                before=settled["prior_train_examples_by_market"][m]
                after=prior["settled"]["prior_train_examples_by_market"][m]+(
                      prior["settled"]["next_week_model_update"][m])
                if before!=after:
                    raise WeeklyAuditError("training_counts_did_not_update_after_settlement:"+m)
        else:
            if packet.get("previous_week_settlement_sha256") is not None:
                raise WeeklyAuditError("week1_has_prior_2024_results")
        for m in MARKETS:
            out=settled["by_market"][m]
            reg=packet["market_packets"][m]
            if (out["pregame_candidates"]!=len(reg["candidates"])
                or out["forecasted"]!=len(frozen["market_results"][m]["predictions"])
                or out["scored_participants"]+out["unmatched_nonparticipating_or_unverified"]
                   !=out["forecasted"]
                or out["model"]["n"]!=out["historical_baseline"]["n"]
                or out["model"]["n"]!=out["scored_participants"]):
                raise WeeklyAuditError("unmatched_same_market_scored_contracts:"+m)
        settlements.append(settled)
        receipts.append({"week":week,"market_count":len(MARKETS),
                         "sealed_forecast_sha256":f_sha,
                         "week_settlement_sha256":s_sha,
                         "forecasts":settled["total_forecasts"],
                         "scored":settled["total_scored"]})
        prior={"settled":settled,"settlement_sha":s_sha}
    market_metrics={}
    for m in MARKETS:
        attempted=sum(w["by_market"][m]["pregame_candidates"] for w in settlements)
        predicted=sum(w["by_market"][m]["forecasted"] for w in settlements)
        graded=sum(w["by_market"][m]["scored_participants"] for w in settlements)
        observed=sum(w["next_week_model_update"][m] for w in settlements)
        if graded>predicted or graded>observed:
            raise WeeklyAuditError("graded_more_than_observed_or_predicted:"+m)
        market_metrics[m]={
            "candidate_count":attempted,"predicted":predicted,"graded":graded,
            "unmatched_predictions":predicted-graded,
            "observed_with_no_pregame_forecast":observed-graded,
            "observed_outcomes":observed,
            "candidate_participation_coverage":graded/predicted if predicted else None,
            "observed_row_coverage":graded/observed if observed else None,
            "proper_score":weighted_metrics(settlements,m),
            "paired_week_block_95pct_descriptive":weekly_interval(
                settlements,m,seed=20261109+list(MARKETS).index(m)),
            "same_contract_model_vs_baseline":True,
        }
    all_metrics=weighted_metrics(settlements,None)
    return {
        "schema":"pickem-nfl-weekly-blind-independent-audit-v1",
        "year":year,"weeks":len(settlements),
        "n_markets":len(MARKETS),"sequential_all_market_reveal_verified":True,
        "all_week_locks_verified":True,
        "training_counts_advance_only_after_previous_week_settlement":True,
        "week_receipts":receipts,
        "all_markets":market_metrics,
        "all_scored_aggregate":all_metrics,
        "overall_week_block_95pct_descriptive":weekly_interval(
            settlements,None,seed=20261109),
        "original_bookmaker_quotes":False,
        "candidate_eligibility_only_prior_rosters":True,
        "2024_originally_untouched_design":False,
        "calibration_or_tier_promotion_authorized":False,
        "original_bayesian_models_reevaluated":False,
        "training_restarted_on_dell":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--weeks",type=int,default=18)
    p.add_argument("--year",type=int,default=2024)
    p.add_argument("--out",type=Path)
    a=p.parse_args(argv)
    result=audit(a.root,expected_weeks=a.weeks,year=a.year)
    raw=json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n"
    if a.out:
        if a.out.exists() and a.out.read_text()!=raw:
            raise WeeklyAuditError("would_overwrite_different_audit_receipt")
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(raw)
    print(json.dumps({"weeks":result["weeks"],"markets":result["n_markets"],
                      "overall":result["all_scored_aggregate"],
                      "by_market":result["all_markets"],
                      "week_block_interval":result["overall_week_block_95pct_descriptive"]},
                     sort_keys=True))


if __name__=="__main__":
    main()
