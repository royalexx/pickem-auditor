"""V5.3 one-game historical-anchor posterior-scenario safety invariants.

Historical reference probabilities are treated ONLY as soft as-of features
of the entire game, not as independent player-level probability overrides.
"""
from __future__ import annotations
import collections,copy,gzip,json,pathlib,sys,unittest
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[2]
BASE=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111"
sys.path.insert(0,str(ROOT/"research"))
from nfl_v5_3_joint_scenario_reweight_20261112 import (
 TiltLearner,STRENGTHS,optimize_weights,systematic_resample,
 tilt_forecast,game_all_strength_draws,effective_sample_size)
from nfl_v5_3_independent_joint_audit_20261112 import independent_game_check
class TestJointTilt(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  file=BASE/"V5_2_HISTORY_PRIORS_TWO_WEEK_20261112T140453Z/2016_week_01_v5_forecast.json.gz"
  cls.base=json.loads(gzip.open(file,"rb").read())
  cls.gid=next(iter(cls.base["games"]))
  cls.game=cls.base["games"][cls.gid]
  cls.offers=[z for z in cls.base["offers"] if z["game_id"]==cls.gid]
  cls.anchor={(f["game_id"],f["team"],f["player_id"],f["market"]):
    float(f["original_v3_p_online"]) for f in cls.offers
    if f.get("status")=="forecast" and f.get("original_v3_p_online") is not None}
 def test_prior_only_tilt_weights_immutable(self):
  a=TiltLearner();old=a.receipt();w=a.get()
  a.update({"targets":[[(i+1)*.01,(i+1)*.02,(i+1)*.03] for i in range(40)]})
  self.assertEqual(old["weeks_prior"],0)
  self.assertTrue(np.array_equal(np.asarray(old["weights"]),w))
  self.assertEqual(a.receipt()["weeks_prior"],1)
  b=TiltLearner();b.restore(a.receipt())
  self.assertTrue(np.allclose(a.get(),b.get()))
 def test_ess_never_below_floor(self):
  rng=np.random.default_rng(7)
  E=rng.integers(0,2,size=(40,128)).astype(float)
  q=np.clip(E.mean(axis=1)+rng.normal(0,.2,40),.005,.995)
  weights,receipt=optimize_weights(E,q,np.full(len(q),1/len(q)),5.,128)
  self.assertAlmostEqual(weights.sum(),1)
  self.assertGreaterEqual(effective_sample_size(weights),32.-1e-4)
  self.assertEqual(receipt["status"],"tilted")
 def test_resample_reproducible(self):
  w=np.linspace(1,10,128);w=w/w.sum()
  self.assertTrue(np.array_equal(
    systematic_resample(w,128,104),systematic_resample(w,128,104)))
 def test_no_historical_reference_is_neutral(self):
  selections,diag=game_all_strength_draws(self.game,self.offers,{},2016,1,self.gid)
  for i,rec in enumerate(diag):
   self.assertEqual(rec["valid_anchors"],0)
   self.assertTrue(np.array_equal(selections[i],np.arange(128)))
 def test_one_shared_scenario_after_soft_history_conditioning(self):
  j=copy.deepcopy(self.base)
  prior=TiltLearner()
  result=tilt_forecast(j,self.anchor,prior,"v5_3_unit_test")
  game=result["games"][self.gid]
  offers=[z for z in result["offers"] if z["game_id"]==self.gid]
  issues=[]
  independent_game_check(game,offers,issues)
  self.assertFalse(issues,str(issues)[:300])
  self.assertEqual(len(game["whole_game_tilt_strength_selection"]),128)
  for z in offers:
   if z["status"]!="forecast":continue
   vals=np.asarray(z["draws"])
   self.assertEqual(len(vals),128)
   self.assertAlmostEqual(z["p_over"],float(np.mean(vals>z["line"])))
   self.assertTrue(z["origin"]=="V5_SINGLE_GAME_SIMULATION")
 def test_bad_anchor_is_never_future_label(self):
  j=copy.deepcopy(self.base)
  # This test injects nonsensical anchor probabilities; no settlement labels
  # or game actuals are supplied to scenario reweighting.
  off={k:2.5 for k in self.anchor}
  result=tilt_forecast(j,off,TiltLearner(),"v5_3_bad_anchor")
  game=result["games"][self.gid]
  issues=[]
  independent_game_check(game,
    [z for z in result["offers"] if z["game_id"]==self.gid],issues)
  self.assertFalse(issues)
  self.assertTrue(all(z["status"]=="no_tilt" for z in game["whole_game_tilt_diagnostics"]))
if __name__=="__main__":unittest.main()
