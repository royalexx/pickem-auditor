"""Leakage, sequencing, and accounting tests for weekly NFL replay."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import nfl_2024_weekly_walkforward as wf
import nfl_pre2024_xgb_replay as common


class WalkforwardGuardTests(unittest.TestCase):
    def test_future_dates_strict(self):
        self.assertTrue(wf.reject_future(
            [{"game_date":"2024-09-05"}],"2024-09-08"))
        with self.assertRaisesRegex(RuntimeError,"future_week"):
            wf.reject_future([{"game_date":"2024-09-08"}],"2024-09-08")
        with self.assertRaisesRegex(RuntimeError,"future_week"):
            wf.reject_future([{"game_date":"2024-09-09"}],"2024-09-08")

    def test_oracle_refuses_to_reveal_until_forecast_is_sha_locked(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with self.assertRaisesRegex(RuntimeError,"oracle_reveal_before"):
                wf.oracle_reveal(root,root/"private",1)
            common.atomic_new(root/"FROZEN"/"week_01.json",{
                "week":1,"stage":"before_week_outcomes","predictions":[]})
            self.assertEqual(len(wf.lock_sha(root,1)),64)
            with self.assertRaises(FileNotFoundError):
                wf.oracle_reveal(root,root/"private",1)

    def test_2024_roster_only_after_revealed_week(self):
        state={"latest_by_player":{
            "a":{"season":2023,"gameday":"2023-12-30",
                 "team":"KC","position":"QB"},
            "b":{"season":2024,"gameday":"2024-09-05",
                 "team":"KC","position":"QB"},
        }}
        old=wf.hybrid.CUTOFF
        try:
            wf.hybrid.CUTOFF=wf.date(2024,9,5)
            r=wf.online_roster(state,["KC"])
            # b played later that day; same-week outcome must NOT appear.
            self.assertEqual(r["KC"],[("a","QB")])
            wf.hybrid.CUTOFF=wf.date(2024,9,12)
            r=wf.online_roster(state,["KC"])
            self.assertEqual(r["KC"],[("b","QB")])
        finally:
            wf.hybrid.CUTOFF=old

    def test_player_history_after_current_week_rejected(self):
        state={k:{} for k in ("player","role","team_offense","opponent_allowed",
                               "league_offense","ngs")}
        state["player"]={("targets","x"):[{"gameday":"2024-09-08","season":2024}]}
        old=wf.hybrid.CUTOFF
        try:
            wf.hybrid.CUTOFF=wf.date(2024,9,8)
            with self.assertRaisesRegex(RuntimeError,"unrevealed_or_same_week"):
                wf.assert_player_state_past(state)
            wf.hybrid.CUTOFF=wf.date(2024,9,12)
            self.assertTrue(wf.assert_player_state_past(state))
        finally:
            wf.hybrid.CUTOFF=old

    def test_never_count_unmatched_as_zero_or_loss(self):
        forecasts=[
            {"game_id":"2024_01_BAL_KC","player_id":"a","market":"targets",
             "research_line":1.5,"p_over":.8,"p_over_hurdle":.85,
             "p_over_no_refit":.79,"p_over_player_prior":.7,
             "p_over_static_player":.65},
            {"game_id":"2024_01_BAL_KC","player_id":"missing","market":"targets",
             "research_line":1.5,"p_over":.2,"p_over_hurdle":.22,
             "p_over_no_refit":.21,"p_over_player_prior":.3,
             "p_over_static_player":None},
        ]
        data=[{"game_id":"2024_01_BAL_KC","player_id":"a",
               "stat":"targets","value":2.}]
        full,graded=wf.score(forecasts,data)
        self.assertEqual(len(full),2)
        self.assertEqual(len(graded),1)
        self.assertIsNone(full[1]["actual_stat"])
        self.assertEqual(wf.metrics(graded)["p_over_hurdle"]["accuracy"],1.)
        self.assertEqual(wf.metrics(graded)["p_over_hurdle"]["n"],1)


if __name__=="__main__":
    unittest.main()
