"""Uniform, honest prospective comparison of frozen model engines and held-out outcomes.

Only same-line, original-contract comparisons are paired. Multiple sportsbook
quotes share the player outcome; no bookmaker rows counted as independent games.
"""
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
import json
import math
import random

from research.v25_morning_validation.score import (
    score_probability, discrete_crps, make_once, h,
)
from research.v25_universal.registry import discover
from v2.nba_ws1.store import instant
from zoneinfo import ZoneInfo
_TZ=ZoneInfo("America/Toronto")

def _event_date(value):
    if not value:return "UNKNOWN"
    try:return instant(value).astimezone(_TZ).date().isoformat()
    except (TypeError,ValueError):return "UNKNOWN"


def mean(xs):
    return math.fsum(xs) / len(xs) if xs else None


def _binary_probability(row, dist, line):
    if row.get("p_over_given_no_push") is not None:
        p = row["p_over_given_no_push"]
        if isinstance(p, bool) or not isinstance(p, (int,float)) or not math.isfinite(p) or not 0<=p<=1:
            raise ValueError("INVALID_PROBABILITY")
        return float(p)
    if dist and dist["kind"] == "discrete":
        above = sum(p for value,p in dist["masses"] if value>line)
        below = sum(p for value,p in dist["masses"] if value<line)
        return above/(above+below) if above+below>0 else None
    return None


def minutes_continuous_scores(parameters, minutes):
    """Deterministic quadrature of conditional-on-playing minutes CRPS.

    Uses actual saved MinuteLaw parameters; no re-estimation or pseudo-sample.
    Numeric tolerance checked with increasing integration resolutions.
    """
    from v2.nba_opportunity import MinuteLaw
    import numpy as np
    law=MinuteLaw(**parameters)
    if not isinstance(minutes,(int,float)) or isinstance(minutes,bool) or not math.isfinite(minutes) or minutes<=0:
        raise ValueError("INVALID_PLAYED_MINUTES")
    cap=law.ot_components()[-1][0]
    def evaluate(n):
        xx=np.sort(np.unique(np.concatenate((np.linspace(0,cap,n),[float(minutes)]))))
        ff=law.cdf(xx)
        return float(np.trapz((ff-(xx>=minutes))**2,xx))
    first=evaluate(2049)
    second=evaluate(4097)
    if not math.isfinite(second) or abs(first-second)>0.03:
        raise ValueError("CONTINUOUS_CRPS_QUADRATURE_UNSTABLE")
    q=law.summary()["quantiles_given_played"]
    return {"crps":second,"abs_error_mean":abs(law.summary()["expected_minutes_given_played"]-minutes),
            "covered_90":int(q["0.05"]<=minutes<=q["0.95"]),
            "pit":float(law.cdf([minutes])[0])}


def _load_lines(path):
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_bytes().splitlines() if l.strip()]


def _model_line(sport, identity, row, actual, line, *, provenance):
    """One forecast with strict source/contract join and explicit conditioning."""
    if row.get("status") != "forecast":
        return {"status":"ABSTAINED_FROZEN_MODEL","reason":row.get("reason","NO_ORIGINAL_FORECAST")}
    if row["conditioning"] == "unconditional" and (not row.get("legal_eligibility_verified")
        or row.get("participation_probability") is None):
        return {"status":"BLOCKED_UNCONDITIONAL_PARTICIPATION_NOT_CERTIFIED"}
    if sport == "NBA" and row["conditioning"] == "conditional_nonpush":
        return {"status":"BLOCKED_NBA_MARKET_NONPUSH_WITHOUT_ORIGINAL_LINE"}
    dist=row.get("validated_distribution")
    metrics={}
    if dist and dist["kind"] == "discrete":
        metrics["crps"]=discrete_crps(dist["masses"],float(actual))
    elif dist and dist["kind"] == "nba_minutes_law":
        metrics.update(minutes_continuous_scores(dist["parameters"],float(actual)))
    if line is not None and actual!=line and row["stat"]!="minutes":
        p=_binary_probability(row,dist,line)
        if p is not None:
            metrics.update(score_probability(p,int(actual>line)))
            metrics["p_over"]=p
    if not metrics:
        return {"status":"NO_SUPPORTED_SCORE"}
    return {"status":"SCORED","metrics":metrics,
            "conditioning":row["conditioning"],"source":provenance,
            "forecast_at":row["forecast_at"]}


