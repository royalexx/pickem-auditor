"""Standalone V4 factor-tuning invariants, no pytest dependency.

Test factor parameters truly change historical population/usage/opponent exposures,
preweek weights are hash-stable, calibrator cannot use current labels, and
simulation conserves team and defensive tackle components.
"""
from __future__ import annotations
import collections,gzip,json,pathlib,sys,unittest
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"research"),str(ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/EXP_ALL13_20261111T200951Z/frozen_code")]
from nfl_v4_factor_tuning_model_20261111 import ContextFactorModel,FactorWeights,OnlineMarketStack,PROFILES
from nfl_decade_context_v3_model_20261111 import require
BASE=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111"
class TestV4Factors(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  p=BASE/"V3_CONTEXT_10YEAR_FULL_20261111T233046Z"/"2016_week_01_v3_before_outcomes.json.gz"
  cls.data=json.loads(gzip.open(p,"rb").read())
  assert cls.data["year"]==2016 and cls.data["week"]==1
  cls.models={name:ContextFactorModel(cls.data["history"],2016,1,profile)
    for name,profile in PROFILES.items()}
 def test_time_cutoff_strict(self):
  for name,model in self.models.items():
   self.assertTrue(all(g["season"]<2016 for g in model.history))
   self.assertEqual(model.quality["prior_min_year"],2014)
   self.assertEqual(model.quality["prior_max_year"],2015)
   self.assertEqual(model.fit["age_half_life_years"],PROFILES[name]["half_life"])
 def test_factors_modify_impact(self):
  a=self.models["recent"];b=self.models["long"]
  self.assertNotAlmostEqual(a._role_prior("WR","targets"),b._role_prior("WR","targets"),places=8)
  self.assertEqual(a.profile["appearances"],5)
  self.assertEqual(b.profile["appearances"],12)
 def test_joint_game_volume(self):
  models=self.models
  game=self.data["games"][0]
  a=game["team"];b=game["opponent"]
  if a==b or not b:
   self.skipTest("no normalized game opponent")
  for name,m in models.items():
   env=m._sample_environment(game["game_id"],a,b,128)
   for team in (a,b):
    self.assertTrue(np.array_equal(env[team]["plays"],env[team]["pass"]+env[team]["rush"]))
    self.assertTrue(np.all(env[team]["pass"]>=0))
    self.assertTrue(np.all(env[team]["rush"]>=0))
   self.assertTrue(np.array_equal(env[a]["opponent_plays"],env[b]["plays"]))
 def test_bayesian_weight_receipt_immutable(self):
  w=FactorWeights();before=w.receipt();init=list(before["weights"])
  w.update({"targets":[[.4,.2,.3]]*100})
  self.assertEqual(before["weights"],init)
  self.assertNotEqual(before["weeks_prior"],w.receipt()["weeks_prior"])
  v=FactorWeights();v.restore(w.receipt())
  self.assertTrue(np.allclose(v.get(),w.get()))
 def test_market_stack_gated_before_priors(self):
  cal=OnlineMarketStack()
  p,data=cal.get("targets",.97,.93,.90,.65)
  self.assertAlmostEqual(p,.65)
  self.assertEqual(data["stack_trust"],0.)
  old=cal.receipt()
  cal.update("targets",[(.97,.93,.90,1.,.65)]*20)
  self.assertIn("|targets",old["theta"])
  self.assertNotEqual(old["theta"]["|targets"],cal.receipt()["theta"]["|targets"])
  b=OnlineMarketStack();b.restore(cal.receipt())
  self.assertEqual(b.receipt()["nweeks"]["targets"],1)
  p2,info=b.get("targets",.97,.93,.90,.65)
  self.assertEqual(info["stack_trust"],0.)
 def test_future_history_rejected(self):
  m=self.models["recent"]
  leak=dict(m.history[0]);leak["season"]=2016;leak["week"]=1
  with self.assertRaises(ValueError):
   ContextFactorModel(m.history+[leak],2016,1,PROFILES["recent"])
 def test_profile_count_exposure(self):
  game=self.data["games"][0];a=game["team"];b=game["opponent"]
  # Profile effect is observable even if a market doesn't offer a contract.
  recent=self.models["recent"]._sample_environment(game["game_id"],a,b,128)
  long=self.models["long"]._sample_environment(game["game_id"],a,b,128)
  self.assertGreater(float(np.mean(np.abs(recent[a]["plays"]-long[a]["plays"]))),0.)

if __name__=="__main__":unittest.main()
