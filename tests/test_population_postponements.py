"""Historical postponed games are not played games or zero-stat observations."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import population_backfill as ingest
import population_history as history
import population_normalizers as normal


def scoreboard(nonfinal="STATUS_POSTPONED",completed=False):
    return {"events":[
        {"id":"401","season":{"type":2},
         "status":{"type":{"name":"STATUS_FINAL","completed":True}}},
        {"id":"402","season":{"type":2},
         "status":{"type":{"name":nonfinal,"completed":completed}}},
        {"id":"403","season":{"type":1},
         "status":{"type":{"name":"STATUS_SCHEDULED","completed":False}}},
    ]}


def completed_nba_game():
    labels=["MIN","PTS","REB","AST","3PT","STL","BLK","TO"]
    def players(base):
        return [{"athlete":{"id":str(base+i),"position":{"abbreviation":"PG"}},
                 "stats":["28:00","14","4","3","2-5","1","0","2"]}
                for i in range(8)]
    return {"header":{"season":{"year":2024},"competitions":[{
        "id":"401","competitors":[
            {"homeAway":"home","team":{"abbreviation":"BOS"}},
            {"homeAway":"away","team":{"abbreviation":"MIA"}}]}]},
        "boxscore":{"players":[
            {"team":{"abbreviation":team},"statistics":[
                {"labels":labels,"athletes":players(base)}]}
            for team,base in (("BOS",100),("MIA",200))]}}


class HistoricalPostponement(unittest.TestCase):
    def test_explicitly_postponed_and_canceled_only(self):
        for label in ("STATUS_POSTPONED","STATUS_CANCELED"):
            with self.subTest(label=label):
                omissions=[]
                self.assertEqual(normal.scoreboard_games(
                    "NBA",scoreboard(label),"2024-01-17",exclusions=omissions),["401"])
                self.assertEqual(omissions,[{
                    "sport":"NBA","day":"2024-01-17","game_id":"402",
                    "reason":"source_confirmed_unplayed_game","source_status":label}])

    def test_unknown_incomplete_and_live_fail_closed(self):
        for label,completed in [
            ("STATUS_SCHEDULED",False),("STATUS_IN_PROGRESS",False),
            ("STATUS_POSTPONED",None),(None,False)]:
            with self.subTest(label=label,completed=completed):
                with self.assertRaisesRegex(ValueError,"nba_past_game_not_final"):
                    normal.scoreboard_games("NBA",scoreboard(label,completed),"2024-01-17")

    def test_postponed_game_does_not_block_completed_date_or_become_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            state=ingest.read_state(folder,"NBA",stream="recent")
            state["cursor"]="2024-01-17"
            ingest.save_state(folder,"NBA",state,stream="recent")
            def fetch(url):
                if "/scoreboard?" in url:
                    return scoreboard()
                if "event=401" in url:
                    return completed_nba_game()
                raise AssertionError("Postponed game's boxscore must not be fetched")
            outcome=ingest.run(folder,"NBA",stream="recent",
                max_days=1,stop_before="2024-01-17",fetcher=fetch)
            self.assertEqual(outcome["advanced"],1)
            self.assertEqual(outcome["status"],"partial")
            self.assertEqual(outcome["cursor_after"],"2024-01-18")
            self.assertEqual(outcome["source_games"],1)
            self.assertEqual(outcome["source_exclusions"][0]["game_id"],"402")
            rows=history.read(folder,sport="NBA",stat="points",before="2024-01-18")
            self.assertEqual(len(rows),16)
            self.assertTrue(all(r["value"]==14 for r in rows))


if __name__=="__main__":
    unittest.main()
