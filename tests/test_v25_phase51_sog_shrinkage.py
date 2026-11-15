"""Phase 5.1 adversarial contract tests, written before S1 implementation."""
import datetime as dt
import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path

from v2 import nhl_sog_rate_shrinkage_prospective as s1

UTC = dt.timezone.utc
def t(x): return dt.datetime.fromisoformat(x.replace("Z","+00:00"))
def model():
    return {
        "schema":"v25_nhl_sog_exposure_gamma_poisson_v1",
        "model_id":"SOG_EXPOSURE_GAMMA_POISSON_V1",
        "input_freeze_at":"2026-11-16T17:00:00Z",
        "event_start_at":"2026-11-16T23:00:00Z",
        "fit_data_cutoff_at":"2026-11-16T16:00:00Z",
        "player_id":"8482001","target_event_id":"2026020555","current_team_id":"MTL",
        "position_group":"F","rate_a":8.0,"rate_b":100.0,
        "tau_minutes":60.0,"plugin_exposure":14.0,"plugin_rate":0.1,
        "own_played_games":5,"peer_players":20,"peer_games":200,
        "source_manifest":[],"own_source_sha256":[],"peer_source_sha256":[],
        "exposure_pmf":[[14.0,1.0]],
        "gamma_parameterization":"shape_rate"
    }
