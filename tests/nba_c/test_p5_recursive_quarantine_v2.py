"""Versioned P5 repair controls. All cases are synthetic before holdout."""
from copy import deepcopy
import unittest

from v2.nba_c import experiment as e
from tests.nba_c.test_p5_c_family import fixture


def wrap(value, shape):
    for kind in shape:
        value = {"nested": value} if kind == "dict" else [value, 0.25]
    return value


SHAPES = ((), ("dict",), ("list",), ("list", "list"),
          ("dict", "list", "dict", "list"), ("list", "dict", "list"))
FORBIDDEN = {"actual": 1, "actual_stats": {"points": 1}, "actual_minutes": 37,
             "target_game_outcome": {"points": 1},
             "official_available_at": "2022-10-21T00:00:00Z",
             "event_end_at": "2022-10-20T23:59:00Z"}


class RecursiveForecastQuarantineV2(unittest.TestCase):
    def cache(self, row):
        return e.CachedCohort([row], authorization="SYNTHETIC_UNIT_TEST")

    def test_forbidden_results_at_every_container_depth(self):
        for key, value in FORBIDDEN.items():
            for shape in SHAPES:
                row = fixture()
                row["pipelines"]["S0"]["model_inputs"] = wrap({key: value}, shape)
                with self.subTest(key=key, shape=shape), self.assertRaisesRegex(
                        e.ExperimentError, "OUTCOME_IN_FORECAST_PIPELINE"):
                    self.cache(row)

    def test_nested_list_postfreeze_clock(self):
        for shape in SHAPES:
            row = fixture()
            row["pipelines"]["S0"]["model_inputs"] = wrap(
                {"source_available_at": "2022-10-20T18:00:00Z"}, shape)
            with self.subTest(shape=shape), self.assertRaisesRegex(
                    e.ExperimentError, "POST_FREEZE"):
                self.cache(row)

    def test_nested_list_identity(self):
        for shape in SHAPES:
            for key, bad in (("game_id", "nba:wrong"), ("player_id", "nba:wrong"),
                             ("source_profile", "historical_reconstruction")):
                row = fixture()
                row["pipelines"]["S0"]["model_inputs"] = wrap({key: bad}, shape)
                with self.subTest(shape=shape, key=key), self.assertRaisesRegex(
                        e.ExperimentError, "LINKED_IDENTITY_MISMATCH"):
                    self.cache(row)

    def test_valid_nested_pregame_numbers_clocks_identity_all_stats(self):
        for stat in e.STATS:
            for shape in SHAPES:
                row = fixture(stat=stat)
                row["pipelines"]["S0"]["model_inputs"] = wrap({
                    "projected_minutes": 31.25, "participation_probability": None,
                    "prior_rates": [0, 0.25, [0.7, 1.2]],
                    "source_available_at": "2022-10-20T16:00:00Z",
                    "game_id": row["game_id"], "player_id": row["player_id"],
                    "source_profile": "SYNTHETIC"}, shape)
                with self.subTest(stat=stat, shape=shape):
                    self.assertEqual(self.cache(row).game_count, 1)

    def test_w3_sparse_fallback_cannot_accept_nested_outcome(self):
        row = fixture()
        row["pipelines"]["S0"]["model_inputs"] = [[{"actual_minutes": 37}]]
        with self.assertRaisesRegex(e.ExperimentError, "OUTCOME_IN_FORECAST_PIPELINE"):
            e.w3_by_stat([row], global_weights={"S0": 1., "SO0": 0., "J0": 0.},
                         min_games=100)

    def test_target_aliases_are_quarantined_with_valid_prior_controls(self):
        aliases = {"actual_attempts": 21, "realized_attempts": 21,
                   "target_game_boxscore": {"points": 30},
                   "target_game_result": {"home_points": 100},
                   "final_roster": ["nba:player:1"], "actual_rebounds": 12,
                   "realized_minutes": 37, "final_score": [100, 98]}
        for key, value in aliases.items():
            row = fixture()
            row["pipelines"]["S0"]["model_inputs"] = [[{key: value}]]
            with self.subTest(key=key), self.assertRaisesRegex(
                    e.ExperimentError, "OUTCOME_IN_FORECAST_PIPELINE"):
                self.cache(row)
        row = fixture()
        row["pipelines"]["S0"]["model_inputs"] = [[{
            "projected_attempts": 21, "projected_minutes": 31.5,
            "candidate_roster": ["nba:player:1"],
            "prior_game_actual_attempts": 20, "prior_game_realized_minutes": 29,
            "prior_game_final_roster": ["nba:player:1"],
            "prior_game_boxscore": {"points": 12}}]]
        self.assertEqual(self.cache(row).game_count, 1)

    def test_cycles_reject_but_shared_pregame_substructures_are_legal(self):
        row = fixture()
        cyclic = []
        cyclic.append(cyclic)
        row["pipelines"]["S0"]["model_inputs"] = cyclic
        with self.assertRaisesRegex(e.ExperimentError, "CYCLIC_FORECAST_INPUT"):
            self.cache(row)
        shared = {"projected_minutes": 30.5}
        row = fixture()
        row["pipelines"]["S0"]["model_inputs"] = [shared, [shared]]
        self.assertEqual(self.cache(row).game_count, 1)

    def test_nested_list_unknown_clock_and_model_cutoff(self):
        for key, value, error in (
                ("unreviewed_at", "2022-10-20T16:00:00Z", "UNSUPPORTED_TIME_FIELD"),
                ("training_cutoff_at", "2022-10-20T18:00:00Z", "POST_FREEZE")):
            row = fixture()
            row["pipelines"]["S0"]["model_inputs"] = [[{key: value}]]
            with self.subTest(key=key), self.assertRaisesRegex(e.ExperimentError, error):
                self.cache(row)


if __name__ == "__main__":
    unittest.main()
