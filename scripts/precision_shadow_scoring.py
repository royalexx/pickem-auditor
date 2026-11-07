#!/usr/bin/env python3
"""Prospective scoring for archived full-NUTS NHL saves and NFL targets shadows.

Uses only an immutable *prior* afternoon bundle and separately verified
completed-game observations. No retrospective prediction or re-ranking.
"""
from __future__ import annotations
import argparse
from collections import defaultdict,Counter
from datetime import date,datetime,timezone,timedelta
import json
import math
import os
from pathlib import Path
import live_pool_exchange as pool

VERSION="precision_converged_shadow_validation_v1"

def instant(v):
 try:
  t=datetime.fromisoformat(str(v).replace("Z","+00:00"))
  if t.tzinfo is None:raise ValueError
  return t.astimezone(timezone.utc)
 except (ValueError,TypeError) as exc:raise ValueError("invalid_immutable_forecast_timestamp") from exc

def key(row):
 return (str(row.get("game_date") or ""),str(row.get("sport") or ""),
         str(row.get("player_id") or ""),str(row.get("stat") or ""),
         str(row.get("side") or ""),str(row.get("reference_line") or ""),
         str(row.get("run_id") or ""),str(row.get("forecast_at") or ""))

def graded(p,y):
 q=float(p.get("q_win"));push=float(p.get("q_push",0))
 if not math.isfinite(q) or not math.isfinite(push) or not (0<=q<=1 and 0<=push<1 and q+push<=1+1e-8):
  raise ValueError("invalid_original_shadow_probability")
 probability=min(1-1e-12,max(1e-12,q/(1-push)))
 return {"q_win_conditional_nonpush":probability,
         "outcome":"win" if y else "loss",
         "brier":(probability-int(y))**2,
         "log_loss":-math.log(probability if y else 1-probability)}

