"""V4.1 QB opportunity repair unit audit without optional pytest deps."""
from __future__ import annotations
import gzip,json,pathlib,sys,unittest,math
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"research"),str(ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/EXP_ALL13_20261111T200951Z/frozen_code")]
from nfl_v4_1_qb_share_repair_model_20261111 import ContextFactorModel
from nfl_v4_factor_tuning_model_20261111 import ContextFactorModel as PreRepair,PROFILES
from v25_decade_qb_components import QBRushComponentModel
BASE=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111"
class TestQBRepair(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  inp=BASE/"V3_CONTEXT_10YEAR_FULL_20261111T233046Z/2016_week_02_v3_before_outcomes.json.gz"
  cls.packet=json.loads(gzip.open(inp,"rb").read())
  cls.pbp=QBRushComponentModel(cls.packet["pbp_prior"],forecast_year=2016,forecast_week=2)
  cls.games={}
  for g in cls.packet["games"]:cls.games[g["game_id"]]=g["opponent"]
 def _first_eligible_game(self):
  for game in self.packet["games"]:
   gid=game["game_id"];ta=game["team"];tb=game["opponent"]
   key=gid+"|"+ta
   qb=self.packet["qb1"].get(key,{}).get("player_id")
   if qb is None:continue
   other=self.packet["qb1"].get(gid+"|"+tb,{}).get("player_id")
   return gid,ta,tb,{ta:qb,tb:other}
  self.fail("No eligible preweek starting QB")
 def test_math_error_identified(self):
  share=.95
  wrong=(12+35*share)/(24+35)
  repaired=(1+60*share)/(2+60)
  self.assertLess(wrong,.78)
  self.assertGreater(repaired,.92)
  self.assertLess(abs(repaired-share),.02)
 def test_eligible_QB_receives_team_pass_share(self):
  gid,ta,tb,qb=self._first_eligible_game()
  m=ContextFactorModel(self.packet["history"],2016,2,PROFILES["recent"])
  a,meta=m.forecast_game(gid,ta,tb,qb,n=128,pbp_model=self.pbp)
  if (ta,qb[ta]) not in a or "pass attempts" not in a[ta,qb[ta]]:
   self.skipTest("selected QB not present in two prior games")
  v=a[ta,qb[ta]]
  self.assertTrue(np.all(v["pass attempts"]>=0))
  self.assertTrue(np.all(v["completions"]<=v["pass attempts"]))
  self.assertTrue(np.all(v["qb rushing attempts"]>=0))
  self.assertTrue(meta[ta]["qb_volume_overwrite_verified"])
  self.assertLess(abs(meta[ta]["qb_share_beta_prior_mean"]-
    meta[ta]["qb_share_prior_measured"]),.02)
  self.assertLessEqual(meta[ta]["qb_pass_attempts_prior_anchored_mean"],
      meta[ta]["qb_pass_attempts_team_eligible_mean"]+1e-10)
 def test_no_ineligible_QB_created(self):
  gid,ta,tb,qb=self._first_eligible_game()
  qb[ta]=None
  m=ContextFactorModel(self.packet["history"],2016,2,PROFILES["recent"])
  d,meta=m.forecast_game(gid,ta,tb,qb,n=128,pbp_model=self.pbp)
  self.assertFalse(any(team==ta and "pass attempts" in z for (team,pid),z in d.items()))
 def test_fixed_source_continuity(self):
  m=ContextFactorModel(self.packet["history"],2016,2,PROFILES["recent"])
  a=m._sample_environment("2016_02_INVENTED","BUF","NYJ",128)
  self.assertTrue(np.array_equal(a["BUF"]["opponent_plays"],a["NYJ"]["plays"]))
  self.assertTrue(np.array_equal(a["BUF"]["plays"],a["BUF"]["pass"]+a["BUF"]["rush"]))
if __name__=="__main__":unittest.main()
