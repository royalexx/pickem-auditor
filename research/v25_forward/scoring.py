"""Independent read-only settlement of additional prospective NFL dates.

Consumes ONLY genuine immutable event FIRST_CAPTURE pointers created before
kickoff. Outcome bytes are independently retrieved after ESPN STATUS_FINAL.
No model predictions are generated. Unknown player/category = unknown.
"""
from pathlib import Path
from collections import Counter, defaultdict
from v2.nba_ws1.store import instant
from research.v25_morning_validation.score import (
    h, fetch_final, nfl_box_values, nfl_stat_observation, make_once, ESPN_NFL,
    EXCLUDED_FOR_SCORE,
)
import json
import math

MAX_EVENTS=90
MAX_DAYS=45
SOURCE="reports/nfl_forward_original"


def _original_contracts(root):
    directories=sorted((Path(root)/SOURCE).glob("????-??-??/event_*"))
    if len(directories)>MAX_EVENTS:
        raise ValueError("FORWARD_EVENT_COUNT_EXCEEDED")
    audit=[]; original=[]
    for directory in directories:
        origin={"path":str(directory.relative_to(root))}
        try:
            first=json.loads((directory/"FIRST_CAPTURE.json").read_text())
            ledger=directory/first["snapshot"]
            if ledger.is_symlink() or not ledger.resolve().is_relative_to(directory.resolve()):
                raise ValueError("FORWARD_FIRST_CAPTURE_PATH_ESCAPE")
            b=ledger.read_bytes()
            if h(b)!=first["sha256"]:
                raise ValueError("FORWARD_ORIGINAL_HASH_CHANGED")
            doc=json.loads(b)
            if doc.get("schema")!="NFLForwardOriginalEvent/1" or doc.get("model_forecasts") is not None:
                raise ValueError("FORWARD_SOURCE_SCHEMA_OR_MIXED_MODEL")
            event=doc["event"]
            kickoff=instant(event["event_start_at"])
            freeze=kickoff-__import__("datetime").timedelta(minutes=30)
            if instant(first["completed_at"])>=freeze:
                raise ValueError("FORWARD_CAPTURE_AFTER_HARD_FREEZE")
            for receipt in doc.get("source_receipts",[])+doc.get("original_offer_receipts",[]):
                if instant(receipt["received_at"]) > instant(first["completed_at"]):
                    raise ValueError("FORWARD_SOURCE_RECEIPT_AFTER_COMPLETION")
            if not doc.get("source_receipts"):
                raise ValueError("FORWARD_ESPN_SOURCE_EVIDENCE_MISSING")
            for row in doc["contracts"]:
                if (row.get("event_id")!=event["event_id"] or not row.get("player_id")
                    or not row.get("original_quote_id") or not row.get("original_offer_source_sha256")
                    or row.get("stat") is None):
                    raise ValueError("FORWARD_ORIGINAL_CONTRACT_IDENTITY_UNCERTIFIED")
                if instant(row.get("original_offer_first_received_at"))>freeze:
                    raise ValueError("FORWARD_QUOTE_AFTER_CUTOFF")
                if not isinstance(row.get("line"),(int,float)) or not math.isfinite(row["line"]):
                    raise ValueError("FORWARD_NONNUMERIC_ORIGINAL_LINE")
                original.append({**row,"original_event_start_at":event["event_start_at"],
                                 "original_event_home":event["home"]["abbr"],
                                 "original_event_away":event["away"]["abbr"],
                                 "original_capture_hash":first["sha256"],
                                 "original_quote_source_certification":"source-possession pregame, publication truth unverified"})
            audit.append({**origin,"status":"ORIGINAL_HASH_AND_TIME_VERIFIED",
                          "contracts":len(doc["contracts"]),
                          "rejected":len(doc["rejected_quote_candidates"])})
        except Exception as exc:
            audit.append({**origin,"status":"ORIGINAL_BLOCKED",
                          "reason":type(exc).__name__+":"+str(exc)})
    return audit,original


def forward_outcomes(root,out,fetch=None):
    audit,original=_original_contracts(root)
    folder=Path(out)/"forward_nfl_sources"
    folder.mkdir(parents=True,exist_ok=True)
    games={}
    for row in original:
        eid=row["event_id"]
        if eid in games:continue
        games[eid]=fetch_final(ESPN_NFL+eid,eid,row["original_event_start_at"],folder,fetch=fetch)
    records=[]
    for row in original:
        event=games[row["event_id"]]
        base={"original_contract_id":row["contract_id"],
              "original_quote_id":row["original_quote_id"],
              "original_quote_source_sha256":row["original_offer_source_sha256"],
              "original_capture_sha256":row["original_capture_hash"],
              "event_id":row["event_id"],
              "event_start_at":row["original_event_start_at"],
              "player_id":str(row["player_id"]),"team_id":row["team"],
              "stat":row["stat"],"line":row["line"],"book":row["book"],
              "sport":"NFL","market_settlement_certified":False}
        if event["status"]!="FINAL":
            records.append({**base,"state":"PENDING_FINAL","reason":event["status"]})
            continue
        try:
            stats,teams=nfl_box_values(event["data"])
            expected={row["original_event_home"],row["original_event_away"]}
            if teams != expected:raise ValueError("FORWARD_ESPN_GAME_TEAM_MISMATCH")
            if row["stat"] in EXCLUDED_FOR_SCORE:
                records.append({**base,"state":"STAT_PARITY_NOT_CERTIFIED"})
                continue
            observed,status,team=nfl_stat_observation(stats,row["player_id"],row["stat"],row["team"])
            if observed is None or status!="OBSERVED":
                records.append({**base,"state":"UNKNOWN_PLAYER_STAT_NOT_ZERO","reason":status})
                continue
            records.append({**base,"state":"SCORED","actual":observed,
                            "outcome_source_sha256":event["source"]["raw_sha256"]})
        except Exception as exc:
            records.append({**base,"state":"SOURCE_OUTCOME_CONFLICT",
                            "reason":type(exc).__name__+":"+str(exc)})
    result={"schema":"NFLForwardOriginalSettlement/1",
            "discovered_events":len(audit),
            "original_verified_events":sum(x["status"]=="ORIGINAL_HASH_AND_TIME_VERIFIED" for x in audit),
            "original_blocked_events":[x for x in audit if x["status"]!="ORIGINAL_HASH_AND_TIME_VERIFIED"],
            "original_contracts":len(original),
            "outcome_states":dict(Counter(r["state"] for r in records)),
            "source_states":dict(Counter(x["status"] for x in games.values())),
            "no_new_model_predictions_generated":True,
            "source_publication_truth_certified":False,
            "product_specific_DNP_settlement_certified":False}
    with (Path(out)/"nfl_forward_contract_outcomes.jsonl").open("xb") as f:
        for r in records:f.write((json.dumps(r,sort_keys=True,allow_nan=False)+"\n").encode())
    make_once(Path(out)/"nfl_forward_settlement.json",result)
    return result
