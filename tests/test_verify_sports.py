"""Verified sports receipt: a scheduled off-day isn't a source outage."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import tempfile
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify_sports.py"
spec = spec_from_file_location("verify_sports", MODULE_PATH)
verifier = module_from_spec(spec)
spec.loader.exec_module(verifier)


class SportCoverageTests(unittest.TestCase):
    def _audit(self, *, notes):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slate = root / "slate.jsonl"
            slate.write_text("".join(json.dumps({
                "sport": sport, "game_date": "2026-10-27",
                "player": "Sample", "stat": "points",
                "retrieved_at": "2026-10-27T15:00:00Z"
            }) + "\n" for sport in ("NHL", "NBA")))
            meta = root / "slate.meta.json"
            meta.write_text(json.dumps({
                "date": "2026-10-27",
                "retrieved_at": "2026-10-27T15:00:00Z",
                "feeds": {
                    "nhl": {"status": "ok", "rows": 1},
                    "nba": {"status": "ok", "rows": 1},
                    "nfl": {"status": "failed", "rows": 0, "notes": notes},
                }
            }))
            report = verifier.audit(slate, meta, root / "receipt.json", root, "morning")
            self.assertTrue((root / "data/history_slate/2026-10-27/morning/nba.jsonl.gz").exists())
            return report

    def test_nfl_no_regular_game_is_not_network_failure(self):
        report = self._audit(notes=[
            "nfl: load_schedules returned no REG game on 2026-10-27. No NFL rows."
        ])
        self.assertEqual(report["status"], "success")
        self.assertEqual(report["source_rows"], {"NHL": 1, "NBA": 1, "NFL": 0})
        self.assertEqual(report["feed_status"]["NFL"]["status"], "no_games_scheduled")

    def test_genuine_nfl_failure_does_not_pass(self):
        report = self._audit(notes=["nfl: URLError: name resolution failed"])
        self.assertEqual(report["status"], "partial")
        self.assertIn("NFL_FEED_UNVERIFIED", report["errors"])


if __name__ == "__main__":
    unittest.main()