def _model_rows(out,discovery):
    nba=_load_lines(out/"nba_settled_candidates.jsonl")
    # The NFL contract audit is a JSON object, not JSONL.
    nfl_dict=json.loads((out/"nfl_contract_audit.json").read_text()) if (out/"nfl_contract_audit.json").is_file() else {}
    nfl=nfl_dict.get("rows",[]) + _load_lines(out/"nfl_forward_contract_outcomes.jsonl")
    nba_index={(r["game_id"],r["player_id"],r["team_id"]):r for r in nba}
    nfl_index={r.get("original_contract_id"):r for r in nfl if r.get("original_contract_id")}
    annotations, matched=[],set()
    for row in discovery["forecasts"]:
        common={"sport":row["sport"],"engine":row["engine"],"event_id":row["event_id"],
                "player_id":row["player_id"],"stat":row["stat"],
                "source_manifest":row["registry_manifest"],
                "conditioning":row["conditioning"],
                "forecast_at":row["forecast_at"],"event_start_at":row["event_start_at"]}
        if row["sport"] == "NFL":
            contract=nfl_index.get(row.get("original_contract_id"))
            if not contract:
                annotations.append({**common,"status":"ORIGINAL_CONTRACT_NOT_IN_WS6_REFERENCE"})
                continue
            if (contract["event_id"]!=row["event_id"] or contract["player_id"]!=row["player_id"]
                or contract["stat"]!=row["stat"] or contract.get("original_quote_id")!=row.get("original_quote_id")
                or contract.get("original_quote_source_sha256")!=row.get("original_quote_source_sha256")
                or float(contract["line"])!=float(row["line"])
                or (row.get("book") is not None and contract["book"]!=row["book"])):
                annotations.append({**common,"status":"ORIGINAL_NFL_IDENTITY_COLLISION"})
                continue
            if contract["state"]!="SCORED":
                annotations.append({**common,"status":"ORIGINAL_CONTRACT_NOT_OUTCOME_SCORABLE",
                                    "reason":contract["state"]})
                continue
            if row["conditioning"]=="given_played" and contract.get("actual") is None:
                annotations.append({**common,"status":"PLAYER_APPEARANCE_UNKNOWN"})
                continue
            actual=contract["actual"]
            r=_model_line("NFL",contract,row,actual,float(contract["line"]),
                          provenance=row["registry_manifest_forecast_sha256"])
            annotations.append({**common,"original_contract_id":row.get("original_contract_id"),
                                "line":row["line"],"status":r["status"],
                                "metrics":r.get("metrics"),"conditioning":r.get("conditioning")})
        elif row["sport"]=="NBA":
            candidate=nba_index.get((row.get("game_id"),row["player_id"],row.get("team_id")))
            if not candidate:
                annotations.append({**common,"status":"ORIGINAL_CANDIDATE_MISSING_OR_UNSETTLED"})
                continue
            if row["source_sha256"] not in candidate.get("original_candidate_source_hashes",[]):
                annotations.append({**common,"status":"NBA_ORIGINAL_SOURCE_RECEIPT_MISMATCH"})
                continue
            if candidate["status"]!="PLAYED":
                annotations.append({**common,"status":"CONDITIONAL_FORECAST_DNP_OR_UNRESOLVED",
                                    "actual_state":candidate["status"]})
                continue
            obs=candidate["actual"]
            stat=row["stat"]
            value=obs["minutes"] if stat=="minutes" else (obs.get("stats") or {}).get(stat)
            if value is None:
                annotations.append({**common,"status":"OFFICIAL_OUTCOME_STAT_UNAVAILABLE"})
                continue
            line=row.get("line")
            if line is None and row["conditioning"]=="conditional_nonpush":
                annotations.append({**common,"status":"MISSING_ORIGINAL_CONTRACT_LINE"})
                continue
            r=_model_line("NBA",candidate,row,value,float(line) if line is not None else None,
                          provenance=row["registry_manifest_forecast_sha256"])
            annotations.append({**common,"game_id":row.get("game_id"),"team_id":row.get("team_id"),
                                "actual":value,"line":line,"status":r["status"],
                                "metrics":r.get("metrics"),"conditioning":r.get("conditioning")})
        else:
            annotations.append({**common,"status":"OUTCOME_PROVIDER_NOT_CONNECTED"})
    return nfl,nba,annotations


