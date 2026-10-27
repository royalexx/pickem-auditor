import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import pickem_math as pm
import settle as st


class SettleTests(unittest.TestCase):
    def _row(self, **extra):
        base = {
            "schema_version": 2,
            "run_id": "00000000-0000-4000-8000-000000000001",
            "run_at": "2026-10-20 12:00 ET",
            "game_date": "2026-10-20",
            "sport": "NBA",
            "matchup": "BOS @ NYK",
            "player": "Example Player",
            "stat": "points",
            "side": "over",
            "reference_line": 20.5,
            "final_rank": "Tier 2",
            "status": "GRADED",
            "researched": True,
            "actual_stat": None,
            "outcome": None,
            "settled_at": None,
            "closing_line": None,
            "closing_q_market": None,
        }
        base.update(extra)
        return base

    def test_settle_row_is_idempotent(self):
        row = self._row()
        fetchers = st.Fetchers.from_tables(
            {
                "NBA": {
                    ("2026-10-20", "example player", "points"): 25.0,
                }
            }
        )
        updated, changed = st.settle_row(row, 25.0, settled_at="2026-10-21T00:00:00+00:00")
        self.assertTrue(changed)
        self.assertEqual(updated["outcome"], "win")
        again, changed_again = st.settle_row(updated, 30.0)
        self.assertFalse(changed_again)
        self.assertEqual(again["actual_stat"], 25.0)

    def test_settle_file_skips_future_games(self):
        row = self._row(game_date="2099-01-01")
        fetchers = st.Fetchers.from_tables({"NBA": {}})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "props.jsonl"
            path.write_text(pm.dump_snapshot(row), encoding="utf-8")
            settled = st.settle_file(path, as_of="2026-10-21", fetchers=fetchers)
            self.assertEqual(settled, 0)

    def test_settle_file_writes_outcome(self):
        row = self._row()
        fetchers = st.Fetchers.from_tables(
            {
                "NBA": {
                    ("2026-10-20", "example player", "points"): 18.0,
                }
            }
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "props.jsonl"
            path.write_text(pm.dump_snapshot(row), encoding="utf-8")
            settled = st.settle_file(path, as_of="2026-10-21", fetchers=fetchers)
            self.assertEqual(settled, 1)
            saved = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(saved["actual_stat"], 18.0)
            self.assertEqual(saved["outcome"], "loss")
            self.assertIsNotNone(saved["settled_at"])
            self.assertIsNone(saved["closing_line"])

    def test_settlement_outcome_push_on_whole_line(self):
        outcome = pm.settlement_outcome("over", 20.0, 20.0)
        self.assertEqual(outcome, "push")


if __name__ == "__main__":
    unittest.main()
