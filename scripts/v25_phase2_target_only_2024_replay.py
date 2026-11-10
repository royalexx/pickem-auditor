#!/usr/bin/env python3
"""Phase 2 2024 NFL week-by-week TARGET-ONLY research scorecard.

Only 2021–2023 plus previous 2024 weeks are ever passed to the
v25_phase2_target_only_forecast.py child subprocess. The child receives an
outcome-free schedule and cannot access the oracle via its input. This is an
offline, post-hoc study of model learning, NOT prospective P0R certification
or a test of unavailable route/verified-injury variables.

Historic lines are synthetic research diagnostic lines, NOT bookmaker quotes.
The archived candidate universe is not a verified pregame roster.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, Counter
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics as stats
import subprocess
import sys

CHILD = Path(__file__).with_name("v25_phase2_target_only_forecast.py")
METHODS = ("updated","no_refit")
CUTS = (.7,.8,.9,.95)


def H(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(",",":"),
                                  allow_nan=False).encode()).hexdigest()


def fail(reason):
    raise RuntimeError("2024_PHASE2_REPLAY_FAIL:"+reason)


def normalise_pre2024(nfl):
    frame=nfl.load_player_stats(seasons=[2021,2022,2023],summary_level="week")
    fields=("season","week","season_type","game_id","team","player_id",
            "position","targets","attempts")
    missing=set(fields)-set(frame.columns)
    if missing: fail("source_columns_missing:"+",".join(sorted(missing)))
    raw=frame.select(list(fields)).to_dicts()
    groups={}
    seen=set()
    for r in raw:
        if r["season_type"]!="REG" or r["season"] not in (2021,2022,2023):continue
        if r.get("team") is None or r.get("game_id") is None:continue
        key=(r["game_id"],r["team"])
        row=groups.setdefault(key,{
            "event_id":r["game_id"],"team":r["team"],"season":int(r["season"]),
            "week":int(r["week"]),"pass_attempts":0,"players":{},
        })
        attempted=r.get("attempts")
        if attempted is not None:
            if not isinstance(attempted,(int,float)) or attempted<0 or not float(attempted).is_integer():
                fail("bad_pre2024_attempts")
            row["pass_attempts"]+=int(attempted)
        if r.get("position") in ("WR","RB","TE"):
            pid=r.get("player_id")
            if not isinstance(pid,str) or not pid:continue
            n=r.get("targets")
            if n is None:n=0
            if not isinstance(n,(int,float)) or n<0 or not float(n).is_integer():
                fail("bad_pre2024_targets")
            if pid in row["players"]:fail("duplicate_pre2024_player_game")
            row["players"][pid]={"role":r["position"],"targets":int(n)}
    rows=sorted(groups.values(),key=lambda r:(r["season"],r["week"],r["event_id"],r["team"]))
    invalid=[r for r in rows
             if sum(p["targets"] for p in r["players"].values())>r["pass_attempts"]]
    if invalid:fail("pre2024_target_total_exceeds_team_pass_attempts:"+str(len(invalid)))
    if len(rows)<1200:fail("incomplete_pre2024_team_games")
    return rows,{"n_player_week_source_rows":len(raw),"n_team_games":len(rows),
                 "n_games":len({r["event_id"] for r in rows}),
                 "first_year":min(r["season"] for r in rows),
                 "last_year":max(r["season"] for r in rows)}


def load_2024_oracle(root:Path):
    path=root/"2024_walkforward_expanding_online_v2__PRIVATE_2024_ORACLE"/"oracle_2024.json"
    data=json.loads(path.read_bytes())
    if set(data["weeks"])!={str(i) for i in range(1,19)}:
        fail("not_all_18_weeks_in_oracle")
    actual=defaultdict(list)
    schedules={}
    for w in range(1,19):
        wk=data["weeks"][str(w)]
        pairs={}
        for raw in wk["team_games"]:
            key=(raw["game_id"],raw["team"])
            if key in pairs:fail("duplicate_team_game_oracle")
            if raw["pass_attempts"] is None or raw["pass_attempts"]<0:
                fail("missing_team_attempts_oracle")
            pairs[key]={
                "event_id":raw["game_id"],"team":raw["team"],"season":2024,
                "week":w,"pass_attempts":int(raw["pass_attempts"]),"players":{}
            }
        for raw in wk["players"]:
            if raw.get("stat")!="targets":continue
            key=(raw["game_id"],raw["team"])
            if key not in pairs:fail("orphan_2024_target_player")
            pid=raw.get("player_id");role=raw.get("position")
            if role not in ("RB","WR","TE") or not pid:
                continue
            n=raw.get("value")
            if n is None or n<0 or not float(n).is_integer():
                fail("invalid_2024_target_actual")
            players=pairs[key]["players"]
            if pid in players:fail("duplicate_2024_target_player_game")
            players[pid]={"role":role,"targets":int(n)}
        for key,row in pairs.items():
            if sum(x["targets"] for x in row["players"].values())>row["pass_attempts"]:
                fail("oracle_2024_targets_exceed_pass_attempts")
            actual[w].append(row)
        # The forecaster receives ONLY these four identity columns:
        schedules[w]=[
            {"event_id":r["event_id"],"team":r["team"],
             "opponent":next((y["opponent"] for y in wk["team_games"]
                              if y["game_id"]==r["event_id"] and y["team"]==r["team"]),None),
             "week":w}
            for r in sorted(pairs.values(),key=lambda t:(t["event_id"],t["team"]))]
        if any(set(s)!={"event_id","team","opponent","week"} or
               not s["opponent"] for s in schedules[w]):
            fail("oracle_leaked_into_schedule")
    return actual,schedules,hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_lines(root:Path):
    folder=root/"2024_walkforward_expanding_online_v2"/"FROZEN"
    lines={};all_counts={};sha={}
    for w in range(1,19):
        path=folder/f"week_{w:02d}.json"
        content=path.read_bytes();sha[w]=hashlib.sha256(content).hexdigest()
        packet=json.loads(content)
        if (packet["week"]!=w or packet["latest_revealed_week"]!=w-1
                or packet["training_label_week_limit"]!=w-1
                or packet["future_2024_week_data_accessed_by_forecaster"] is not False):
            fail("original_weekly_frozen_metadata_leak")
        count=0;found={}
        for row in packet["predictions"]:
            if row.get("market")!="targets":continue
            count+=1
            key=(row["game_id"],row["team"],row["player_id"])
            if key in found:fail("duplicate_original_research_line")
            found[key]=float(row["research_line"])
        lines[w]=found;all_counts[w]=count
    return lines,all_counts,sha


def crps(samples, y):
    # O(M log M) empirical CRPS; no random scoring perturbation.
    m=len(samples)
    if not m:fail("empty_predictive_samples")
    sorted_s=sorted(samples)
    abs_error=sum(abs(x-y) for x in sorted_s)/m
    pair=sum((2*i-m+1)*x for i,x in enumerate(sorted_s))/(m*m)
    return abs_error-pair


def metrics(points):
    if not points:return {"n":0,"crps":None,"mae":None,"brier":None,
                           "accuracy":None}
    n=len(points)
    out={"n":n,
         "crps":sum(x["crps"] for x in points)/n,
         "mae":sum(x["mae"] for x in points)/n}
    if "brier" in points[0]:
        out.update(brier=sum(x["brier"] for x in points)/n,
                   accuracy=sum(x["hit"] for x in points if x["hit"] is not None)/
                   sum(x["hit"] is not None for x in points)
                   if any(x["hit"] is not None for x in points) else None)
    return out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--samples",type=int,default=512)
    parser.add_argument("--seed",type=int,default=20261110)
    args=parser.parse_args()
    if args.output_dir.exists():parser.error("immutable_research_output_dir_already_exists")
    import nflreadpy as nfl
    pre,pre_coverage=normalise_pre2024(nfl)
    oracle,schedules,oracle_sha=load_2024_oracle(args.root)
    original_lines,original_n,original_sha=frozen_lines(args.root)
    # The oracle is held by this parent only. The child receives ONE file
    # containing 2021–23 and, after each completed forecast, earlier 2024.
    args.output_dir.mkdir(parents=True)
    history=list(pre)
    perweek=[];results=[];source_hashes={}
    for w in range(1,19):
        if max((r["week"] for r in history if r["season"]==2024),default=0)!=w-1:
            fail("future_or_missing_training_week")
        snapshot={
            "schema":"v25-p2-target-only-asof-week-v1",
            "week":w,
            "history":history,
            "schedule":schedules[w],
        }
        # Zero current/future data fields in the child input by construction.
        if any(r["season"]==2024 and r["week"]>=w for r in snapshot["history"]):
            fail("current_or_future_stats_in_child_file")
        if any(set(s)!={"event_id","team","opponent","week"}
               for s in snapshot["schedule"]):
            fail("outcome_field_in_child_schedule")
        incoming=args.output_dir/f"asof_2024_week_{w:02d}.json"
        outgoing=args.output_dir/f"FROZEN_2024_week_{w:02d}.json"
        incoming.write_text(json.dumps(snapshot,sort_keys=True,separators=(",",":")))
        p=subprocess.run([sys.executable,str(CHILD),
            "--input",str(incoming),"--output",str(outgoing),
            "--samples",str(args.samples),"--seed",str(args.seed)],
            capture_output=True,text=True,timeout=180)
        if p.returncode:fail("child_fail_w"+str(w)+":"+p.stderr[-1600:])
        completed=json.loads(outgoing.read_bytes())
        if (completed["week"]!=w
                or completed["train_2024_max_week"]!=w-1
                or completed["future_outcomes_exposed_to_forecaster"] is not False
                or completed["original_input_sha256"]!=H(snapshot)):
            fail("frozen_child_manifest_mismatch")
        source_hashes[str(w)]={
            "asof_input_sha":hashlib.sha256(incoming.read_bytes()).hexdigest(),
            "forecasts_sha":hashlib.sha256(outgoing.read_bytes()).hexdigest(),
            "original_legacy_frozen_sha":original_sha[w],
            "fitted_last_2024_week":completed["train_2024_max_week"],
            "historical_team_games":completed["history_game_count"],
        }
        # Only after the child exits and its output SHA is fixed do we bring
        # back same-week outcomes. The child is never given this oracle path.
        actuals={(x["event_id"],x["team"]):x for x in oracle[w]}
        team_points=defaultdict(list);target_points=defaultdict(list)
        confidence=defaultdict(list)
        coverage=Counter()
        for result in completed["forecasts"]:
            key=(result["event_id"],result["team"])
            actual=actuals.get(key)
            if actual is None:fail("missing_oracle_team_result")
            for mode in METHODS:
                model=result["models"][mode]
                if model["status"]!="shadow_target_allocation_without_routes":
                    coverage[mode+"_team_not_modeled"]+=1
                    continue
                xs=model["pass_attempts"];y=actual["pass_attempts"]
                team_points[mode].append({
                    "crps":crps(xs,y),"mae":abs(sum(xs)/len(xs)-y),
                    "event_id":key[0],"team":key[1],"week":w,
                })
                original_candidates={
                    pid:line for (event,team,pid),line in original_lines[w].items()
                    if event==key[0] and team==key[1]
                }
                for pid,line in original_candidates.items():
                    if pid not in model["player_targets"]:
                        coverage[mode+"_candidate_not_asof_roster"]+=1
                        continue
                    truth=actual["players"].get(pid)
                    if truth is None:
                        coverage[mode+"_candidate_not_in_settled_source"]+=1
                        continue
                    y=truth["targets"]
                    pred=model["player_targets"][pid]
                    q_over=sum(v>line for v in pred)/len(pred)
                    q_under=sum(v<line for v in pred)/len(pred)
                    q_push=sum(v==line for v in pred)/len(pred)
                    if abs(q_over+q_under+q_push-1)>1e-10:
                        fail("over_under_push_not_complementary")
                    if q_push:coverage[mode+"_push_probability_nonzero"]+=1
                    if y==line:coverage[mode+"_actual_push"]+=1
                    event={"crps":crps(pred,y),"mae":abs(sum(pred)/len(pred)-y),
                           "event_id":key[0],"team":key[1],"player_id":pid,
                           "week":w,"line":line,"actual":y,"q_over":q_over,
                           "q_under":q_under,"q_push":q_push}
                    if y!=line and q_over+q_under:
                        p_over=q_over/(q_over+q_under)
                        event["brier"]=(p_over-int(y>line))**2
                        event["hit"]=int((p_over>.5)==(y>line)) if p_over!=.5 else None
                        event["confidence"]=max(p_over,1-p_over)
                        event["chosen_side"]="over" if p_over>.5 else "under" if p_over<.5 else "tie"
                        confidence[mode].append(event)
                    target_points[mode].append(event)
                    coverage[mode+"_scored_targets"]+=1
                coverage[mode+"_all_original_targets_in_team"]+=len(original_candidates)
                if mode=="updated":
                    indep=model["independent_poisson_targets"]
                    for pid,line in original_candidates.items():
                        truth=actual["players"].get(pid)
                        if pid not in indep or truth is None:continue
                        y=truth["targets"];samples=indep[pid]
                        p_over=sum(v>line for v in samples)/len(samples)
                        p_under=sum(v<line for v in samples)/len(samples)
                        q_push=sum(v==line for v in samples)/len(samples)
                        r={"crps":crps(samples,y),
                           "mae":abs(sum(samples)/len(samples)-y),
                           "event_id":key[0],"team":key[1],"player_id":pid,"week":w}
                        if y!=line and p_over+p_under:
                            prob=p_over/(p_over+p_under)
                            r["brier"]=(prob-int(y>line))**2
                            r["hit"]=int((prob>.5)==(y>line)) if prob!=.5 else None
                        target_points["independent_poisson"].append(r)
        row={
            "week":w,
            "n_team_games":len(actuals),
            "n_original_research_targets":original_n[w],
            "team":{"updated":metrics(team_points["updated"]),
                    "no_refit":metrics(team_points["no_refit"])},
            "targets":{mode:metrics(target_points[mode])
                       for mode in (*METHODS,"independent_poisson")},
            "candidate_coverage":dict(sorted(coverage.items())),
            "high_confidence":{},
        }
        for mode in METHODS:
            row["high_confidence"][mode]={}
            for c in CUTS:
                chosen=[r for r in confidence[mode]
                        if r["confidence"]>=c and r["hit"] is not None]
                row["high_confidence"][mode][str(int(100*c))]={
                    "n":len(chosen),
                    "accuracy":sum(r["hit"] for r in chosen)/len(chosen)
                                 if chosen else None,
                    "mean_claimed":sum(r["confidence"] for r in chosen)/len(chosen)
                                 if chosen else None,
                    "overs":sum(r["chosen_side"]=="over" for r in chosen),
                    "unders":sum(r["chosen_side"]=="under" for r in chosen),
                }
        perweek.append(row)
        results.append({
            "week":w,
            "team_scores":{k:team_points[k] for k in METHODS},
            "target_scores":{k:target_points[k] for k in
                             (*METHODS,"independent_poisson")},
            "confidence":{k:confidence[k] for k in METHODS},
        })
        # Reveal AFTER scoring, never during a week. Only then extend history.
        history+=oracle[w]
        print("REVEAL_COMPLETE",json.dumps({
            "week":w,
            "training_latest_week_before_forecast":w-1,
            "team_crps_online":row["team"]["updated"]["crps"],
            "team_crps_no_refit":row["team"]["no_refit"]["crps"],
            "targets_online_n":row["targets"]["updated"]["n"],
            "targets_online_crps":row["targets"]["updated"]["crps"],
            "targets_online_80pct_n":row["high_confidence"]["updated"]["80"]["n"],
        }),flush=True)
    # Only original same-game, same player identity matched records used
    # for paired learning claims, not a favorable subset of each model.
    def aggregate(kind,model):
        if kind=="team":
            rows=[x for batch in results for x in batch["team_scores"][model]]
        else:
            rows=[x for batch in results for x in batch["target_scores"][model]]
        return metrics(rows)
    pairs={}
    for kind in ("team","target"):
        index =lambda rec:(rec["week"],rec["event_id"],rec["team"],
                           rec.get("player_id",""))
        all_online=[r for b in results for r in
                    (b["team_scores"]["updated"] if kind=="team"
                     else b["target_scores"]["updated"])]
        frozen=[r for b in results for r in
                (b["team_scores"]["no_refit"] if kind=="team"
                 else b["target_scores"]["no_refit"])]
        a={index(r):r for r in all_online};b={index(r):r for r in frozen}
        common=sorted(set(a)&set(b))
        deltas=[(k[0],a[k]["crps"]-b[k]["crps"]) for k in common]
        by_week=defaultdict(list)
        for w,d in deltas:by_week[w].append(d)
        samples=[]
        rng=random.Random(args.seed)
        for j in range(3000):
            weeks=rng.choices(list(sorted(by_week)),k=18)
            choices=[d for w in weeks for d in by_week[w]]
            samples.append(sum(choices)/len(choices))
        samples.sort()
        pairs[kind]={"matched_contracts":len(common),
            "online_minus_no_refit_crps":sum(d for w,d in deltas)/len(deltas),
            "week_cluster_95":[samples[75],samples[2924]],
            "n_week_clusters":len(by_week),
            "online_better_week_count":sum(
                stats.mean(by_week[w])<0 for w in by_week),
        }
    confidence_all={}
    for mode in METHODS:
        confidence_all[mode]={}
        scored=[r for x in results for r in x["confidence"][mode] if r["hit"] is not None]
        for c in CUTS:
            subset=[r for r in scored if r["confidence"]>=c]
            confidence_all[mode][str(int(c*100))]={
                "n":len(subset),
                "hit_rate":sum(r["hit"] for r in subset)/len(subset) if subset else None,
                "mean_claimed":sum(r["confidence"] for r in subset)/len(subset) if subset else None,
                "over_n":sum(r["chosen_side"]=="over" for r in subset),
                "under_n":sum(r["chosen_side"]=="under" for r in subset),
            }
    report={
        "schema":"v25-phase2-2024-target-only-weekly-learning-report-1",
        "source":"public_nflverse_2021_2023_weekly_stats_and_archived_2024_oracle",
        "study_type":"retrospective_counterfactual_target_only_no_routes",
        "production_model_validated":False,
        "true_pregame_source_publication_verified":False,
        "current_or_future_outcomes_passed_to_model":False,
        "input_freeze_audited_by_independent_subprocess":True,
        "original_2024_source_oracle_sha":oracle_sha,
        "original_2024_research_quote_kind":"synthetic_no_verified_bookmaker",
        "initial_training_coverage":pre_coverage,
        "pre2024_fit_only":True,
        "updated_2024_history_revealed_only_after_each_frozen_forecast":True,
        "actual_routes_in_history":False,
        "verified_roster_history":False,
        "high_confidence_is_research_calibration_not_betting":True,
        "all_original_2024_frozen_target_candidates":sum(original_n.values()),
        "weekly":perweek,
        "overall":{
            "team":{m:aggregate("team",m) for m in METHODS},
            "targets":{m:aggregate("target",m)
                       for m in (*METHODS,"independent_poisson")},
            "high_confidence":confidence_all,
            "paired_online_vs_no_refit":pairs,
        },
        "frozen_week_sha_manifest":source_hashes,
    }
    report["report_sha256"]=H(report)
    file=args.output_dir/"FINAL_RESEARCH_REPORT.json"
    if file.exists():fail("immutable_final_report_exists")
    file.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print("PHASE2_2024_FINAL",json.dumps({
        "report_sha256":report["report_sha256"],
        "pre2024_games":pre_coverage["n_games"],
        "team_online":report["overall"]["team"]["updated"],
        "team_no_refit":report["overall"]["team"]["no_refit"],
        "targets_online":report["overall"]["targets"]["updated"],
        "targets_no_refit":report["overall"]["targets"]["no_refit"],
        "targets_independent":report["overall"]["targets"]["independent_poisson"],
        "confidence":confidence_all["updated"],
        "paired_crps":pairs,
        "status":"RESEARCH_ONLY_NO_PRODUCTION_PROMOTION"
    },sort_keys=True),flush=True)


if __name__=="__main__":
    main()