def _as_metrics(nfl,annotations):
    items=[]
    for r in nfl:
        if r.get("state")!="SCORED":continue
        for model,result in (r.get("scores") or {}).items():
            if result.get("status") not in ("SCORED","PUSH_ONLY"):continue
            values=result["metrics"]
            items.append({"sport":"NFL","event_id":r["event_id"],"player_id":r["player_id"],
                          "stat":r["stat"],"engine":model,"conditioning":"given_played" if model!="C2" else "conditional_nonpush",
                          "contract_key":r["original_contract_id"],"actual":r["actual"],
                          "event_date":_event_date(r.get("event_start_at")),
                          "line":r["line"],"metrics":values,
                          "binary_y":int(r["actual"]>r["line"]) if r["actual"]!=r["line"] else None,
                          "p_over":result.get("p_over_given_no_push")})
    for row in annotations:
        if row["status"]!="SCORED":continue
        key=row.get("original_contract_id") if row["sport"]=="NFL" else (
            row.get("game_id"),row["player_id"],row["stat"],row.get("line"))
        metrics=row["metrics"]
        if row["sport"]=="NFL":
            parent=next((v for v in nfl if v.get("original_contract_id")==key),None)
            if parent is None:continue
            actual=parent["actual"];line=parent["line"]
        else:
            actual=row["actual"];line=row.get("line")
        items.append({"sport":row["sport"],"event_id":row["event_id"],"player_id":row["player_id"],
                      "stat":row["stat"],"engine":row["engine"],"conditioning":row["conditioning"],
                      "contract_key":str(key),"actual":actual,"line":line,"metrics":metrics,
                      "event_date":_event_date(row.get("event_start_at")),
                      "binary_y":int(actual>line) if line is not None and actual!=line else None,
                      "p_over":metrics.get("p_over")})
    return items


