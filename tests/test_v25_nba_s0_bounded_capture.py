"""Research S0 bounded ORIGINAL pregame STARTER-PROXY selection regression tests.

No test fixtures masquerade as real original source admissions.
"""
import copy
import unittest
from research.nba_p1_original.feature_store import STATS
from research.nba_p1_original.rolling import (
    AcquisitionError, _bounded_canary_subset, WindowPolicy,
)


def fixture():
    rows = []
    for n in range(1, 10):
        pid = f"espn:player:{n:03d}"
        team = "espn:team:11" if n <= 3 or n == 9 else "espn:team:18"
        history = [
            {"game_id": "espn:game:9001", "team_id": team,
             "participation": "played", "starter": n != 8,
             "minutes": 24 + n},
            {"game_id": "espn:game:9002", "team_id": team,
             "participation": "played", "starter": n != 8,
             "minutes": 26 + n},
        ]
        if n == 8:
            history[-1]["participation"] = "dnp"
            history[-1]["starter"] = None
            history[-1]["minutes"] = None
        availability = (
            "RULED_OUT_SOURCE_REPORTED" if n == 7
            else "UNVERIFIED_AVAILABILITY"
        )
        for stat in STATS:
            rows.append({"player_id": pid, "team_id": team,
                         "stat_key": stat,
                         "features": {
                             "prior_player_history": copy.deepcopy(history),
                             "availability_status": availability,
                             "current_name": "Synthetic " + str(n),
                             "position": "G",
                             "official_nba_player_id": None,
                         }})
    manifest = {
        "event_id": "espn:game:9999",
        "feature_rows": len(rows), "player_candidates_accepted": 9,
        "player_candidates_total": 9, "player_candidates_rejected": 0,
        "source_listed_count": 9, "unknown_availability": 8,
        "questionable_count": 0, "ruled_out_count": 1,
        "name_supported_count": 9, "position_supported_count": 9,
        "official_player_ids_verified_count": 0, "rejected": [],
    }
    return rows, manifest