def stamp(t):return t.isoformat().replace("+00:00","Z")
class MathTests(unittest.TestCase):
    def test_s1_mean_variance(self):
        x=s1.build_paired_distributions(model(),forecast_at="2026-11-16T18:00:00Z",
             code_sha="a"*40,expected_event_id="2026020555",expected_player_id="8482001")
        self.assertAlmostEqual(x["S1"]["mean"],1.12)
        self.assertAlmostEqual(x["S1"]["variance"],1.12)
        self.assertGreater(x["M2"]["variance"],x["S1"]["variance"])
        self.assertAlmostEqual(x["M2"]["mean"],x["S1"]["mean"])
        self.assertAlmostEqual(x["M0"]["mean"],1.4)
        self.assertAlmostEqual(x["S1"]["pmf"][0],math.exp(-1.12))
        self.assertAlmostEqual(sum(x["S1"]["pmf"]),1.,places=10)
    def test_gamma_parameterization(self):
        m=model();m["rate_b"]=0.01
        x=s1.build_paired_distributions(m,forecast_at="2026-11-16T18:00:00Z",
             code_sha="a"*40,expected_event_id="2026020555",expected_player_id="8482001")
        self.assertAlmostEqual(x["S1"]["mean"],11200.)
    def test_integer_line_push(self):
        pmf=s1.poisson_pmf(1.3)
        p=s1.exact_contract_probs(pmf,2)
        self.assertAlmostEqual(p["push"],pmf[2])
        self.assertAlmostEqual(p["under"],pmf[0]+pmf[1])
        self.assertAlmostEqual(p["over"]+p["under"]+p["push"],1.)
    def test_half_line_no_push(self):
        p=s1.exact_contract_probs(s1.poisson_pmf(1.3),2.5)
        self.assertEqual(p["push"],0)
        self.assertAlmostEqual(sum(p[k] for k in ("over","under","push")),1)
    def test_zero_and_tail6(self):
        p=s1.poisson_pmf(0)
        self.assertEqual(p,[1.0])
        q=s1.poisson_pmf(2.2)
        self.assertAlmostEqual(1-sum(q[:6]),s1.summary(q)["tail6"],places=12)
    def test_normalization_across_rates(self):
        for mu in [0,0.02,.05,1,2,3,8,17,40,75,120]:
            p=s1.poisson_pmf(mu)
            self.assertTrue(all(x>=0 and math.isfinite(x) for x in p))
            self.assertAlmostEqual(sum(p),1,places=10)
    def test_deterministic(self):
        a=s1.poisson_pmf(4.4);b=s1.poisson_pmf(4.4);self.assertEqual(a,b)
    def test_exact_count_crps(self):
        p=s1.poisson_pmf(1.4)
        z=s1.score_count(p,2)
        self.assertGreater(z["crps"],0)
        self.assertAlmostEqual(z["nll"],-math.log(p[2]))
    def test_no_postgame_features(self):
        for field in ["current_game_sog","current_game_toi","actual_sog",
                      "actual_toi","final_score","current_game_played","postgame_roster"]:
            with self.subTest(field=field):
                m=model();m[field]=1
                with self.assertRaises(s1.S1Blocked):s1.build_paired_distributions(
                    m,forecast_at="2026-11-16T18:00:00Z",code_sha="a"*40,
                    expected_event_id="2026020555",expected_player_id="8482001")
    def test_late_freeze(self):
        m=model();m["input_freeze_at"]="2026-11-16T23:05:00Z"
        with self.assertRaises(s1.S1Blocked):s1.build_paired_distributions(m,
            forecast_at="2026-11-16T23:06:00Z",code_sha="a"*40,
            expected_event_id="2026020555",expected_player_id="8482001")
    def test_after_event_forecast(self):
        with self.assertRaises(s1.S1Blocked):s1.build_paired_distributions(model(),
            forecast_at="2026-11-17T00:00:00Z",code_sha="a"*40,
            expected_event_id="2026020555",expected_player_id="8482001")
    def test_training_after_freeze(self):
        m=model();m["fit_data_cutoff_at"]="2026-11-16T19:00:00Z"
        with self.assertRaises(s1.S1Blocked):s1.build_paired_distributions(m,
            forecast_at="2026-11-16T20:00:00Z",code_sha="a"*40,
            expected_event_id="2026020555",expected_player_id="8482001")
    def test_player_event_collision(self):
        for kw in [dict(expected_player_id="8482999"),dict(expected_event_id="other")]:
            args=dict(expected_player_id="8482001",expected_event_id="2026020555");args.update(kw)
            with self.assertRaises(s1.S1Blocked):s1.build_paired_distributions(model(),
                forecast_at="2026-11-16T18:00:00Z",code_sha="a"*40,**args)
    def test_naive_time(self):
        with self.assertRaises(s1.S1Blocked):s1.build_paired_distributions(model(),
            forecast_at="2026-11-16T18:00:00",code_sha="a"*40,
            expected_event_id="2026020555",expected_player_id="8482001")
    def test_missing_code_commit(self):
        with self.assertRaises(s1.S1Blocked):s1.build_paired_distributions(model(),
            forecast_at="2026-11-16T18:00:00Z",code_sha="unknown",
            expected_event_id="2026020555",expected_player_id="8482001")
    def test_negative_or_bad_gamma(self):
        for field,val in [("rate_a",0),("rate_b",0),("rate_a",float("nan")),
                          ("rate_b",-10),("plugin_exposure",0)]:
            m=model();m[field]=val
            with self.subTest(field=field,val=val),self.assertRaises(s1.S1Blocked):
                s1.build_paired_distributions(m,forecast_at="2026-11-16T18:00:00Z",
                  code_sha="a"*40,expected_event_id="2026020555",expected_player_id="8482001")
    def test_short_positive_toi(self):
        self.assertEqual(s1.valid_played_toi(0.05),0.05)
        with self.assertRaises(s1.S1Blocked):s1.valid_played_toi(0)
    def test_no_mutable_forecast(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"sealed.json"
            a={"x":1};sha=s1.append_exact(p,a)
            self.assertEqual(s1.append_exact(p,a),sha)
            with self.assertRaises(s1.S1Blocked):s1.append_exact(p,{"x":2})
    def test_duplicate_player_game_detected(self):
        with self.assertRaises(s1.S1Blocked):
            s1.assert_unique_player_games([("g1","p1"),("g1","p1")])
    def test_source_receipt_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"obs.json"
            p.write_bytes(b'{"x":1}')
            good=hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(s1.verify_sha_bytes(p,good),b'{"x":1}')
            p.write_bytes(b'{"x":2}')
            with self.assertRaises(s1.S1Blocked):s1.verify_sha_bytes(p,good)
    def test_source_after_freeze_and_same_day(self):
        m=model();m["source_manifest"]=[{"received_at":"2026-11-16T18:00:00Z"}]
        with self.assertRaises(s1.S1Blocked):s1.build_paired_distributions(m,
            forecast_at="2026-11-16T19:00:00Z",code_sha="a"*40,
            expected_event_id="2026020555",expected_player_id="8482001")
    def test_outcome_free_model(self):
        x=s1.build_paired_distributions(model(),forecast_at="2026-11-16T18:00:00Z",
            code_sha="a"*40,expected_event_id="2026020555",expected_player_id="8482001")
        self.assertNotIn("actual_sog",json.dumps(x))

if __name__=="__main__":unittest.main()
