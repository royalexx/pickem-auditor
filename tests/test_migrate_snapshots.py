import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import migrate_snapshots as ms
import pickem_math as pm


class MigrateSnapshotsTests(unittest.TestCase):
    def test_migrates_legacy_books_and_schema_version(self):
        legacy = {
            "run_at": "2026-10-21 21:00 ET",
            "game_date": "2026-10-21",
            "sport": "NBA",
            "matchup": "LAL vs GSW",
            "player": "Example",
            "stat": "points",
            "side": "over",
            "reference_line": 24.5,
            "final_rank": "Unranked",
            "status": "UNRANKED",
            "researched": True,
            "books": "DraftKings -123/-104",
            "q_model": 0.58,
        }
        migrated = ms.migrate_row(legacy)
        self.assertEqual(migrated["schema_version"], 1)
        self.assertIsInstance(migrated["books"], list)
        self.assertEqual(migrated["books"][0]["book"], "DraftKings")
        self.assertEqual(migrated["q_win"], 0.58)

    def test_rewrite_uses_lf_endings(self):
        legacy = {
            "run_at": "t",
            "game_date": "2026-10-21",
            "sport": "NBA",
            "matchup": "A @ B",
            "player": "P",
            "stat": "points",
            "side": "over",
            "reference_line": 1.5,
            "final_rank": "Reject",
            "status": "GRADED",
            "researched": True,
            "books": "FanDuel -110/-110",
        }
        body = json.dumps(legacy) + "\r\n"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "props.jsonl"
            path.write_text(body, encoding="utf-8")
            count = ms.migrate_file(path)
            self.assertEqual(count, 1)
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("\r", text)
            row = json.loads(text.splitlines()[0])
            self.assertEqual(row["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
