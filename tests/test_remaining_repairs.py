"""Offline adversarial coverage for temporal, allocation and collection repairs."""
import copy
from datetime import datetime,timedelta,timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import usage_baseline as ub
import lineup_feeds as lf
import shared_context as sc
import context_validation as cv
import probability_blend as pb
import test_shared_context as fixtures

def nba_box():
    return {'header':{'season':{'type':2},'competitions':[{'date':'2026-10-01T23:00:00Z','status':{'type':{'completed':True}}}]},
      'boxscore':{'players':[{'team':{'abbreviation':'T'},'statistics':[{'names':['points','threePointFieldGoalsMade-threePointFieldGoalsAttempted'],
      'totals':['30','5-12'],'athletes':[{'athlete':{'id':'P'},'stats':['10','2-5']},
      {'athlete':{'id':'R'},'stats':['20','3-7']},{'athlete':{'id':'Q'},'didNotPlay':True,'stats':[]}]}]}]}}

class HistoryIntegrityTests(unittest.TestCase):
    def test_zero_exposure_reduces_usage_without_polluting_conversion(self):
        c,data=fixtures.baseline()
        with patch.object(ub,'load',return_value=data):before=ub.project(c,fixtures.NOW)
        data['observations'][-1].update(value=0,workload=0)
        with patch.object(ub,'load',return_value=data):after=ub.project(c,fixtures.NOW)
        self.assertLess(after['terms']['opportunities'],before['terms']['opportunities'])
        self.assertIn('g14',after['terms']['recent_observation_ids'])

    def test_prior_future_rows_and_forged_ids_cannot_qualify_a(self):
        c,data=fixtures.baseline();data['prior_observations']=[dict(id='prior',date='2027-01-01',value=20,workload=30)]
        with patch.object(ub,'load',return_value=data):
            with self.assertRaises(ValueError):ub.verify_a(c,fixtures.NOW)
        c,data=fixtures.baseline();c['observation_ids']['baseline'][0]='forged'
        with patch.object(ub,'load',return_value=data):self.assertFalse(ub.verify_a(c,fixtures.NOW))

    def test_timestamp_is_compared_in_toronto(self):
        self.assertEqual(ub.local_day('2026-10-26T01:00:00Z').isoformat(),'2026-10-25')
        with self.assertRaises(ValueError):ub.local_day('2026-10-26T01:00:00')

    def test_collector_archive_is_immutable_and_corruption_detected(self):
        import fetch_slate as fs
        c,data=fixtures.baseline();row={k:c[k] for k in ('sport','team','stat','game_date','player_id')}
        row.update(retrieved_at=fixtures.NOW.isoformat(),source_url='https://www.nba.com/stats/')
        fs.apply_log_summary(row,[dict(tie=r['id'],when=r['date'],value=r['value'],workload=r['workload']) for r in data['observations']])
        with tempfile.TemporaryDirectory() as d,ub.using_directory(d):
            ub.persist([row],d);c['scouting']['historical_usage']=row['historical_usage']
            loaded=ub.load(c,fixtures.NOW);digest=loaded['content_sha256']
            self.assertTrue((Path(d)/'usage'/'snapshots'/(digest+'.json')).exists())
            path=Path(d)/'usage'/(row['historical_usage']+'.json');bad=json.loads(path.read_text())
            bad['observations'][0]['value']=999;path.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError,'checksum'):ub.load(c,fixtures.NOW)

class EmbeddedAllocationTests(unittest.TestCase):
    def case(self):return fixtures.JointAllocationTests().setup_case()
    def apply(self,c,a,b,blend,ctx,data):
        with tempfile.TemporaryDirectory() as d,patch.object(sc,'history_path',return_value=Path(d)/'h.json'):
            (Path(d)/'h.json').write_text(json.dumps(data));return sc.apply(c,a,b,blend,ctx,fixtures.NOW)

    def test_absence_already_in_baseline_does_not_receive_full_bonus(self):
        c,a,b,blend,ctx=self.case();data=fixtures.history()
        ids=[str(i) for i in range(20,35)]
        c['observation_ids']={'baseline':ids[:10],'recent':ids[10:],'prior':[]}
        a['shrunk_mean']=40;b['mean_b']=40;b['terms'].update(observation_ids=ids,recent_observation_ids=ids[-5:],observed_production={i:40 for i in ids})
        out=self.apply(c,a,b,blend,ctx,data)
        self.assertTrue(out['applied'],out);self.assertEqual(out['factors'],{'a':1,'b':1})
        self.assertEqual(out['components']['a']['mean'],40)

    def test_mixed_baseline_only_moves_remaining_distance(self):
        c,a,b,blend,ctx=self.case();data=fixtures.history()
        ids=[str(i) for i in list(range(10))+list(range(20,30))]
        c['observation_ids']={'baseline':ids[:10],'recent':ids[10:],'prior':[]}
        a['shrunk_mean']=30;b['mean_b']=30;b['terms'].update(observation_ids=ids,recent_observation_ids=ids[-5:],
            observed_production={i:data['games'][int(i)]['production']['P'] for i in ids})
        out=self.apply(c,a,b,blend,ctx,data)
        self.assertTrue(out['applied'],out);self.assertAlmostEqual(out['factors']['a'],4/3)
        self.assertEqual(out['components']['a']['mean'],40)

    def test_inconsistent_or_missing_source_coverage_blocks_context(self):
        c,a,b,blend,ctx=self.case();data=fixtures.history();data['games'][0]['production']['P']=19;data['games'][0]['production']['R']=51
        out=self.apply(c,a,b,blend,ctx,data);self.assertFalse(out['eligible']);self.assertIn('disagree',out['detail'])
        data=fixtures.history();data['games']=data['games'][1:]
        self.assertFalse(self.apply(c,a,b,blend,ctx,data)['eligible'])

