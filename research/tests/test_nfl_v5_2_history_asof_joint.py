"""Adversarial invariants for the one-game NFL offense+defense simulation.

Uses original 2016 Week 2 frozen retrospective packet, NEVER Week 2 outcomes.
No historical synthetic-line performance claims follow from passing tests.
"""
from __future__ import annotations
import collections,copy,gzip,json,pathlib,sys,unittest
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[2]
BASE=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111"
sys.path[:0]=[str(ROOT/"research"),str(BASE/"EXP_ALL13_20261111T200951Z/frozen_code")]
from nfl_v5_2_historical_joint_model_20261112 import (
 JointGameModel,PROFILES,validate_joint_state,draw_allocation,JointFactorWeights)
from v25_decade_qb_components import QBRushComponentModel

class JointNFLTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  p=BASE/"V3_CONTEXT_10YEAR_FULL_20261111T233046Z/2016_week_02_v3_before_outcomes.json.gz"
  cls.packet=json.loads(gzip.open(p,"rb").read())
  cls.mod=JointGameModel(cls.packet["history"],2016,2,PROFILES["balanced"])
  cls.pbp=QBRushComponentModel(cls.packet["pbp_prior"],forecast_year=2016,forecast_week=2)
  teams=collections.defaultdict(dict)
  for row in cls.packet["games"]:
   teams[row["game_id"]][row["team"]]=row["opponent"]
  chosen=next((gid for gid,r in teams.items()
              if len(r)==2 and any(
                cls.packet["qb1"].get(gid+"|"+team,{}).get("player_id") for team in r)),
             None)
  if chosen is None:raise RuntimeError("no_prior_qualified_game_fixture")
  cls.gid=chosen
  cls.teams=tuple(sorted(teams[chosen]))
  cls.qb={t:cls.packet["qb1"][chosen+"|"+t]["player_id"] for t in cls.teams}
  cls.draws,cls.meta,cls.state=cls.mod.forecast_game(
   chosen,*cls.teams,cls.qb,n=128,pbp_model=cls.pbp,return_state=True)
 def test_one_environment_draw_not_resampled(self):
  original=self.mod._sample_environment
  calls=[]
  def hook(*args,**kwargs):
   calls.append((args,kwargs))
   return original(*args,**kwargs)
  self.mod._sample_environment=hook
  try:
   self.mod.forecast_game(self.gid,*self.teams,self.qb,n=128,pbp_model=self.pbp)
  finally:
   self.mod._sample_environment=original
  self.assertEqual(len(calls),1)
 def test_offense_defense_same_exact_game(self):
  validate_joint_state(self.state,self.draws,self.teams,128)
  for t in self.teams:
   opponent=self.teams[1] if t==self.teams[0] else self.teams[0]
   self.assertTrue(np.array_equal(self.state[t]["opponent_plays"],
                                  self.state[opponent]["plays"]))
   self.assertTrue(np.array_equal(self.state[t]["opponent_completions"],
                                  self.state[opponent]["team_completions"]))
 def test_no_independent_QB_rewrite(self):
  for t in self.teams:
   qb=self.state[t]["eligible_qb1"]
   if qb is None:continue
   d=self.draws[t,qb];self.assertTrue(np.array_equal(
     d["pass attempts"],self.state[t]["qb1_attempts"]))
   self.assertTrue(np.array_equal(
     d["passing yards"],self.state[t]["qb1_passing_yards"]))
   self.assertTrue(np.array_equal(
     d["qb rushing attempts"],self.state[t]["qb1_rush_attempts"]))
 def test_named_targets_and_tackles_are_bounded(self):
  for t in self.teams:
   state=self.state[t]
   self.assertTrue(np.all(state["known_targets"]<=state["pass_attempts"]))
   self.assertTrue(np.all(state["known_rb_carries"]+state["qb1_rush_attempts"]
                          <=state["rush_attempts"]))
   self.assertTrue(np.all(state["defensive_tackle_events"]<=
                          state["defensive_eligible_events"]))
 def test_tampering_pass_cannot_be_silent(self):
  bad=copy.deepcopy(self.state)
  t=self.teams[0];bad[t]["qb1_attempts"][0]+=1
  with self.assertRaises(ValueError):
   validate_joint_state(bad,self.draws,self.teams,128)
 def test_tampering_defensive_exposure_cannot_be_silent(self):
  bad=copy.deepcopy(self.state)
  t=self.teams[0];bad[t]["opponent_rush_attempts"][0]+=1
  with self.assertRaises(ValueError):
   validate_joint_state(bad,self.draws,self.teams,128)
 def test_tampering_receiver_catches_cannot_be_silent(self):
  bad=copy.deepcopy(self.draws)
  targets=[z for (team,pid),z in bad.items() if team==self.teams[0] and "targets" in z]
  if not targets:self.skipTest("no_eligible_receivers")
  targets[0]["receptions"][0]=targets[0]["targets"][0]+1
  with self.assertRaises(ValueError):
   validate_joint_state(self.state,bad,self.teams,128)
 def test_prior_only_history(self):
  self.assertTrue(all(g["season"]<2016 or(g["season"]==2016 and g["week"]<2)
                      for g in self.mod.history))
 def test_three_profile_scenario_weights_frozen(self):
  old=JointFactorWeights();receipt=old.receipt()
  copied=JointFactorWeights();copied.restore(receipt)
  self.assertTrue(np.allclose(old.get(),copied.get()))
  self.assertAlmostEqual(sum(receipt["weights"]),1)
 def test_multinomial_including_unassigned(self):
  rng=np.random.default_rng(42)
  raw=np.asarray([0,7,10,15]*32)
  got=draw_allocation(rng,raw,[.3,.2,.5])
  self.assertEqual(got.shape,(3,128))
  self.assertTrue(np.array_equal(got.sum(axis=0),raw))
 def test_scenario_participation_counts_bounded(self):
  for team in self.teams:
   state=self.state[team]
   self.assertTrue(np.all(state["scenario_active_skill_count"]<=
       state["source_roster_skill_count"]))
   self.assertTrue(np.all(state["scenario_active_defender_count"]<=
       state["source_roster_defender_count"]))
 def test_historical_priors_respect_strict_asof(self):
  p=self.mod._history_priors
  yr,wk=p["source_max_year_week"]
  self.assertLess((yr,wk),(2016,2))
  self.assertTrue(0<p["rec_target_rate"]<=1)
  self.assertTrue(0<p["catch_rate"]<1)
  self.assertTrue(0<p["def_tackle_conversion"]<=1)
 def test_future_game_row_rejected_before_fitting(self):
  fake=copy.deepcopy(self.packet["history"][-1])
  fake["season"]=2016;fake["week"]=2
  with self.assertRaises(ValueError):
   JointGameModel(self.packet["history"]+[fake],2016,2,PROFILES["balanced"])
 def test_historical_learning_is_reproducible(self):
  other=JointGameModel(self.packet["history"],2016,2,PROFILES["balanced"])
  self.assertEqual(other._history_priors,self.mod._history_priors)
  self.assertEqual(dict(other._role_participation),dict(self.mod._role_participation))
 def test_extra_tackle_exposure_still_shared(self):
  for team in self.teams:
   opp=self.teams[1] if team==self.teams[0] else self.teams[0]
   self.assertTrue(np.array_equal(
     self.state[team]["opponent_auxiliary_credit_opportunities"],
     self.state[opp]["auxiliary_credited_tackle_opportunities"]))
 def test_unqualified_qb_is_not_projected(self):
  q={t:None for t in self.teams}
  d,m,s=self.mod.forecast_game(self.gid,*self.teams,q,
                                n=128,pbp_model=self.pbp,return_state=True)
  self.assertTrue(all(s[t]["eligible_qb1"] is None for t in self.teams))
  self.assertFalse(any("pass attempts" in v for v in d.values()))
  validate_joint_state(s,d,self.teams,128)

if __name__=="__main__":unittest.main()
