"""Adversarial time travel/lineage tests. Synthetic fixtures never certify live data."""
from __future__ import annotations
import copy,datetime,sys,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research"))
from nfl_v5_4_prospective_source_gate_20261112 import validate_prospective_packet,AsOfViolation
SHA="f"*64
def rec(source,first="2026-11-12T12:00:00Z",ingested="2026-11-12T12:20:00Z"):
 return {"source_id":source,"sha256":SHA,"original_capture_verified":True,
    "first_available_at":first,"ingested_at":ingested,"published_at":first}
def valid():
 sources={k:[rec(k)] for k in ("schedule","game_history","player_history","play_by_play",
          "starter_selector","injury_availability","model_artifact")}
 return {"event_id":"event_2026_11_12_test",
  "event_start_at":"2026-11-12T18:00:00Z",
  "input_freeze_at":"2026-11-12T14:00:00Z",
  "forecast_at":"2026-11-12T14:10:00Z",
  "model_training_cutoff_at":"2026-11-12T13:55:00Z",
  "research_only":False,"certification_claim":"prospective",
  "source_receipts":sources,
  "quote":{"quote_id":"original-quote-test","market":"targets",
     "event_id":"event_2026_11_12_test","quote_timestamp":"2026-11-12T13:55:00Z",
     "receipt":rec("quote")},
  "starters":{"A":{"team":"A","player_id":"QB1","status":"confirmed_starter","receipt":rec("qbA")},
             "B":{"team":"B","player_id":"QB2","status":"confirmed_starter","receipt":rec("qbB")}},
  "training_records":{k:[{"event_id":"historical_completed",
     "game_end_at":"2026-11-11T21:00:00Z",
     "source_available_at":"2026-11-12T10:00:00Z",
     "source_receipt_sha256":SHA}] for k in ("game_history","player_history","play_by_play")},
  "pregame_features":{"home":"A","away":"B","weather":{"roof":"closed"}}}
class TestSourceGate(unittest.TestCase):
 def test_control_fixture_valid_structure(self):
  self.assertEqual(validate_prospective_packet(valid())["status"],
       "SOURCE_CERTIFIED_PRE_FUTURE_FORECAST")
 def deny(self,mutator):
  p=valid();mutator(p)
  with self.assertRaises(AsOfViolation):validate_prospective_packet(p)
 def test_future_source_rejected(self):
  self.deny(lambda p:p["source_receipts"]["player_history"][0].update(
      {"first_available_at":"2026-11-12T15:00:00Z"}))
 def test_delayed_ingestion_rejected(self):
  self.deny(lambda p:p["source_receipts"]["game_history"][0].update(
      {"ingested_at":"2026-11-12T14:40:00Z"}))
 def test_game_after_training_cutoff_rejected(self):
  self.deny(lambda p:p["training_records"]["game_history"][0].update(
      {"game_end_at":"2026-11-12T14:20:00Z"}))
 def test_future_record_source_rejected(self):
  self.deny(lambda p:p["training_records"]["play_by_play"][0].update(
      {"source_available_at":"2026-11-12T14:20:00Z"}))
 def test_target_game_training_leak_rejected(self):
  self.deny(lambda p:p["training_records"]["player_history"][0].update(
      {"event_id":p["event_id"]}))
 def test_future_quote_rejected(self):
  self.deny(lambda p:p["quote"].update(
      {"quote_timestamp":"2026-11-12T14:11:00Z"}))
 def test_quote_identity_mismatch_rejected(self):
  self.deny(lambda p:p["quote"].update({"event_id":"another_event"}))
 def test_naive_timestamp_rejected(self):
  self.deny(lambda p:p.update({"forecast_at":"2026-11-12T14:00:00"}))
 def test_unknown_starting_qb_rejected(self):
  self.deny(lambda p:p["starters"]["A"].update({"status":"probable"}))
 def test_missing_starter_receipt_rejected(self):
  self.deny(lambda p:p["starters"]["A"].pop("receipt"))
 def test_missing_original_capture_rejected(self):
  self.deny(lambda p:p["source_receipts"]["play_by_play"][0].update(
      {"original_capture_verified":False}))
 def test_postgame_label_field_rejected(self):
  self.deny(lambda p:p["pregame_features"].update(
      {"final_score":{"A":35,"B":7}}))
 def test_nested_postgame_field_rejected(self):
  self.deny(lambda p:p["pregame_features"].update(
      {"team":{"outcome_label":1}}))
 def test_no_retroarchive_promotion(self):
  self.deny(lambda p:p.update({"research_only":True}))
 def test_wrong_freeze_order(self):
  self.deny(lambda p:p.update(
      {"input_freeze_at":"2026-11-12T14:11:00Z"}))
 def test_missing_family(self):
  self.deny(lambda p:p["source_receipts"].pop("injury_availability"))
if __name__=="__main__":unittest.main()
