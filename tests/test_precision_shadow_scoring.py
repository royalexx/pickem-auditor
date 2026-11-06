"""Offline safety tests for immutable NUTS saves/targets validation."""
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import precision_shadow_scoring as audit
import precision_shadow_release as release

DAY="2026-11-05"
START="2026-11-05T23:30:00Z"
AT="2026-11-05T22:10:00Z"
SCORE="2026-11-06T15:00:00Z"

def source():
 return {"phase":"afternoon","game_date":DAY,"forecasts":[],"shadow":{
   "nhl_saves_nuts":[],"nfl_targets_nuts":[]}}

def original():
 return {"game_date":DAY,"sport":"NHL","stat":"goalie saves",
         "player_id":"848001","side":"under","reference_line":20.5,
         "run_id":"frozen-1","forecast_at":AT,"actual_stat":None}

def saves():
 return {**original(),"status":"forecast","ranking_allowed":False,"shadow_only":True,
         "event_start":START,"generated_at":"2026-11-05T22:20:00Z",
         "trained_through":"2026-10-28","q_win":.72,"q_push":0}

def target(kind="market"):
 return {"status":"forecast","ranking_allowed":False,"shadow_only":True,
         "sport":"NFL","game_date":DAY,"stat":"targets","market":"targets",
         "game_id":"2026_10_BAL_CIN","player_id":"00-0000001",
         "team":"BAL","opponent":"CIN","run_id":"frozen-1",
         "line_origin":kind,"reference_line":5.5,"side":"over",
         "event_start":START,"parent_forecast_at":AT,
         "forecast_at":"2026-11-05T22:20:00Z",
         "training_cutoff_exclusive":"2026-09-01T00:00:00Z",
         "q_win":.7,"q_push":0}

def nfl_original():
 return {"game_date":DAY,"sport":"NFL","stat":"targets","player_id":"00-0000001",
         "side":"over","reference_line":5.5,"run_id":"frozen-1",
         "forecast_at":AT,"actual_stat":None}

def population():
 return [{"sport":"NFL","stat":"targets","game_date":DAY,
          "game_id":"2026_10_BAL_CIN","player_id":"00-0000001",
          "team":"BAL","opponent":"CIN","value":7}]

class ShadowScoringTests(unittest.TestCase):
 def test_scores_saved_goalie_without_regenerating_or_updating_original(self):
  a=source();r=original();a["forecasts"].append(r)
  a["shadow"]["nhl_saves_nuts"].append(saves())
  old=json.dumps(a,sort_keys=True)
  settled={**r,"actual_stat":17,"outcome":"win"}
  result=audit.audit(DAY,a,[settled],[])
  self.assertEqual(result["scored_rows"],1)
  self.assertEqual(result["summaries"]["nhl_saves_nuts:market"]["wins"],1)
  self.assertEqual(old,json.dumps(a,sort_keys=True))

 def test_synthetic_target_projection_scores_only_against_official_targets(self):
  a=source();a["shadow"]["nfl_targets_nuts"].append(target(kind="research_threshold"))
  result=audit.audit(DAY,a,[],population())
  self.assertEqual(result["scored_rows"],1)
  self.assertEqual(result["predictions"][0]["market_type"],"research_threshold")
  self.assertAlmostEqual(result["summaries"]["nfl_targets_nuts:research_threshold"]["brier"],.09)

 def test_posted_target_line_must_have_original_market_snapshot(self):
  a=source();a["shadow"]["nfl_targets_nuts"].append(target("market"))
  self.assertEqual(audit.audit(DAY,a,[],population())["scored_rows"],0)
  a["forecasts"].append(nfl_original())
  self.assertEqual(audit.audit(DAY,a,[],population())["scored_rows"],1)
  self.assertIn("nfl_targets_nuts:market",audit.audit(DAY,a,[],population())["summaries"])

 def test_wrong_game_or_team_and_post_start_predictions_are_never_scored(self):
  a=source();a["shadow"]["nfl_targets_nuts"].append(target("research_threshold"))
  rows=population();rows[0]["team"]="CIN"
  self.assertEqual(audit.audit(DAY,a,[],rows)["scored_rows"],0)
  a["shadow"]["nfl_targets_nuts"][0]["forecast_at"]="2026-11-05T23:31:00Z"
  self.assertEqual(audit.audit(DAY,a,[],population())["scored_rows"],0)

 def test_duplicate_predicted_identity_is_rejected(self):
  a=source();a["forecasts"].append(original())
  a["shadow"]["nhl_saves_nuts"]=[saves(),saves()]
  with self.assertRaisesRegex(ValueError,"duplicate_immutable_nhl"):
   audit.audit(DAY,a,[{**original(),"actual_stat":17,"outcome":"win"}],[])

 def test_missing_prediction_not_converted_into_zero_stat(self):
  a=source();a["shadow"]["nfl_targets_nuts"].append(target("research_threshold"))
  self.assertEqual(audit.audit(DAY,a,[],[])["scored_rows"],0)

class ReleaseTests(unittest.TestCase):
 def test_pinned_download_and_second_run_is_idempotent(self):
  payload=b"synthetic-model-bytes"
  import hashlib
  digest=hashlib.sha256(payload).hexdigest()
  with tempfile.TemporaryDirectory() as tmp:
   tag="synthetic-test-tag"
   assets={"parameters.npz":digest}
   listing={"tag_name":tag,"assets":[{"name":"parameters.npz","size":len(payload),
         "browser_download_url":f"https://github.com/{release.REPO}/releases/download/{tag}/parameters.npz"}]}
   calls=[]
   def opener(req,timeout):
    calls.append(req.full_url)
    return io.BytesIO(json.dumps(listing).encode() if "/releases/tags/" in req.full_url else payload)
   with patch.dict(release.RELEASES,{"test":(tag,assets)}):
    result=release.fetch("test",Path(tmp),token="fake",opener=opener)
    self.assertEqual(result["assets"]["parameters.npz"]["status"],"downloaded")
    second=release.fetch("test",Path(tmp),token="fake",opener=opener)
    self.assertEqual(second["assets"]["parameters.npz"]["status"],"existing")
    self.assertEqual(len(calls),3)
    (Path(tmp)/"parameters.npz").write_bytes(b"tampered")
    again=release.fetch("test",Path(tmp),token="fake",opener=opener)
    self.assertEqual(again["assets"]["parameters.npz"]["sha256"],digest)

if __name__=="__main__":unittest.main()
