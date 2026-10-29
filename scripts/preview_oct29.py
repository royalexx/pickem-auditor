#!/usr/bin/env python3
"""Read-only one-day shadow preview. Never promote historical joint research fits."""
import argparse
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo("America/Toronto")
KEYS=("game_date","sport","player_id","stat","side","reference_line","forecast_at","run_id")

def read(path):
    if not Path(path).is_file():
        return []
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]

def identity(row):
    return tuple(str(row.get(k)) for k in KEYS)

def numeric(x):
    return round(float(x),6) if isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(float(x)) else None

def safe_status(obj):
    return obj.get("status","missing") if isinstance(obj,dict) else "missing"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True)
    p.add_argument("--snapshots",default="data/prop_snapshots.jsonl")
    p.add_argument("--out",default="reports/preview_oct29.json")
    args=p.parse_args()
    originals=[]
    for row in read(args.snapshots):
        if row.get("game_date")!=args.date or row.get("run_type")!="shadow":
            continue
        try:
            at=datetime.fromisoformat(row["forecast_at"].replace("Z","+00:00"))
            start=datetime.fromisoformat(row["event_start"].replace("Z","+00:00"))
            if (not at.tzinfo or not start.tzinfo or not at<start
                  or at.astimezone(TZ).date().isoformat()!=args.date):
                continue
        except (ValueError,TypeError,KeyError,AttributeError):
            continue
        originals.append(row)
    # Distinct (run, player, line, side) identities. Never silently replace
    # a prior forecast; newest verified pregame snapshot is for preview only.
    chosen={}
    for row in originals:
        key=identity(row)
        chosen[key]=row
    def sidecar(path):
        out={}
        for r in read(path):
            out[identity(r)]=r
        return out
    a=sidecar("data/bayesian_shadow/"+args.date+".jsonl")
    b=sidecar("data/bayesian_b_shadow/"+args.date+".jsonl")
    mc=sidecar("data/posterior_mc/"+args.date+".jsonl")
    rows=[]
    counts=Counter()
    for key,r in chosen.items():
        a0=r.get("engine_a") or {}; b0=r.get("engine_b") or {}
        b1=b.get(key) or {}; a1=a.get(key) or {}; sim=mc.get(key) or {}
        sim_a=(sim.get("engines") or {}).get("A") or {}
        sim_b=(sim.get("engines") or {}).get("B") or {}
        mix=r.get("blend") or {}
        rec={
            "date":args.date,"sport":r.get("sport"),"matchup":r.get("matchup"),
            "event_start":r.get("event_start"),"player":r.get("player"),
            "player_id":r.get("player_id"),"stat":r.get("stat"),
            "side":r.get("side"),"line":r.get("reference_line"),
            "baseline_rank":r.get("final_rank"),"reason":r.get("reason"),
            "forecast_at":r.get("forecast_at"),"run_id":r.get("run_id"),
            "market_probability":numeric(r.get("q_market")),
            "simple_engine_a":numeric(a0.get("q_win_robust")),
            "simple_engine_a_reliable":a0.get("reliable") is True,
            "simple_engine_b":numeric(b0.get("q_win_b",b0.get("q_win"))),
            "simple_engine_b_reliable":b0.get("reliable") is True and not b0.get("abstain"),
            "simple_final":numeric(mix.get("q_win",r.get("q_model"))),
            "simple_blend_validated":mix.get("validated") is True,
            "bayesian_a":numeric(a1.get("q_win")) if safe_status(a1)=="forecast" else None,
            "bayesian_b":numeric(b1.get("q_win")) if safe_status(b1)=="forecast" else None,
            "bayesian_a_status":safe_status(a1),"bayesian_b_status":safe_status(b1),
            "bayesian_a_unavailable_reason":a1.get("reason"),
            "bayesian_b_unavailable_reason":b1.get("reason"),
            "mc_a":numeric(sim_a.get("q_win")) if safe_status(sim_a)=="forecast" else None,
            "mc_b":numeric(sim_b.get("q_win")) if safe_status(sim_b)=="forecast" else None,
            "mc_a_draws":sim_a.get("draws") if safe_status(sim_a)=="forecast" else None,
            "mc_b_draws":sim_b.get("draws") if safe_status(sim_b)=="forecast" else None,
            "mc_a_status":safe_status(sim_a),"mc_b_status":safe_status(sim_b),
            "mc_a_unavailable_reason":sim_a.get("reason"),
            "mc_b_unavailable_reason":sim_b.get("reason"),
            "bayesian_joint_hierarchical":"not_connected_to_live_slate",
        }
        if rec["simple_final"] is not None and rec["market_probability"] is not None:
            rec["simple_market_edge"]=round(rec["simple_final"]-rec["market_probability"],6)
        else:
            rec["simple_market_edge"]=None
        rows.append(rec)
        counts[r.get("sport") or "UNKNOWN"]+=1
    rows.sort(key=lambda r:(r["simple_market_edge"] if r["simple_market_edge"] is not None else -10),reverse=True)
    all_forecasts={"schema":"research_only_one_day_shadow_preview_v1",
      "date":args.date,"source":"timestamped_original_pregame_rows_and_sidecars",
      "research_only":True,"rank_authority":False,"new_joint_bayesian_deployed":False,
      "explanation":"Prior historical joint NUTS posterior is a validation artifact, not a prospective October 2026 player prop scorer. Bayesian A/B are distinct older shadow methods.",
      "forecast_rows":len(rows),"sport_counts":dict(counts),
      "bayesian_a_available":sum(r["bayesian_a"] is not None for r in rows),
      "bayesian_b_available":sum(r["bayesian_b"] is not None for r in rows),
      "mc_a_available":sum(r["mc_a"] is not None for r in rows),
      "mc_b_available":sum(r["mc_b"] is not None for r in rows),
      "both_simple_engines_reliable":sum(r["simple_engine_a_reliable"] and r["simple_engine_b_reliable"] for r in rows),
      "mc_draws_min":1024,"mc_draws_max":8192,"rows":rows}
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(all_forecasts,indent=2,sort_keys=True,allow_nan=False)+"\n")
    print("PREVIEW_SUMMARY="+json.dumps({k:v for k,v in all_forecasts.items() if k!="rows"},sort_keys=True))
    for sport in ("NHL","NBA","NFL"):
        subset=[r for r in rows if r["sport"]==sport]
        print("SPORT_PREVIEW "+sport+" rows="+str(len(subset)))
        for r in subset[:20]:
            print("PREVIEW_PICK "+json.dumps({k:r[k] for k in
              ("sport","player","stat","side","line","market_probability","simple_engine_a","simple_engine_b","simple_final","simple_market_edge","baseline_rank","bayesian_a","bayesian_b","mc_a","mc_b","mc_a_draws","mc_b_draws")},sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
