"""Adversarial tests for P2 2024 target-only subexperiment, not route P2."""
from __future__ import annotations
from copy import deepcopy
import unittest

from scripts.v25_phase2_target_only_forecast import forecast


def fixture(week=1):
    games=[]
    # Synthetic prior 2021–2023 team games never read outcomes in 2024.
    for season in (2021,2022,2023):
        for game in range(210):
            team="A" if game%2 else "B"
            games.append({
              "event_id":f"synthetic-{season}-{game}",
              "season":season,"week":game%18+1,
              "team":team,
              "pass_attempts":30+game%7,
              "players":{
                "receiver_A" if team=="A" else "receiver_B":{
                    "role":"WR","targets":5+game%3},
                "tightend_A" if team=="A" else "tightend_B":{
                    "role":"TE","targets":3+game%2},
              },
            })
    # 1260 team games, satisfying minimum initial cohort.
    out={
      "schema":"v25-p2-target-only-asof-week-v1",
      "week":week,"history":games,
      "schedule":[{"event_id":"synthetic-2024-week-"+str(week),
                   "team":"A","opponent":"B","week":week}],
    }
    for prior in range(1,week):
        out["history"].append({
          "event_id":f"synthetic-2024-{prior}",
          "season":2024,"week":prior,
          "team":"A","pass_attempts":31,
          "players":{"receiver_A":{"role":"WR","targets":6}}
        })
    return out


class TestPhase2TargetOnlyIsolation(unittest.TestCase):
    def test_week_one_starts_with_no_2024_training(self):
        report=forecast(fixture(),samples=128)
        self.assertEqual(report["train_2024_max_week"],0)
        self.assertEqual(report["initial_training_game_count"],1260)
        self.assertFalse(report["future_outcomes_exposed_to_forecaster"])
        self.assertFalse(report["source_data_asof_publication_independently_certified"])

    def test_prior_week_only_and_repeat_seed(self):
        first=forecast(fixture(3),samples=128,seed=45)
        copy=forecast(fixture(3),samples=128,seed=45)
        self.assertEqual(first,copy)
        self.assertEqual(first["train_2024_max_week"],2)
        self.assertNotEqual(first,forecast(fixture(3),samples=128,seed=46))

    def test_lookahead_history_poisoned_weeks_rejected(self):
        for future in (3,4,18):
            p=fixture(3)
            p["history"].append({
               "event_id":"poison-current-or-future", "season":2024,
               "week":future,"team":"A","pass_attempts":99999,
               "players":{},
            })
            with self.assertRaisesRegex(ValueError,"current_or_future_week_observation"):
                forecast(p,samples=128)
        poison=fixture(1)
        poison["history"].append({
          "event_id":"2025-leak","season":2025,"week":1,"team":"A",
          "pass_attempts":30,"players":{},
        })
        with self.assertRaisesRegex(ValueError,"current_or_future_week_observation"):
            forecast(poison,samples=128)

    def test_current_game_postgame_total_cannot_enter_schedule(self):
        for field in ("pass_attempts","targets","final_score","routes",
                      "snap_counts","team_final_plays"):
            p=fixture()
            p["schedule"][0][field]=52
            with self.assertRaisesRegex(ValueError,"schedule_contains_outcome"):
                forecast(p,samples=128)

    def test_zero_team_target_accounting_errors(self):
        p=fixture()
        p["history"][0]["players"]["receiver_B"]["targets"]=99
        with self.assertRaisesRegex(ValueError,"historical_targets_exceed_pass_attempts"):
            forecast(p,samples=128)

    def test_targets_conserved_across_shared_team_attempt_scenarios(self):
        out=forecast(fixture(),samples=128)
        row=out["forecasts"][0]
        for mode in ("updated","no_refit"):
            x=row["models"][mode]
            self.assertTrue(x["all_targets_conserved"])
            self.assertFalse(x["original_current_week_roster_verified"])
            for i,a in enumerate(x["pass_attempts"]):
                total=sum(v[i] for v in x["player_targets"].values())
                self.assertLessEqual(total,a)
                self.assertGreaterEqual(a-total,0)
            self.assertIn("receiver_A",x["player_targets"])

    def test_original_game_roster_from_future_not_accepted_as_training(self):
        p=fixture()
        p["history"].append({
           "event_id":p["schedule"][0]["event_id"],
           "season":2024,"week":1,"team":"A",
           "pass_attempts":101,
           "players":{"future_rookie":{"role":"WR","targets":20}},
        })
        with self.assertRaisesRegex(ValueError,"current_or_future_week"):
            forecast(p,samples=128)

    def test_missing_current_roster_names_do_not_become_false_zeros(self):
        out=forecast(fixture(),samples=128)
        players=out["forecasts"][0]["models"]["updated"]["player_targets"]
        self.assertNotIn("future_rookie",players)
        self.assertTrue(out["fixed_count_roster_proxy_not_true_routes"])


if __name__=="__main__":
    unittest.main()