def _report(items,denominators):
    group=defaultdict(list)
    for row in items:
        group[(row["sport"],row["stat"],row["engine"],row["conditioning"])].append(row)
    model_metrics=[]
    for key,rows in sorted(group.items()):
        games={r["event_id"] for r in rows}
        ps=[r for r in rows if r["binary_y"] is not None and r["p_over"] is not None]
        bins=[]
        for i in range(10):
            block=[r for r in ps if min(9,int(r["p_over"]*10))==i]
            bins.append({"range":[i/10,(i+1)/10],"n":len(block),
                         "mean_predicted":mean([r["p_over"] for r in block]),
                         "empirical_over_rate":mean([r["binary_y"] for r in block])})
        metrics={metric:{"n":sum(metric in r["metrics"] for r in rows),
                         "mean":mean([r["metrics"][metric] for r in rows if metric in r["metrics"]])}
                 for metric in ("brier","logloss","crps","abs_error_mean","covered_90","pit")
                 if any(metric in r["metrics"] for r in rows)}
        model_metrics.append(dict(zip(("sport","market","engine","conditioning"),key),
            original_contracts_scored=len(rows),distinct_games=len(games),
            distinct_game_dates=len({r.get("event_date","UNKNOWN") for r in rows}),
            metrics=metrics,calibration_deciles=bins,
            calibration_status="PROVISIONAL_DESCRIPTIVE" if len(games)<30 else "REVIEW_REQUIRED"))
    # Compute paired loss on the *identical* original contract, with clustering
    # by game instead of treating four books as four independent games.
    pair_group=defaultdict(list)
    bycontract=defaultdict(dict)
    for row in items:
        ident=(row["sport"],row["event_id"],row["player_id"],row["stat"],str(row["contract_key"]))
        bycontract[ident][row["engine"]]=row
    for ident, engines in bycontract.items():
        for a,b in combinations(sorted(engines),2):
            for metric in ("brier","logloss","crps"):
                if metric in engines[a]["metrics"] and metric in engines[b]["metrics"]:
                    pair_group[(ident[0],ident[3],a,b,metric)].append({
                        "event_id":ident[1],"delta":engines[a]["metrics"][metric]-engines[b]["metrics"][metric]})
    paired=[]
    for key,rows in sorted(pair_group.items()):
        groups=defaultdict(list)
        for r in rows:groups[r["event_id"]].append(r["delta"])
        intervals=None
        # Games alone, even 11 in the same date, are not multi-day research.
        # Present no CI until multiple genuinely prospective date clusters accrue.
        dates={r.get("event_date","UNKNOWN") for r in items if r["event_id"] in groups}
        if len(groups)>=20 and len(dates)>=5:
            rng=random.Random(20261115)
            vals=list(groups.values());sims=[]
            for _ in range(800):
                draws=rng.choices(vals,k=len(vals))
                sims.append(mean([delta for block in draws for delta in block]))
            sims.sort()
            intervals=[sims[20],sims[780]]
        paired.append({"sport":key[0],"market":key[1],"first":key[2],"second":key[3],
                       "metric":key[4],"paired_contracts":len(rows),
                       "distinct_games":len(groups),"mean_first_minus_second":mean([r["delta"] for r in rows]),
                       "game_cluster_bootstrap_95":intervals,
                       "status":"DESCRIPTIVE_NO_INDEPENDENT_TEMPORAL_HOLDOUT"})
    return {"schema":"V25UnifiedResearchValidation/1","models":model_metrics,"paired":paired,
            "denominators":denominators,"scored_row_count":len(items),
            "meta":{"multiple_books_same_event_dependent":True,
                    "conditional_on_observed_appearance_not_pick_hit_rate":True,
                    "game_cluster_not_individual_contract_bootstrap":True,
                    "model_promotion_allowed":False,"different_market_units_not_combined":True}}


def build(storage,output):
    """Run after NFL/ NBA original outcome audits and before final manifest."""
    storage=Path(storage);output=Path(output)
    from research.v25_forward.scoring import forward_outcomes
    forward=forward_outcomes(storage,output)
    discovery=discover(storage)
    nfl,nba,annotations=_model_rows(output,discovery)
    with (output/"registered_model_scoring.jsonl").open("xb") as f:
        for row in annotations:
            f.write((json.dumps(row,sort_keys=True,allow_nan=False)+"\n").encode())
    noforecast=Counter(row["status"] for row in annotations)
    items=_as_metrics(nfl,annotations)
    summary=_report(items,{"NFL_original_contracts":1845 if nfl else 0,
                           "NBA_original_slots":10,
                           "NBA_settled_candidates":len(nba),
                           "registered_forecasts_discovered":len(discovery["forecasts"]),
                           "registered_validation_states":dict(noforecast),
                           "invalid_registry_rows":len(discovery["rejected"])})
    summary["discovery"]={k:v for k,v in discovery.items() if k!="forecasts"}
    summary["forward_original_collection"]=forward
    make_once(output/"unified_model_comparison.json",summary)
    return { "status":"UNIFIED_DESCRIPTIVE_ONLY",
             "registry_forecasts":len(discovery["forecasts"]),
             "registry_rejections":len(discovery["rejected"]),
             "scored_model_metric_groups":len(summary["models"]),
             "paired_metric_groups":len(summary["paired"]),
             "NFL_forward_original_contracts":forward["original_contracts"]}
