"""Immutable pregame morning forecast audit: ONE contract, ONE outcome.

Side-level scoring of both Over and Under yields tautological ~50% hit and
mean P(Win). This module scores a canonical Over result once per original
source/market/player/line/period and independently audits side complementarity.

It MUST NOT infer an event/player identity from a display name, repair stale
prices, backfill a postgame forecast, or normalize incoherent model sides.
Unreliable/incoherent shadows are excluded per-model and counted in coverage.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math

SCHEMA="morning_contract_level_strict_v1"
TOL=1e-8
AUDITED_MODELS=(
 "engine_a","engine_b","bayesian_a","bayesian_b",
 "production_consensus","market_raw_novig",
 "online_bayesian_a","online_bayesian_b","online_player_rate",
 "diagnostic_70_30",
)


def canonical_source_digest(row):
    return hashlib.sha256(json.dumps(row,sort_keys=True,separators=(",",":"),
                         ensure_ascii=False,allow_nan=False).encode("utf-8")).hexdigest()


def _time(value,field):
    if not isinstance(value,str) or not value:
        raise ValueError("missing_"+field)
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_"+field) from exc
    if dt.tzinfo is None:
        raise ValueError("naive_"+field)
    return dt.astimezone(timezone.utc)


def _prob(value):
    if value is None:return None
    if isinstance(value,bool):return None
    try:p=float(value)
    except (ValueError,TypeError,OverflowError):return None
    return p if math.isfinite(p) and 0<=p<=1 else None


def _identity(row):
    required=("game_date","run_id","sport","event_id","player_id",
              "stat","period","event_start","line")
    if any(row.get(k) is None or row.get(k)=="" for k in required):
        raise ValueError("incomplete_original_contract_identity")
    if row["side"] not in ("over","under"):
        raise ValueError("invalid_side")
    if row["sport"] not in ("NBA","NHL","NFL"):
        raise ValueError("unsupported_sport")
    if row["period"]!="full":
        raise ValueError("unsupported_period")
    try:
        line=float(row["line"])
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValueError("invalid_line") from exc
    if not math.isfinite(line):raise ValueError("nonfinite_line")
    forecast=_time(row.get("forecast_at"),"forecast")
    event=_time(row["event_start"],"event")
    if forecast>=event:raise ValueError("forecast_not_pregame")
    return (str(row["game_date"]),str(row["run_id"]),str(row["sport"]),
            str(row["event_id"]),str(row["player_id"]),str(row["stat"]),
            str(row["period"]),str(row["event_start"]),line)


def score_contract_rows(rows,*,models=AUDITED_MODELS,reference="market_raw_novig"):
    """Produce strict one-contract-one-score report.

    Every input *side* is preserved in its source file. A missing or invalid
    pair is an exclusion, never a fabricated Under/zero. Missing model sides
    don't count as misses; model-specific sample size is explicit.
    """
    if not isinstance(rows,list):
        raise TypeError("side_rows_must_be_list")
    grouped=defaultdict(dict)
    rejects=Counter()
    accepted=[]
    if len(set(models))!=len(tuple(models)):
        raise ValueError("duplicate_model_names")
    for row in rows:
        if not isinstance(row,dict):
            rejects["malformed_side_row"]+=1
            continue
        try:key=_identity(row)
        except ValueError as exc:
            rejects[str(exc)]+=1
            continue
        if row["side"] in grouped[key]:
            raise ValueError("duplicate_original_side")
        grouped[key][row["side"]]=row
    statistics_=defaultdict(list)
    coverage=defaultdict(Counter)
    matched=defaultdict(list)
    by_sport=Counter()
    for key in sorted(grouped):
        pair=grouped[key]
        if set(pair)!={"over","under"}:
            rejects["unpaired_original_contract"]+=1
            continue
        over,under=pair["over"],pair["under"]
        if (over.get("original_source_run_id")!=key[1]
                or under.get("original_source_run_id")!=key[1]):
            rejects["source_run_id_conflicts_with_original"]+=1
            continue
        if any(over.get(x)!=under.get(x) for x in
               ("actual_stat","team","opponent","event_start",
                "game_date","period","original_source_run_id")):
            rejects["contradictory_original_pair"]+=1
            continue
        if over.get("outcome") not in ("win","loss"):
            rejects["unsettled_or_push_original_pair"]+=1
            continue
        if (over["outcome"],under.get("outcome")) not in (
                ("win","loss"),("loss","win")):
            rejects["incoherent_settled_opposite_sides"]+=1
            continue
        actual=over.get("actual_stat")
        try:actual=float(actual)
        except (TypeError,ValueError,OverflowError):
            rejects["missing_or_invalid_actual"]+=1
            continue
        if not math.isfinite(actual):
            rejects["nonfinite_actual"]+=1
            continue
        if (actual>key[-1])!=(over["outcome"]=="win") or actual==key[-1]:
            rejects["outcome_inconsistent_with_exact_original_line"]+=1
            continue
        by_sport[key[2]]+=1
        y=int(over["outcome"]=="win")
        evaluated={}
        for model in models:
            p=_prob(over.get(model))
            q=_prob(under.get(model))
            m=(key[2],key[5],model)
            if p is None and q is None:
                coverage[m]["both_sides_unavailable"]+=1
                continue
            if p is None or q is None:
                coverage[m]["one_side_unavailable"]+=1
                continue
            if abs(p+q-1)>TOL:
                coverage[m]["noncomplementary_probabilities"]+=1
                continue
            coverage[m]["scored"]+=1
            brier=(p-y)**2
            loss=-(y*math.log(max(1e-12,p))+
                   (1-y)*math.log(max(1e-12,1-p)))
            selected=None if abs(p-.5)<1e-12 else "over" if p>.5 else "under"
            hit=None if selected is None else int((p>.5)==bool(y))
            high=max(p,1-p)>=.8
            rec={"event_id":key[3],"run_id":key[1],
                 "player_id":key[4],"brier":brier,"log_loss":loss,
                 "p_over":p,"y_over":y,"selected":selected,
                 "selected_hit":hit,"confidence":max(p,1-p),
                 "high80":high,"game_date":key[0]}
            statistics_[m].append(rec)
            evaluated[model]=rec
        if reference in evaluated:
            for model,rec in evaluated.items():
                if model==reference:continue
                matched[(key[2],key[5],model)].append({
                    "game":key[3],"date":key[0],
                    "brier_delta_vs_reference":rec["brier"]-
                              evaluated[reference]["brier"],
                    "log_loss_delta_vs_reference":rec["log_loss"]-
                              evaluated[reference]["log_loss"],
                })
        accepted.append({
          "game_date":key[0],"run_id":key[1],"sport":key[2],
          "event_id":key[3],"player_id":key[4],"stat":key[5],
          "line":key[-1],"period":key[6],"actual":actual,
          "observed_over":y,"models_scored":sorted(evaluated),
          "source_over_forecast_sha256":over.get("original_forecast_sha256"),
          "source_under_forecast_sha256":under.get("original_forecast_sha256"),
          "original_forecast_at_over":over.get("forecast_at"),
          "original_forecast_at_under":under.get("forecast_at"),
          "original_event_start":key[7],
          "original_team":over.get("team"),
          "original_opponent":over.get("opponent"),
          "original_book_probability_over":_prob(over.get(reference)),
          "model_exclusions":{
           model:"missing_or_invalid_probability" if (
               _prob(over.get(model)) is None or
               _prob(under.get(model)) is None
           ) else "noncomplementary_probabilities"
           for model in models if model not in evaluated
          }
        })
    metrics=defaultdict(lambda:defaultdict(dict))
    for (sport,stat,model),recs in sorted(statistics_.items()):
        n=len(recs)
        selected=[r for r in recs if r["selected_hit"] is not None]
        hi=[r for r in selected if r["high80"]]
        games={r["event_id"] for r in recs}
        dates={r["game_date"] for r in recs}
        metrics[sport][stat][model]={
            "n_contracts":n,"n_games":len(games),"n_dates":len(dates),
            "mean_p_over":sum(r["p_over"] for r in recs)/n,
            "observed_over_frequency":sum(r["y_over"] for r in recs)/n,
            "brier":sum(r["brier"] for r in recs)/n,
            "log_loss":sum(r["log_loss"] for r in recs)/n,
            "selected_n":len(selected),
            "selected_hit_rate":(sum(r["selected_hit"] for r in selected)/
                                 len(selected) if selected else None),
            "selected_over_n":sum(r["selected"]=="over" for r in selected),
            "selected_under_n":sum(r["selected"]=="under" for r in selected),
            "tie_abstentions":n-len(selected),
            "selected_confidence_ge80_n":len(hi),
            "selected_confidence_ge80_hits":sum(r["selected_hit"] for r in hi),
            "selected_confidence_ge80_mean":(
                sum(r["confidence"] for r in hi)/len(hi) if hi else None),
            "full_calendar_date_cluster_power_available":len(dates)>1,
            "not_release_eligible":True,
        }
    deltas=defaultdict(lambda:defaultdict(dict))
    for (sport,stat,model),recs in sorted(matched.items()):
        n=len(recs)
        deltas[sport][stat][model]={
            "paired_n":n,
            "n_game_clusters":len({r["game"] for r in recs}),
            "n_date_clusters":len({r["date"] for r in recs}),
            "mean_brier_delta_vs_market":sum(r["brier_delta_vs_reference"] for r in recs)/n,
            "mean_logloss_delta_vs_market":sum(r["log_loss_delta_vs_reference"] for r in recs)/n,
            "negative_delta_favors_model":True,
            "market_reference":reference,
        }
    # Coverage is reported even where there are no valid scored entries.
    reasons=defaultdict(lambda:defaultdict(dict))
    for (sport,stat,model),counts in sorted(coverage.items()):
        reasons[sport][stat][model]=dict(counts)
    return {
      "schema":SCHEMA,"raw_original_side_rows":len(rows),
      "original_distinct_contract_keys":len(grouped),
      "settled_valid_paired_contracts":len(accepted),
      "invalid_or_unsettled_contract_reasons":dict(rejects),
      "accepted_contracts_by_sport":dict(by_sport),
      "metrics":{s:dict(v) for s,v in metrics.items()},
      "paired_model_vs_market":{s:dict(v) for s,v in deltas.items()},
      "model_coverage_and_invalidity":{s:dict(v) for s,v in reasons.items()},
      "one_contract_one_outcome":True,
      "refuses_probability_pair_renormalization":True,
      "model_promotion_allowed":False,
      "tier1_tier2_publication_allowed":False,
      # Keep individual models' missing/invalid records in the report.
      "contract_ledger":accepted,
    }
