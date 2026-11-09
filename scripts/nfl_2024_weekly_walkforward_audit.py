#!/usr/bin/env python3
"""Summarize 18-week NFL online learning vs frozen-parameter counterfactual.

Runs AFTER the full sequential replay finishes. Uses only graded, matched
research contracts with the same weekly synthetic line for each comparator.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import random
from pathlib import Path

METHODS={
    "rolling_prior":"p_over_player_prior",
    "static_2023_prior":"p_over_static_player",
    "team_xgb_bayes":"p_over",
    "team_xgb_bayes_hurdle_online":"p_over_hurdle",
    "team_xgb_bayes_hurdle_no_refit":"p_over_no_refit",
}


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe(rows):
    d={"n":len(rows)}
    if not rows:
        return d
    d["actual_under_share"]=sum(r["actual_over"]==0 for r in rows)/len(rows)
    for name,key in METHODS.items():
        a=[r for r in rows if r.get(key) is not None]
        if not a:
            continue
        d[name]={
            "n":len(a),
            "accuracy":sum(int((r[key]>=.5)==bool(r["actual_over"])) for r in a)/len(a),
            "brier":sum((r[key]-r["actual_over"])**2 for r in a)/len(a),
            "logloss":sum(-(r["actual_over"]*math.log(max(1e-6,min(1-1e-6,r[key])))+
                (1-r["actual_over"])*math.log(max(1e-6,min(1-1e-6,1-r[key])))) for r in a)/len(a),
            "predicted_under_share":sum(r[key]<.5 for r in a)/len(a),
        }
    return d


def paired_diff(rows,a,b,kind="brier"):
    p,q=METHODS[a],METHODS[b]
    rows=[r for r in rows if r.get(p) is not None and r.get(q) is not None]
    if not rows:
        return None
    if kind=="brier":
        return sum((r[p]-r["actual_over"])**2-(r[q]-r["actual_over"])**2
                   for r in rows)/len(rows)
    if kind=="accuracy":
        return sum(int((r[p]>=.5)==bool(r["actual_over"])) -
                   int((r[q]>=.5)==bool(r["actual_over"])) for r in rows)/len(rows)
    raise ValueError("unknown_comparison_score")


def block_bootstrap(allrows,model_a,model_b,kind,*,replications=500):
    groups=collections.defaultdict(list)
    for r in allrows:
        if r.get(METHODS[model_a]) is not None and r.get(METHODS[model_b]) is not None:
            groups[r["game_id"]].append(r)
    games=list(groups.values())
    rng=random.Random(20261109)
    obs=paired_diff([r for group in games for r in group],model_a,model_b,kind)
    vals=[]
    for _ in range(replications):
        sample=[]
        for __ in range(len(games)):
            sample.extend(games[rng.randrange(len(games))])
        vals.append(paired_diff(sample,model_a,model_b,kind))
    vals.sort()
    return {"A_minus_B":obs,"interval_95pc":[vals[int(.025*len(vals))],
                    vals[int(.975*len(vals))-1]],
            "block":"2024 NFL game","n_games":len(games),
            "replications":replications}


def audit(root):
    root=Path(root)
    if not (root/"FINAL_SUMMARY.json").exists():
        raise RuntimeError("walkforward_18_week_run_not_finished")
    summary=json.loads((root/"FINAL_SUMMARY.json").read_bytes())
    if not summary["complete"] or len(summary["weeks"])!=18:
        raise RuntimeError("incomplete_walkforward_ledger")
    byweek={}
    allrows=[]
    market_rows=collections.defaultdict(list)
    previous_n_team=0
    previous_n_hurdle=0
    for week in range(1,19):
        frozenpath=root/"FROZEN"/("week_%02d.json"%week)
        revealedpath=root/"REVEALED"/("week_%02d.json"%week)
        updatepath=root/"UPDATES"/("after_week_%02d.json"%week)
        frozen=json.loads(frozenpath.read_bytes())
        revealed=json.loads(revealedpath.read_bytes())
        update=json.loads(updatepath.read_bytes())
        if checksum(frozenpath)!=revealed["frozen_sha"]:
            raise RuntimeError("weekly_forecast_modified_after_outcome_reveal")
        if update["locked_forecast_sha"]!=revealed["frozen_sha"] or (
            update["revealed_score_sha"]!=checksum(revealedpath)):
            raise RuntimeError("update_not_tied_to_frozen_week")
        if frozen["latest_revealed_week"]!=week-1 or (
            frozen["training_label_week_limit"]!=week-1):
            raise RuntimeError("future_training_label_in_preweek_receipt")
        if update["updated_after_revealed_week"]!=week or (
            update["2024_training_seasons_weeks"]!=list(range(1,week+1))):
            raise RuntimeError("training_skipped_week_or_future_used")
        if update["trained_team_records"]<previous_n_team or (
            update["trained_hurdle_records"]<previous_n_hurdle):
            raise RuntimeError("decreasing_expanding_training_population")
        previous_n_team=update["trained_team_records"]
        previous_n_hurdle=update["trained_hurdle_records"]
        rows=[r for r in revealed["full_research_rows"] if r["graded"]]
        if len(rows)!=revealed["score"]["graded"]:
            raise RuntimeError("weekly_graded_count_disagreement")
        for r in rows:
            if r["model_asof"]!=frozen["forecast_asof"] or (
                r["training_last_revealed_week"]!=week-1):
                raise RuntimeError("forecast_after_week_start_or_future_week")
            market_rows[r["market"]].append(r)
        allrows.extend(rows)
        byweek[week]={
            "forecasted":len(frozen["predictions"]),
            "graded":len(rows),
            "unmatched":len(frozen["predictions"])-len(rows),
            "team_train_records":previous_n_team,
            "hurdle_train_records":previous_n_hurdle,
            "2024_hurdle_train_records":update["2024_hurdle_train_records"],
            **describe(rows),
        }
    if len(allrows)!=summary["graded"]:
        raise RuntimeError("cumulative_graded_count_mismatch")
    cum=[]
    sofar=[]
    for week in range(1,19):
        sofar.extend([r for r in allrows if r["week"]==week])
        stats=describe(sofar)
        cum.append({"week":week,**stats})
    paired={}
    for a,b in [
        ("team_xgb_bayes_hurdle_online","team_xgb_bayes_hurdle_no_refit"),
        ("team_xgb_bayes_hurdle_online","rolling_prior"),
        ("rolling_prior","static_2023_prior")]:
        paired[a+"_minus_"+b]={
          kind:block_bootstrap(allrows,a,b,kind)
          for kind in ("accuracy","brier")}
    report={
        "schema":"nfl_2024_weekly_learning_progression_audit_v1",
        "production_eligible":False,
        "synthesized_lines_not_bookmaker":True,
        "frozen_before_reveal_and_retrained_after_each_week":True,
        "overall":describe(allrows),
        "cumulative_by_week":cum,
        "weekly":byweek,
        "by_market":{market:describe(rows) for market,rows in market_rows.items()},
        "paired_game_bootstrap":paired,
        "forecasts":summary["forecasts"],
        "graded":summary["graded"],
        "unmatched":summary["forecasts"]-summary["graded"],
    }
    auditdir=root/"AUDIT"
    auditdir.mkdir(exist_ok=True)
    if (auditdir/"PROGRESSION.json").exists():
        raise RuntimeError("audit_already_exists_refuse_overwrite")
    (auditdir/"PROGRESSION.json").write_text(json.dumps(
                    report,sort_keys=True,indent=2)+"\n")
    lines=["# 2024 weekly NFL model learning progression","",
      "All results are on matched synthetic lines, not actual offered sportsbook props. "
      "Each week was forecast and SHA-locked before the week's outcomes were revealed. "
      "Team XGBoost and the active-zero classifier were refit after every revealed slate. "
      "No 2024 hyperparameter search or contemporaneous 2024 rosters were used.","",
      "## Weekly learning curve","",
      "| Week | Graded | Team rows | 2024 hurdle rows | Online hurdle accuracy | Online hurdle Brier | No-refit Brier | Rolling prior Brier |",
      "|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for w,s in byweek.items():
        def fmt(k,field):
            value=s.get(k,{}).get(field)
            return "%.4f"%value if value is not None else "—"
        lines.append("| %s | %d | %d | %d | %s | %s | %s | %s |"%
           (w,s["graded"],s["team_train_records"],s["2024_hurdle_train_records"],
            fmt("team_xgb_bayes_hurdle_online","accuracy"),
            fmt("team_xgb_bayes_hurdle_online","brier"),
            fmt("team_xgb_bayes_hurdle_no_refit","brier"),
            fmt("rolling_prior","brier")))
    lines.extend(["","## Overall accuracy, Brier and bias","","| Method | Matched | Accuracy | Brier | Under prediction share |",
                  "|---|---:|---:|---:|---:|"])
    for name in METHODS:
        s=report["overall"].get(name)
        if not s:continue
        lines.append("| %s | %d | %.4f | %.5f | %.2f%% |"%(
          name,s["n"],s["accuracy"],s["brier"],100*s["predicted_under_share"]))
    lines.extend(["",
         "## Paired uncertainty", "",
         "Intervals use an exploratory 500-replicate NFL-game cluster bootstrap. "
         "They do not resolve roster/line selection bias or across-week player dependence."])
    for key,parts in paired.items():
        for kind,m in parts.items():
            lines.append("- %s / %s: A − B = %.5f; approx. 95%% CI [%.5f, %.5f]"%(
                key,kind,m["A_minus_B"],*m["interval_95pc"]))
    lines.extend(["","## Data and limits","",
      "Forecasted: %s; graded: %s; unmatched: %s (not counted as losses or zeros)."%(
        report["forecasts"],report["graded"],report["unmatched"]),
      "Model progression is an observational post hoc walk-forward backtest. "
      "Predictions must not be represented as real sportsbook betting performance."])
    (auditdir/"REPORT.md").write_text("\n".join(lines)+"\n")
    print("WALKFORWARD_AUDIT_SUMMARY",json.dumps({
        "overall":report["overall"],"paired":report["paired_game_bootstrap"],
        "forecasts":report["forecasts"],"graded":report["graded"],
        "unmatched":report["unmatched"]}),flush=True)
    for w,s in byweek.items():
        print("WALKFORWARD_AUDIT_WEEK",w,json.dumps({
          "graded":s["graded"],"team_rows":s["team_train_records"],
          "hurdle_2024_rows":s["2024_hurdle_train_records"],
          "online":s.get("team_xgb_bayes_hurdle_online"),
          "no_refit":s.get("team_xgb_bayes_hurdle_no_refit"),
          "rolling_prior":s.get("rolling_prior")}),flush=True)
    return report


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    a=p.parse_args()
    audit(a.root)
