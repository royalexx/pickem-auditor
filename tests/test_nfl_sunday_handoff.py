"""Independent adversarial contract-matching unit tests, no source calls."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from nfl_sunday_source_contract import build_universe, expected_events
from nfl_sunday_handoff import validate_handoff

def fixture():
    ev=[dict(x,espn_event_id=str(45000000+i),schedule_verified=True)
        for i,x in enumerate(expected_events())]
    x=ev[1]
    q={"sport":"NFL","event_id":"prop1","event_start":x["scheduled_kickoff"],
       "event_teams":["KC","ATL"],"team":"","opponent":"",
       "player":"Exact Player","stat":"pass attempts","book":"B1",
       "line":30.5,"over_odds":-110,"under_odds":-110,
       "retrieved_at":"2026-11-15T04:45:00Z"}
    m=build_universe(events=ev,quotes=[q],
       quote_receipts={"propline":{"sha256":"a"*64,"source_received_at":"2026-11-15T04:46:00Z",
                  "source_bytes_verified":True,"archive_path":"source_control/raw/a.bin"}},
       rosters={"KC":{"athletes":[{"id":"abc","fullName":"Exact Player",
                     "position":{"abbreviation":"QB"},"status":{"type":"active"}}],
                     "receipt_sha256":"b"*64}},
       depth_qbs={"KC":{"espn_player_id":"abc"}},
       injuries={},nfl_rows=[],freeze_at="2026-11-15T05:00:00Z",code_sha="c"*40)
    m["_file_sha256"]="f"*64
    src=m["candidates"][0]
    row={k:src.get(k) for k in
         ("candidate_id","event_id","player_id","quote_id","stat","period",
          "line","book","source_sha256","event_start_at","input_freeze_at")}
    row.update(source_manifest_file_sha256="f"*64,model_id="simple_pois",
        model_version="0.1",model_training_cutoff_at="2026-11-15T04:00:00Z",
        forecast_at="2026-11-15T05:01:00Z",
        probabilities={"over":.4,"under":.6,"push":0},research_only=True)
    return m,row

class HandoffTests(unittest.TestCase):
    def test_valid_exact_source_bound_shadow(self):
        m,row=fixture()
        self.assertTrue(m["candidates"][0]["research_shadow_eligible"])
        r=validate_handoff(m,"simple_models",[row])
        self.assertEqual((r["accepted"],r["rejected"]),(1,0))
    def test_wrong_source_manifest_hash(self):
        m,row=fixture()
        row["source_manifest_file_sha256"]="0"*64
        self.assertEqual(validate_handoff(m,"simple_models",[row])["rejected"],1)
    def test_wrong_original_quote_identity(self):
        for key,value in (("book","fake"),("line",31.5),("event_id","other"),
                          ("player_id","other"),("quote_id","other"),
                          ("source_sha256","1"*64),("period","half")):
            with self.subTest(key=key):
                m,row=fixture();row[key]=value
                self.assertEqual(validate_handoff(m,"simple_models",[row])["rejected"],1)
    def test_training_cutoff_future(self):
        m,row=fixture()
        row["model_training_cutoff_at"]="2026-11-15T05:20:00Z"
        self.assertEqual(validate_handoff(m,"simple_models",[row])["reasons"],
                         {"POST_FREEZE_MODEL_TRAINING":1})
    def test_start_after_game(self):
        m,row=fixture()
        row["forecast_at"]="2026-11-16T00:00:00Z"
        self.assertEqual(validate_handoff(m,"simple_models",[row])["reasons"],
                         {"FORECAST_OUTSIDE_PREGAME_WINDOW":1})
    def test_probability_mass_not_one(self):
        m,row=fixture()
        row["probabilities"]={"over":.5,"under":.7,"push":0.}
        self.assertEqual(validate_handoff(m,"simple_models",[row])["reasons"],
                         {"PROBABILITY_MASS_MISMATCH":1})
    def test_probability_missing_push(self):
        m,row=fixture()
        row["probabilities"].pop("push")
        self.assertEqual(validate_handoff(m,"simple_models",[row])["rejected"],1)
    def test_shadow_only_enforced(self):
        m,row=fixture();row["research_only"]=False
        self.assertEqual(validate_handoff(m,"simple_models",[row])["reasons"],
                         {"SHADOW_ONLY_REQUIRED":1})
    def test_duplicate_forecast_rejected(self):
        m,row=fixture();r=validate_handoff(m,"simple_models",[row,row])
        self.assertEqual((r["accepted"],r["rejected"]),(1,1))
    def test_unknown_source_candidate_rejected(self):
        m,row=fixture();row["candidate_id"]="not-original"
        self.assertEqual(validate_handoff(m,"simple_models",[row])["rejected"],1)
    def test_wrong_workstream_rejected(self):
        m,row=fixture()
        with self.assertRaises(ValueError):
            validate_handoff(m,"shared",[row])
    def test_missing_model_cutoff_rejected(self):
        m,row=fixture();row.pop("model_training_cutoff_at")
        self.assertEqual(validate_handoff(m,"simple_models",[row])["rejected"],1)

if __name__=="__main__":
    unittest.main()
