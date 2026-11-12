"""Independent forensic negative controls for V5.1 archived scenario accounting."""
from __future__ import annotations
import copy,gzip,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
BASE=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111"
sys.path.insert(0,str(ROOT/"research"))
from nfl_v5_independent_game_state_audit_20261112 import independent_game_check
class AdversarialArchiveAudit(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  p=BASE/"V5_1_SHARED_PARTICIPATION_PILOT_20261112T133929Z/2016_week_02_v5_forecast.json.gz"
  data=json.loads(gzip.open(p,"rb").read())
  cls.gameid=next(iter(data["games"]))
  cls.game=data["games"][cls.gameid]
  cls.offers=[z for z in data["offers"] if z["game_id"]==cls.gameid]
 def test_clean_archived_game_passes(self):
  issues=[]
  independent_game_check(self.game,self.offers,issues)
  self.assertEqual(issues,[])
 def test_one_team_tempo_tamper_rejected(self):
  corrupt=copy.deepcopy(self.game)
  home=corrupt["teams"][0]
  corrupt["joint_state"][home]["plays"][0]+=1
  issues=[]
  independent_game_check(corrupt,self.offers,issues)
  self.assertTrue(any("offensive_plays" in z for z in issues))
 def test_defender_can_not_invent_tackles(self):
  corrupt=copy.deepcopy(self.game)
  home=corrupt["teams"][0]
  corrupt["joint_state"][home]["credited_assists"][0]+=1
  issues=[]
  independent_game_check(corrupt,self.offers,issues)
  self.assertTrue(any("defense_assist_credits" in z for z in issues))
 def test_opponent_defense_cannot_have_own_independent_clock(self):
  corrupt=copy.deepcopy(self.game)
  home=corrupt["teams"][0]
  corrupt["joint_state"][home]["opponent_plays"][0]+=2
  issues=[]
  independent_game_check(corrupt,self.offers,issues)
  self.assertTrue(any("defense_same_plays_as_opponent" in z for z in issues))
 def test_profile_selection_not_per_player(self):
  corrupt=copy.deepcopy(self.game)
  corrupt["source_profile_indices"][0]=19
  issues=[]
  independent_game_check(corrupt,self.offers,issues)
  self.assertIn("mask_only_three_profiles",issues)
 def test_unverified_fallback_flag_fails(self):
  corrupt=copy.deepcopy(self.game)
  corrupt["cross_player_fallback_used"]=True
  issues=[]
  independent_game_check(corrupt,self.offers,issues)
  self.assertIn("no_player_level_fallback",issues)
if __name__=="__main__":unittest.main()
