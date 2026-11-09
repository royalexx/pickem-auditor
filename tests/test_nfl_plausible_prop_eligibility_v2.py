"""Conservative v2 player/market research gating; pregame-only tests."""
from __future__ import annotations
from collections import defaultdict
from datetime import date,timedelta
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from nfl_research_prop_eligibility_v2 import (
 position_market_eligible,eligible_pregame_research_candidate,MARKET_POSITIONS)

def state_with_games(player_id="P",position="RB",games=8,asof="2024-01-01"):
 s={"player":defaultdict(list)}
 first=date.fromisoformat(asof)-timedelta(days=games*7+7)
 for n in range(games):
  gd=(first+timedelta(days=n*7)).isoformat()
  for market,value in (("carries",11.),("rushing yards",47.),
    ("rushing touchdowns",0.),("targets",4.),("receptions",3.),
    ("receiving yards",24.),("receiving touchdowns",0.),
    ("pass attempts",26.),("passing yards",212.),
    ("passing touchdowns",1.),("completions",19.)):
   s["player"][(market,player_id)].append({"gameday":gd,"value":value,"snaps":45.})
 return s

class StrictV2NFLPropMarketTests(unittest.TestCase):
 def test_reject_all_wr_rushing_props(self):
  for m in ("carries","rushing yards","rushing touchdowns"):
   self.assertFalse(position_market_eligible(m,"WR"))
 def test_reject_rb_receiving_touchdowns_unsupported_offer(self):
  self.assertFalse(position_market_eligible("receiving touchdowns","RB"))
  allowed,reason=eligible_pregame_research_candidate(state_with_games(),market="receiving touchdowns",
      player_id="P",position="RB",game_day="2024-09-01")
  self.assertFalse(allowed)
  self.assertEqual(reason,"position_market_not_plausible")
 def test_reject_qb_rushing_touchdown_without_quote(self):
  self.assertFalse(position_market_eligible("rushing touchdowns","QB"))
 def test_admit_receivers_for_td_and_backs_for_rushing_td(self):
  self.assertTrue(position_market_eligible("receiving touchdowns","WR"))
  self.assertTrue(position_market_eligible("receiving touchdowns","TE"))
  self.assertTrue(position_market_eligible("rushing touchdowns","RB"))
 def test_legitimate_rb_targets_and_rushing_have_pregame_usage(self):
  s=state_with_games()
  for m in ("targets","receptions","receiving yards","carries","rushing yards","rushing touchdowns"):
   with self.subTest(market=m):
    self.assertTrue(eligible_pregame_research_candidate(s,market=m,
       player_id="P",position="RB",game_day="2024-09-01")[0])
 def test_preweek_history_never_sees_future(self):
  s=state_with_games()
  s["player"][("carries","P")].append({"gameday":"2024-09-08","value":25.,"snaps":60.})
  with self.assertRaisesRegex(ValueError,"future_history"):
   eligible_pregame_research_candidate(s,market="carries",player_id="P",
        position="RB",game_day="2024-09-08")
 def test_no_source_can_reinterpret_gated_as_real_quote(self):
  from nfl_prop_offer_validation import validated_bookmaker_prop,OfferNotVerified
  with self.assertRaises(OfferNotVerified):
   validated_bookmaker_prop({"source_kind":"research_synthetic","player_id":"P",
                "market":"carries","line":11.5})
if __name__=="__main__":unittest.main()
