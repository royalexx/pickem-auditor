"""Strict pre-2024 isolation for XGBoost Bayesian optimization and NFL sources."""
import sys
from pathlib import Path
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from nfl_pre2024_pbp_ngs_sources import (
 CUTOFF,ftn_safe_history,ngs_pre2024_rows,aggregate_games,
 assert_pre2024_training_inputs,
)
from nfl_pre2024_xgboost_optuna import (
 MARKETS,FEATURES,make_training_rows,validation_folds,_cutoff,
 fit_one_market,make_feature,
)

class Pre2024StrictCutoff(unittest.TestCase):
 def test_training_2024_labels_hard_blocked(self):
  with self.assertRaisesRegex(ValueError,"2024_plus"):
   _cutoff({"game_date":"2024-09-08","season":"2024"})
 def test_2023_january_2024_games_hard_blocked(self):
  with self.assertRaisesRegex(ValueError,"2024_plus_date"):
   _cutoff({"game_date":"2024-01-07","season":"2023"})
 def test_unproven_ftn_pull_never_allowed(self):
  x=[{"season":2023,"nflverse_game_id":"2023_10_A_B",
      "nflverse_play_id":31,"date_pulled":"2024-09-06 13:30:00+00:00"}]
  self.assertEqual(ftn_safe_history(x,{"2023_10_A_B":"2023-11-01"}),[])
 def test_ftn_audited_pre2024_allowed_only(self):
  x=[{"season":2023,"nflverse_game_id":"G",
      "nflverse_play_id":5,"date_pulled":"2023-10-02"}]
  self.assertEqual(len(ftn_safe_history(x,{"G":"2023-10-01"})),1)
 def test_pbp_2024_season_banned(self):
  with self.assertRaisesRegex(ValueError,"pre2024"):
   aggregate_games([{"season":2024,"game_id":"G"}],{"G":"2024-09-08"})
 def test_pbp_played_jan24_not_training(self):
  a,c=aggregate_games([{"season":2023,"season_type":"REG",
     "game_id":"G","week":18,"posteam":"A","defteam":"B",
     "pass_attempt":1,"play_id":1}],{"G":"2024-01-07"})
  self.assertEqual(a,[])
 def test_ngs_2024_season_banned(self):
  with self.assertRaisesRegex(ValueError,"2024_plus"):
   ngs_pre2024_rows([{"season":2024,"week":1}],
                    "passing",{(2024,1,"A"):"2024-09-08"})
 def test_ngs_2023_week18_in_2024_excluded(self):
  self.assertEqual(ngs_pre2024_rows([{"season":2023,"week":18,"team_abbr":"A",
          "player_gsis_id":"P","season_type":"REG"}],
          "passing",{(2023,18,"A"):"2024-01-07"}),[])
 def test_assert_no_2024_training(self):
  with self.assertRaisesRegex(ValueError,"2024_plus"):
   assert_pre2024_training_inputs(player_rows=[{"game_date":"2024-01-01","season":"2023"}],
            pbp_games=[],ngs_rows=[])
 def test_validation_folds_chronological(self):
  rows=[]
  import datetime
  for i in range(42):
   d=datetime.date(2021,9,15)+datetime.timedelta(days=19*i)
   if d>=CUTOFF:break
   for j in range(5):rows.append(dict(date=d.isoformat()))
  folds=validation_folds(rows)
  self.assertGreaterEqual(len(folds),1)
  for tr,va in folds:
   self.assertLess(max(rows[i]["date"] for i in tr),min(rows[i]["date"] for i in va))
 def test_feature_selection_never_2024(self):
  from collections import defaultdict
  state={k:defaultdict(list) for k in ("player","role","team_offense","opponent_allowed","league_offense","ngs")}
  with self.assertRaisesRegex(ValueError,"2024"):
   make_feature(state,stat="targets",player_id="P",position="WR",
              team="A",opponent="B",asof="2024-09-08")
 def test_full_11_volume_markets(self):
  self.assertEqual(len(MARKETS),11)
  self.assertEqual(len(FEATURES),29)
  self.assertNotIn("rushing touchdowns",MARKETS)

if __name__=="__main__":unittest.main()
