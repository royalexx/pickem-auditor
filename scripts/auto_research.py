#!/usr/bin/env python3
"""Attempt structured ESPN pregame research, without inventing lineup/scouting facts.

This stage improves packet completeness but does NOT grant final Tier approval.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import tempfile
import os

SCRIPT=Path(__file__).resolve().parent
if str(SCRIPT) not in sys.path:sys.path.insert(0,str(SCRIPT))
import fetch_slate as fs
from research_resolver import resolve

def refresh(*,slate:Path,quotes:Path,packet_path:Path,out:Path,now=None,fetch=None):
    now=now or datetime.now(timezone.utc);fetch=fetch or fs.fetch_json
    if not slate.is_file() or not quotes.is_file() or not packet_path.is_file():
        raise ValueError("RESEARCH_INPUT_MISSING")
    packet=json.loads(packet_path.read_text(encoding="utf-8"))
    date=now.astimezone(__import__("zoneinfo").ZoneInfo("America/Toronto")).date().isoformat()
    if packet.get("date") != date:
        raise ValueError("RESEARCH_PACKET_DATE_MISMATCH")
    rows=fs.read_jsonl(slate);priced=fs.read_jsonl(quotes)
    prep=fs.prepare_pipeline(rows,priced,now=now.isoformat())
    candidate_ids=sorted({item.get("id") for item in prep if item.get("id")})
    if not candidate_ids:
        raise ValueError("RESEARCH_NO_PRICED_CANDIDATES")
    merged,report=resolve(packet,candidate_ids,fetch,now=now)
    # Never rewrite the packet when a resolver fails or loses identity.
    if merged.get("date") != packet["date"]:
        raise ValueError("RESEARCH_IDENTITY_MISMATCH")
    packet_path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",encoding="utf-8",dir=packet_path.parent,
                                     prefix=".researched-",delete=False) as tmp:
        json.dump(merged,tmp,ensure_ascii=False,indent=2)
        tmp.write("\n");tmp_path=tmp.name
    os.replace(tmp_path,packet_path)
    summary={
        "date":date,"candidate_ids":len(candidate_ids),
        "source_attempts":len(report.get("attempts") or []),
        "verified_pregame_games":len(report.get("verified_pregame_games") or []),
        "resolved_statuses":len(report.get("resolved_statuses") or []),
        "resolved_venues":len(report.get("resolved_venues") or []),
        "resolved_goalies":len(report.get("resolved_goalies") or []),
        "started_games_excluded":len(report.get("started_games") or []),
        "evidence_complete":False,
        "note":"Structured evidence only; missing scouting and adversarial validation retain existing ranking vetoes.",
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2))
    return summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",default=None)
    p.add_argument("--slate",default="data/slate_fetch.jsonl")
    p.add_argument("--quotes",default="data/odds_quotes.jsonl")
    p.add_argument("--out",default="reports/structured_research.json")
    args=p.parse_args()
    now=datetime.now(timezone.utc)
    date=args.date or now.astimezone(__import__("zoneinfo").ZoneInfo("America/Toronto")).date().isoformat()
    try:
        refresh(slate=Path(args.slate),quotes=Path(args.quotes),
                packet_path=Path(args.slate).parent/f"research_{date}.json",
                out=Path(args.out),now=now)
    except (OSError,ValueError,TypeError) as exc:
        print("STRUCTURED_RESEARCH_BLOCKED:",type(exc).__name__,str(exc)[:180],file=sys.stderr)
        return 2
    return 0
if __name__=="__main__":sys.exit(main())