class CollectorTests(unittest.TestCase):
    def test_nba_roster_and_attempts_come_from_complete_box_score(self):
        out=lf.espn_game(nba_box(),'NBA','T','threes','g','https://www.espn.com/game')
        self.assertEqual(out['production'],{'P':2,'R':3})
        self.assertEqual(out['features']['three_point_attempts'],{'P':5,'R':7})
        self.assertNotIn('Q',out['active_players'])

    def test_espn_active_flag_does_not_erase_bench_players(self):
        data=nba_box();players=data['boxscore']['players'][0]['statistics'][0]['athletes']
        players[1]['active']=False;players[2]['reason']="COACH'S DECISION"
        out=lf.espn_game(data,'NBA','T','threes','g','https://www.espn.com/game')
        self.assertEqual(out['production'],{'P':2,'R':3,'Q':0})
        self.assertEqual(out['features']['three_point_attempts']['Q'],0)

    def test_missing_count_is_not_a_zero_and_totals_must_balance(self):
        data=nba_box();data['boxscore']['players'][0]['statistics'][0]['athletes'][0]['stats']=[]
        with self.assertRaises(ValueError):lf.espn_game(data,'NBA','T','points','g','https://www.espn.com/game')
        data=nba_box();data['boxscore']['players'][0]['statistics'][0]['totals'][0]='99'
        with self.assertRaises(ValueError):lf.espn_game(data,'NBA','T','points','g','https://www.espn.com/game')

    def test_nfl_incomplete_roster_is_explicitly_unsupported(self):
        with self.assertRaisesRegex(ValueError,'active roster'):
            lf.espn_game(nba_box(),'NFL','T','tackles + assists','g','https://www.espn.com/game',id_map={'P':'00-P'})

    def test_nhl_source_keys_and_final_status(self):
        data=dict(gameType=2,gameState='OFF',gameDate='2026-10-01',homeTeam=dict(abbrev='T',sog=3),
            playerByGameStats={'homeTeam':{'forwards':[dict(playerId=1,sog=2,blockedShots=0,toi='18:30')],
                'defense':[dict(playerId=2,sog=1,blockedShots=1,toi='21:00')],'goalies':[dict(playerId=3,saves=20,toi='60:00')]}})
        out=lf.nhl_game(data,'T','shots on goal','g','https://api-web.nhle.com/game')
        self.assertEqual(out['team_total'],3);self.assertEqual(out['features']['ice_time']['1'],18.5)
        data['gameState']='LIVE'
        with self.assertRaises(ValueError):lf.nhl_game(data,'T','shots on goal','g','https://api-web.nhle.com/game')

    def test_collection_is_bounded_and_does_not_commit_partial_history(self):
        events={'events':[{'id':'g','season':{'type':2},'date':'2026-10-01T23:00:00Z','competitions':[{'status':{'type':{'completed':True}},'competitors':[{'team':{'abbreviation':'T'}}]}]}]}
        def fetch(url):
            if '/teams?' in url:return {'sports':[{'leagues':[{'teams':[{'team':{'id':'1','abbreviation':'T'}}]}]}]}
            return events if '/schedule?' in url else nba_box()
        with tempfile.TemporaryDirectory() as d,ub.using_directory(d):
            data=lf.collect('NBA','T','points','2026-10-03',fetch=fetch,max_games=1)
            self.assertEqual(data['collection']['completed'],1)
            path=sc.history_path('NBA','T','points');original=path.read_bytes()
            def broken(url):
                if '/teams?' in url:return {'sports':[{'leagues':[{'teams':[{'team':{'id':'1','abbreviation':'T'}}]}]}]}
                return events if '/schedule?' in url else {}
            with self.assertRaises(ValueError):lf.collect('NBA','T','points','2026-10-03',fetch=broken,max_games=1)
            self.assertEqual(path.read_bytes(),original)

