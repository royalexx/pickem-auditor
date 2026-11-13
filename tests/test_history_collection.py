"""Parallel history fetches preserve the serial data and failure contract."""
from pathlib import Path
import sys
import threading
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import fetch_slate as fs

class HistoryCollectionTests(unittest.TestCase):
    def test_nfl_dates_and_ids_are_season_specific(self):
        rows=[dict(season=2025,week=1,recent_team='CHI',passing_yards=100)]
        games=[dict(season=2025,week=1,game_type='REG',home_team='CHI',away_team='GB',gameday='2025-09-07',game_id='2025_01_GB_CHI'),
               dict(season=2026,week=1,game_type='REG',home_team='CHI',away_team='GB',gameday='2026-09-06',game_id='2026_01_GB_CHI')]
        result=fs.date_nfl_weeks(rows,games,2025)
        self.assertEqual(result[0]['game_date'],'2025-09-07')
        self.assertEqual(result[0]['game_id'],'2025_01_GB_CHI')
        self.assertNotIn('game_date',rows[0])

    def test_custom_output_routes_nfl_season_store_with_usage_data(self):
        from unittest.mock import patch
        with patch.object(fs,'fetch_nfl',return_value=([],[])) as fetch:
            feeds=fs._builtin_fetchers('2026-10-26','2026-10-26T12:00:00Z',None,None,None,data_dir='/tmp/example')
            feeds['nfl']()
        self.assertEqual(fetch.call_args.kwargs['season_store_path'],Path('/tmp/example/season/nfl_2026.sqlite3'))

    def test_negative_nfl_yards_are_observations_but_negative_counts_are_not(self):
        from datetime import datetime,timezone
        import usage_baseline as ub
        rows=[dict(id='1',date='2026-10-01',value=-3,workload=30)]
        c=dict(sport='NFL',stat='rushing yards',game_date='2026-10-26')
        now=datetime(2026,10,26,tzinfo=timezone.utc)
        self.assertEqual(ub.validate_rows(rows,c,now)[0][2],-3)
        c['stat']='receptions'
        with self.assertRaises(ValueError):ub.validate_rows(rows,c,now)

    def test_parallel_matches_serial_provenance_and_missing_history(self):
        def loader(player,season,urls):
            urls.append(f'https://www.example.com/{player}/{season}')
            if player=='B' or (player=='C' and season==2025):return None
            return [dict(id=player,season=season)]
        a=[];b=[]
        serial=fs.load_history_pairs(['A','B','C'],2026,2025,loader,a,workers=1)
        parallel=fs.load_history_pairs(['A','B','C'],2026,2025,loader,b,workers=4)
        self.assertEqual(serial,parallel);self.assertEqual(a,b)
        self.assertEqual(serial[2:],(1,1))
        self.assertNotIn('https://www.example.com/B/2025',a)

    def test_four_history_requests_can_run_without_shared_url_lists(self):
        barrier=threading.Barrier(4,timeout=3)
        def loader(player,season,urls):
            if season==2026:barrier.wait()
            urls.append(f'https://www.example.com/{player}/{season}')
            return [player,season]
        urls=[]
        result=fs.load_history_pairs(['A','B','C','D'],2026,2025,loader,urls)
        self.assertEqual(result[2:],(0,0))
        self.assertEqual(urls,[f'https://www.example.com/{p}/{s}' for p in 'ABCD' for s in (2026,2025)])

    def test_history_concurrency_is_bounded(self):
        for value in (0,5,True,1.5):
            with self.assertRaises(ValueError):fs.load_history_pairs([],2026,2025,None,[],workers=value)

    def test_raw_rows_cannot_establish_priced_history_coverage(self):
        from unittest.mock import patch
        row=dict(sport='NBA',team='BOS',player='Example Player',stat='points')
        with patch.object(fs,'_pipeline_ready',return_value=True),patch.object(fs,'quotes_for_row',return_value=[]):
            result=fs.collected_coverage([row],[])
        self.assertFalse(result['has_priced_history_rows'])
        self.assertEqual(result['by_sport']['NBA']['history_ready_rows'],1)
        self.assertEqual(result['by_sport']['NBA']['priced_history_ready_rows'],0)
        with patch.object(fs,'_pipeline_ready',return_value=False), \
             patch.object(fs,'quotes_for_row',return_value=[{}]),patch.object(fs,'primary_price',return_value={'line':10}):
            result=fs.collected_coverage([row],[{}])
        self.assertFalse(result['has_priced_history_rows'])
        self.assertEqual(result['by_sport']['NBA']['priced_rows'],1)

    def test_nhl_reads_past_api_hundred_row_cap(self):
        import json
        from types import SimpleNamespace
        fixtures=Path(__file__).parent/'fixtures'
        load=lambda name:json.loads((fixtures/name).read_text())
        starts=[]
        class Stats:
            def skater_stats_summary(self,**kwargs):
                starts.append((kwargs['start'],kwargs['limit']))
                if kwargs['start']==0:
                    return [dict(playerId=str(i),teamAbbrevs='ZZZ',gamesPlayed=2,shots=1) for i in range(100)]
                return load('nhl_skaters.json')
            def goalie_stats_summary(self,**kwargs):return []
            def team_summary(self,**kwargs):return load('nhl_teams.json')
            def player_game_log(self,*args):return []
        client=SimpleNamespace(stats=Stats(),schedule=SimpleNamespace(daily_schedule=lambda **k:load('nhl_schedule.json')))
        rows, _, _ = fs.fetch_nhl('2026-10-22','2026-10-22T16:00:00Z',client=client)
        self.assertTrue(rows)
        self.assertEqual(starts,[(0,100),(100,100)])

if __name__=='__main__':unittest.main()
