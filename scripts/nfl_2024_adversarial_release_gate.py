"""Independent adversarial release gate for NFL historical research replays.

Historical replay is NOT a bookmaker-available slate. This checks immutable
weekly lock receipts, incremental learning, calibration, class imbalance,
missingness, and baseline comparisons; it NEVER promotes production weights.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

EXPECTED_MARKETS = 16
EXPECTED_WEEKS = 18

def _read(path):
    return json.loads(Path(path).read_text())

def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def binary_scores(rows):
    """Score only rows with actual outcomes, not unresolved/void rows."""
    n=len(rows)
    if n==0:return dict(n=0)
    p=[float(r["model_p_over"]) for r in rows]
    baseline=[float(r["baseline_p_over"]) for r in rows]
    y=[int(r["actual_over"]) for r in rows]
    if any(not math.isfinite(q) or q<0 or q>1 for q in p+baseline):
        raise ValueError("nonfinite_or_invalid_probability")
    if any(t not in (0,1) for t in y):
        raise ValueError("invalid_outcome")
    return dict(n=n,
        accuracy=sum(int(r["hit"]) for r in rows)/n,
        always_under_accuracy=sum(1-v for v in y)/n,
        predicted_under_share=sum(r["predicted_side"]=="under" for r in rows)/n,
        observed_under_share=sum(1-v for v in y)/n,
        brier_model=sum((a-b)**2 for a,b in zip(p,y))/n,
        brier_baseline=sum((a-b)**2 for a,b in zip(baseline,y))/n,
        log_loss_model=sum(-v*math.log(max(1e-12,min(1-1e-12,a)))-(1-v)*math.log1p(-max(1e-12,min(1-1e-12,a))) for a,v in zip(p,y))/n,
        log_loss_baseline=sum(-v*math.log(max(1e-12,min(1-1e-12,a)))-(1-v)*math.log1p(-max(1e-12,min(1-1e-12,a))) for a,v in zip(baseline,y))/n)

def _read_csv(path):
    with Path(path).open(newline="") as f:return list(csv.DictReader(f))

def audit(root):
    root=Path(root)
    report=root/"PERFORMANCE_REPORT"
    original=_read(report/"AUDIT_SUMMARY.json")
    all_rows=_read_csv(report/"every_2024_prop_frozen_prediction_and_settlement.csv")
    selected=_read_csv(report/"2024_preselected_top10_all_outcomes_including_unmatched.csv")
    forecast_n=len(all_rows)
    if forecast_n!=original["observations"]["forecasted"]:
        raise ValueError("original_report_forecast_mismatch")
    if len(set((r["week"],r["game_id"],r["player_id"],r["market"]) for r in all_rows))!=forecast_n:
        raise ValueError("duplicate_forecast_contracts")
    if any(r["hit"] not in ("","0","1") for r in all_rows+selected):
        raise ValueError("unrecognized_result_type")
    graded=[r for r in all_rows if r["hit"] in ("0","1")]
    topgraded=[r for r in selected if r["hit"] in ("0","1")]
    if len(graded)!=original["observations"]["graded"] or len(selected)!=original["top10_preselected_count"]:
        raise ValueError("original_report_settlement_mismatch")
    if len(topgraded)!=original["top10_matched"]:
        raise ValueError("original_selected_match_count_mismatch")
    bymarket={}
    for m in sorted({r["market"] for r in all_rows}):
        sub=[r for r in all_rows if r["market"]==m]
        settled=[r for r in sub if r["hit"] in ("0","1")]
        bymarket[m]={**binary_scores(settled),
             "forecasted":len(sub),"unmatched":len(sub)-len(settled)}
    if len(bymarket)!=EXPECTED_MARKETS:
        raise ValueError("unexpected_market_count")
    receipts=[]
    prev=None
    training_ok=True
    roster_sources=set()
    model_statuses=Counter()
    for week in range(1,EXPECTED_WEEKS+1):
        d=root/f"2024_week_{week:02d}"
        lock=_read(d/"lock.json")
        settled=_read(d/"settlement.json")
        packet=_read(d/"pregame_packet.json")
        frozen=_read(d/"frozen_all_markets.json")
        fh=_hash(d/"frozen_all_markets.json")
        if fh!=lock["forecast_sha256"] or fh!=settled["forecast_sha256"]:
            raise ValueError("corrupted_or_changed_frozen_forecast_week_"+str(week))
        if _hash(d/"pregame_packet.json")!=lock["packet_sha256"]:
            raise ValueError("corrupted_pregame_packet_week_"+str(week))
        if packet["target_week_results_in_packet"] is not False:
            raise ValueError("preweek_forecast_contains_current_outcomes")
        if (settled["markets_scored"]!=EXPECTED_MARKETS or
            settled["all_markets_frozen_before_any_result"] is not True):
            raise ValueError("not_all_markets_frozen_before_reveal")
        if prev is not None:
            for market,n in settled["prior_train_examples_by_market"].items():
                expected=(prev["prior_train_examples_by_market"][market]+
                          prev["next_week_model_update"][market])
                if expected!=n:raise ValueError("weekly_update_discontinuous_"+str(week))
        roster_sources.add(packet["source_roster"])
        for market,row in frozen["market_results"].items():
            model_statuses[row["status"]]+=1
        receipts.append(dict(week=week,forecast_sha256=fh,
            prior_examples=settled["prior_train_examples_by_market"],
            previous_week_increment_checked=(week>1)))
        prev=settled
    summary=binary_scores(graded)
    top_summary=binary_scores(topgraded)
    top_under=sum(r["predicted_side"]=="under" for r in selected)
    fail=[]
    def veto(code,evidence):
        fail.append(dict(code=code,evidence=evidence))
    if not original["2024_bookmaker_lines_available"]:
        veto("NO_PREGAME_BOOKMAKER_QUOTES","All lines are synthetic: no quoted odds or availability")
    if roster_sources!={"pregame_confirmed_active_roster"}:
        veto("NO_PREGAME_ACTIVE_ROSTER","Roster is reconstructed from last observed participation")
    if (forecast_n-len(graded))/forecast_n>.05:
        veto("UNSETTLED_POOL_OVER_5_PERCENT",
             f"{forecast_n-len(graded)}/{forecast_n} ({(forecast_n-len(graded))/forecast_n:.1%}) unmatched")
    if len(selected)!=len(topgraded):
        veto("TOP10_UNSETTLED",f"{len(selected)-len(topgraded)} of {len(selected)} selected unmatched")
    if summary["predicted_under_share"]>.90:
        veto("DIRECTIONAL_UNDER_COLLAPSE",f"{summary['predicted_under_share']:.2%} under")
    if top_under/len(selected)>.90:
        veto("TOP10_ALL_UNDERS",f"{top_under}/{len(selected)} selected Unders")
    if summary["accuracy"]-summary["always_under_accuracy"]<.03:
        veto("LESS_THAN_3PP_LIFT_OVER_ALWAYS_UNDER",f"{summary['accuracy']-summary['always_under_accuracy']:.2%} lift")
    if summary["brier_model"]>=summary["brier_baseline"]:
        veto("MODEL_BRIER_NO_BETTER_THAN_HISTORICAL",
             f"model={summary['brier_model']:.5f}, baseline={summary['brier_baseline']:.5f}")
    labels=set(r["line_type"] for r in all_rows)
    if original.get("hybrid_research_lines") and labels=={"synthetic_preweek_position_median"}:
        veto("REPORTED_LINE_SOURCE_MISLABELED","Hybrid data ledger incorrectly says position_median")
    if top_summary["accuracy"]+.02<top_summary["n"]*0+sum(
        float(r["selected_model_probability"]) for r in topgraded)/max(1,len(topgraded)):
        veto("TOP10_CONFIDENCE_EXAGGERATED","Selected matched confidence exceeds observed by >2pp")
    for m,stat in bymarket.items():
        if stat["predicted_under_share"]>.90:
            veto("MARKET_UNDER_90:"+m,f"{stat['predicted_under_share']:.2%}")
    cals=[]
    for lo in [.5,.6,.7,.8,.9]:
        sub=[r for r in graded if lo<=float(r["selected_model_probability"])<
             (lo+.1 if lo<.9 else 1.000001)]
        if not sub:continue
        cals.append(dict(low=lo,n=len(sub),
            claimed=sum(float(r["selected_model_probability"]) for r in sub)/len(sub),
            actual=sum(int(r["hit"]) for r in sub)/len(sub)))
        c=cals[-1]
        if c["n"]>200 and c["claimed"]-c["actual"]>.03:
            veto("MISCALE_CONFIDENCE_BIN:"+str(lo),f"claimed {c['claimed']:.3f}; actual {c['actual']:.3f}")
    return dict(schema="pickem-2024-adversarial-release-gate-v1",
        source_replay=str(root),historical_16_market_lock_verified=True,
        weekly_increment_verified=True,training_boundary=original.get("initial_fit_uses_only_seasons"),
        model_types=dict(model_statuses),n_forecasted=forecast_n,
        n_graded=len(graded),n_unmatched=forecast_n-len(graded),
        top10_count=len(selected),top10_matched=len(topgraded),
        top10_under_share=top_under/len(selected),overall=summary,
        top10_graded=top_summary,market_stats=bymarket,
        confidence_buckets=cals,issues=fail,release_allowed=False,
        released_probabilities=None)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    record=audit(a.root)
    output=Path(a.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    body=json.dumps(record,indent=2,sort_keys=True,allow_nan=False)+"\n"
    if output.exists() and output.read_text()!=body:
        raise ValueError("would_mutate_prior_audit_receipt")
    output.write_text(body)
    print(json.dumps({k:record[k] for k in ("release_allowed","n_forecasted","n_graded","n_unmatched","top10_under_share")}))
    print("RELEASE_BLOCKING_ISSUES",len(record["issues"]))
if __name__=="__main__":main()
