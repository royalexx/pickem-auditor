"""Fail-closed point-in-time source certification gate for future NFL game slates.

This is NOT a way to retro-certify synthetic 2016–2025 research data.
Only original captured pregame sources can satisfy the contract.

No source without accessible timestamps or authenticated receipt can be
certified; values derived from target game/postgame records are prohibited.
All downstream prediction/selection stages must separately check eligibility.
"""
from __future__ import annotations
import datetime,hashlib,json
from collections.abc import Mapping,Sequence
class AsOfViolation(ValueError):pass
def fail(code):raise AsOfViolation(code)
def utc(value,field):
 if not isinstance(value,str):fail("MISSING_UTC_"+field)
 try:ts=datetime.datetime.fromisoformat(value.replace("Z","+00:00"))
 except ValueError:fail("INVALID_UTC_"+field)
 if ts.tzinfo is None or ts.utcoffset() is None:
  fail("NAIVE_TIMESTAMP_"+field)
 return ts.astimezone(datetime.timezone.utc)
def require(value,code):
 if not value:fail(code)
def receipt(r,cutoff,category):
 require(isinstance(r,Mapping),"RECEIPT_NOT_OBJECT_"+category)
 require(isinstance(r.get("source_id"),str) and r["source_id"],"MISSING_SOURCE_ID_"+category)
 require(isinstance(r.get("sha256"),str) and len(r["sha256"])==64,
        "MISSING_CONTENT_SHA_"+category)
 require(bool(r.get("original_capture_verified")),"ORIGINAL_CAPTURE_UNVERIFIED_"+category)
 available=utc(r.get("first_available_at"),category+"_first_available_at")
 ingested=utc(r.get("ingested_at"),category+"_ingested_at")
 require(available<=cutoff,"FUTURE_SOURCE_AVAILABLE_"+category)
 require(ingested<=cutoff,"SOURCE_NOT_INGESTED_PREWEEK_"+category)
 if r.get("published_at") is not None:
  require(utc(r["published_at"],category+"_published_at")<=cutoff,
          "SOURCE_PUBLISHED_AFTER_FREEZE_"+category)
 return available
def validate_prospective_packet(packet):
 """Return immutable metadata about an authentic pregame forecast; raise
 on ONE missing source. No optimistic fallback and no invented information.
 """
 require(isinstance(packet,Mapping),"PACKET_NOT_OBJECT")
 event_start=utc(packet.get("event_start_at"),"event_start_at")
 freeze=utc(packet.get("input_freeze_at"),"input_freeze_at")
 forecast=utc(packet.get("forecast_at"),"forecast_at")
 cutoff=utc(packet.get("model_training_cutoff_at"),"model_training_cutoff_at")
 require(cutoff<=freeze<=forecast<event_start,"INVALID_TEMPORAL_ORDER")
 require(packet.get("research_only") is False,"CANNOT_CERTIFY_RESEARCH_ARCHIVE")
 require(packet.get("certification_claim")=="prospective","NOT_PROSPECTIVE_CAPTURE")
 require(isinstance(packet.get("event_id"),str) and packet["event_id"],"MISSING_EVENT_ID")
 sources=packet.get("source_receipts")
 require(isinstance(sources,Mapping),"MISSING_RECEIPT_LEDGER")
 for family in ("schedule","game_history","player_history","play_by_play",
                "starter_selector","injury_availability","model_artifact"):
  require(family in sources,"MISSING_SOURCE_FAMILY_"+family)
  items=sources[family]
  require(isinstance(items,Sequence) and not isinstance(items,(str,bytes)) and len(items)>0,
          "MISSING_SOURCE_"+family)
  for rr in items:receipt(rr,freeze,family)
 qs=packet.get("quote")
 require(isinstance(qs,Mapping),"QUOTE_MISSING")
 receipt(qs.get("receipt"),freeze,"market_quote")
 require(utc(qs.get("quote_timestamp"),"quote_timestamp")<=forecast,
         "QUOTE_AFTER_FORECAST")
 require(qs.get("event_id")==packet["event_id"],"QUOTE_EVENT_COLLISION")
 require(bool(qs.get("quote_id")) and bool(qs.get("market")),"QUOTE_TERMS_MISSING")
 starters=packet.get("starters")
 require(isinstance(starters,Mapping) and len(starters)==2,"STARTER_VERIFICATION_MISSING")
 for team,player in starters.items():
  require(isinstance(player,Mapping),"STARTER_NOT_OBJECT")
  require(player.get("status")=="confirmed_starter","STARTER_UNCERTAIN")
  require(player.get("team")==team and bool(player.get("player_id")),
          "STARTER_IDENTITY_MISMATCH")
  ref=player.get("receipt")
  receipt(ref,freeze,"confirmed_starter")
 datasets=packet.get("training_records")
 require(isinstance(datasets,Mapping),"TRAINING_LINEAGE_MISSING")
 for family in ("game_history","player_history","play_by_play"):
  items=datasets.get(family)
  require(isinstance(items,list),"TRAINING_RECORDS_MISSING_"+family)
  for rec in items:
   require(isinstance(rec,Mapping),"BAD_HISTORY_ROW_"+family)
   require(rec.get("event_id")!=packet["event_id"],"TARGET_GAME_IN_TRAINING_"+family)
   require(utc(rec.get("game_end_at"),"historical_game_end")<=cutoff,
           "HISTORICAL_OUTCOME_AFTER_TRAINING_CUTOFF_"+family)
   require(utc(rec.get("source_available_at"),"historical_source_available")<=cutoff,
           "HISTORICAL_SOURCE_NOT_YET_AVAILABLE_"+family)
   require(bool(rec.get("source_receipt_sha256")),"TRAINING_SOURCE_SHA_MISSING_"+family)
 input_obj=packet.get("pregame_features")
 require(isinstance(input_obj,Mapping),"PREGAME_FEATURES_MISSING")
 forbidden={"actual","observed_over","final_score","final_team_pass_attempts",
    "final_snap_count","final_routes","postgame_injury","game_result",
    "settlement","outcome_label","realized_player_stat"}
 def check(v):
  if isinstance(v,Mapping):
   for k,x in v.items():
    require(k not in forbidden,"POSTGAME_FIELD_IN_PREGAME_FEATURES_"+k)
    check(x)
  elif isinstance(v,(list,tuple)):
   for item in v:check(item)
 check(input_obj)
 return {"status":"SOURCE_CERTIFIED_PRE_FUTURE_FORECAST",
   "event_id":packet["event_id"],"training_cutoff_at":cutoff.isoformat(),
   "freeze_at":freeze.isoformat(),"forecast_at":forecast.isoformat(),
   "event_start_at":event_start.isoformat(),
   "distinct_source_families":len(sources),
   "is_retro_archive":False,"no_current_game_outcomes_in_model_features":True}
