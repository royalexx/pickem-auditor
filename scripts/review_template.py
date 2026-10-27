#!/usr/bin/env python3
"""Create non-attested source-review templates for the current priority queue.

A template is NEVER a verified report. Source links are investigation prompts.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from pick_verification import forecast_digest, select, write_atomic


def make(rows, queue, date, *, now=None, limit=10):
    now=now or datetime.now(timezone.utc)
    selection, excluded, run_id, batch_count = select(rows, queue, date, now,
                                                        "initial", limit)
    entries=[]
    for item, row in selection:
        entries.append({
            "candidate_id":item["candidate_id"],
            "forecast_sha256":forecast_digest(row),
            "sport":row["sport"],"player":row["player"],
            "player_id":row.get("player_id"),"team":row["team"],
            "game":item["game"],"stat":row["stat"],"side":row["side"],
            "line":row["reference_line"],"event_start":row["event_start"],
            "decision":"pending", "reviewer":None, "source_read":False,
            "reviewed_at":None, "supporting":[], "opposing":[],
            "source_guides":item.get("source_guides") or [],
            "required_packet_paths":item.get("source_tasks") or [],
            "missing_evidence":item.get("missing_evidence") or [],
        })
    return {
        "date":date,
        "schema":"review-input-template-v1",
        "source_forecast_run_id":run_id,
        "generated_at":now.isoformat(),
        "publication_eligible":False,
        "completion_rule":"Read every source; record direct quotations and opposing evidence. "
                          "Remove investigative fields from each attestation; "
                          "supply fresh source facts only. Never backdate.",
        "game_day_reports":None,
        "scouting_reports":None,
        "attestations":entries,
        "excluded":dict(excluded),
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date",required=True)
    parser.add_argument("--snapshots",default="data/prop_snapshots.jsonl")
    parser.add_argument("--queue",default="reports/research_triage.json")
    parser.add_argument("--out",default="reports/review_template.json")
    parser.add_argument("--limit",type=int,default=10)
    args=parser.parse_args()
    rows=[json.loads(s) for s in Path(args.snapshots).read_text().splitlines() if s.strip()]
    q=json.loads(Path(args.queue).read_text())
    result=make(rows,q,args.date,limit=args.limit)
    write_atomic(args.out,result)
    print(json.dumps({"date":args.date,"pending_subjects":len(result["attestations"]),
                      "publication_eligible":False}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
