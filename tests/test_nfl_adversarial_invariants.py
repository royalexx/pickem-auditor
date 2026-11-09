"""Numerical and replay protection tests for 2024 adversarial NFL audit."""
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))

from bayesian_engine import student_t_cdf
from nfl_research_hybrid_lines import hybrid_research_line
from nfl_weekly_blind_multimarket_hybrid import probability_over, make_state
from nfl_2024_adversarial_release_gate import binary_scores


class NumericalProbabilityAudit(unittest.TestCase):
    def test_student_t_cdf_matches_scipy(self):
        from scipy.stats import t
        for df in (2.1,3.,5.,8.,10.,30.,100.):
            for x in (-16.,-8.,-3.,-.5,0.,.5,3.,8.,16.):
                with self.subTest(df=df,x=x):
                    self.assertAlmostEqual(student_t_cdf(x,df),float(t.cdf(x,df)),delta=1e-9)

    def test_count_and_continuous_probabilities_match_scipy(self):
        from scipy.stats import nbinom, norm
        for mu in (.01,.5,3.,8.,30.,120.):
            for line in (.5,1.5,4.5,8.5,30.5):
                with self.subTest(mu=mu,line=line):
                    expected=float(nbinom.sf(math.floor(line),8.,8./(8.+mu)))
                    got=probability_over(mu,line,"targets",10.)
                    self.assertAlmostEqual(expected,got,delta=1e-11)
        for mu in (0.,10.,50.,150.):
            for line in (.5,5.5,20.5,50.5):
                with self.subTest(mu=mu,line=line):
                    self.assertAlmostEqual(probability_over(mu,line,"receiving yards",17.),
                                           float(norm.sf(line,loc=mu,scale=17.)),delta=1e-11)

    def test_log1p_retransformation_underestimates_arithmetic_mean(self):
        xs=[0.,0.,0.,0.,20.,20.]
        biased=math.expm1(sum(math.log1p(x) for x in xs)/len(xs))
        expected=sum(xs)/len(xs)
        self.assertLess(biased,expected*.5)

    def test_game_history_leak_is_blocked(self):
        state=make_state()
        state["player"][("tackles + assists","P")]=[
            {"gameday":"2024-09-08","value":9.,"snaps":70}]
        with self.assertRaisesRegex(ValueError,"future_or_current_week_leak"):
            hybrid_research_line(state,market="tackles + assists",player_id="P",
                                 position="MLB",game_day="2024-09-08")
        line,e=hybrid_research_line(state,market="tackles + assists",player_id="P",
                                   position="MLB",game_day="2024-09-15")
        self.assertGreaterEqual(line,.5)
        self.assertEqual(e["history_games"],1)

    def test_hybrid_uses_50_30_20_when_history_sufficient(self):
        s=make_state()
        s["player"][("tackles + assists","P")]=[
            {"gameday":f"2023-10-{i:02d}","value":v}
            for i,v in enumerate([2,4,6,8,10,12,14,16,18,20],1)]
        line,e=hybrid_research_line(s,market="tackles + assists",
                    player_id="P",position="MLB",game_day="2024-09-01")
        expected=.5*16+.3*11+.2*8.5
        self.assertEqual(line,math.floor(expected)+.5)
        self.assertAlmostEqual(e["w5"],.5)
        self.assertAlmostEqual(e["w10"],.3)
        self.assertAlmostEqual(e["w_role"],.2)

    def test_negative_yards_not_deleted(self):
        s=make_state()
        s["player"][("rushing yards","P")]=[
            {"gameday":"2023-11-01","value":-6.}]
        line,_=hybrid_research_line(s,market="rushing yards",
             player_id="P",position="RB",game_day="2024-01-01")
        self.assertTrue(math.isfinite(line))
        self.assertGreaterEqual(line,.5)

    def test_gate_scores_respect_realized_outcome_not_reported_accuracy(self):
        rows=[
        {"actual_over":"1","model_p_over":"0.9","baseline_p_over":"0.5","hit":"1","predicted_side":"over","selected_model_probability":"0.9"},
        {"actual_over":"0","model_p_over":"0.1","baseline_p_over":"0.5","hit":"1","predicted_side":"under","selected_model_probability":"0.9"}]
        result=binary_scores(rows)
        self.assertEqual(result["n"],2)
        self.assertEqual(result["accuracy"],1.)
        self.assertEqual(result["always_under_accuracy"],.5)
        self.assertAlmostEqual(result["brier_model"],.01)

    def test_hybrid_does_not_report_bookmaker_source(self):
        line,e=hybrid_research_line(make_state(),market="tackles + assists",
                    player_id="Rookie",position="MLB",game_day="2024-09-01")
        self.assertTrue(e["synthetic_not_bookmaker"])
        self.assertEqual(line,8.5)


class VerifiedOfferSafetyTests(unittest.TestCase):
    def offer(self):
        return dict(source_kind="bookmaker_quote",market_available=True,
           player_active_asof=True,identity_verified=True,
           player_id="P",game_id="G",market="tackles + assists",
           bookmaker="book",quote_id="quote-123",source_sha256="a"*64,
           kickoff="2024-09-08T18:00:00Z",quoted_at="2024-09-08T17:00:00Z",
           roster_status_available_at="2024-09-08T16:00:00Z",
           line=8.5,over_decimal_odds=1.91,under_decimal_odds=1.91)

    def test_bookmaker_offer_validation_requires_quotes_and_availability(self):
        from nfl_prop_offer_validation import validated_bookmaker_prop,OfferNotVerified
        o=self.offer()
        verified=validated_bookmaker_prop(o)
        self.assertTrue(verified["availability_verified"])
        self.assertEqual(verified["line_source"],"verified_bookmaker_quote")
        for key,value in (("source_kind","hybrid_research"),("market_available",False),
                          ("player_active_asof",False),("identity_verified",False),
                          ("quoted_at","2024-09-09T01:00:00Z")):
            with self.subTest(key=key):
                z={**o,key:value}
                with self.assertRaises(OfferNotVerified):validated_bookmaker_prop(z)

    def test_market_selection_abstains_when_research_line_only(self):
        from nfl_prop_offer_validation import rank_verified_props
        p=dict(player_id="P",game_id="G",market="tackles + assists",
            p_over=.99,p_under=.01,p_push=0.)
        self.assertEqual(rank_verified_props([p]),[])
        self.assertEqual(rank_verified_props([{**p,"offer":{
            **self.offer(),"source_kind":"hybrid_research"}}]),[])

    def test_verified_positive_ev_can_rank_but_no_fake_quota(self):
        from nfl_prop_offer_validation import rank_verified_props
        p=dict(player_id="P",game_id="G",market="tackles + assists",
            p_over=.65,p_under=.35,p_push=0.,offer=self.offer())
        chosen=rank_verified_props([p])
        self.assertEqual(len(chosen),1)
        self.assertEqual(chosen[0]["side"],"over")
        self.assertGreater(chosen[0]["expected_value_per_unit"],0)


if __name__=="__main__":unittest.main()