class BoundedOriginalCaptureTests(unittest.TestCase):
    def test_default_p1_is_full_not_mutated(self):
        r, s = fixture()
        full, original = _bounded_canary_subset(r, s, None)
        self.assertIs(full, r)
        self.assertIs(original, s)
        self.assertEqual(len(full), 9 * len(STATS))

    def test_prior_starters_precede_id_order_and_balance_both_teams(self):
        rows, summary = fixture()
        chosen, report = _bounded_canary_subset(rows, summary, 6)
        ids = sorted({r["player_id"] for r in chosen})
        self.assertEqual(ids, [f"espn:player:{i:03d}" for i in (2, 3, 4, 5, 6, 9)])
        self.assertEqual(report["feature_rows"], 6 * len(STATS))
        self.assertEqual(report["player_candidates_accepted"], 6)
        self.assertEqual(report["player_candidates_rejected"], 3)
        self.assertEqual(report["source_listed_count"], 6)
        sel = report["bounded_canary_selection"]
        self.assertTrue(sel["no_target_outcome_data_used"])
        self.assertTrue(sel["no_bench_fallback"])
        self.assertEqual(sel["current_start_status"],
                         "PROJECTED_ONLY_NOT_CONFIRMED_PREGAME")
        self.assertEqual(sel["eligible_candidate_count"], 7)
        self.assertEqual({x["team_id"] for x in sel["selected_player_evidence"]},
                         {"espn:team:11", "espn:team:18"})
        self.assertTrue(all(x["historical_starts_verified"] == 2 and
                            x["current_starter_confirmed"] is False
                            for x in sel["selected_player_evidence"]))
        self.assertEqual(len(summary["rejected"]), 0)
        self.assertEqual(summary["player_candidates_accepted"], 9)

    def test_ineligible_histories_or_ruled_out_not_selected(self):
        rows, summary = fixture()
        chosen, report = _bounded_canary_subset(rows, summary, 24)
        ids = {x["player_id"] for x in chosen}
        self.assertNotIn("espn:player:007", ids)
        self.assertNotIn("espn:player:008", ids)
        self.assertEqual(len(ids), 7)
        self.assertIn("espn:player:009", ids)
        self.assertEqual(report["bounded_canary_selection"]["maximum_per_team"], 5)

    def test_bench_only_never_falls_back_to_lexicographic_selection(self):
        rows, summary = fixture()
        for r in rows:
            for h in r["features"]["prior_player_history"]:
                h["starter"] = False
        chosen, report = _bounded_canary_subset(rows, summary, 6)
        self.assertEqual(chosen, [])
        self.assertEqual(report["feature_rows"], 0)
        self.assertEqual(report["bounded_canary_selection"]["eligible_candidate_count"], 0)

    def test_one_prior_start_insufficient(self):
        rows, summary = fixture()
        for r in rows:
            if r["player_id"] == "espn:player:009":
                r["features"]["prior_player_history"][0]["starter"] = False
        chosen, _ = _bounded_canary_subset(rows, summary, 6)
        self.assertNotIn("espn:player:009", {x["player_id"] for x in chosen})

    def test_changed_team_not_accepted_from_old_roster(self):
        rows, summary = fixture()
        for r in rows:
            if r["player_id"] == "espn:player:009":
                r["features"]["prior_player_history"][0]["team_id"] = "espn:team:18"
        chosen, _ = _bounded_canary_subset(rows, summary, 6)
        self.assertNotIn("espn:player:009", {x["player_id"] for x in chosen})

    def test_quasi_starter_string_true_not_admitted(self):
        rows, summary = fixture()
        for r in rows:
            if r["player_id"] == "espn:player:009":
                r["features"]["prior_player_history"][0]["starter"] = "true"
        chosen, _ = _bounded_canary_subset(rows, summary, 6)
        self.assertNotIn("espn:player:009", {x["player_id"] for x in chosen})

    def test_target_game_history_is_never_accepted(self):
        rows, summary = fixture()
        for r in rows:
            if r["player_id"] == "espn:player:009":
                r["features"]["prior_player_history"][1]["game_id"] = summary["event_id"]
        with self.assertRaisesRegex(AcquisitionError, "TARGET_STARTER_LEAKAGE"):
            _bounded_canary_subset(rows, summary, 6)

    def test_non_bundle_input_fails_closed(self):
        rows, summary = fixture()
        rows.pop()
        with self.assertRaisesRegex(AcquisitionError,
                                   "INCOMPLETE_CANARY_PLAYER_STAT_BUNDLE"):
            _bounded_canary_subset(rows, summary, 6)

    def test_cross_team_stat_bundle_fails_closed(self):
        rows, summary = fixture()
        rows[0]["team_id"] = "espn:team:18"
        with self.assertRaisesRegex(AcquisitionError,
                                   "CANARY_STAT_BUNDLE_TEAM_MISMATCH"):
            _bounded_canary_subset(rows, summary, 6)

    def test_invalid_team_fails_closed(self):
        rows, summary = fixture()
        for r in rows:
            if r["player_id"] == "espn:player:009":
                r["team_id"] = None
        with self.assertRaisesRegex(AcquisitionError,
                                   "STARTER_CANDIDATE_TEAM_UNVERIFIED"):
            _bounded_canary_subset(rows, summary, 6)

    def test_limits_fail_closed(self):
        rows, summary = fixture()
        for limit in (0, -1, 25, 1.0, False, "6"):
            with self.subTest(limit=limit):
                with self.assertRaisesRegex(AcquisitionError,
                                           "CANARY_PLAYER_LIMIT_BOUNDS"):
                    _bounded_canary_subset(rows, summary, limit)

    def test_window_policy_not_relaxed(self):
        w = WindowPolicy()
        self.assertEqual((w.early_open_minutes, w.early_deadline_minutes), (70, 50))
        self.assertEqual((w.final_open_minutes, w.final_deadline_minutes), (35, 20))


if __name__ == "__main__":
    unittest.main()
