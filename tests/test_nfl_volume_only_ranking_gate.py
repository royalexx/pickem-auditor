"""NFL volume-only policy regression safety: research, conditional and verified boards."""
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from nfl_volume_market_policy import NFL_VOLUME_MARKETS,nfl_volume_market_allowed
from slate_candidate_ranking import candidate

class NFLVolumeOnlyRankingSafety(unittest.TestCase):
 def test_all_touchdowns_and_sparse_markets_blocked(self):
  for stat in ("passing touchdowns","rushing touchdowns","receiving touchdowns",
       "anytime touchdown scorer","anytime td","touchdowns",
       "qb hits","passes defended","other unknown"):
   with self.subTest(stat=stat):
    self.assertFalse(nfl_volume_market_allowed("NFL",stat))
 def test_expected_volume_markets_allowed(self):
  self.assertEqual(len(NFL_VOLUME_MARKETS),11)
  for stat in NFL_VOLUME_MARKETS:
   self.assertTrue(nfl_volume_market_allowed("NFL",stat))
 def test_non_nfl_markets_unmodified(self):
  for sport in ("NBA","NHL"):
   self.assertTrue(nfl_volume_market_allowed(sport,"goals"))
   self.assertTrue(nfl_volume_market_allowed(sport,"touchdowns"))
 def test_research_candidate_rejected_before_model_scoring(self):
  for stat in ("passing touchdowns","rushing touchdowns","receiving touchdowns","qb hits","passes defended"):
   row=dict(sport="NFL",stat=stat)
   pick,reason=candidate(row,{},data_root=ROOT)
   self.assertIsNone(pick)
   self.assertEqual(reason,"nfl_market_excluded_volume_only_policy")

if __name__=="__main__":
 unittest.main()
