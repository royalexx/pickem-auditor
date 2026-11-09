"""Adversarial same-game leg-dependence and T+A safety tests."""
from __future__ import annotations
from datetime import date,timedelta
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import reform_step9_game_leg_dependence as s


def contract(*,p=.65,y="over",player="p1",name="Test Player",
             stat="targets",line=4.5,team="BUF",game="g1",
             day="2026-11-08",model="Market",sport="NFL"):
    value={"over":p,"under":1-p,"side":"over" if p>.5 else "under",
           "p":max(p,1-p),"hit":int((p>.5 and y=="over") or (p<.5 and y=="under")),
           "side_sum":1.0,"winner":y}
    return {"sport":sport,"stat":stat,"date":day,"game_id":game,
            "outcome":y,"contract":(sport,day+"T18:00:00Z",team,
                    "BAL" if team=="BUF" else "BUF",player,name,stat,
                    format(line,".15g")),
            "models":{model:value}}


def historical(*,p=.63,y="over",player="Name",stat="receptions",
               game="G1",day="2026-11-05",team="BAL"):
    value={"over":p,"under":1-p,"side":"over" if p>.5 else "under",
           "p":max(p,1-p),"hit":int((p>.5 and y=="over") or (p<.5 and y=="under")),
           "winner":y}
    return {"sport":"NFL","stat":stat,"date":day,"game_id":game,
            "outcome":y,"contract":(day,"NFL",game,team,player,stat,"3.5"),
            "models":{"Engine_A":value}}


