"""Source-owning historical roster continuity is *not* confirmed today's lineup."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))

from recent_lineup_tendency import evaluate
from shared_context import import_history
from usage_baseline import using_directory

NOW=datetime(2026,10,28,20,30,tzinfo=timezone.utc)


def fixture(root, sport="NHL", player_id="42", omitted=()):
    row={"sport":sport,"stat":"shots on goal" if sport=="NHL" else "points",
         "team":"BOS","player":"Example Player","player_id":player_id,
         "game_date":"2026-10-28"}
    games=[]
    for i in range(5):
        active=["123"]
        if i not in omitted:active.append(str(player_id))
        values={p:(1.0 if p==str(player_id) else 2.0) for p in active}
        games.append({"id":f"game-{i}","date":f"2026-10-{27-i:02d}",
                      "source_url":"https://site.api.espn.com/apis/site/v2/sports/test/summary?event="+str(i),
                      "active_players":active,"production":values,
                      "team_total":sum(values.values()),"roster_complete":True})
    history={"sport":sport,"team":"BOS","stat":row["stat"],"games":games,
             "retrieved_at":"2026-10-28T19:00:00Z",
             "collection":{"discovered":5,"completed":5,"errors":[]}}
    with using_directory(root):
        import_history(history)
    return row


class RecentTendencyTests(unittest.TestCase):
    def test_five_complete_rosters_support_high_continuity_not_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            row=fixture(directory)
            result=evaluate(row,NOW,root=directory)
            self.assertEqual(result["status"],"high_continuity")
            self.assertEqual(result["played_last_5"],5)
            self.assertTrue(result["likely_available"])
            self.assertFalse(result["confirmed_active"])
            self.assertFalse(result["usable_for_verified_tier"])
            self.assertEqual(len(result["team_game_ids"]),5)
            self.assertEqual(len(result["source_snapshot_sha256"]),64)

    def test_one_missed_game_reduces_evidence_two_misses_never_high(self):
        with tempfile.TemporaryDirectory() as directory:
            row=fixture(directory,omitted=(3,))
            result=evaluate(row,NOW,root=directory)
            self.assertEqual(result["status"],"moderate_continuity")
            self.assertFalse(result["likely_available"])
        with tempfile.TemporaryDirectory() as directory:
            row=fixture(directory,omitted=(0,4))
            result=evaluate(row,NOW,root=directory)
            self.assertEqual(result["status"],"low_continuity")

    def test_injury_and_source_conflict_overrule_five_appearances(self):
        with tempfile.TemporaryDirectory() as directory:
            row=fixture(directory)
            packet={"availability":{"Example Player":{"status":{"value":"out"}}}}
            self.assertEqual(evaluate(row,NOW,root=directory,packet=packet)["status"],
                             "negative_current_report")
            packet["availability"]["Example Player"]["status"]["value"]="questionable"
            self.assertEqual(evaluate(row,NOW,root=directory,packet=packet)["status"],
                             "uncertain_injury")
            packet={"_source_conflicts":[{"player":"Example Player","resolution":"unresolved"}]}
            self.assertEqual(evaluate(row,NOW,root=directory,packet=packet)["status"],
                             "conflicting_sources")

    def test_goaltender_not_projected_from_bench_dressing(self):
        with tempfile.TemporaryDirectory() as directory:
            row=fixture(directory)
            row["stat"]="goalie saves"
            result=evaluate(row,NOW,root=directory)
            self.assertEqual(result["status"],"starter_unknown")
            self.assertFalse(result["likely_available"])

    def test_nfl_numeric_espn_identity_not_a_gsis_roster(self):
        row={"sport":"NFL","stat":"receptions","team":"BOS",
             "player":"Example Player","player_id":"123","game_date":"2026-10-28"}
        result=evaluate(row,NOW)
        self.assertEqual(result["reason"],"NFL_GSIS_PLAYER_ID_BRIDGE_MISSING")
        self.assertFalse(result["likely_available"])

    def test_missing_or_stale_team_history_is_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            row=fixture(directory)
            row["team"]="MTL"
            self.assertEqual(evaluate(row,NOW,root=directory)["status"],"unknown")
        with tempfile.TemporaryDirectory() as directory:
            row=fixture(directory)
            from shared_context import history_path
            with using_directory(directory):
                path=history_path(row["sport"],row["team"],row["stat"])
            data=json.loads(path.read_text())
            data["collection"]["completed"]=4
            path.write_text(json.dumps(data))
            self.assertEqual(evaluate(row,NOW,root=directory)["reason"],"INCOMPLETE_TEAM_GAME_COVERAGE")

if __name__=="__main__":
    unittest.main()