class ProspectiveValidationTests(unittest.TestCase):
    def test_snapshot_loop_drops_a_game_that_started_during_processing(self):
        import jobs
        now=datetime(2026,10,26,20,tzinfo=timezone.utc)
        row={'id':'NBA|P|points|over','_meta':{'event_start':'2026-10-26T19:59:00Z'}}
        with patch.object(jobs.pm,'evaluate_candidate') as evaluate:
            snapshots,errors=jobs.run_pipeline_batch([row],clock_fn=lambda:now)
        self.assertEqual((snapshots,errors),([],0));evaluate.assert_not_called()

    def snapshot(self,i=0):
        dt=datetime(2025,1,1,tzinfo=timezone.utc)+timedelta(days=i)
        return dict(forecast_at=dt.replace(hour=12).isoformat(),event_start=dt.replace(hour=20).isoformat(),
            game_date=dt.date().isoformat(),run_at='wrong sort label',sport='NBA',player='P',stat='points',side='over',reference_line=10.5,outcome='win',
            engine_a=dict(version='history-v5',reliable=True,observation_ids_verified=True,q_win_robust=.5,q_push_robust=0),
            engine_b=dict(version='scouting-v7',reliable=True,abstain=False,baseline_origin='collector_observations',q_win=.5,q_push=0),
            blend=dict(q_win=.5,q_push=0),shared_context=dict(version=sc.VERSION,applied=True,eligible=True,q_win=.6,q_push=0))

    def test_earliest_forecast_uses_actual_timestamp(self):
        row=self.snapshot();later=copy.deepcopy(row);later.update(forecast_at='2025-01-01T13:00:00+00:00',run_at='earliest alphabetic')
        later['shared_context']['q_win']=.9
        data=cv.rows_from_snapshots([later,row],'NBA|points')
        self.assertEqual(len(data),1);self.assertEqual(data[0]['context'][0],.6)

    def test_postgame_forecast_and_wrong_local_game_date_excluded(self):
        row=self.snapshot();row['forecast_at']=row['event_start'];self.assertEqual(cv.rows_from_snapshots([row],'NBA|points'),[])
        row=self.snapshot();row['game_date']='2025-01-02';self.assertEqual(cv.rows_from_snapshots([row],'NBA|points'),[])

    def test_fixed_context_validation_can_succeed_but_does_not_fit_new_model(self):
        rows=[]
        for day in range(90):
            for i in range(5):
                row=self.snapshot(day);row['player']=str(i);row['outcome']='win' if i<3 else 'loss';rows.append(row)
        cfg=cv.fit(rows,'NBA|points')
        self.assertNotIn('weight_a',cfg)
        self.assertTrue(cv.eligible(cfg,'NBA|points','A_ONLY',datetime(2026,1,1).date()))
        self.assertFalse(cv.eligible(cfg,'NBA|points','new blend',datetime(2026,1,1).date()))

class SettlementIntegrityTests(unittest.TestCase):
    def test_nfl_uses_target_game_not_first_player_week(self):
        import settle
        games=[dict(game_id='g2',gameday='2026-10-25',game_type='REG',season=2026,week=8,home_team='T',away_team='X',result=7)]
        rows=[
            dict(player='P', player_id='p', team='T', season=2026, week=7,
                 def_tackles_solo=99, def_tackles_with_assist=0, def_tackle_assists=2),
            dict(player='P', player_id='p', team='T', season=2026, week=8,
                 def_tackles_solo=5, def_tackles_with_assist=0, def_tackle_assists=2),
        ]
        self.assertEqual(settle._nfl_value(rows,games,'P','tackles + assists','2026-10-25'),7)
        self.assertEqual(settle._nfl_value(rows,games,'P','tackles','2026-10-25'),5)
        self.assertIsNone(settle._nfl_value(rows,games,'P','unknown','2026-10-25'))
        games[0]['result']=None
        self.assertIsNone(settle._nfl_value(rows,games,'P','tackles','2026-10-25'))

    def test_nba_dnp_is_not_an_under_win_and_date_is_local(self):
        import settle
        game=dict(when='2026-10-26T01:00:00Z',minutes=0,points=0)
        self.assertIsNone(settle._nba_value([game],'points','2026-10-25'))
        game.update(minutes=12,points=8)
        self.assertEqual(settle._nba_value([game],'points','2026-10-25'),8)
        self.assertIsNone(settle._nba_value([game],'points','2026-10-26'))

if __name__=='__main__':unittest.main()