def audit(day,afternoon,settled,population):
 if afternoon.get("phase")!="afternoon" or afternoon.get("game_date")!=day:
  raise ValueError("canonical_afternoon_bundle_required")
 frozen={}
 for row in afternoon.get("forecasts",[]):
  k=key(row)
  if k in frozen:raise ValueError("duplicate_original_frozen_forecast")
  frozen[k]=row
 finalized={}
 for row in settled:
  k=key(row)
  if k in finalized:raise ValueError("duplicate_settlement")
  finalized[k]=row
 obs={}
 for row in population:
  if row.get("sport")!="NFL" or row.get("stat")!="targets" or row.get("game_date")!=day:continue
  k=(str(row.get("game_id") or ""),str(row.get("player_id") or ""))
  if k in obs and obs[k]!=row:raise ValueError("conflicting_official_nfl_target_count")
  obs[k]=row
 all_scored=[];pending=Counter();count=Counter()
 for label in ("nhl_saves_nuts","nfl_targets_nuts"):
  records=(afternoon.get("shadow") or {}).get(label,[])
  seen=set()
  for row in records:
   if row.get("status")!="forecast":
    pending[(label,str(row.get("reason") or "unavailable"))]+=1
    continue
   if row.get("game_date")!=day or row.get("ranking_allowed") is not False or row.get("shadow_only") is not True:
    raise ValueError("invalid_archived_research_prediction")
   if label=="nhl_saves_nuts":
    source_at=instant(row.get("forecast_at"))
    generated_at=instant(row.get("generated_at"))
    start=instant(row.get("event_start"))
    if not source_at<start or not generated_at<start or date.fromisoformat(str(row["trained_through"]))>=date.fromisoformat(day):
     pending[(label,"not_prospective_or_cutoff_overlaps")]+=1;continue
    k=key(row)
    if k in seen:raise ValueError("duplicate_immutable_nhl_nuts_forecast")
    seen.add(k)
    original=frozen.get(k);result=finalized.get(k)
    if not original or not result or original.get("actual_stat") is not None:
     pending[(label,"missing_frozen_source_or_settlement")]+=1;continue
    if result.get("outcome") not in ("win","loss") or result.get("actual_stat") is None:
     pending[(label,"unsettled_or_push")]+=1;continue
    # Match the immutable original's exact side, player, line and timestamp.
    score=graded(row,result["outcome"]=="win")
    scored={"game_date":day,"model":label,"sport":"NHL","market_type":"market",
            "stat":row["stat"],"player_id":row["player_id"],
            "game_id":result.get("event_id"),
            "line":row["reference_line"],"side":row["side"],
            "original_forecast_at":row["forecast_at"],
            "model_forecast_at":row["generated_at"],
            "actual_stat":result["actual_stat"],**score}
   else:
    if row.get("stat")!="targets" or row.get("market")!="targets":
     raise ValueError("nfl_targets_forecast_stat_contract_changed")
    if row.get("line_origin") not in ("market","research_threshold"):
     raise ValueError("invalid_targets_line_provenance")
    start=instant(row.get("event_start"))
    generated_at=instant(row.get("generated_at") or row.get("forecast_at"))
    source_at=instant(row.get("parent_forecast_at"))
    cutoff=instant(row.get("training_cutoff_exclusive"))
    if not cutoff<source_at<=generated_at<start:
     pending[(label,"not_prospective_or_cutoff_overlaps")]+=1;continue
    k=(str(row.get("game_id") or ""),str(row.get("player_id") or ""))
    fingerprint=(k,row.get("line_origin"),row.get("side"),row.get("reference_line"),row.get("parent_forecast_at"))
    if fingerprint in seen:raise ValueError("duplicate_immutable_nfl_nuts_forecast")
    seen.add(fingerprint)
    if row["line_origin"]=="market":
     # Synthetic receiver projections are never allowed through this gate.
     original_key=(str(row["game_date"]),"NFL",str(row["player_id"]),"targets",
                   str(row["side"]),str(row["reference_line"]),
                   str(row["run_id"]),str(row["parent_forecast_at"]))
     if original_key not in frozen:
      pending[(label,"unverified_market_target_line")]+=1;continue
    actual=obs.get(k)
    if not actual:
     pending[(label,"official_targets_not_verified")]+=1;continue
    if row.get("team")!=actual.get("team") or row.get("opponent")!=actual.get("opponent"):
     pending[(label,"team_or_opponent_mismatch")]+=1;continue
    value=actual.get("value")
    if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or value<0:
     raise ValueError("invalid_official_nfl_targets_value")
    if value==row["reference_line"]:
     pending[(label,"push")]+=1;continue
    win=(value>row["reference_line"]) == (row["side"] in ("over","higher"))
    score=graded(row,win)
    scored={"game_date":day,"model":label,"sport":"NFL",
            "market_type":row["line_origin"],"stat":"targets",
            "player_id":row["player_id"],"game_id":row["game_id"],
            "line":row["reference_line"],"side":row["side"],
            "original_forecast_at":row["parent_forecast_at"],
            "model_forecast_at":row["forecast_at"],"actual_stat":value,**score}
   count[label]+=1;all_scored.append(scored)
 summaries={}
 for name in ("nhl_saves_nuts","nfl_targets_nuts"):
  for kind in ("market","research_threshold"):
   sub=[r for r in all_scored if r["model"]==name and r["market_type"]==kind]
   if not sub:continue
   n=len(sub)
   summaries[name+":"+kind]={"n":n,"wins":sum(r["outcome"]=="win" for r in sub),
     "brier":sum(r["brier"] for r in sub)/n,
     "log_loss":sum(r["log_loss"] for r in sub)/n,
     "distinct_player_games":len({(r["game_id"],r["player_id"]) for r in sub})}
 return {"schema":VERSION,"date":day,"summaries":summaries,
         "scored_rows":len(all_scored),"pending_reasons":{f"{k[0]}:{k[1]}":v for k,v in pending.items()},
         "predictions":all_scored,"ranking_allowed":False,
         "automatic_promotion":False,"updated_past_forecasts":False}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--day",required=True);p.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
 p.add_argument("--out",type=Path,required=True)
 p.add_argument("--predictions-out",type=Path,required=True)
 a=p.parse_args();date.fromisoformat(a.day)
 token=os.environ.get("GITHUB_TOKEN")
 if not token:raise ValueError("GitHub token required")
 before=(date.fromisoformat(a.day)+timedelta(days=1)).isoformat()
 docs=[doc for doc,_ in pool.iter_remote_docs(token=token,before=before,after=a.day,phase="afternoon")]
 selection=pool.canonical_afternoon_docs(docs)
 if a.day not in selection:raise ValueError("original_afternoon_archive_missing")
 data=a.root/"data/live_pool_staging/populations"/(a.day+".jsonl")
 if not data.is_file():raise ValueError("official_completed_population_missing")
 result=audit(a.day,selection[a.day],
      pool.jsonl(a.root/"data/morning_prior_predictions.jsonl"),pool.jsonl(data))
 a.out.parent.mkdir(parents=True,exist_ok=True);a.predictions_out.parent.mkdir(parents=True,exist_ok=True)
 a.out.write_text(json.dumps({k:v for k,v in result.items() if k!="predictions"},indent=2,sort_keys=True)+"\n")
 pool.dump_jsonl(a.predictions_out,result["predictions"])
 print("CONVERGED_SHADOW_VALIDATION "+json.dumps({k:v for k,v in result.items() if k!="predictions"},sort_keys=True),flush=True)
if __name__=="__main__":main()
