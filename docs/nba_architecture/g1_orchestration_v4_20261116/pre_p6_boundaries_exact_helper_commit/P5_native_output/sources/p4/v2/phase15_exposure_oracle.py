"""Gate C: isolated, postgame workload-oracle attribution on verified settled rows.

Only use a source-verified realized minutes/TOI field in a retrospective
diagnostic. The substituted actual exposure MUST NOT be written into any
pregame model input, calibration or original archived forecast.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from pathlib import Path
import hashlib
import json
import math
import statistics

from .official_nba_nhl_capture import SettlementCaptureError, nhl_stat_rows, nba_stat_rows


def _mean(v):
    return sum(v)/len(v) if v else None


def _number(v,name,*,positive=False):
    if isinstance(v,bool):raise SettlementCaptureError("boolean_"+name)
    try: x=float(v)
    except (TypeError,ValueError,OverflowError) as exc:
        raise SettlementCaptureError("invalid_"+name) from exc
    if not math.isfinite(x) or (positive and x<=0):
        raise SettlementCaptureError("nonfinite_or_nonpositive_"+name)
    return x


def _q_over_count(rate,line):
    lam=_number(rate,"poisson_rate")
    if lam<0:raise SettlementCaptureError("negative_poisson_rate")
    cutoff=math.floor(_number(line,"line"))
    terms=[]
    for k in range(max(0,cutoff+1)):
        if lam==0:pmf=float(k==0)
        else:pmf=math.exp(-lam+k*math.log(lam)-math.lgamma(k+1))
        terms.append(pmf)
    upto=math.fsum(terms)
    push=terms[cutoff] if line==cutoff and cutoff>=0 and terms else 0.
    under=upto-push
    over=max(0,1-upto)
    return over/(over+under) if over+under>0 else None


def evaluate_workload_oracle(phase1,settlements,source_root):
    if phase1.get("schema")!="v25-phase1-nhl-nba-certified-replay-v1":
        raise SettlementCaptureError("incorrect_phase1_scored_schema")
    if phase1.get("model_promotion_authorized") is not False:
        raise SettlementCaptureError("promotion_flag_invalid")
    root=Path(source_root).resolve()
    original={(c["sport"],str(c["event_id"]),str(c["player_id"]),c["stat"]):c
              for c in phase1["contracts"] if c["outcome"]["status"] in ("over","under","push")}
    if not original:
        return {"status":"BLOCKED_NO_SETTLED_OPPORTUNITY","rows":0}
    seen=set()
    matched=[]
    quarantine=Counter()
    for settlement in settlements:
        key=(settlement["sport"],str(settlement["event_id"]),
             str(settlement["player_id"]),settlement["stat"])
        if key in seen:raise SettlementCaptureError("duplicate_oracle_player_stat")
        seen.add(key)
        c=original.get(key)
        if c is None:raise SettlementCaptureError("settlement_oracle_mismatch")
        if c["outcome"]["actual"]!=settlement["actual"]:
            raise SettlementCaptureError("score_and_oracle_actual_inconsistent")
        rel=settlement.get("source_archive_path")
        if (not isinstance(rel,str) or not rel or rel.startswith("/")
                or "\\" in rel or ".." in rel.split("/")):
            raise SettlementCaptureError("oracle_unsafe_source_path")
        loc=(root/rel).resolve()
        if not loc.is_relative_to(root) or not loc.is_file():
            raise SettlementCaptureError("oracle_missing_provider_source")
        raw=loc.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=settlement["source_sha256"]:
            raise SettlementCaptureError("oracle_source_bytes_tampered")
        doc=json.loads(raw)
        team=settlement["sport"]
        teams={c["team_id"],c["opponent_id"]}
        samples=(nhl_stat_rows(doc,expected_teams=teams) if team=="NHL"
                 else nba_stat_rows(doc,expected_teams=teams))
        official=samples.get(str(settlement["player_id"]))
        if official is None or official["team"]!=c["team_id"]:
            raise SettlementCaptureError("oracle_official_identity_mismatch")
        if official[c["stat"]]!=settlement["actual"]:
            raise SettlementCaptureError("oracle_outcome_disagrees_source")
        actual_minutes=_number(official["observed_workload_minutes"],"realized_exposure",positive=True)
        if abs(actual_minutes-_number(settlement["observed_workload_minutes"],"recorded_minutes"))>1e-9:
            raise SettlementCaptureError("oracle_exposure_source_mismatch")
        expected_minutes=_number(c["opportunity"].get("projected_workload"),
                                 "projected_exposure",positive=True)
        actual=_number(c["outcome"]["actual"],"realized_shots")
        obj={"sport":team,"event_id":c["event_id"],"stat":c["stat"],
             "player_id":c["player_id"],
             "projected_minutes":expected_minutes,"actual_minutes":actual_minutes,
             "actual":actual,"line":c["line"]}
        for model in ("naive_recent_exposure_rate","pooled_peer_shrunk_rate"):
            source=c["models"][model]
            if source["status"]!="counterfactual_shadow":
                quarantine[model+"_not_available"]+=1
                continue
            rate=_number(source["distribution"]["rate"],model+"_lambda")
            oracle=rate*actual_minutes/expected_minutes
            obj[model]={
                "original_lambda":rate,"postgame_actual_time_oracle_lambda":oracle,
                "original_count_squared_error":(rate-actual)**2,
                "oracle_count_squared_error":(oracle-actual)**2,
                "original_brier":(_number(source["p_over_nonpush"],"p") -
                     int(c["outcome"]["status"]=="over"))**2
                     if c["outcome"]["status"]!="push" else None,
                "oracle_brier":(_q_over_count(oracle,c["line"])-
                     int(c["outcome"]["status"]=="over"))**2
                     if c["outcome"]["status"]!="push" else None,
            }
        matched.append(obj)
    if set(original)!=seen:
        raise SettlementCaptureError("oracle_cannot_drop_scored_contracts")
    if not matched:raise SettlementCaptureError("oracle_no_matched_source")
    results={}
    for model in ("naive_recent_exposure_rate","pooled_peer_shrunk_rate"):
        cohort=[c for c in matched if model in c]
        results[model]={
            "n":len(cohort),
            "mean_projected_count":_mean([c[model]["original_lambda"] for c in cohort]),
            "mean_postgame_oracle_count":_mean([c[model]["postgame_actual_time_oracle_lambda"] for c in cohort]),
            "mean_actual_count":_mean([c["actual"] for c in cohort]),
            "original_count_mse":_mean([c[model]["original_count_squared_error"] for c in cohort]),
            "oracle_time_count_mse":_mean([c[model]["oracle_count_squared_error"] for c in cohort]),
            "oracle_minus_original_count_mse":_mean([
                c[model]["oracle_count_squared_error"]-c[model]["original_count_squared_error"]
                for c in cohort]),
            "original_brier":_mean([c[model]["original_brier"] for c in cohort
                                    if c[model]["original_brier"] is not None]),
            "postgame_oracle_time_brier":_mean([c[model]["oracle_brier"] for c in cohort
                                    if c[model]["oracle_brier"] is not None]),
            "postgame_oracle_inadmissible_for_pregame_ranking":True,
        }
    mins=[c["projected_minutes"]-c["actual_minutes"] for c in matched]
    out={
        "schema":"v25_phase15_gateC_retrospective_one_factor_time_oracle_v1",
        "status":"PARTIAL_NHL_ONLY_NOT_FOUR_FACTOR",
        "source_verified_scored_contracts":len(matched),
        "distinct_game_clusters":len({c["event_id"] for c in matched}),
        "observed_sports":dict(Counter(c["sport"] for c in matched)),
        "mean_projected_minus_actual_minutes":_mean(mins),
        "mean_absolute_minutes_error":_mean(list(map(abs,mins))),
        "projected_minutes_mean":_mean([c["projected_minutes"] for c in matched]),
        "actual_minutes_mean":_mean([c["actual_minutes"] for c in matched]),
        "model_oracles":results,
        "quarantine_reasons":dict(quarantine),
        "four_factor_attribution_status":"BLOCKED_MISSING_GENUINE_PREGAME_FACTOR_FORECASTS",
        "causal_identification":False,
        "oracle_releasable_as_model":False,
        "training_updated":False,
        "tier_release":False,
    }
    return out
