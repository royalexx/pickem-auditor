#!/usr/bin/env python3
"""Immutable full-universe counterfactual replay, never rewrite old forecasts.

`forecast` is a separate process supplied only prior-game inputs and schedule
identities. `run` owns the outcome oracle and reveals a week only AFTER the
forecast and calibration objects have been written and hashed persistently.
2024 is development-exposed and source possession in 2024 is uncertified.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import numpy as np

from v25_opportunity_distribution import (
    OpportunityModel,VERSION,POLICY,MARKETS,normalise_player_source,canonical,digest,reject)
from v25_nfl_2024_all_volume_rolling_calibration import fit_from_past,ptransform,role_for
from nfl_contract_settlement import index_outcomes,settle

HERE=Path(__file__).resolve().parent
MODELS=("repair","simple_control")
METHODS=("raw","global","role")

def serialise(x):
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,dict):return {k:serialise(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [serialise(v) for v in x]
    return x

def file_hash(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def write_once(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=canonical(serialise(obj))
    content=gzip.compress(raw,mtime=0) if path.suffix==".gz" else raw+b"\n"
    with path.open("xb") as f:f.write(content)
    return hashlib.sha256(content).hexdigest()

def read(path):
    raw=path.read_bytes()
    if path.suffix==".gz":raw=gzip.decompress(raw)
    return json.loads(raw)

def forecast_snapshot(snapshot,n,seed):
    if set(snapshot)!={"schema","week","history","schedule"} or snapshot["schema"]!="v25-opportunity-asof-v1":
        reject("snapshot_contains_outcome_or_unrecognised_field")
    m=OpportunityModel(snapshot["history"],snapshot["week"])
    output=[];seen=set()
    for g in snapshot["schedule"]:
        if set(g)!={"event_id","team","opponent","week"} or g["week"]!=snapshot["week"] or g["team"]==g["opponent"]:
            reject("schedule_outcome_or_invalid_identity")
        key=(g["event_id"],g["team"])
        if key in seen:reject("duplicate_schedule_game_team")
        seen.add(key)
        team=serialise(m.forecast_team(g["team"],g["event_id"],n=n,seed=seed))
        # The accepted research interface exposes count marginals explicitly.
        # Unaccepted yard candidates and the joint challenger remain separately
        # available for comparisons, never masquerading as the default.
        team["research_default_draws"]={pid:{market:values for market,values in markets.items()
            if "yards" not in market} for pid,markets in team["simple_control"].items()}
        output.append({**g,**team})
    if not output:reject("empty_schedule")
    return {"schema":VERSION,"week":snapshot["week"],"models":MODELS,
       "research_default_model":"simple_control",
       "default_supported_markets":[m for m in MARKETS if "yards" not in m],
       "default_abstained_markets":{m:"retain_existing_yard_model_no_accepted_replacement" for m in MARKETS if "yards" in m},
       "model_labels":{"simple_control":"appearance_matched_role_shrunk_marginal_distributions",
                       "repair":"physically_constrained_joint_opportunity_challenger"},
       "default_is_joint_scenario_model":False,
       "default_selection_reason":"retain_simple_count_baseline_until_joint_CRPS_gain_is_demonstrated",
       "forecast_input_content_sha256":digest(snapshot),"forecasts":output,
       "samples":n,"seed":seed,"policy":POLICY,
       "current_or_future_results_in_forecaster":False,
       "current_roster_verified":False,"research_only":True,
       "production_promotion_authorized":False,
       "code_hashes":{p.name:file_hash(p) for p in [HERE/"v25_opportunity_distribution.py",Path(__file__)]},
       "runtime":{"python":platform.python_version(),"numpy":np.__version__}}

def sample_score(values,actual,line):
    a=np.asarray(values,dtype=float);s=np.sort(a);n=len(s)
    p=float(np.mean(a>line));u=float(np.mean(a<line));push=float(np.mean(a==line))
    y=None if actual==line else int(actual>line)
    q=p/(p+u) if p+u else None
    return {"n_samples":n,"mean":float(np.mean(a)),"actual":actual,
       "bias":float(np.mean(a)-actual),"mae":float(abs(np.mean(a)-actual)),
       "crps":float(np.mean(abs(a-actual))-np.sum((2*np.arange(n)-n+1)*s)/(n*n)),
       "p10":float(np.quantile(a,.1)),"p90":float(np.quantile(a,.9)),
       "coverage80":bool(np.quantile(a,.1)<=actual<=np.quantile(a,.9)),
       "p_zero":float(np.mean(a==0)),"actual_zero":int(actual==0),
       "p_over":p,"p_under":u,"p_push":push,"q":q,"y":y}

def probability_score(q,y):
    return {"q":float(q),"y":int(y),"brier":(q-y)**2,
       "log_loss":-y*math.log(max(1e-9,q))-(1-y)*math.log(max(1e-9,1-q)),
       "hit":None if q==.5 else int((q>.5)==bool(y))}

def metrics(rows):
    if not rows:return {"n":0}
    result={"n":len(rows)}
    for k in ("brier","log_loss","bias","mae","crps","coverage80","p_zero","actual_zero","mean","actual"):
        vals=[r[k] for r in rows if r.get(k) is not None]
        if vals:result[k]=float(np.mean(vals))
    vals=[r["hit"] for r in rows if r.get("hit") is not None]
    result["directional_hit"]=float(np.mean(vals)) if vals else None
    binary=[r for r in rows if r.get("q") is not None and r.get("y") is not None]
    if binary:
        result["mean_over"]=float(np.mean([r["q"] for r in binary]))
        result["observed_over"]=float(np.mean([r["y"] for r in binary]))
    result["selective"]={}
    for t in (.7,.8,.9,.95):
        chosen=[r for r in binary if max(r["q"],1-r["q"])>=t and r.get("hit") is not None]
        result["selective"][str(int(100*t))]={"n":len(chosen),
            "hit":float(np.mean([r["hit"] for r in chosen])) if chosen else None,
            "claimed":float(np.mean([max(r["q"],1-r["q"]) for r in chosen])) if chosen else None,
            "under":sum(r["q"]<.5 for r in chosen),"over":sum(r["q"]>.5 for r in chosen)}
    return result

def paired(a,b,field):
    key=lambda r:(r["week"],r["game_id"],r["team"],r["player_id"],r["market"],r["line"])
    x={key(r):r for r in a if r.get(field) is not None};y={key(r):r for r in b if r.get(field) is not None}
    keys=sorted(x.keys()&y.keys());byweek=defaultdict(list)
    for k in keys:byweek[k[0]].append(x[k][field]-y[k][field])
    if not keys:return {"n":0}
    rng=np.random.default_rng(20261110);ws=sorted(byweek)
    sums=np.array([sum(byweek[w]) for w in ws]);ns=np.array([len(byweek[w]) for w in ws])
    ix=rng.integers(0,len(ws),(2000,len(ws)))
    boot=sums[ix].sum(axis=1)/ns[ix].sum(axis=1)
    return {"n":len(keys),"new_minus_reference":float(sums.sum()/ns.sum()),
       "weeks":len(ws),"week_cluster_95":np.quantile(boot,[.025,.975]).tolist(),
       "descriptive_development_exposed_2024":True}

def run(args):
    if args.output_dir.exists():reject("immutable_output_directory_exists")
    source=read(args.source);source_rejections=[]
    history_all=normalise_player_source(source["rows"],rejection_ledger=source_rejections)
    past=[g for g in history_all if g["season"]<2024]
    if len(past)<1200:reject("incomplete_pre2024_history")
    if args.audit_export:
        bundle=read(args.audit_export)
        original_packets={w:{"week":w,"latest_revealed_week":w-1,"predictions":[r for r in bundle["rows"] if r["week"]==w]} for w in range(1,19)}
        oracle={"weeks":{}}
        for w in range(1,19):
            games=[g for g in history_all if g["season"]==2024 and g["week"]==w]
            labels=[{"game_id":r["game_id"],"team":r["team"],"player_id":r["player_id"],"stat":r["market"],"value":r["actual"]} for r in original_packets[w]["predictions"] if r["actual"] is not None]
            oracle["weeks"][str(w)]={"team_games":[{"game_id":g["event_id"],"team":g["team"],"opponent":g["opponent"]} for g in games],"players":labels}
        oracle_sha=bundle["source_sha"]["pickem_runs/2024_walkforward_expanding_online_v2__PRIVATE_2024_ORACLE/oracle_2024.json"]
        original_sha={w:bundle["source_sha"][f"pickem_runs/2024_walkforward_expanding_online_v2/FROZEN/week_{w:02d}.json"] for w in range(1,19)}
    else:
        oracle_path=args.root/"2024_walkforward_expanding_online_v2__PRIVATE_2024_ORACLE/oracle_2024.json"
        oracle=read(oracle_path);oracle_sha=file_hash(oracle_path)
        original_packets={w:read(args.root/f"2024_walkforward_expanding_online_v2/FROZEN/week_{w:02d}.json") for w in range(1,19)}
        original_sha={w:file_hash(args.root/f"2024_walkforward_expanding_online_v2/FROZEN/week_{w:02d}.json") for w in range(1,19)}
    if set(oracle["weeks"])!={str(w) for w in range(1,19)}:reject("incomplete_2024_oracle")
    args.output_dir.mkdir(parents=True)
    write_once(args.output_dir/"SOURCE_REJECTIONS.json",source_rejections)
    code_dir=args.output_dir/"code"
    code_dir.mkdir()
    code_sha={}
    for name in ("v25_opportunity_distribution.py","v25_opportunity_repair_replay.py",
                 "nfl_contract_settlement.py","v25_nfl_2024_all_volume_rolling_calibration.py"):
        raw=(HERE/name).read_bytes()
        with (code_dir/name).open("xb") as f:f.write(raw)
        code_sha[name]=hashlib.sha256(raw).hexdigest()
    histories=defaultdict(list);ledgers=defaultdict(list);coverage=Counter();manifests=[];weekly=[]
    for week in range(1,19):
        wk=oracle["weeks"][str(week)]
        schedules=[{"event_id":g["game_id"],"team":g["team"],"opponent":g["opponent"],"week":week} for g in wk["team_games"]]
        snapshot={"schema":"v25-opportunity-asof-v1","week":week,"history":past,"schedule":schedules}
        prefix=args.output_dir/f"week_{week:02d}"
        inp=prefix.with_name(prefix.name+"_asof_input.json.gz");out=prefix.with_name(prefix.name+"_forecast.json.gz")
        input_sha=write_once(inp,snapshot)
        p=subprocess.run([sys.executable,str((code_dir/Path(__file__).name).resolve()),"forecast","--input",str(inp),"--output",str(out),"--samples",str(args.samples),"--seed",str(args.seed)],capture_output=True,text=True,timeout=480)
        if p.returncode:raise RuntimeError("forecast_child_failed:"+p.stderr[-2000:])
        forecast=read(out)
        if forecast["forecast_input_content_sha256"]!=digest(snapshot):reject("input_digest_changed")
        original=original_packets[week]
        if original["latest_revealed_week"]!=week-1:reject("invalid_original_cutoff")
        index={}
        proxy={}
        for g in forecast["forecasts"]:
            proxy[g["event_id"],g["team"]]=g["qb_primary_proxy"]
            for model,field in [("repair","draws"),("simple_control","simple_control")]:
                for pid,markets in g[field].items():
                    for market,arr in markets.items():index[model,g["event_id"],g["team"],pid,market]=arr
        # Freeze all current offered probabilities and full prior-only fit
        # preimages before looking up any current outcome.
        offers=[];calibrators={}
        for model in MODELS:
            for market in MARKETS:
                hs=histories[model,market]
                if any(r["week"]>=week for r in hs):reject("future_calibration_label")
                calibrators[model+"|"+market]=fit_from_past(hs)
        for r in original["predictions"]:
            for model in MODELS:
                values=index.get((model,r["game_id"],r["team"],r["player_id"],r["market"]))
                if values is None:
                    coverage[model+":no_asof_model_or_role"]+=1;continue
                a=np.asarray(values);line=r["research_line"]
                if "yards" in r["market"] and float(line).is_integer():
                    coverage[model+":integer_yard_line_requires_discrete_distribution"]+=1
                    continue
                over=int(sum(a>line));under=int(sum(a<line))
                if not over+under:
                    coverage[model+":all_predictive_push"]+=1;continue
                offers.append({"model":model,"game_id":r["game_id"],"team":r["team"],"player_id":r["player_id"],"market":r["market"],"research_line":line,
                    "role":role_for(r["position"]),"q":over/(over+under),
                    "old_p_over":r["p_over"],"old_mean":r["simulated_mean"],
                    "qb_primary_proxy":proxy[r["game_id"],r["team"]]})
        calibration={"week":week,"training_only_through_week":week-1,
            "history_counts":{m+"|"+s:len(histories[m,s]) for m in MODELS for s in MARKETS},
            "full_parameter_preimages":calibrators,"current_offers_without_outcomes":offers,
            "numpy_version":np.__version__,"source_capture_certified":False}
        cal_path=prefix.with_name(prefix.name+"_calibration.json.gz")
        cal_sha=write_once(cal_path,calibration)
        # Current labels become visible only after both immutable writes.
        truth=index_outcomes(wk["players"]);current=[];new_history=defaultdict(list)
        for offer in offers:
            st=settle(offer,truth);coverage[offer["model"]+":"+st["state"]]+=1
            if st["state"]=="UNMATCHED":continue
            model=offer["model"];market=offer["market"]
            values=index[model,offer["game_id"],offer["team"],offer["player_id"],market]
            score=sample_score(values,st["actual"],offer["research_line"])
            row={"week":week,"game_id":offer["game_id"],"team":offer["team"],"player_id":offer["player_id"],"market":market,"line":offer["research_line"],"model":model,
                "role":offer["role"],"is_primary_qb_proxy":offer["player_id"]==offer["qb_primary_proxy"],**score}
            for method in METHODS:
                item={**row,"method":method}
                if st["state"]=="SETTLED" and score["q"] is not None:
                    q=ptransform(score["q"],offer["role"],calibrators[model+"|"+market],method)
                    item.update(probability_score(q,score["y"]))
                ledgers[model,method,market].append(item);current.append(item)
            old={**row,"model":"frozen_archive_raw","method":"raw","crps":None,
                 "mean":offer["old_mean"],"bias":offer["old_mean"]-st["actual"],
                 "mae":abs(offer["old_mean"]-st["actual"]),"coverage80":None,"p_zero":None,
                 "p10":None,"p90":None}
            if st["state"]=="SETTLED":
                old.update(probability_score(offer["old_p_over"],score["y"]))
            # One old row per matching repair contract, for exact pairing.
            if model=="repair":ledgers["frozen_archive_raw","raw",market].append(old)
            if st["state"]=="SETTLED" and score["q"] is not None:
                new_history[model,market].append({"p":score["q"],"y":score["y"],"role":offer["role"],"week":week})
        scored_path=prefix.with_name(prefix.name+"_settled.json.gz")
        settled_sha=write_once(scored_path,current)
        for key,items in new_history.items():histories[key].extend(items)
        fresh=[g for g in history_all if g["season"]==2024 and g["week"]==week]
        # Training updates use the newly collected observed boxes only after
        # freeze; evaluation retains ORIGINAL oracle values and exact teams.
        past.extend(fresh)
        manifests.append({"week":week,"input_file":inp.name,"input_sha256":input_sha,
           "forecast_file":out.name,"forecast_sha256":file_hash(out),
           "calibration_file":cal_path.name,"calibration_sha256":cal_sha,
           "settled_file":scored_path.name,"settled_sha256":settled_sha,
           "original_source_forecast_sha256":original_sha[week],
           "evaluated_contract_table_content_sha256":digest(original["predictions"]),
           "train_through_week":week-1})
        summary={"week":week,"candidate_n":len(original["predictions"]),
           "market_models":{market:{model:{method:metrics([r for r in current if r["market"]==market and r["model"]==model and r["method"]==method]) for method in METHODS} for model in MODELS} for market in MARKETS}}
        weekly.append(summary)
        print("REPAIR_WEEK_DONE",json.dumps({"week":week,"saved_forecast":out.name,"input_sha256":input_sha,"n_offers":len(offers)}),flush=True)
    markets={}
    for market in MARKETS:
        market_ledger={m:{method:ledgers[m,method,market] for method in METHODS} for m in MODELS}
        markets[market]={"models":{m:{method:metrics(rows) for method,rows in methods.items()} for m,methods in market_ledger.items()},
           "frozen_archive_matched":metrics(ledgers["frozen_archive_raw","raw",market]),
           "repair_minus_simple_matched":{field:paired(ledgers["repair","raw",market],ledgers["simple_control","raw",market],field) for field in ("crps","brier","bias")},
           "repair_minus_archive_matched_brier":paired(ledgers["repair","raw",market],ledgers["frozen_archive_raw","raw",market],"brier")}
        if market in MARKETS[:3]:
            markets[market]["primary_proxy_cohort"]={m:metrics([r for r in ledgers[m,"raw",market] if r["is_primary_qb_proxy"]]) for m in (*MODELS,"frozen_archive_raw")}
    result={"schema":VERSION,"status":"COMPLETED_RESEARCH_NOT_PRODUCTION_CERTIFIED",
       "source_file_sha256":file_hash(args.source),"original_oracle_reference_sha256":oracle_sha,
       "source_rejection_counts":dict(Counter(x["reason"] for x in source_rejections)),
       "evaluation_input_kind":"verified_audit_export_exact_contracts" if args.audit_export else "original_full_oracle",
       "audit_export_sha256":file_hash(args.audit_export) if args.audit_export else None,
       "source_retrieved_at":source["retrieved_at"],"weeks":18,"samples":args.samples,"seed":args.seed,
       "source_2024_possession_certified":False,"2024_development_exposed":True,
       "production_promotion_authorized":False,"tier_publication_authorized":False,
       "conditional_non_qb_distribution_not_availability_forecast":True,
       "frozen_code_sha256":code_sha,
       "coverage":dict(coverage),"manifest":manifests,"markets":markets,"weekly":weekly,
       "policy":POLICY,"numpy_version":np.__version__}
    result["receipt_sha256"]=digest(result)
    write_once(args.output_dir/"FINAL_REPAIR_REPORT.json",result)
    write_once(args.output_dir/"RESEARCH_SCORED_LEDGER.json.gz",{ "|".join(k):v for k,v in ledgers.items()})
    print("REPAIR_FINAL",json.dumps({"receipt_sha256":result["receipt_sha256"],"markets":{m:{"repair_raw":v["models"]["repair"]["raw"],"simple":v["models"]["simple_control"]["raw"],"paired":v["repair_minus_simple_matched"]} for m,v in markets.items()}}),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);subs=p.add_subparsers(dest="mode",required=True)
    a=subs.add_parser("forecast");a.add_argument("--input",type=Path,required=True);a.add_argument("--output",type=Path,required=True)
    b=subs.add_parser("run");b.add_argument("--source",type=Path,required=True)
    location=b.add_mutually_exclusive_group(required=True)
    location.add_argument("--root",type=Path);location.add_argument("--audit-export",type=Path)
    b.add_argument("--output-dir",type=Path,required=True)
    for sub in (a,b):sub.add_argument("--samples",type=int,default=512);sub.add_argument("--seed",type=int,default=20261110)
    args=p.parse_args()
    if args.mode=="forecast":write_once(args.output,forecast_snapshot(read(args.input),args.samples,args.seed))
    else:run(args)
    return 0

if __name__=="__main__":raise SystemExit(main())
