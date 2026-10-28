"""Research ranks are useful but must never masquerade as approved picks."""
import copy
from datetime import datetime, timezone
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import research_ranked_board as rb
from pick_verification import forecast_digest
from research_triage import build as triage

NOW = datetime(2026, 10, 27, 20, 30, tzinfo=timezone.utc)
DATE = "2026-10-27"


def fixture():
    ident = "NHL|Example Skater|shots on goal|over"
    books = [
        {"book": "FanDuel", "line": 2.5, "book_side": "over",
         "target": -110, "other": -110},
        {"book": "DraftKings", "line": 2.5, "book_side": "over",
         "target": -112, "other": -108},
    ]
    row = {
        "game_date": DATE, "run_type": "shadow", "run_id": "stable",
        "forecast_at": "2026-10-27T20:00:00Z",
        "event_start": "2026-10-27T23:00:00Z",
        "sport": "NHL", "player": "Example Skater", "player_id": "42",
        "team": "BOS", "opponent": "NSH", "stat": "shots on goal",
        "side": "over", "reference_line": 2.5, "reason": "STATUS_NOT_VERIFIED",
        "books": books, "q_grade": .61, "q_market": .56,
        "q_market_comparable": .56, "q_push": 0,
        "current_role_n": 20, "soft_flags": 0,
        "engine_a": {"reliable": True}, "engine_b": {"reliable": True},
        "market": {"retrieved_at": "2026-10-27T19:55:00Z", "market_valid": True},
        "inputs": {"id": ident, "side": "over", "line": 2.5},
    }
    queue = triage([row], DATE, now=NOW)
    return [row], queue


