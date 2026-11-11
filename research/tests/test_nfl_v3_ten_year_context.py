"""Tests for the new research-only 10-year NFL context challenger.

These tests do not approve the model for live betting. They assert chronology,
QB inclusion, shared latent environment, calibration freeze and source limits.
"""
from __future__ import annotations
import pathlib,sys,collections
import numpy as np
import pytest

ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT/"research"))
from nfl_decade_context_v3_model_20261111 import (
    MatchupRegressor,GameContextModel,OnlineBayesCalibrator,seed)

def data():
 out=[]
 for year in range(2014,2025):
  for week in range(1,19):
   for team,opp in (("A","B"),("B","A")):
    passn=31+((year+week+(team=="B"))%9)
    rushn=20+((year*2+week+(team=="A"))%9)
    qb="qba" if team=="A" else "qbb"
    role={"QB":{"pass attempts":passn,"completions":int(passn*.62),
      "passing yards":float(passn*6),"carries":2,
      "rushing yards":8.},
      "WR":{"targets":8,"receptions":5,"receiving yards":62.},
      "RB":{"targets":2,"receptions":1,"receiving yards":8.,
      "carries":15,"rushing yards":65.},
      "LB":{"tackles + assists":6,"solo tackles":4,"tackle assists":1}}
    ids={qb:{"role":"QB","values":role["QB"]},
       "wr"+team:{"role":"WR","values":role["WR"]},
       "rb"+team:{"role":"RB","values":role["RB"]},
       "lb"+team:{"role":"LB","values":role["LB"]}}
    out.append({"season":year,"week":week,
     "event_id":f"{year}_{week:02d}_A_B","team":team,"opponent":opp,
     "pass_attempts":passn,"rush_attempts":rushn,"players":ids})
 return out

def test_ten_year_window_and_strict_before_current():
 hist=[x for x in data() if x["season"]>=2015 and
       (x["season"]<2025 or x["season"]==2025 and x["week"]<1)]
 reg=MatchupRegressor(hist)
 m=GameContextModel(hist,2025,1,reg)
 assert m.quality["prior_min_year"]==2015
 assert m.quality["prior_max_year"]==2024
 assert m.quality["training_rows"]>300
 assert m.quality["latest_training_year_week"]<(2025,1)

def test_future_game_failure_closed():
 hist=[x for x in data() if x["season"]<=2023]
 reg=MatchupRegressor(hist)
 leak={"season":2024,"week":3,"event_id":"LEAK","team":"A",
       "opponent":"B","pass_attempts":32,"rush_attempts":23,"players":{}}
 with pytest.raises(ValueError,match="history_contains_current_or_future"):
  GameContextModel(hist+[leak],2024,3,reg)

def test_opponent_game_environment_and_qb_identity():
 hist=[x for x in data() if x["season"]>=2015 and x["season"]<=2024]
 reg=MatchupRegressor(hist)
 m=GameContextModel(hist,2025,1,reg)
 env=m._sample_environment("FUTURE","A","B",128)
 assert np.array_equal(env["A"]["opponent_plays"],env["B"]["plays"])
 assert np.array_equal(env["B"]["opponent_plays"],env["A"]["plays"])
 for t in ("A","B"):
  assert np.array_equal(env[t]["pass"]+env[t]["rush"],env[t]["plays"])
  assert np.all(env[t]["pass"]<=env[t]["plays"])
 draws,meta=m.forecast_game("FUTURE","A","B",
     {"A":"qba","B":"qbb"},n=128,pbp_model=None)
 assert np.mean(draws["A","qba"]["pass attempts"])>0
 assert np.mean(draws["B","qbb"]["pass attempts"])>0
 assert "qbb" not in {k[1] for k in draws if k[0]=="A"}
 assert meta["A"]["qualified_qb_in_candidates"]

def test_no_unqualified_qb_forecast():
 hist=[x for x in data() if x["season"]>=2015 and x["season"]<=2024]
 m=GameContextModel(hist,2025,1,MatchupRegressor(hist))
 draws,meta=m.forecast_game("FUTURE","A","B",
    {"A":None,"B":"qbb"},n=128,pbp_model=None)
 assert ("A","qba") not in draws
 assert not meta["A"]["qualified_qb_in_candidates"]

def test_calibration_receipt_is_not_mutated_by_settlement():
 a=OnlineBayesCalibrator()
 before=a.receipt()
 old=a.apply("targets",.9)
 a.update([("targets",.9,0) for _ in range(25)])
 after=a.receipt()
 assert before["state"]=={}
 assert after["state"]!={}
 assert a.apply("targets",.9)<old
 assert a.apply("targets",.9)<.9

def test_random_seed_is_stable():
 assert seed("A",2025,1)==seed("A",2025,1)
 assert seed("A",2025,1)!=seed("A",2025,2)
