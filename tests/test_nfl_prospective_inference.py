"""Pure inference contracts using controlled posterior arrays, no training."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import nfl_context_model as model


class ProspectiveInference(unittest.TestCase):
    def setUp(self):
        self.design={"source_digest":"inference-fixture","cutoff":"2026-09-01T00:00:00Z",
            "market":"targets","feature_names":["home","core2","core3","core4","core5","core6","core7"],
            "players":["receiver"],"teams":["A","B"],"positions":["WR"],"seasons":["2024","2025"],
            "player_position":{"receiver":"WR"},"center":[0.]*7,"scale":[1.]*7}
        n=16
        arrays={"population_workload":np.full((n,1),-1.),"population_log_rate":np.full((n,1),np.log(.12)),
            "player_effect":np.zeros((n,1,2)),"team_effect":np.zeros((n,2,2)),"season_effect":np.zeros((n,2,2)),
            "season_sd":np.full((n,2),.1),"beta_workload":np.zeros((n,7)),"beta_rate":np.zeros((n,7)),
            "workload_sigma":np.full(n,.3),"count_dispersion":np.full(n,10.)}
        self.cache={"source_digest":"inference-fixture","n":n,"arrays":arrays}
        self.row={"game_id":"future-game","player_id":"receiver","team":"A","opponent":"B","position":"WR",
            "season":"2026","start_time":"2026-11-01T18:00:00Z","feature_time":"2026-11-01T18:00:00Z",
            "stat":"targets","feature_names":self.design["feature_names"],"x":[1.,0.,0.,0.,0.,0.,0.]}

    def predict(self,row,line=5.5):
        return model.forecast(self.cache,self.design,row,line=line,draws=1000,diagnostic={"posterior_sampling_ok":True})

    def test_missing_or_null_outcome_forecasts_without_fabricated_scoring(self):
        prospective=self.predict(self.row)
        null=self.predict({**self.row,"target":None})
        observed=self.predict({**self.row,"target":3})
        self.assertEqual(prospective,null)
        self.assertIsNone(prospective["target"])
        self.assertIsNone(prospective["log_predictive_density"])
        self.assertIsNotNone(observed["log_predictive_density"])
        for key in ("q_over","q_under","q_push","expected_value","expected_snaps","predictive_interval_90"):
            self.assertEqual(prospective[key],observed[key])
        self.assertAlmostEqual(sum(prospective[k] for k in ("q_over","q_under","q_push")),1.)
        self.assertFalse(prospective["ranking_allowed"])
        integer=self.predict(self.row,line=5.)
        self.assertGreater(integer["q_push"],0.)
        self.assertAlmostEqual(sum(integer[k] for k in ("q_over","q_under","q_push")),1.)

    def test_invalid_observed_count_is_not_scored(self):
        for target in (True,-1,1.5,float("nan"),float("inf"),"3"):
            with self.subTest(target=target),self.assertRaisesRegex(ValueError,"invalid_nfl_observed_count"):
                self.predict({**self.row,"target":target})