class Step9LegDependenceTests(unittest.TestCase):
    def test_two_sides_one_contract_and_invalid_source_pair_fails_closed(self):
        r=contract()
        legs,ex=s.validated_legs([r],model="Market",source="nov8_current")
        self.assertEqual(len(legs),1)
        self.assertEqual(legs[0]["hit"],1)
        self.assertEqual(legs[0]["p"],.65)
        broken=copy.deepcopy(r)
        broken["models"]["Market"]["under"]=.4
        missing,ex=s.validated_legs([broken],model="Market",source="nov8_current")
        self.assertEqual(missing,[])
        self.assertEqual(ex,{"noncomplementary_or_invalid_original_pair":1})

    def test_duplicate_contract_is_not_independent_extra_leg(self):
        r=contract()
        with self.assertRaisesRegex(s.LegDependenceError,"duplicate_original_settled_contract"):
            s.validated_legs([r,r],model="Market",source="nov8_current")

    def test_historical_source_layout_and_original_side_identity(self):
        r=historical()
        got,ex=s.validated_legs([r],model="Engine_A",source="nov5_7_retrospective")
        self.assertEqual(len(got),1)
        self.assertEqual(got[0]["player_id"],"Name")
        r["models"]["Engine_A"]["hit"]=0
        with self.assertRaisesRegex(s.LegDependenceError,"legacy_side_inconsistent"):
            s.validated_legs([r],model="Engine_A",source="nov5_7_retrospective")

    def test_same_player_same_stat_different_line_excluded(self):
        rows=[
            contract(player="p1",stat="targets",line=4.5),
            contract(player="p1",stat="targets",line=5.5),
            contract(player="p1",stat="receptions",line=3.5),
            contract(player="p2",stat="targets",line=4.5),
        ]
        audit=s.dependence_audit(rows,model="Market",source="nov8_current")
        self.assertEqual(audit["eligible_one_side_per_contract"],4)
        self.assertEqual(audit["dropped_same_player_stat_pairs"],1)
        self.assertEqual(audit["all_same_game_pairs"]["n_pairs"],5)
        self.assertEqual(
            audit["by_relationship"]["same_player_different_stats"]["n_pairs"],2)
        self.assertFalse(audit["multi_leg_probability_authorized"])

    def test_exact_pair_product_residual_and_shared_fixture(self):
        rows=[contract(p=.7,y="over",player="A",team="BUF"),
              contract(p=.6,y="under",player="B",team="BUF")]
        a,b=[s.leg(x,model="Market",source="nov8_current")[0] for x in rows]
        pair=s.pair_receipt(a,b)
        self.assertEqual(pair["relationship"],"same_team_distinct_players")
        self.assertAlmostEqual(pair["independence_product"],.42)
        self.assertAlmostEqual(pair["joint_hit"],0)
        self.assertAlmostEqual(pair["joint_excess"],-.42)
        self.assertAlmostEqual(pair["residual_product"],(.3)*(-.6))
        self.assertIsNone(s.pair_category(a,{**b,"game_id":"other"})) if False else None
        with self.assertRaisesRegex(s.LegDependenceError,"pair_must_share_game"):
            s.pair_receipt(a,{**b,"game_id":"other"})

    def test_opposing_team_distinct_player_class(self):
        rows=[contract(player="A",team="BUF"),
              contract(player="B",team="BAL")]
        a,b=[s.leg(x,model="Market",source="nov8_current")[0] for x in rows]
        self.assertEqual(s.pair_receipt(a,b)["relationship"],
                         "opposing_teams_distinct_players")

    def test_single_game_many_pairs_still_no_confidence_interval(self):
        rows=[contract(player=f"A{i}",stat="targets",p=.6)
              for i in range(40)]
        result=s.dependence_audit(rows,model="Market",source="nov8_current")
        self.assertEqual(result["all_same_game_pairs"]["n_pairs"],780)
        self.assertEqual(result["all_same_game_pairs"]["n_games"],1)
        self.assertEqual(result["all_same_game_pairs"]["n_dates"],1)
        self.assertIsNone(result["all_same_game_pairs"]["interval_95"])
        self.assertEqual(result["all_same_game_pairs"]["status"],
                         "insufficient_independent_games_or_dates")

    def test_many_games_on_two_dates_still_cannot_certify_correlation(self):
        rows=[]
        for i in range(30):
            day="2026-11-08" if i<15 else "2026-11-09"
            rows.extend([contract(player=f"P{i}_A",game=f"G{i}",day=day),
                         contract(player=f"P{i}_B",game=f"G{i}",day=day)])
        result=s.dependence_audit(rows,model="Market",source="nov8_current")
        self.assertEqual(result["all_same_game_pairs"]["n_games"],30)
        self.assertIsNone(result["all_same_game_pairs"]["interval_95"])

    def test_sufficient_games_and_dates_bootstrap_game_not_pair(self):
        rows=[]
        for i in range(40):
            day=(date(2026,9,1)+timedelta(days=i)).isoformat()
            for j in range(5):
                rows.append(contract(player=f"P{i}_{j}",game=f"G{i}",
                                     day=day,p=.65 if j%2 else .55,
                                     y="over" if j%3 else "under"))
        result=s.dependence_audit(rows,model="Market",source="nov8_current",draws=200)
        score=result["all_same_game_pairs"]
        self.assertEqual(score["n_games"],40)
        self.assertEqual(score["n_dates"],40)
        self.assertEqual(score["n_pairs"],400)
        self.assertEqual(len(score["interval_95"]),2)
        self.assertEqual(score["pair_weighting"],"equal_game_weight_not_independent_pair_rows")
        self.assertEqual(
            result,s.dependence_audit(rows,model="Market",source="nov8_current",draws=200))

    def test_cross_game_control_requires_other_game_and_same_market(self):
        rows=[contract(player="A",game="G1",stat="targets"),
              contract(player="B",game="G2",stat="targets"),
              contract(player="C",game="G2",stat="carries")]
        legs,_=s.validated_legs(rows,model="Market",source="nov8_current")
        neg=s.cross_game_same_day_control(legs)
        self.assertEqual(len(neg),2)
        self.assertTrue(all(x["relationship"]=="cross_game_same_date_stat_control"
                            for x in neg))
        self.assertEqual(s.cross_game_same_day_control(legs[:1]),[])

    def test_frechet_bounds_not_a_fake_independence_joint_probability(self):
        out=s.frechet_entry_bounds([.7,.6])
        self.assertAlmostEqual(out["frechet_lower_bound"],.3)
        self.assertAlmostEqual(out["frechet_upper_bound"],.6)
        self.assertAlmostEqual(out["independence_product_for_comparison_only"],.42)
        self.assertFalse(out["joint_probability_approved"])
        self.assertFalse(out["payout_ev_approved"])
        four=s.frechet_entry_bounds([.8]*4)
        self.assertAlmostEqual(four["frechet_lower_bound"],.2)
        self.assertAlmostEqual(four["frechet_upper_bound"],.8)
        with self.assertRaisesRegex(s.LegDependenceError,"invalid_leg_marginal"):
            s.frechet_entry_bounds([.7,float("nan")])


if __name__=="__main__":
    unittest.main()
