"""Adversarial independent WS6 postgame scoring tests (no original artifacts changed)."""
import json, math, unittest
from research.ws6_nfl_sunday_20261115.independent_postgame_20261116 import (
    assess, crps_sample, dedup, get_stat, interval_draw, norm, parse_boxscore, utc, paired, verify_joint_contract_identity
)
class TestIndependentPostgame(unittest.TestCase):
    def test_over_under_swap_detected(self):
        yes=assess(.9,0,5,4.5);no=assess(.1,0,5,4.5)
        self.assertLess(yes["brier"],no["brier"])
        self.assertEqual(yes["hit"],1);self.assertEqual(no["hit"],0)
    def test_integer_push_requires_explicit_three_way(self):
        s=assess(.4,.2,5,5)
        self.assertEqual(s["direction"],"PUSH")
        self.assertIsNone(s["brier"])
        self.assertAlmostEqual(s["three_way_logloss"],-math.log(.2))
    def test_nonpush_probability_conditional(self):
        s=assess(.3,.5,7,6.5)
        self.assertAlmostEqual(s["p_over_cond"],.6)
    def test_probability_integrity(self):
        self.assertIsNone(assess(.8,.4,5,6))
        self.assertIsNone(assess(float("nan"),0,5,6))
    def test_duplicate_books_collapsed(self):
        base={"model":"A","event":"e","player":"P","player_id":"1","market":"receptions",
              "line":4.5,"period":"full_game","p_over":.4,"p_push":0.,
              "mean":4.0,"brier":.16}
        dup=[dict(base),dict(base,quote_id="second")]
        good,bad=dedup(dup)
        self.assertEqual(len(good),1);self.assertEqual(good[0]["duplicate_quotes"],1)
        self.assertEqual(len(bad),0)
        good,bad=dedup([dict(base),dict(base,p_over=.5)])
        self.assertEqual(len(good),0);self.assertEqual(len(bad),1)
    def test_joint_original_contract_identity_red_team(self):
        original={"quote_id":"x","event_id":"game1","stat":"receptions","line":4.5,"player":"Player A"}
        good={"quote_id":"x","event_id":"game1","normalized_market":"receptions","period":"full_game","line":4.5,"original_record":{"player":"Player A"}}
        self.assertTrue(verify_joint_contract_identity(original,good))
        for field,wrong in (("quote_id","y"),("event_id","game2"),("normalized_market","receiving_yards"),("period","first_half"),("line",5.5)):
            with self.subTest(field=field),self.assertRaises(ValueError):
                verify_joint_contract_identity(original,dict(good,**{field:wrong}))
        with self.assertRaises(ValueError):
            verify_joint_contract_identity(original,dict(good,original_record={"player":"Player B"}))

    def test_wrong_game_cannot_match(self):
        fixtures={"1":{"_ids":{"a":{"id":"a","name":"Player A","team":"NE","stats":{"receptions":5},"present_categories":["receiving"],"defensive_parity_ok":True}},"_names":{norm("Player A"):{"a"}}}}
        self.assertEqual(get_stat("2","a","Player A","receptions",fixtures)[1],"EVENT_MISSING")
        self.assertEqual(get_stat("1","b","Player A","receptions",fixtures)[1],"PLAYER_NOT_BOXED")
        self.assertEqual(get_stat("1","a","Player B","receptions",fixtures)[1],"PLAYER_ID_NAME_CONFLICT")
        self.assertEqual(get_stat("1","a","Player A","pass_attempts",fixtures)[1],"CATEGORY_NOT_BOXED")
    def test_name_collision_quarantine(self):
        fixtures={"1":{"_ids":{},"_names":{norm("Same Player"):{"1","2"}}}}
        self.assertEqual(get_stat("1",None,"Same Player","receptions",fixtures)[1],"PLAYER_NAME_AMBIGUOUS")
    def test_missing_category_not_zero(self):
        mock={"header":{"competitions":[{"status":{"type":{"name":"STATUS_FINAL"}}}]},
              "boxscore":{"players":[{"team":{"abbreviation":"ATL"},"statistics":[
               {"name":"rushing","labels":["CAR","YDS"],"athletes":[{"athlete":{"id":"12","displayName":"Known Runner"},"stats":["2","14"]}]}]}]}}
        ids,names,errs=parse_boxscore("game",json.dumps(mock).encode())
        self.assertEqual(ids["12"]["stats"]["rush_attempts"],2)
        self.assertNotIn("receiving_targets",ids["12"]["stats"])
        self.assertEqual(get_stat("game","12","Known Runner","receiving_targets",{"game":{"_ids":ids,"_names":names}})[1],"CATEGORY_NOT_BOXED")
    def test_nonfinal_rejected(self):
        mock={"header":{"competitions":[{"status":{"type":{"name":"STATUS_IN_PROGRESS"}}}]},"boxscore":{"players":[]}}
        with self.assertRaises(ValueError):parse_boxscore("e",json.dumps(mock).encode())
    def test_pit_and_crps_small_law(self):
        self.assertAlmostEqual(crps_sample([0,1],0),.25)
        self.assertEqual(interval_draw([0,0,0,0],0,.9)[0],1)
    def test_timestamps_must_have_timezone(self):
        self.assertIsNone(utc("2026-11-15T18:00:00"))
        self.assertGreaterEqual(utc("2026-11-15T18:00:00Z"),utc("2026-11-15T17:00:00Z"))
    def test_game_matched_bootstrap(self):
        common={"player_id":"1","player":"P","market":"receptions","line":4.5,"period":"full_game","brier":.1}
        a=[dict(common,event="a"),dict(common,event="b",brier=.3)]
        b=[dict(common,event="a",brier=.4),dict(common,event="b",brier=.2)]
        x=paired(a,b,seed=12)
        self.assertEqual(x["matched"],2)
        self.assertEqual(x["games"],2)
        self.assertAlmostEqual(x["delta_a_minus_b"],-.1)
        self.assertEqual(x["date_cluster_ci"],"UNESTIMABLE_SINGLE_DATE")
if __name__=="__main__":unittest.main()