class ResearchRankedBoardTests(unittest.TestCase):
    def test_genuine_numeric_ranking_without_creating_approved_pick(self):
        rows, queue = fixture()
        original = copy.deepcopy(rows)
        board = rb.build(rows, queue, DATE, now=NOW)
        self.assertEqual(len(board["research_ranked"]), 1, board)
        candidate = board["research_ranked"][0]
        self.assertEqual(candidate["research_rank"], "Screened Research Candidate")
        self.assertEqual(candidate["forecast_calibration"], "not_certified_for_tier_hit_rate")
        self.assertEqual(candidate["lineup_status"], "unconfirmed")
        self.assertFalse(candidate["lineup_tendency"]["confirmed_active"])
        self.assertFalse(candidate["publication_eligible"])
        self.assertFalse(candidate["verified_pick"])
        self.assertFalse(candidate["actionable_without_verification"])
        self.assertEqual(candidate["forecast_sha256"], forecast_digest(rows[0]))
        self.assertEqual(rows, original)

    def test_remarkable_prospects_need_strong_probabilities_not_old_58pct_floor(self):
        rows, queue = fixture()
        rows[0].update(q_grade=.74, q_market=.70, q_market_comparable=.70)
        candidate = rb.build(rows, queue, DATE, now=NOW)["research_ranked"][0]
        self.assertEqual(candidate["research_rank"], "Tier 3 Research Prospect")
        self.assertFalse(candidate["verified_pick"])
        rows[0].update(q_grade=.82, q_market=.77, q_market_comparable=.77)
        candidate = rb.build(rows, queue, DATE, now=NOW)["research_ranked"][0]
        self.assertEqual(candidate["research_rank"], "Tier 2 Research Prospect")
        self.assertEqual(candidate["forecast_calibration"], "not_certified_for_tier_hit_rate")
        rows[0].update(q_grade=.91, q_market=.87, q_market_comparable=.87)
        candidate = rb.build(rows, queue, DATE, now=NOW)["research_ranked"][0]
        self.assertEqual(candidate["research_rank"], "Unicorn Research Prospect")
        self.assertFalse(candidate["publication_eligible"])

    def test_actual_collector_uses_input_books_and_undated_prices_are_not_fresh(self):
        rows, queue = fixture()
        original = rows[0]
        original["books"] = [
            {"book": "FanDuel", "line": 2.5, "over": -110, "under": -110,
             "retrieved_at": None},
            {"book": "DraftKings", "line": 2.5, "over": -112, "under": -108,
             "retrieved_at": None},
        ]
        original["inputs"]["books"] = [
            {"book": "FanDuel", "line": 2.5, "book_side": "over",
             "target": -110, "other": -110},
            {"book": "DraftKings", "line": 2.5, "book_side": "over",
             "target": -112, "other": -108},
        ]
        original["market"]["retrieved_at"] = None
        board = rb.build(rows, queue, DATE, now=NOW)
        self.assertEqual(len(board["research_ranked"]), 1, board)
        item = board["research_ranked"][0]
        self.assertFalse(item["price_timestamp_verified"])
        self.assertTrue(item["price_refresh_required"])
        self.assertFalse(item["publication_eligible"])

    def test_stale_or_invalid_market_and_large_gap_cannot_rank(self):
        rows, queue = fixture()
        rows[0]["market"]["retrieved_at"] = "2026-10-27T19:00:00Z"
        self.assertEqual(rb.build(rows, queue, DATE, now=NOW)["research_ranked"], [])
        rows, queue = fixture()
        rows[0]["q_market_comparable"] = .50
        rows[0]["q_market"] = .50
        self.assertEqual(rb.build(rows, queue, DATE, now=NOW)["research_ranked"], [])
        rows, queue = fixture()
        rows[0]["books"] = rows[0]["books"][:1]
        self.assertEqual(rb.build(rows, queue, DATE, now=NOW)["research_ranked"], [])

    def test_missing_engine_or_started_event_never_ranks(self):
        rows, queue = fixture()
        rows[0]["engine_b"]["reliable"] = False
        self.assertEqual(rb.build(rows, queue, DATE, now=NOW)["research_ranked"], [])
        rows, queue = fixture()
        after = datetime(2026, 10, 28, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(rb.build(rows, queue, DATE, now=after)["research_ranked"], [])

    def test_queue_drift_cannot_publish(self):
        rows, queue = fixture()
        queue["queue"][0]["line"] = 3.5
        self.assertEqual(rb.build(rows, queue, DATE, now=NOW)["research_ranked"], [])
        rows, queue = fixture()
        queue["run_id"] = "old-run"
        self.assertEqual(rb.build(rows, queue, DATE, now=NOW)["status"],
                         "snapshot_queue_mismatch")

    def test_verified_pick_is_never_misclassified_as_research(self):
        rows, queue = fixture()
        row = rows[0]
        d = {"candidate_id": row["inputs"]["id"],
             "forecast_sha256": forecast_digest(row),
             "checked_at": "2026-10-27T20:20:00Z",
             "decision": "verified", "publication_eligible": True}
        receipt = {"schema": "pick-verification-v1", "date": DATE,
                   "source_forecast_run_id": "stable", "decisions": [d]}
        board = rb.build(rows, queue, DATE, now=NOW, decisions=[receipt])
        self.assertEqual(board["research_ranked"], [])
        self.assertEqual(board["excluded"]["already_on_verified_board"], 1)

    def test_negative_active_status_blocks_research_not_just_verified(self):
        rows, queue = fixture()
        d = {"candidate_id": rows[0]["inputs"]["id"],
             "forecast_sha256": forecast_digest(rows[0]),
             "checked_at": "2026-10-27T20:20:00Z",
             "decision": "blocked",
             "blockers": ["PLAYER_NOT_CONFIRMED_ACTIVE"]}
        receipt = {"schema": "pick-verification-v1", "date": DATE,
                   "source_forecast_run_id": "stable", "decisions": [d]}
        result = rb.build(rows, queue, DATE, now=NOW, decisions=[receipt])
        self.assertEqual(result["research_ranked"], [])
        self.assertEqual(result["excluded"]["explicit_negative_status"], 1)


if __name__ == "__main__":
    unittest.main()
