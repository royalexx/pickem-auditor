"""Read-only convergence audit contract; no sampler required."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import precision_nhl_convergence as c

def manifest():
    return {"schema":"multisport_joint_fit_manifest_v1","sport":"NHL",
            "stat":"saves","source_digest":"1234","rows":23000,
            "players":["a","b"],"sampler_chains":4,
            "sampler_retained_draws_per_chain":2000,"max_per_position":0,
            "diagnosed_all_player_and_opponent_effects":True,
            "diagnostics":{"posterior_sampling_ok":True,"max_rhat":1.003,
                           "min_bulk_ess":412,"divergences":0,"minimum_bfmi":0.65}}

class SavedFitCheck(unittest.TestCase):
    def test_not_yet_finished_not_converged(self):
        with tempfile.TemporaryDirectory() as d:
            r=c.inspect(Path(d),"saves")
            self.assertEqual(r["status"],"unavailable")
            self.assertFalse(r["strict_convergence"])

    def test_strict_requirements_all_hold(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"manifest.json").write_text(json.dumps(manifest()))
            (p/"model_receipt.json").write_text(json.dumps({"stat":"saves","status":"converged"}))
            (p/"posterior.nc").touch()
            result=c.inspect(p,"saves")
            self.assertEqual(result["status"],"converged")
            self.assertFalse(result["production_eligible"])

    def test_rejects_failed_sampler_even_if_numeric_diagnostics_good(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"manifest.json").write_text(json.dumps(manifest()))
            (p/"model_receipt.json").write_text(json.dumps({"stat":"saves","status":"failed"}))
            (p/"posterior.nc").touch()
            self.assertFalse(c.inspect(p,"saves")["strict_convergence"])

    def test_rejects_hidden_player_effects_or_bad_ess(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            m=manifest()
            m["diagnosed_all_player_and_opponent_effects"]=False
            m["diagnostics"]["min_bulk_ess"]=300
            (p/"manifest.json").write_text(json.dumps(m))
            (p/"model_receipt.json").write_text(json.dumps({"stat":"saves","status":"converged"}))
            (p/"posterior.nc").touch()
            self.assertFalse(c.inspect(p,"saves")["strict_convergence"])

if __name__=="__main__":
    unittest.main()
