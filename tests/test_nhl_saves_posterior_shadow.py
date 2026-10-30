"""NHL saves shadow integration offline safety tests: no PyMC/network needed."""
from __future__ import annotations
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import nhl_saves_posterior_shadow as sh

NOW=datetime(2026,10,30,15,0,tzinfo=timezone.utc)

def manifest():
    return {
        "schema":"multisport_joint_fit_manifest_v1",
        "model_version":"multisport-joint-bayes-v1",
        "sport":"NHL","stat":"saves","family":"count",
        "max_per_position":0,"diagnosed_all_player_and_opponent_effects":True,
        "sampler_chains":4,"sampler_retained_draws_per_chain":2000,
        "training_cutoff_exclusive":"2026-10-29",
        "last_game":"2026-10-28","source_digest":"sha-verified-source",
        "players":["123"]+[str(n) for n in range(200,211)],"player_position":{"123":"G"},
        "positions":["G"],"seasons":["2024","2025","2026"],
        "opponents":["MTL","BOS"],
        "diagnostics":{"posterior_sampling_ok":True,
                       "max_rhat":1.0092,"min_bulk_ess":815.,
                       "divergences":0,"minimum_bfmi":.507}
    }

def row(**changes):
    r={
        "game_date":"2026-10-30","run_type":"shadow",
        "sport":"NHL","stat":"saves",
        "player_id":"123","player":"Goalie",
        "team":"BOS","opponent":"MTL",
        "home_team":"BOS","away_team":"MTL",
        "matchup_orientation_verified":True,
        "side":"under","reference_line":27.5,
        "run_id":"active-run",
        "forecast_at":"2026-10-30T10:10:00-04:00",
        "event_start":"2026-10-30T19:00:00-04:00",
    }
    r.update(changes)
    return r

def receipt():
    return {"schema":"precision_nhl_model_receipt_v1","status":"converged",
            "stat":"saves","as_of_exclusive":"2026-10-29"}

class NHLShadowSafety(unittest.TestCase):
    def test_live_slate_goalie_saves_alias_is_accepted(self):
        official=row(stat="goalie saves")
        result=sh.validate_candidate(official,manifest(),NOW)
        self.assertEqual(result["player_id"],"123")

    def test_live_alias_is_selected_and_scored_by_run(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            snapshots=folder/"snapshots.jsonl"
            snapshots.write_text(json.dumps(row(stat="goalie saves"))+"\n",encoding="utf-8")
            model=SimpleNamespace(posterior=SimpleNamespace(sizes={"chain":4,"draw":2000}))
            projected={**row(stat="goalie saves"),"version":sh.VERSION,
                       "release_tag":sh.TAG,"status":"forecast",
                       "publication_eligible":False,"ranking_allowed":False,
                       "q_over":0.5,"q_under":0.5,"q_win":0.5}
            with (
                patch.object(sh,"load_model",return_value=manifest()),
                patch.dict(sys.modules,{"arviz":SimpleNamespace(from_netcdf=lambda p:model)}),
                patch("joint_population_bayes.posterior_cache",return_value={}),
                patch.object(sh,"evaluate",return_value=projected) as evaluate,
            ):
                receipt=sh.run(snapshots=snapshots,model_dir=folder,game_date="2026-10-30",
                               out=folder/"out.jsonl",receipt=folder/"receipt.json",now=NOW)
            self.assertEqual(evaluate.call_count,1)
            self.assertEqual(receipt["forecast_count"],1)
            self.assertEqual(json.loads((folder/"out.jsonl").read_text())["stat"],"goalie saves")

    def test_valid_prospective_context(self):
        x=sh.validate_candidate(row(),manifest(),NOW)
        self.assertEqual(x["player_id"],"123")
        self.assertTrue(x["home"])
        self.assertEqual(x["side"],"under")

    def test_abstains_on_untrusted_input(self):
        cases=[
            {"player_id":"wrong"},{"opponent":"NYR"},
            {"matchup_orientation_verified":False},{"home_team":"NYR"},
            {"event_start":"2026-10-30T10:30:00-04:00"},
            {"forecast_at":"2026-10-30T20:00:00-04:00"},
            {"reference_line":float("nan")},{"side":"unknown"},
            {"run_id":""},{"game_date":"2026-10-28"},
        ]
        for change in cases:
            with self.subTest(change=change),self.assertRaises(sh.ModelUnavailable):
                sh.validate_candidate(row(**change),manifest(),NOW)

    def test_season_rollover_abstains(self):
        with self.assertRaises(sh.ModelUnavailable):
            sh.validate_candidate(row(game_date="2027-10-30",
                 forecast_at="2027-10-30T10:00:00-04:00",
                 event_start="2027-10-30T19:00:00-04:00"),manifest(),
                 datetime(2027,10,30,15,tzinfo=timezone.utc))

    def test_market_side_and_rank_separation(self):
        q={"q_over":.21,"q_under":.79,"q_push":0.,
           "numerical_mc_se":.004}
        with patch("joint_population_bayes.forecast",return_value=q):
            r=sh.evaluate(row(),manifest=manifest(),posterior=object(),
                          cache={},now=NOW)
        self.assertEqual(r["status"],"forecast")
        self.assertEqual(r["q_win"],.79)
        self.assertFalse(r["ranking_allowed"])
        self.assertFalse(r["publication_eligible"])
        self.assertFalse(r["calibrated"])

    def test_rejects_modified_release_assets(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            (folder/"manifest.json").write_text(json.dumps(manifest()))
            (folder/"model_receipt.json").write_text(json.dumps(receipt()))
            (folder/"posterior.nc").write_bytes(b"fake")
            trusted={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}
            with patch.object(sh,"EXPECTED_SHA",trusted):
                self.assertEqual(sh.load_model(folder)["stat"],"saves")
                (folder/"posterior.nc").write_bytes(b"changed")
                with self.assertRaises(sh.ModelUnavailable):
                    sh.load_model(folder)

    def test_rejects_saved_convergence_failure(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            bad=manifest()
            bad["diagnostics"]["max_rhat"]=1.03
            (folder/"manifest.json").write_text(json.dumps(bad))
            (folder/"model_receipt.json").write_text(json.dumps(receipt()))
            (folder/"posterior.nc").write_bytes(b"fake")
            trusted={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}
            with patch.object(sh,"EXPECTED_SHA",trusted),self.assertRaises(sh.ModelUnavailable):
                sh.load_model(folder)

if __name__=="__main__":
    unittest.main()
