"""Regression coverage for the real NFL Engine B collection failure."""
import copy
from datetime import datetime,timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import fetch_slate as fs
import usage_baseline as ub
import context_feeds as cf

NOW=datetime(2026,11,1,16,tzinfo=timezone.utc)

def fixture(n=7):
    current=[dict(id=f'current-{i}',date=f'2026-10-{i+1:02}',value=3+i%2,workload=50.) for i in range(n)]
    prior=[dict(id=f'prior-{i}',date=f'2025-10-{i+1:02}',value=3+i%2,workload=50.) for i in range(17)]
    def games(rows):return [dict(tie=r['id'],when=r['date'],value=r['value'],workload=r['workload']) for r in rows]
    s=fs.summarize_log(games(current),'receptions',games(prior))
    c=dict(sport='NFL',stat='receptions',player_id='P',team='ATL',game_date='2026-11-01',
           line=3.5,side='over',dist=s['suggested_dist'],scouting={'historical_usage':'verified'})
    for target,source in [('baseline_mean','baseline_window_mean'),('baseline_n','baseline_n'),
                          ('recent_mean','recent_mean'),('recent_n','recent_n'),('season_n','season_n')]:c[target]=s[source]
    c['observation_ids']=copy.deepcopy(s['observation_ids'])
    c['prior_mean']=s['prior_season_mean'];c['prior_n']=s['prior_n']
    if c['dist']=='negbin':c['var_ratio']=s['var_ratio']
    return c,dict(observations=current,prior_observations=prior,content_sha256='hashed-source',source_url='nflreadpy.load_player_stats')

class EngineBWorkflowTests(unittest.TestCase):
    def test_collector_fetches_and_joins_prior_snaps_separately(self):
        class Loader:
            def __init__(self):self.snap_seasons=[]
            def load_schedules(self,seasons):
                year=seasons[0]
                return [dict(season=year,week=1,game_type='REG',home_team='ATL',away_team='TB',
                             gameday='2026-11-01' if year==2026 else '2025-09-07',game_id=f'{year}_01_TB_ATL')]
            def load_player_stats(self,seasons,summary_level):
                return [dict(player_id='P',player_display_name='Player',position='WR',season=seasons[0],
                             week=1,recent_team='ATL',games=1,receptions=4,targets=6,receiving_yards=40)]
            def load_snap_counts(self,seasons):
                self.snap_seasons.extend(seasons)
                return [dict(player='Player',team='ATL',season=seasons[0],week=1,
                             offense_snaps=60 if seasons[0]==2026 else 42)]
            def load_team_stats(self,**kw):return []
            def load_ftn_charting(self,**kw):return []
            def load_pbp(self,**kw):return []
        loader=Loader()
        rows,notes=fs.fetch_nfl('2026-11-01',NOW.isoformat(),loader=loader)
        row=next(r for r in rows if r['stat']=='receptions')
        self.assertEqual(loader.snap_seasons,[2026,2025])
        self.assertEqual(row['usage_observations'][0]['workload'],60)
        self.assertEqual(row['prior_usage_observations'][0]['workload'],42)

    def test_seven_current_games_use_real_verified_same_role_prior(self):
        c,data=fixture()
        with patch.object(ub,'load',return_value=data):
            self.assertTrue(ub.verify_a(c,NOW))
            r=ub.project(c,NOW)
        self.assertTrue(r['reliable'])
        self.assertEqual(r['quality']['n'],7)
        self.assertAlmostEqual(r['quality']['effective_n'],13.8)
        self.assertEqual(len(r['terms']['prior_observation_ids']),17)
        self.assertEqual(len(c['observation_ids']['prior']),17)

    def test_unused_missing_prior_does_not_corrupt_current_workload(self):
        c,data=fixture()
        c['observation_ids']['prior']=[]
        for row in data['prior_observations']:row['workload']=None
        with patch.object(ub,'load',return_value=data):r=ub.project(c,NOW)
        self.assertFalse(r['abstain'])
        self.assertFalse(r['reliable'])
        self.assertIn('thin_usage_history',r['quality']['reasons'])
        self.assertEqual(r['terms']['prior_observation_ids'],[])

    def test_missing_current_workload_still_blocks(self):
        c,data=fixture();data['observations'][0]['workload']=None
        with patch.object(ub,'load',return_value=data),self.assertRaisesRegex(ValueError,'invalid source workload'):ub.project(c,NOW)

    def test_unverified_or_changed_role_prior_does_not_qualify(self):
        c,data=fixture()
        with patch.object(ub,'load',return_value=data),patch.object(ub,'verify_a',return_value=False):
            self.assertFalse(ub.project(c,NOW)['reliable'])
        for row in data['prior_observations']:row['workload']=15.
        with patch.object(ub,'load',return_value=data):self.assertFalse(ub.project(c,NOW)['reliable'])

    def test_prior_snap_index_cannot_reuse_current_year_same_week(self):
        current=[dict(player='Player',team='ATL',season=2026,week=1,offense_snaps=60)]
        prior=[dict(player='Player',team='ATL',season=2025,week=1,offense_snaps=42)]
        log=fs.index_game_log([dict(player_display_name='Player',player_id='P',team='ATL',season=2025,week=1,receptions=4,game_date='2025-09-07')])
        r=fs.nfl_series_from_log(log,fs.index_player_snaps(prior),'ATL','Player','P','receptions','receptions')
        self.assertEqual(r[0]['workload'],42)
        self.assertNotEqual(r[0]['workload'],current[0]['offense_snaps'])

    def test_injury_reports_are_scoped_to_todays_game_week(self):
        class Loader:
            def load_injuries(self,seasons):return [
                dict(full_name='Player',gsis_id='P',team='ATL',season=2026,week=2,report_status='Out'),
                dict(full_name='Player',gsis_id='P',team='ATL',season=2026,week=8,report_status='Questionable'),
                dict(full_name='Practice only',gsis_id='Q',team='ATL',season=2026,week=8,practice_status='Out')]
        rows,notes=cf.fetch_nfl_injuries(Loader(),2026,{'Player','Practice only'},NOW.isoformat(),game_date='2026-11-01',
            schedule=[dict(gameday='2026-11-01',home_team='ATL',away_team='TB',week=8)])
        self.assertEqual([(r['player'],r['status']) for r in rows],[('Player','questionable')])

if __name__=='__main__':unittest.main()
