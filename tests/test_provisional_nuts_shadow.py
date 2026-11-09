"""Offline contract tests for pinned, never-promoted NFL provisional forecasts."""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import provisional_nuts_shadow as shadow


class ProvisionalSafetyTests(unittest.TestCase):
    def test_pins_only_four_complete_provisional_nfl_artifacts(self):
        cfg=shadow.load_policy()
        self.assertEqual(len(cfg["models"]),4)
        self.assertEqual({x["stat"] for x in cfg["models"]},
            {"pass attempts","targets","rushing touchdowns","receiving touchdowns"})
        self.assertTrue(all(len(x["sha256"])==64 for x in cfg["models"]))
        self.assertEqual(cfg["scope"],"shadow_only_no_production_ranking")

    def test_diagnostics_research_gate_exact_and_not_production(self):
        p=shadow.load_policy()["policy"]
        d={"posterior_sampling_ok":False,"max_rhat":1.016,
           "min_bulk_ess":351.0,"divergences":0,"minimum_bfmi":.62}
        self.assertTrue(shadow.provisional_diagnostics(d,p))
        for patching in ({"posterior_sampling_ok":True},{"max_rhat":1.021},
                         {"min_bulk_ess":299},{"divergences":1},
                         {"minimum_bfmi":.29}):
            self.assertFalse(shadow.provisional_diagnostics({**d,**patching},p))

    def test_receipt_validation_cannot_inflate_quality(self):
        cfg=shadow.load_policy()
        asset=cfg["models"][0]
        m={"schema":"multisport_joint_fit_manifest_v1","model_version":"multisport-joint-bayes-v1",
           "sport":"NFL","stat":asset["stat"],"family":"count",
           "max_per_position":0,"diagnosed_all_player_and_opponent_effects":True,
           "sampler_chains":4,"sampler_retained_draws_per_chain":2000,
           "sampler_tuning_iterations_per_chain":1800,"training_cutoff_exclusive":"2026-10-29",
           "source_digest":"valid","players":["id"],"opponents":["NE"],
           "diagnostics":{"posterior_sampling_ok":False,**{k:asset[k] for k in
               ("max_rhat","min_bulk_ess","minimum_bfmi","divergences")}}}
        self.assertTrue(shadow.verify_manifest(m,asset,cfg))
        tampered=copy.deepcopy(m)
        tampered["diagnostics"]["max_rhat"]=1.001
        with self.assertRaisesRegex(ValueError,"not_eligible"):
            shadow.verify_manifest(tampered,asset,cfg)
        tampered=copy.deepcopy(m)
        tampered["diagnostics"]["posterior_sampling_ok"]=True
        with self.assertRaisesRegex(ValueError,"not_eligible"):
            shadow.verify_manifest(tampered,asset,cfg)

    def test_latest_completed_tackles_artifact_can_join_original_four(self):
        cfg=shadow.load_policy()
        extra={"index":9,"sport":"NFL","stat":"tackles + assists",
               "run_id":123456789,"artifact_id":987654321,
               "size_bytes":50000000,"sha256":"a"*64,
               "max_rhat":1.013,"min_bulk_ess":355.,
               "minimum_bfmi":.55,"divergences":0,
               "strict_accepted":False}
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"dynamic.json"
            cfg["models"].append(extra)
            p.write_text(json.dumps(cfg),encoding="utf-8")
            updated=shadow.load_policy(p)
            self.assertEqual(updated["models"][-1]["stat"],"tackles + assists")
            self.assertEqual(len(updated["models"]),5)
            # The original 4 pins must remain byte-for-byte identical.
            updated["models"][0]["sha256"]="f"*64
            p.write_text(json.dumps(updated),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"original_four"):
                shadow.load_policy(p)

    def test_unfinished_or_unqualified_tackles_is_never_accepted(self):
        cfg=shadow.load_policy()
        extra={"index":9,"sport":"NFL","stat":"tackles + assists",
               "run_id":123456789,"artifact_id":987654321,
               "size_bytes":50000000,"sha256":"a"*64,
               "max_rhat":1.03,"min_bulk_ess":200.,
               "minimum_bfmi":.20,"divergences":2}
        self.assertFalse(shadow.provisional_diagnostics({
            "posterior_sampling_ok":False,"max_rhat":extra["max_rhat"],
            "min_bulk_ess":extra["min_bulk_ess"],
            "minimum_bfmi":extra["minimum_bfmi"],
            "divergences":extra["divergences"]},cfg["policy"]))
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"extended.json"
            cfg["models"].append(extra)
            p.write_text(json.dumps(cfg),encoding="utf-8")
            loaded=shadow.load_policy(p)
            # Extended policy does not approve diagnostics on its own.
            self.assertEqual(len(loaded["models"]),5)

    def test_strictly_accepted_successor_stays_research_only(self):
        cfg=shadow.load_policy()
        strict={"posterior_sampling_ok":True,"max_rhat":1.006,
                "min_bulk_ess":450.,"minimum_bfmi":.5,"divergences":0}
        self.assertTrue(shadow.provisional_diagnostics(
            strict,cfg["policy"],strict_accepted=True))
        self.assertFalse(shadow.provisional_diagnostics(
            strict,cfg["policy"],strict_accepted=False))

    def test_prediction_preserves_research_only_status_and_provenance(self):
        cfg=shadow.load_policy()
        asset=cfg["models"][0]
        manifest={"last_game":"2026-01-04","source_digest":"seed",
                  "diagnostics":{"posterior_sampling_ok":False}}
        at=datetime(2026,11,8,12,tzinfo=timezone.utc)
        row={"game_date":"2026-11-08","sport":"NFL","player_id":"GSIS1",
             "stat":"pass attempts","side":"over","reference_line":25.5,
             "forecast_at":at.isoformat(),"event_start":(at+timedelta(hours=2)).isoformat(),
             "team":"NE","opponent":"BUF","home_team":"NE","away_team":"BUF",
             "matchup_orientation_verified":True,"run_id":"test"}
        # Pin inference completion to the *original pregame test instant*.
        # Using real wall-clock time makes this historical fixture post-kickoff.
        with patch.object(shadow.parent,"candidate_context",
                          return_value={"player_id":"GSIS1","opponent":"BUF","season":"2026",
                                        "home":True,"line":25.5}), patch.object(
            shadow,"provisional_forecast",return_value={
                "q_over":.65,"q_under":.35,"q_push":0.0}), patch.object(shadow, "datetime") as clock:
            clock.now.return_value = at + timedelta(seconds=1)
            result=shadow.forecast_one(row,manifest,None,at,asset)
        self.assertEqual(result["status"],"forecast")
        self.assertAlmostEqual(result["q_win"],.65)
        self.assertIs(result["ranking_allowed"],False)
        self.assertIs(result["publication_eligible"],False)
        self.assertIs(result["provisional"],True)
        self.assertIs(result["sampler_diagnostics"]["posterior_sampling_ok"],False)

    def test_no_predictions_after_kickoff(self):
        cfg=shadow.load_policy()
        asset=cfg["models"][0]
        now=datetime(2026,11,8,19,tzinfo=timezone.utc)
        row={"game_date":"2026-11-08","sport":"NFL","player_id":"1","stat":"pass attempts",
             "side":"over","reference_line":25.5,"forecast_at":now.isoformat(),
             "event_start":(now-timedelta(minutes=1)).isoformat()}
        m={"last_game":"2026-01-04","source_digest":"seed",
           "diagnostics":{"posterior_sampling_ok":False}}
        result=shadow.forecast_one(row,m,None,now,asset)
        self.assertEqual(result["status"],"unavailable")
        self.assertFalse(result["ranking_allowed"])
        self.assertTrue(result.get("reason"))


if __name__=="__main__":
    unittest.main()
