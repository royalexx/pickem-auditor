"""Adversarial mathematical/lineage tests for the new SOG experiment."""
import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path

from v2.nhl_sog_exposure_shadow import (
    ExperimentBlocked, fit_model, forecast_lines, same_data_ablations,
    bin_toi_minutes, categorical_brier, evaluate_paired_dates, power_null_simulation,
    verify_observation, stable_hash,
)

F="2026-11-12T18:00:00Z"
START="2026-11-13T00:00:00Z"


def make_obs(root, pid, game, toi, sog, position="F",
             received="2026-11-11T12:00:00Z", played=True):
    doc={"schema":"v25_nhl_sog_observation_v1",
         "player_id":pid,"event_id":game,"position_group":position,
         "toi_minutes":toi,"shots_on_goal":sog,"played":played,
         "event_ended_at":"2026-11-10T05:00:00Z"}
    raw=json.dumps(doc,sort_keys=True,separators=(",",":")).encode()
    digest=hashlib.sha256(raw).hexdigest()
    (root/"raw").mkdir(exist_ok=True)
    (root/"raw"/(digest+".json")).write_bytes(raw)
    return {"archive_path":"raw/"+digest+".json","content_sha256":digest,
            "received_at":received,"source_kind":"collector_observed_bytes",
            "source_url":"https://api-web.nhle.com/v1/gamecenter/example/boxscore"}


def fixture(root, low_toi=False):
    own=[make_obs(root,"target",f"o{j}",0.4 if low_toi and j==0 else 13+j/10,2+j%3)
         for j in range(10)]
    peers=[make_obs(root,f"peer{j}",f"p{j}-{k}",12+(k%8),1+(j+k)%4)
           for j in range(20) for k in range(10)]
    return own, peers


class NHLSOGExposureTests(unittest.TestCase):
    def test_half_up_and_short_play(self):
        self.assertEqual(bin_toi_minutes(0.25),0.5)
        self.assertEqual(bin_toi_minutes(0.75),1.0)
        self.assertEqual(bin_toi_minutes(0.1),0.5)
        self.assertEqual(bin_toi_minutes(64.75),65)
        with self.assertRaises(ExperimentBlocked):
            bin_toi_minutes(0)

    def test_conjugacy_support_and_ablations(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            own,peers=fixture(root,low_toi=True)
            model=fit_model(own,peers,archive_root=root,player_id="target",
                            position_group="F",input_freeze_at=F,event_start_at=START)
            self.assertEqual(model["schema"],"v25_nhl_sog_exposure_gamma_poisson_v1")
            self.assertEqual(model["rate_b"],60+sum(0.4 if j==0 else 13+j/10 for j in range(10)))
            self.assertAlmostEqual(model["rate_a"],60*model["peer_rate"]+sum(2+j%3 for j in range(10)))
            self.assertAlmostEqual(sum(q for _,q in model["exposure_pmf"]),1)
            self.assertGreater(model["exposure_pmf"][0][0],0)
            p=forecast_lines(model,[0.5,2,2.5,3,8])
            self.assertEqual(p["0.5"]["push"],0)
            self.assertGreater(p["2"]["push"],0)
            self.assertAlmostEqual(sum(p["2"][k] for k in ("over","under","push")),1)
            self.assertGreater(p["0.5"]["over"],p["8"]["over"])
            for item in p.values():
                self.assertTrue(all(0<=item[k]<=1 for k in ("over","under","push")))
            self.assertGreater(model["variance"],model["mean"])
            ab=same_data_ablations(model)
            self.assertEqual(set(ab),{"plugin_poisson","fixed_exposure_gamma_poisson",
                                      "mixture_exposure_plugin_poisson","full_gamma_poisson_exposure"})
            self.assertAlmostEqual(ab["full_gamma_poisson_exposure"]["mean"],model["mean"])
            self.assertEqual(stable_hash(model),stable_hash(json.loads(json.dumps(model))))

    def test_missing_and_corrupt_sources_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);own,peers=fixture(root)
            base=dict(archive_root=root,player_id="target",position_group="F",
                      input_freeze_at=F,event_start_at=START)
            with self.assertRaises(ExperimentBlocked):
                fit_model(own,peers[:190],**base)
            with self.assertRaises(ExperimentBlocked):
                fit_model(own,peers+[peers[0]],**base)
            mutated=dict(own[0],content_sha256="1"*64)
            with self.assertRaises(ExperimentBlocked):
                fit_model([mutated]+own[1:],peers,**base)
            late=dict(own[0],received_at="2026-11-12T19:00:00Z")
            with self.assertRaises(ExperimentBlocked):
                fit_model([late]+own[1:],peers,**base)
            future=dict(own[0])
            with self.assertRaises(ExperimentBlocked):
                fit_model(own,peers,role_change=True,**base)
            self.assertEqual(verify_observation(own[0],root,F)["player_id"],"target")

    def test_dnp_excludes_and_early_exit_retained(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);own,peers=fixture(root)
            own[0]=make_obs(root,"target","o0",0,0,played=False)
            with self.assertRaises(ExperimentBlocked):
                fit_model(own,peers,archive_root=root,player_id="target",
                          position_group="F",input_freeze_at=F,event_start_at=START)
            own[0]=make_obs(root,"target","o0",0.1,0,played=True)
            model=fit_model(own,peers,archive_root=root,player_id="target",
                            position_group="F",input_freeze_at=F,event_start_at=START)
            self.assertGreater(model["zero_probability"],0)

    def test_proper_score_and_fixed_date_estimand(self):
        self.assertEqual(categorical_brier({"over":1,"under":0,"push":0},"over"),0)
        self.assertEqual(categorical_brier({"over":0,"under":1,"push":0},"over"),2)
        rows=[
          {"date":"a","game_id":"g1","contract_id":"x","control":{"over":.4,"under":.6,"push":0},
           "challenger":{"over":.6,"under":.4,"push":0},"state":"over"},
          {"date":"a","game_id":"g1","contract_id":"y","control":{"over":.4,"under":.6,"push":0},
           "challenger":{"over":.6,"under":.4,"push":0},"state":"under"},
          {"date":"b","game_id":"g2","contract_id":"z","control":{"over":.3,"under":.5,"push":.2},
           "challenger":{"over":.3,"under":.5,"push":.2},"state":"push"}]
        out=evaluate_paired_dates(rows)
        self.assertEqual(out["date_count"],2)
        self.assertEqual(out["matched_contracts"],3)
        self.assertAlmostEqual(out["mean_date_delta"],0)
        power=power_null_simulation(dates=8,replicates=100,seed=20261112)
        self.assertTrue(0<=power["empirical_type1_rate"]<=1)
        self.assertEqual(power["dates"],8)


if __name__=="__main__":
    unittest.main()
