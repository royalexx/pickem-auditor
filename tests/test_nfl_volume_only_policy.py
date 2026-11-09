"""End-to-end NFL volume-only ranking and blind replay policy invariants."""
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from nfl_volume_market_policy import NFL_VOLUME_MARKETS, NFL_EXCLUDED_MARKETS, nfl_volume_market_allowed
from nfl_prop_offer_validation import validated_bookmaker_prop, rank_verified_props, OfferNotVerified
from nfl_weekly_blind_volume_only import MARKETS, eligible
from slate_candidate_ranking import candidate

class VolumeOnlyPolicy(unittest.TestCase):
    def test_exact_market_registry(self):
        self.assertEqual(set(MARKETS),set(NFL_VOLUME_MARKETS))
        self.assertEqual(len(MARKETS),11)

    def test_all_touchdown_and_sparse_markets_blocked(self):
        for m in ("passing touchdowns","receiving touchdowns","rushing touchdowns",
                  "anytime td","anytime touchdown","anytime touchdown scorer",
                  "touchdowns","qb hits","passes defended"):
            with self.subTest(m=m):
                self.assertFalse(nfl_volume_market_allowed("NFL",m))
                self.assertNotIn(m,MARKETS)

    def test_nfl_unknown_market_rejected(self):
        self.assertFalse(nfl_volume_market_allowed("NFL","weird prop"))
        self.assertFalse(nfl_volume_market_allowed("NFL",None))

    def test_other_sports_not_affected(self):
        for sport in ("NHL","NBA"):
            self.assertTrue(nfl_volume_market_allowed(sport,"goals"))
            self.assertTrue(nfl_volume_market_allowed(sport,"saves"))

    def test_wr_rush_and_defensive_mismatch_excluded(self):
        for m in ("carries","rushing yards"):
            self.assertFalse(eligible(m,"WR"))
            self.assertTrue(eligible(m,"RB"))
        self.assertFalse(eligible("targets","QB"))
        self.assertTrue(eligible("tackles + assists","LB"))

    def offer(self,market="targets"):
        return dict(source_kind="bookmaker_quote",market_available=True,
            player_active_asof=True,identity_verified=True,player_id="P",
            game_id="G",market=market,bookmaker="B",quote_id="Q",
            source_sha256="a"*64,kickoff="2024-09-08T18:00:00Z",
            quoted_at="2024-09-08T17:00:00Z",
            roster_status_available_at="2024-09-08T16:00:00Z",
            line=5.5,over_decimal_odds=2.1,under_decimal_odds=1.8)

    def test_verified_offer_cannot_bypass_exclusion(self):
        for market in ("rushing touchdowns","passing touchdowns",
                       "receiving touchdowns","qb hits","passes defended"):
            with self.subTest(market=market):
                with self.assertRaisesRegex(OfferNotVerified,"volume_only"):
                    validated_bookmaker_prop(self.offer(market))
                self.assertEqual(rank_verified_props([dict(player_id="P",game_id="G",
                      market=market,p_over=.9,p_under=.1,p_push=0,
                      offer=self.offer(market))]),[])

    def test_approved_market_without_offer_abstains(self):
        self.assertEqual(rank_verified_props([dict(player_id="P",game_id="G",
                    market="targets",p_over=.7,p_under=.3)]),[])

    def test_volume_market_quote_eligible_for_rank(self):
        p=dict(player_id="P",game_id="G",market="targets",
            p_over=.7,p_under=.3,p_push=0.,offer=self.offer("targets"))
        got=rank_verified_props([p])
        self.assertEqual(len(got),1)
        self.assertEqual(got[0]["market"],"targets")
        self.assertEqual(got[0]["side"],"over")

    def test_research_top10_gate_rejects_excluded_before_other_checks(self):
        for m in ("rushing touchdowns","qb hits","passes defended"):
            _,reason=candidate(dict(sport="NFL",stat=m),{},data_root=ROOT)
            self.assertEqual(reason,"nfl_market_excluded_volume_only_policy")

if __name__=="__main__":unittest.main()
