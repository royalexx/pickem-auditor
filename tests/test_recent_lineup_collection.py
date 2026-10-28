"""Bounded recent-only collection does not destroy long history or invent status."""
import sys
import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))

import recent_lineup_collection as rc
from recent_lineup_tendency import tendency_path,evaluate

DATE="2026-10-28"
NOW=datetime(2026,10,28,20,30,tzinfo=timezone.utc)


class RecentCollectionTests(unittest.TestCase):
    def test_collects_five_sources_into_date_archive_without_baseline_mutation(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            queue={"date":DATE,"queue":[
                {"sport":"NHL","team":"BOS","stat":"shots on goal","player_id":"42"},
                {"sport":"NHL","team":"BOS","stat":"shots on goal","player_id":"43"},
                {"sport":"NHL","team":"BOS","stat":"goalie saves","player_id":"44"},
            ]}
            history={"sport":"NHL","team":"BOS","stat":"shots on goal",
                     "retrieved_at":NOW.isoformat(),
                     "collection":{"discovered":5,"completed":5,"errors":[]},
                     "games":[{"id":f"g{i}","date":f"2026-10-{27-i:02}",
                               "active_players":["42","43"],
                               "source_url":f"https://api-web.nhle.com/gamecenter/{i}",
                               "roster_complete":True,"team_total":2.,
                               "production":{"42":1.,"43":1.}}
                              for i in range(5)]}
            with patch.object(rc,"collect",return_value=history) as mocked:
                result=rc.run(queue,DATE,root=root,now=NOW)
                self.assertEqual(mocked.call_count,1)
                self.assertFalse(mocked.call_args.kwargs["persist"])
                self.assertEqual(mocked.call_args.kwargs["max_games"],5)
                self.assertEqual(result["completed"],1)
            target=tendency_path(root,"NHL","BOS","shots on goal",DATE)
            self.assertTrue(target.is_file())
            self.assertFalse((root/"lineups").exists())
            item={"sport":"NHL","stat":"shots on goal","team":"BOS",
                  "player_id":"42","player":"Skater","game_date":DATE}
            tendency=evaluate(item,NOW,root=root)
            self.assertEqual(tendency["status"],"high_continuity")
            with patch.object(rc,"collect",side_effect=AssertionError("should not fetch")):
                result=rc.run(queue,DATE,root=root,now=NOW)
                self.assertEqual(result["attempts"][0]["status"],"reused_source_checked_archive")

    def test_partial_external_source_never_creates_active_claim(self):
        with tempfile.TemporaryDirectory() as t:
            q={"date":DATE,"queue":[{"sport":"NBA","team":"BOS","stat":"points","player_id":"10"}]}
            with patch.object(rc,"collect",side_effect=ValueError("missing game")):
                result=rc.run(q,DATE,root=t,now=NOW)
            self.assertEqual(result["completed"],0)
            self.assertFalse(result["proves_current_active_status"])
            self.assertEqual(result["attempts"][0]["status"],"source_unavailable")

if __name__=="__main__":
    unittest.main()
