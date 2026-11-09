"""Plausible NFL prop-market eligibility and pregame-history tests."""
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from nfl_research_prop_eligibility import (
    MARKET_POSITIONS,position_market_eligible,eligible_pregame_research_candidate
)

def example_state(played=7,latest="2023-12-17",player_id="P",position="WR"):
    from collections import defaultdict
    from datetime import date,timedelta
    d=date.fromisoformat(latest)
    state={"player":defaultdict(list)}
    for i in range(played):
        gd=(d-timedelta(days=7*(played-i-1))).isoformat()
        for m,val in [("targets",6.),("receptions",4.),("receiving yards",65.),
                      ("receiving touchdowns",0.),("carries",1.),
                      ("rushing yards",5.),("rushing touchdowns",0.),
                      ("tackles + assists",7.),("solo tackles",5.),
                      ("tackle assists",2.),("qb hits",1.),("passes defended",1.)]:
            state["player"][(m,player_id)].append(
             {"gameday":gd,"snaps":65.,"value":val,"position":position})
    return state

class PlausiblePropEligibilityTests(unittest.TestCase):
    def test_wr_rushing_props_never_generated(self):
        for market in ("carries","rushing yards","rushing touchdowns"):
            self.assertFalse(position_market_eligible(market,"WR"))
            self.assertEqual(eligible_pregame_research_candidate(example_state(),
               market=market,position="WR",player_id="P",game_day="2024-09-08")[0],False)

    def test_qb_not_eligible_to_receive(self):
        for market in ("targets","receptions","receiving yards","receiving touchdowns"):
            self.assertFalse(position_market_eligible(market,"QB"))

    def test_correct_offensive_positions(self):
        for market in ("pass attempts","completions","passing yards","passing touchdowns"):
            self.assertEqual(MARKET_POSITIONS[market],frozenset({"QB"}))
        for market in ("carries","rushing yards","rushing touchdowns"):
            self.assertEqual(MARKET_POSITIONS[market],frozenset({"QB","RB"}))

    def test_qb_hits_secondary_not_eligible(self):
        for position in ("CB","DB","S","FS","SS"):
            self.assertFalse(position_market_eligible("qb hits",position))

    def test_dl_passes_defended_not_market_proxy(self):
        for position in ("DE","DT","NT"):
            self.assertFalse(position_market_eligible("passes defended",position))

    def test_wr_receiving_market_positive_past_usage(self):
        state=example_state()
        for m in ("targets","receptions","receiving yards","receiving touchdowns"):
            permitted,reason=eligible_pregame_research_candidate(state,
               market=m,position="WR",player_id="P",game_day="2024-09-08")
            self.assertTrue(permitted,(m,reason))

    def test_not_enough_prior_games_abstains(self):
        state=example_state(played=2)
        result=eligible_pregame_research_candidate(state,market="targets",position="WR",
                      player_id="P",game_day="2024-09-08")
        self.assertEqual(result,(False,"insufficient_prior_player_appearances"))

    def test_low_targets_abstain_even_with_history(self):
        state=example_state()
        for r in state["player"][("targets","P")]:r["value"]=0.
        permitted,reason=eligible_pregame_research_candidate(state,market="receiving touchdowns",
                        position="WR",player_id="P",game_day="2024-09-08")
        self.assertEqual((permitted,reason),(False,"insufficient_receiving_opportunity"))

    def test_future_history_aborts_not_skips(self):
        state=example_state(latest="2024-09-09")
        with self.assertRaisesRegex(ValueError,"future_history"):
            eligible_pregame_research_candidate(state,market="targets",position="WR",
                         player_id="P",game_day="2024-09-08")

    def test_rushing_yards_rb_requires_carry_opportunity(self):
        s=example_state(position="RB")
        s["player"][("rushing yards","P")][-1]["value"]=-4.
        self.assertEqual(eligible_pregame_research_candidate(s,market="rushing yards",
             position="RB",player_id="P",game_day="2024-09-08"),
             (False,"insufficient_rushing_opportunity"))
        for r in s["player"][("carries","P")]:r["value"]=12.
        self.assertTrue(eligible_pregame_research_candidate(s,market="rushing yards",
             position="RB",player_id="P",game_day="2024-09-08")[0])

    def test_cannot_conflate_research_eligibility_with_verified_bookmaker(self):
        from nfl_prop_offer_validation import validated_bookmaker_prop,OfferNotVerified
        s=example_state()
        ok,_=eligible_pregame_research_candidate(s,market="targets",
                    position="WR",player_id="P",game_day="2024-09-08")
        self.assertTrue(ok)
        with self.assertRaises(OfferNotVerified):
            validated_bookmaker_prop({
             "source_kind":"research_synthetic","player_id":"P",
             "market":"targets","line":6.5,"market_available":True})

if __name__=="__main__":unittest.main()
