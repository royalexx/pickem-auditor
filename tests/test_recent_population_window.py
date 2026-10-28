"""No-network tests for recent-season priority collection and strict dated model windows."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import population_backfill as backfill
import population_history as hist
import population_window_check as windows
import population_nfl
from test_population_multisport import nhl_box


class MultiSeasonWindowTests(unittest.TestCase):
    def test_recent_stream_preserves_existing_2018_archive_cursor(self):
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder)
            def get(url):
                if "/score/" in url:
                    self.assertIn("2023-10-01",url)
                    return {"games":[{"id":2023020001,"gameType":2,"gameState":"FINAL"}]}
                data=nhl_box()
                data["id"]=2023020001
                return data
            response=backfill.run(d,"NHL",stream="recent",max_days=1,
                                  stop_before="2023-10-02",fetcher=get)
            self.assertEqual(response["stream"],"recent")
            self.assertEqual(response["advanced"],1)
            self.assertEqual(response["source_games"],1)
            self.assertEqual(backfill.read_state(d,"NHL",stream="recent")["cursor"],"2023-10-02")
            self.assertEqual(backfill.read_state(d,"NHL")["cursor"],"2018-10-01")
            self.assertTrue((d/"reports/population_nhl_recent_receipt.json").is_file())
            self.assertEqual(len(hist.read(d,sport="NHL",stat="hits",
                                           before="2023-10-02")),36)
            with self.assertRaisesRegex(ValueError,"nfl_recent_stream_not_supported"):
                backfill.run(d,"NFL",stream="recent")
            with self.assertRaisesRegex(ValueError,"population_state_mismatch"):
                backfill.read_state(d,"NHL",stream="archive") if False else self._mismatch(d)

    @staticmethod
    def _mismatch(d):
        p=backfill.state_file(d,"NHL")
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text('{"schema":"multi-sport-population-cursor-v1","sport":"NHL",'
                     '"stream":"recent","cursor":"2023-10-03",'
                     '"dates_complete":0,"source_games":0,"market_rows_inserted":0}')
        return backfill.read_state(d,"NHL")

    def test_nfl_multiple_completed_seasons_progress_and_no_partial_current(self):
        with tempfile.TemporaryDirectory() as directory:
            def loader(year):
                schedule=[{"game_id":f"{year}_01_BUF_LAR",
                           "season":year,"week":1,"game_type":"REG",
                           "gameday":f"{year}-09-10",
                           "away_team":"BUF","home_team":"LAR"}]
                stats=[{"season":year,"week":1,"season_type":"REG",
                        "team":"BUF","opponent_team":"LAR","position":"WR",
                        "player_id":"player-1","player_display_name":"John Smith",
                        "targets":8,"receptions":5,"receiving_yards":66.,
                        "receiving_tds":1}]
                snaps=[{"season":year,"week":1,"game_type":"REG",
                        "game_id":f"{year}_01_BUF_LAR","team":"BUF",
                        "opponent":"LAR","player":"John Smith","offense_snaps":54}]
                return stats,snaps,schedule
            result=backfill.run(directory,"NFL",max_nfl_seasons=3,
                     nfl_loader=loader,stop_before="2022-04-01")
            self.assertEqual(result["status"],"partial")
            self.assertEqual(result["advanced"],3)
            self.assertEqual(result["source_games"],3)
            self.assertEqual(backfill.read_state(directory,"NFL")["cursor"],"2021")
            self.assertGreater(result["market_rows_added"],3)
            self.assertEqual(len(hist.read(directory,sport="NFL",stat="targets",
                                            before="2022-01-01")),3)
            # Next completed year is 2021, which closes in March 2022;
            # past-season data must never be rejected as a current slate.
            caught=backfill.run(directory,"NFL",max_nfl_seasons=3,
                     nfl_loader=loader,stop_before="2021-12-01")
            self.assertEqual(caught["advanced"],0)
            self.assertEqual(backfill.read_state(directory,"NFL")["cursor"],"2021")

    def test_multi_season_asof_continuity_and_incomplete_stream_veto(self):
        with tempfile.TemporaryDirectory() as directory:
            def make(day,season,gid,player):
                return hist.make(sport="NBA",stat="points",
                    game_id=gid,game_date=day,season=season,
                    player_id=str(player),position="PG",
                    team="BOS",opponent="MIA",home=True,
                    value=12+player%7,workload=25+player%8,
                    workload_unit="minutes",source_url="https://example.org/game",
                    source_sha256="b"*64)
            rows=[]
            for year,season in ((2023,"2024"),(2024,"2025")):
                for g in range(8):
                    for player in range(20):
                        rows.append(make(f"{year}-11-{g+1:02d}",season,
                                         f"{year}-{g}",player))
            rows.append(make("2025-02-15","2025","2025-test",0))
            hist.persist(directory,rows)
            with self.assertRaisesRegex(ValueError,"POPULATION_COLLECTION_INCOMPLETE"):
                windows.inspect(directory,sport="NBA",stat="points",
                    train_from="2023-10-01",as_of="2025-01-01",
                    until="2025-03-01",min_rows=300)
            stream=backfill.read_state(directory,"NBA",stream="recent")
            stream["cursor"]="2025-03-01"
            backfill.save_state(directory,"NBA",stream,stream="recent")
            report=windows.inspect(directory,sport="NBA",stat="points",
                train_from="2023-10-01",as_of="2025-01-01",
                until="2025-03-01",max_seasons=4,min_rows=300)
            self.assertEqual(report["status"],"ready")
            self.assertEqual(report["training_seasons"],["2024","2025"])
            self.assertEqual(report["training_rows"],320)
            self.assertEqual(report["heldout_rows"],1)
            self.assertEqual(report["source"]["stream"],"recent")
            selected=hist.read(directory,sport="NBA",stat="points",
                after="2023-10-01",before="2025-01-01",max_seasons=4)
            self.assertEqual(len(selected),320)
            self.assertEqual(len({r["season"] for r in selected}),2)

    def test_gap_between_2018_and_recent_must_not_count_as_complete_seasons(self):
        with tempfile.TemporaryDirectory() as directory:
            rows=[hist.make(sport="NBA",stat="points",game_id=str(i),
                game_date="2018-10-20" if i<160 else "2023-10-20",
                season="2019" if i<160 else "2024",player_id=str(i%20),
                position="PG",team="BOS",opponent="MIA",home=True,
                value=15,workload=30,workload_unit="minutes",
                source_url="https://example.org/game",source_sha256="c"*64)
                for i in range(320)]
            rows.append(hist.make(sport="NBA",stat="points",game_id="future",
                game_date="2024-01-02",season="2024",player_id="1",
                position="PG",team="BOS",opponent="MIA",home=True,
                value=15,workload=30,workload_unit="minutes",
                source_url="https://example.org/game",source_sha256="c"*64))
            hist.persist(directory,rows)
            archive=backfill.read_state(directory,"NBA")
            archive["cursor"]="2024-02-01"
            backfill.save_state(directory,"NBA",archive)
            with self.assertRaisesRegex(ValueError,"DISCONNECTED_TRAINING_SEASONS"):
                windows.inspect(directory,sport="NBA",stat="points",
                    train_from="2018-10-01",as_of="2023-12-01",
                    until="2024-02-01",max_seasons=5,min_rows=300)


if __name__=="__main__":
    unittest.main()
