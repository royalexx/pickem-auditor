"""Gate D bookmaker-original quoted-price math; no pretending pick'em operator terms."""
from __future__ import annotations
import unittest
from v2.phase15_market_research import decimal_price,chosen_book_edge,evaluate_market_research
from v2.official_nba_nhl_capture import SettlementCaptureError


def sample(*,prob=.60,line=1.5,actual="over"):
    return {"sport":"NHL","event_id":"g1","player_id":"p1",
            "stat":"shots on goal","line":line,
            "outcome":{"status":actual},
            "models":{
              "naive_recent_exposure_rate":{"status":"counterfactual_shadow","p_over_nonpush":prob},
              "pooled_peer_shrunk_rate":{"status":"counterfactual_shadow","p_over_nonpush":prob},
              "real_no_vig_market":{
                "status":"available",
                "source":"original_pregame_two_sided_bookmaker_via_PropLine",
                "p_over_nonpush":.5,"book":"Pinnacle",
                "over_american":-110,"under_american":-110
              }
            }}


class OfficialBookmarketResearchTests(unittest.TestCase):
    def test_decimal_american_odds(self):
        self.assertAlmostEqual(decimal_price(-110),1+100/110)
        self.assertAlmostEqual(decimal_price(150),2.5)

    def test_prohibit_unrealistic_or_broken_prices(self):
        for p in (0,-50,50,99,-99):
            with self.assertRaises(SettlementCaptureError):decimal_price(p)

    def test_select_over_only_when_above_book_break_even(self):
        c=sample(prob=.6)
        x=chosen_book_edge(c,"naive_recent_exposure_rate")
        self.assertEqual(x["side"],"over")
        self.assertGreater(x["model_implied_roi_if_true"],0)
        self.assertAlmostEqual(x["book_vig"],2*(1/(1+100/110))-1)

    def test_select_under_when_model_says_unders_have_price_edge(self):
        c=sample(prob=.30)
        self.assertEqual(chosen_book_edge(c,"pooled_peer_shrunk_rate")["side"],"under")

    def test_near_market_50pct_does_not_mint_edge(self):
        c=sample(prob=.50)
        self.assertIsNone(chosen_book_edge(c,"naive_recent_exposure_rate")["side"])

    def test_integer_line_requires_official_push_policy(self):
        c=sample(line=2)
        self.assertEqual(chosen_book_edge(c,"naive_recent_exposure_rate")["status"],
                         "unsupported_integer_line_push_payoff")

    def test_no_pickem_roi_or_promotion_claim_from_one_settled_game(self):
        c=sample(prob=.6)
        phase={"schema":"v25-phase1-nhl-nba-certified-replay-v1",
               "tier1_tier2_publication_allowed":False,
               "prepared_attempt_count":2,"contracts":[c]}
        r=evaluate_market_research(phase)
        self.assertEqual(r["matched_models"]["naive_recent_exposure_rate"][
            "counterfactual_selected_settled"],1)
        self.assertIs(r["pickem_operator_payout_multiplier_proven"],False)
        self.assertFalse(r["production_model_promotion_allowed"])
        self.assertIn("BLOCKED",r["economic_edge_gate"])

    def test_fake_book_source_rejected(self):
        c=sample()
        c["models"]["real_no_vig_market"]["source"]="invented_odds"
        with self.assertRaisesRegex(SettlementCaptureError,"unverified_original"):
            chosen_book_edge(c,"naive_recent_exposure_rate")


if __name__=="__main__":
    unittest.main()
