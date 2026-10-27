#!/usr/bin/env python3
"""Audit already-persisted afternoon forecasts. No API keys or API calls."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

def report(path:Path,game_date:str)->dict:
    data=[json.loads(s) for s in path.read_text(encoding="utf-8").splitlines() if s.strip()]
    rows=[r for r in data if str(r.get("game_date") or "")[:10]==game_date]
    ranks=Counter(str(r.get("final_rank") or "MISSING") for r in rows)
    sports=Counter(str(r.get("sport") or "UNKNOWN") for r in rows)
    result={
        "game_date":game_date,
        "audited_at_utc":datetime.now(timezone.utc).isoformat(),
        "total_history_rows":len(data),
        "date_forecast_rows":len(rows),
        "sports":dict(sports),
        "rank_counts":dict(ranks),
        "both_engines_returned":sum(bool(r.get("engine_a")) and bool(r.get("engine_b")) for r in rows),
        "model_probability_present":sum(isinstance(r.get("q_model"),(int,float)) for r in rows),
        "market_probability_present":sum(isinstance(r.get("q_market"),(int,float)) for r in rows),
        "grade_probability_present":sum(isinstance(r.get("q_grade"),(int,float)) for r in rows),
        "unverified_research":sum(not bool(r.get("researched")) for r in rows),
        "shadow_records":sum(r.get("run_type")=="shadow" for r in rows),
        "duplicate_identity_count":len(rows)-len({(r.get("run_id"),r.get("sport"),r.get("player"),r.get("stat"),r.get("side"),r.get("reference_line")) for r in rows}),
        "source_only_not_approved":True,
        "status":"success" if rows else "no_new_forecasts"
    }
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--path",default="data/prop_snapshots.jsonl")
    p.add_argument("--date",required=True)
    p.add_argument("--out",default="reports/afternoon_audit.json")
    args=p.parse_args()
    result=report(Path(args.path),args.date)
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
    return 0 if result["status"]=="success" and not result["duplicate_identity_count"] else 2

if __name__=="__main__":
    sys.exit(main())
