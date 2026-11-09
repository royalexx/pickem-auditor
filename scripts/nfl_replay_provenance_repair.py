"""Rebuild trustworthy research line provenance from immutable weekly packet and lock.

Never silently relabel a historical artifact. Write a distinct corrected
ledger with checked line equality, packet SHA-256, and prior-only methodology.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def repair(root, out):
    root=Path(root);out=Path(out)
    records={}
    seen=0
    for w in range(1,19):
        week=root/f"2024_week_{w:02d}"
        packet_path=week/"pregame_packet.json"
        frozen_path=week/"frozen_all_markets.json"
        packet=json.loads(packet_path.read_text())
        frozen=json.loads(frozen_path.read_text())
        lock=json.loads((week/"lock.json").read_text())
        if sha256(packet_path)!=lock["packet_sha256"]:
            raise ValueError("packet_hash_invalid")
        if sha256(frozen_path)!=lock["forecast_sha256"]:
            raise ValueError("frozen_forecast_hash_invalid")
        if packet["target_week_results_in_packet"] is not False:
            raise ValueError("target_outcome_in_pregame_packet")
        local={}
        for m,meta in packet["market_packets"].items():
            for c in meta["candidates"]:
                k=(w,c["game_id"],c["player_id"],m)
                if k in local:raise ValueError("duplicate_candidate_in_packet")
                local[k]=c
        for m,meta in frozen["market_results"].items():
            for f in meta["predictions"]:
                k=(w,f["game_id"],f["player_id"],m)
                if k in records:raise ValueError("duplicate_frozen_forecast")
                candidate=local.get(k)
                if candidate is None:raise ValueError("forecast_not_in_pregame_candidate_packet")
                if abs(float(f["research_line"])-float(candidate["line"]))>1e-12:
                    raise ValueError("forecast_line_not_equal_locked_packet")
                if candidate["line_source"]!=f["research_line_source"]:
                    raise ValueError("line_source_not_equal_locked_packet")
                evidence=candidate.get("line_evidence",{})
                if evidence.get("synthetic_not_bookmaker") is not True:
                    raise ValueError("attempted_false_bookmaker_provenance")
                records[k]=(f["research_line_source"],
                    evidence.get("history_games"),evidence.get("w5"),evidence.get("w10"),
                    evidence.get("w_role"),evidence.get("role_reference"))
                seen+=1
    original=root/"PERFORMANCE_REPORT/every_2024_prop_frozen_prediction_and_settlement.csv"
    with original.open(newline="") as h:rows=list(csv.DictReader(h))
    if len(rows)!=seen:raise ValueError("missing_prediction_in_graded_ledger")
    new=[]
    for r in rows:
        k=(int(r["week"]),r["game_id"],r["player_id"],r["market"])
        fields=records.pop(k,None)
        if fields is None:raise ValueError("ledger_prediction_not_in_frozen_lock")
        method,hist,w5,w10,wr,role=fields
        nr={**r,"line_type":method,
            "line_provenance_source":"weekly_packet_and_frozen_hash_verified",
            "synthetic_not_bookmaker":True,"line_history_games":hist,
            "line_weight_last5":w5,"line_weight_last10":w10,
            "line_weight_role":wr,"role_reference_line":role}
        new.append(nr)
    if records:raise ValueError("frozen_predictions_not_in_ledger")
    if out.exists():raise ValueError("refusing_overwrite_of_existing_repaired_ledger")
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(new[0].keys()))
        writer.writeheader()
        writer.writerows(new)
    return {"repaired":len(new),"output":str(out),"sha256":sha256(out),
        "line_sources":sorted({x["line_type"] for x in new}),
        "all_nonbookmaker":True}
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    print(json.dumps(repair(a.root,a.out),sort_keys=True))
