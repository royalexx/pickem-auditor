#!/usr/bin/env python3
"""Independent frozen-file rescore. Does not fit or invoke the forecaster."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import gzip,hashlib,json,math
from pathlib import Path
import numpy as np

def read(p):
    raw=p.read_bytes()
    return json.loads(gzip.decompress(raw) if p.suffix==".gz" else raw)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def need(ok,reason):
    if not ok:raise AssertionError("OPPORTUNITY_RECEIPT_AUDIT_REJECTED:"+reason)

def crps(values,actual):
    # Independent order-statistic expression for empirical CRPS.
    x=sorted(float(v) for v in values);n=len(x)
    return sum(abs(v-actual) for v in x)/n-sum((2*i-n+1)*v for i,v in enumerate(x))/(n*n)

def run(folder,audit_export):
    report=read(folder/"FINAL_REPAIR_REPORT.json");bundle=read(audit_export)
    need(report["audit_export_sha256"]==sha(audit_export),"changed_audit_input")
    need(report["production_promotion_authorized"] is False,"unauthorised_promotion")
    body={k:v for k,v in report.items() if k!="receipt_sha256"}
    need(hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()==report["receipt_sha256"],"report_content_digest")
    need(len(report["manifest"])==18,"incomplete_weeks")
    checks=Counter();computed=defaultdict(list)
    for name,expected in report["frozen_code_sha256"].items():
        need(sha(folder/"code"/name)==expected,"changed_frozen_code")
        checks["frozen_code_hash"]+=1
    for receipt in report["manifest"]:
        week=receipt["week"]
        for field in ("input","forecast","calibration","settled"):
            need(sha(folder/receipt[field+"_file"])==receipt[field+"_sha256"],field+"_hash")
            checks[field+"_hash"]+=1
        inp=read(folder/receipt["input_file"]);forecast=read(folder/receipt["forecast_file"])
        cal=read(folder/receipt["calibration_file"]);settled=read(folder/receipt["settled_file"])
        need(inp["week"]==week and set(inp)=={"schema","week","history","schedule"},"input_schema")
        need(all(g["season"]<2024 or g["season"]==2024 and g["week"]<week for g in inp["history"]),"future_training")
        need(all(set(g)=={"event_id","team","opponent","week"} for g in inp["schedule"]),"outcome_in_schedule")
        need(cal["training_only_through_week"]==week-1,"calibration_future_week")
        need(all(f["latest_week"]<week for f in cal["full_parameter_preimages"].values()),"future_fitted_parameter")
        checks["calendar_cutoff"]+=1
        frozen={}
        for team in forecast["forecasts"]:
            attempt=np.asarray(team["team_pass_attempts"])
            need(np.all(attempt>=0) and np.all(attempt==attempt.astype(int)),"invalid_attempt_samples")
            q=np.zeros(len(attempt),dtype=int);t=q.copy()
            for pid,markets in team["draws"].items():
                q+=np.asarray(markets.get("pass attempts",q*0),dtype=int)
                t+=np.asarray(markets.get("targets",t*0),dtype=int)
                if "completions" in markets:need(np.all(np.asarray(markets["completions"])<=markets["pass attempts"]),"completion_capacity")
                if "receptions" in markets:need(np.all(np.asarray(markets["receptions"])<=markets["targets"]),"reception_capacity")
            need(np.array_equal(q+team["unknown_qb_attempts"],attempt),"qb_conservation")
            need(np.array_equal(t+team["unknown_receiver_targets"]+team["non_target_attempts"],attempt),"target_conservation")
            if "unknown_rb_attempts" in team:
                carries=sum((np.asarray(p.get("carries",[0]*len(attempt))) for p in team["draws"].values()),np.zeros(len(attempt),dtype=int))
                need(np.array_equal(carries+team["unknown_rb_attempts"]+team["non_rb_rush_attempts"],team["team_rush_attempts"]),"rush_conservation")
                for p in team["draws"].values():
                    if all(m in p for m in ("tackles + assists","solo tackles","tackle assists")):
                        need(np.all(np.asarray(p["solo tackles"])+p["tackle assists"]<=p["tackles + assists"]),"tackle_categories")
            for model,key in [("repair","draws"),("simple_control","simple_control")]:
                for pid,markets in team[key].items():
                    for market,arr in markets.items():frozen[model,team["event_id"],team["team"],pid,market]=arr
            checks["joint_team_scenarios_conserved"]+=len(attempt)
        truth={(r["game_id"],r["team"],r["player_id"],r["market"],r["research_line"]):r["actual"] for r in bundle["rows"] if r["week"]==week}
        seen=set()
        for row in settled:
            identity=(row["game_id"],row["team"],row["player_id"],row["market"],row["line"])
            key=(row["model"],row["method"],*identity)
            need(key not in seen,"duplicate_scored_contract");seen.add(key)
            need(identity in truth and truth[identity] is not None and truth[identity]==row["actual"],"wrong_actual_identity")
            vals=frozen[row["model"],row["game_id"],row["team"],row["player_id"],row["market"]]
            over=sum(v>row["line"] for v in vals);under=sum(v<row["line"] for v in vals)
            q=over/(over+under) if over+under else None
            fit=cal["full_parameter_preimages"][row["model"]+"|"+row["market"]]
            if q is not None and row["method"]!="raw" and fit["active"]:
                p=max(.0005,min(.9995,q));v=fit["a"]+fit["b"]*math.log(p/(1-p))
                if row["method"]=="role":v+=fit["offset"].get(row["role"],0.)
                q=1/(1+math.exp(-max(-30.,min(30.,v))))
            if row["actual"]!=row["line"] and q is not None:
                need(abs(row["q"]-q)<1e-12,"changed_frozen_probability")
                y=int(row["actual"]>row["line"])
                need(row["y"]==y and abs(row["brier"]-(q-y)**2)<1e-12,"wrong_binary_score")
                checks["independent_probability_scores"]+=1
            if row["method"]=="raw":
                c=crps(vals,row["actual"])
                need(abs(row["crps"]-c)<1e-10,"wrong_count_crps")
                checks["independent_count_crps"]+=1
            computed[row["model"],row["method"],row["market"]].append(row)
        checks["settled_weekly_rows"]+=len(settled)
    for market,groups in report["markets"].items():
        for model,methods in groups["models"].items():
            for method,expected in methods.items():
                actual=computed[model,method,market]
                need(len(actual)==expected["n"],"aggregate_n")
                for field in ("brier","bias","crps","mean","actual"):
                    vals=[r[field] for r in actual if r.get(field) is not None]
                    if vals:need(abs(float(np.mean(vals))-expected[field])<1e-10,"aggregate_"+field)
                checks["independent_market_method_aggregates"]+=1
    result={"schema":"v25-opportunity-repair-independent-frozen-audit-v1",
       "passed":True,"source_report_file_sha256":sha(folder/"FINAL_REPAIR_REPORT.json"),
       "source_report_receipt_sha256":report["receipt_sha256"],"checks":dict(checks),
       "historical_source_capture_certified":False,"production_promotion_authorized":False,
       "method":"separate_no_fit_frozen_sample_and_exact_team_contract_rescore"}
    result["sha256"]=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--folder",type=Path,required=True);p.add_argument("--audit-export",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    result=run(a.folder,a.audit_export)
    with a.output.open("x") as f:json.dump(result,f,indent=2)
    print(json.dumps(result,sort_keys=True))

if __name__=="__main__":main()
