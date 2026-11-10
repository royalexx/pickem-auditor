"""Exact historical research settlement. Never assume missing means zero."""
from __future__ import annotations
import math

def index_outcomes(rows):
    indexed={}
    for r in rows:
        key=(r["game_id"],r["team"],r["player_id"],r["stat"])
        if key in indexed:
            raise ValueError("duplicate_exact_outcome_identity")
        v=r["value"]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):
            raise ValueError("invalid_official_outcome")
        indexed[key]=v
    return indexed

def settle(contract,indexed):
    key=(contract["game_id"],contract["team"],contract["player_id"],contract["market"])
    line=contract["research_line"]
    if isinstance(line,bool) or not isinstance(line,(float,int)) or not math.isfinite(line):
        raise ValueError("invalid_contract_line")
    if key not in indexed:
        return {"state":"UNMATCHED","actual":None,"actual_over":None}
    v=indexed[key]
    if v==line:
        return {"state":"PUSH","actual":v,"actual_over":None}
    return {"state":"SETTLED","actual":v,"actual_over":int(v>line)}
