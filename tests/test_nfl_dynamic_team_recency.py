"""Chronological, team-first, last-five-week and engine-credibility tests."""
import sys,unittest,math
from pathlib import Path
from collections import defaultdict
from datetime import date,timedelta
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from nfl_dynamic_opportunity import (
 dynamic_player_projection,team_opportunity_factor,extend_team_histories,
 PLAYER_LOOKBACK,TEAM_HALF_LIFE_DAYS,PLAYER_HALF_LIFE_DAYS)
from adaptive_engine_credibility_shadow import ShadowCredibility

def empty():
 return dict(player=defaultdict(list),role_history=defaultdict(list),
  team_history=defaultdict(list),allowed_history=defaultdict(list),
  league_team=defaultdict(list))
def entry(day,val,season,team="A"):
 return dict(gameday=day,value=val,season=season,team=team)
def form_state(recent=8.,old=1.,team_recent=45.):
 s=empty()
 for i in range(10):
  d=(date(2022,9,1)+timedelta(days=i*7)).isoformat()
  s["player"][("targets","P")].append(entry(d,old,2022))
  s["role_history"][("targets","WR")].append(entry(d,4.,2022))
 for i in range(5):
  d=(date(2024,10,1)+timedelta(days=i*7)).isoformat()
  s["player"][("targets","P")].append(entry(d,recent,2024))
  s["role_history"][("targets","WR")].append(entry(d,4.,2024))
  team=entry(d,team_recent,2024)
  s["team_history"][("targets","A")].append(team)
  s["allowed_history"][("targets","B")].append(team)
  s["league_team"]["targets"].append(team)
  s["league_team"]["targets"].append(entry(d,team_recent,2024,"C"))
 return s
def predict(s,day="2024-11-12"):
 return dynamic_player_projection(s,market="targets",player_id="P",
  team="A",opponent="B",position="WR",game_day=day,season=2024,default_role=5.)

class DynamicOpportunityTests(unittest.TestCase):
 def test_last_five_override_two_years_ago(self):
  s=form_state(recent=9.,old=0.)
  mu,ev=predict(s)
  self.assertIsNotNone(mu)
  self.assertGreater(mu,7.)
  self.assertAlmostEqual(ev["player_recent_weight"],.82,places=6)
  self.assertEqual(ev["player_recent_games"],5)
 def test_recent_downturn_matters(self):
  hi,_=predict(form_state(recent=9.,old=7.))
  lo,_=predict(form_state(recent=1.,old=7.))
  self.assertGreater(hi,lo+5.)
 def test_current_team_appearance_required(self):
  s=form_state()
  s["player"][("targets","P")]=[r for r in s["player"][("targets","P")] if r["season"]==2022]
  mu,ev=predict(s)
  self.assertIsNone(mu)
  self.assertEqual(ev["status"],"no_pregame_current_team_appearance")
 def test_old_roster_cannot_enter_synthetic_week1(self):
  s=form_state()
  # Historical-as-of state contains 2022 information only; future 2024
  # observations must not exist in the model before Week 1.
  s["player"][("targets","P")]=[
      r for r in s["player"][("targets","P")] if r["season"]<2024]
  s["role_history"][("targets","WR")]=[
      r for r in s["role_history"][("targets","WR")] if r["season"]<2024]
  s["team_history"].clear();s["allowed_history"].clear();s["league_team"].clear()
  mu,ev=predict(s,day="2024-09-07")
  self.assertIsNone(mu)
 def test_future_current_week_aborts(self):
  s=form_state()
  s["player"][("targets","P")].append(entry("2024-11-12",100.,2024))
  with self.assertRaisesRegex(ValueError,"future"):
   predict(s)
 def test_team_and_opponent_factors_shift(self):
  s=form_state()
  before,ev=team_opportunity_factor(s,"targets","A","B",date(2024,11,12))
  self.assertAlmostEqual(before,1.)
  for i in range(5):
   d=(date(2024,10,1)+timedelta(days=i*7)).isoformat()
   s["team_history"][("targets","A")][i]["value"]=75.
   s["allowed_history"][("targets","B")][i]["value"]=75.
  after,ev2=team_opportunity_factor(s,"targets","A","B",date(2024,11,12))
  self.assertGreater(after,before+.05)
  self.assertLessEqual(after,1.35)
 def test_team_aggregation_once_per_fixture(self):
  s=empty()
  base={"season":2023,"game_id":"G","gameday":"2023-11-19","stat":"targets",
        "team":"A","opponent":"B"}
  extend_team_histories(s,[{**base,"player_id":"X","value":8.},
                            {**base,"player_id":"Y","value":5.}])
  self.assertEqual(len(s["team_history"][("targets","A")]),1)
  self.assertEqual(s["team_history"][("targets","A")][0]["value"],13.)
 def test_team_history_cannot_see_same_week(self):
  s=form_state()
  s["team_history"][("targets","A")].append(entry("2024-11-12",100.,2024))
  with self.assertRaisesRegex(ValueError,"future"):
   team_opportunity_factor(s,"targets","A","B",date(2024,11,12))
 def test_recent_form_decays_faster_than_team(self):
  self.assertLess(PLAYER_HALF_LIFE_DAYS,TEAM_HALF_LIFE_DAYS)

class EngineWeightShadowTests(unittest.TestCase):
 def test_unsettled_outcomes_rejected(self):
  s=ShadowCredibility(engines=("A","B"))
  with self.assertRaisesRegex(ValueError,"unsettled"):
   s.update_settled_slate("2024-10-01",[("G",None,{"A":.8,"B":.2})])
 def test_update_after_settlement_only(self):
  s=ShadowCredibility(engines=("A","B"))
  self.assertIsNone(s.weights(release=True))
  out=s.update_settled_slate("2024-10-01",[("G",1,{"A":.9,"B":.1})])
  self.assertGreater(out["next_slate_shadow_weights"]["A"],.5)
  self.assertFalse(out["production_allowed"])
 def test_no_future_then_past_update(self):
  s=ShadowCredibility(engines=("A","B"))
  s.update_settled_slate("2024-10-01",[("G",1,{"A":.9,"B":.1})])
  with self.assertRaisesRegex(ValueError,"nonchronological"):
   s.update_settled_slate("2024-09-30",[("H",0,{"A":.9,"B":.1})])
 def test_slate_order_no_change(self):
  rows=[("G",1,{"A":.9,"B":.2}),("H",0,{"A":.1,"B":.8})]
  a=ShadowCredibility(engines=("A","B"));b=ShadowCredibility(engines=("A","B"))
  a.update_settled_slate("2024-10-01",rows)
  b.update_settled_slate("2024-10-01",list(reversed(rows)))
  self.assertEqual(a.weights(),b.weights())
 def test_correlated_markets_one_game(self):
  s=ShadowCredibility(engines=("A","B"))
  s.update_settled_slate("2024-10-01",[
     ("G",1,{"A":.9,"B":.1}) for _ in range(30)])
  self.assertEqual(s.settled_games,1)
 def test_probability_invalid_aborts(self):
  s=ShadowCredibility(engines=("A","B"))
  with self.assertRaisesRegex(ValueError,"invalid_probability"):
   s.update_settled_slate("2024-10-01",[("G",1,{"A":float("nan"),"B":.2})])

if __name__=="__main__":unittest.main()
