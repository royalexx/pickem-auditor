import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import lineup_feeds as lf
import usage_baseline as ub

def hockey(ident='1',day='2026-10-01'):
    return dict(gameType=2,gameState='OFF',gameDate=day,
                homeTeam={'abbrev':'CHI','sog':3},awayTeam={'abbrev':'BOS'},
                playerByGameStats={'homeTeam':{'forwards':[{'playerId':1,'sog':3,'blockedShots':1,'toi':'10:00'}],
                'defense':[],'goalies':[{'playerId':2,'saves':28,'toi':'60:00'}]}})

def football():
    return {'header':{'season':{'type':2},'competitions':[{'date':'2026-10-01T23:00:00Z',
            'status':{'type':{'completed':True}}}]},'boxscore':{'players':[{'team':{'abbreviation':'CHI'},
            'statistics':[{'name':'defensive','keys':['soloTackles','totalTackles'],'totals':['5','8'],
            'athletes':[{'athlete':{'id':'10'},'stats':['5','8']}]}]}]}}

def roster():
    return dict(event_id='1',team='CHI',date='2026-10-01',source_url='https://www.nfl.com/game/1',
                roster_complete=True,active_players=['00-0000001','00-0000002'])

class FeedCompletionTests(unittest.TestCase):
    def test_source_alias_reaches_canonical_engine_baseline(self):
        from datetime import datetime,timezone
        import shared_context as sc
        from unittest.mock import patch
        row=dict(sport='NHL',player_id='2',team='CHI',stat='goalie saves',game_date='2026-10-02',
                 retrieved_at='2026-10-02T12:00:00Z',source_url='https://api-web.nhle.com/game/1',
                 usage_observations=[dict(id='1',date='2026-10-01',value=28,workload=60)])
        with tempfile.TemporaryDirectory() as d,ub.using_directory(d):
            ub.persist([row],d)
            candidate={**row,'stat':'saves','scouting':{'historical_usage':row['historical_usage']}}
            loaded=ub.load(candidate,datetime(2026,10,2,12,10,tzinfo=timezone.utc))
            self.assertEqual(loaded['stat'],'saves')
            self.assertEqual(sc.history_path('NHL','CHI','saves'),sc.history_path('NHL','CHI','goalie saves'))

    def test_canonical_goalie_saves_counts_goaltender_only(self):
        row=lf.nhl_game(hockey(),'CHI','goalie saves','1','https://api-web.nhle.com/game/1')
        self.assertEqual(row['team_total'],28)
        self.assertEqual(row['production'],{'1':0,'2':28})

    def test_nhl_lookback_collects_both_seasons(self):
        called=[]
        def fetch(url):
            called.append(url)
            if '20252026' in url:return {'games':[dict(id=1,gameDate='2026-04-01',gameState='OFF',gameType=2)]}
            if '20262027' in url:return {'games':[dict(id=2,gameDate='2026-10-01',gameState='OFF',gameType=2)]}
            return hockey(day='2026-04-01' if '/1/' in url else '2026-10-01')
        with tempfile.TemporaryDirectory() as d,ub.using_directory(d):
            out=lf.collect('NHL','CHI','goalie saves','2026-10-02',lookback_days=200,fetch=fetch)
        self.assertEqual(out['collection']['completed'],2)
        self.assertTrue(any('20252026' in u for u in called))

    def test_verified_nfl_roster_keeps_zero_stat_active_player(self):
        manifest=roster();manifest['game_id']='2026_04_CHI_NYG'
        out=lf.espn_game(football(),'NFL','CHI','tackles + assists','1','https://www.espn.com/game/1',
                         id_map={'10':'00-0000001'},active_roster=manifest)
        self.assertEqual(out['production'],{'00-0000001':8,'00-0000002':0})
        self.assertEqual(out['roster_source_url'],roster()['source_url'])
        self.assertEqual(out['id'],'2026_04_CHI_NYG')
        self.assertEqual(out['source_event_id'],'1')

    def test_wrong_game_day_team_or_incomplete_roster_rejected(self):
        for key,value in [('event_id','2'),('date','2026-10-02'),('team','BOS'),('roster_complete',False),
                          ('active_players',['00-0000002'])]:
            with self.subTest(key=key):
                row=roster();row[key]=value
                with self.assertRaises(ValueError):
                    lf.espn_game(football(),'NFL','CHI','tackles','1','https://www.espn.com/game/1',
                                 id_map={'10':'00-0000001'},active_roster=row)

    def test_roster_import_rejects_duplicate_without_overwriting(self):
        data={'version':'nfl-active-rosters-v1','games':[roster()]}
        with tempfile.TemporaryDirectory() as d,ub.using_directory(d):
            path=lf.import_active_rosters(data);before=path.read_bytes()
            data['games'].append(copy.deepcopy(roster()))
            with self.assertRaises(ValueError):lf.import_active_rosters(data)
            self.assertEqual(path.read_bytes(),before)

    def test_nfl_collection_loads_imported_manifest(self):
        def fetch(url):
            if '/teams?' in url:return {'sports':[{'leagues':[{'teams':[{'team':{'id':'3','abbreviation':'CHI'}}]}]}]}
            if '/schedule?' in url:return {'events':[{'id':'1','date':'2026-10-01T23:00:00Z','competitions':[
                {'status':{'type':{'completed':True}},'competitors':[{'team':{'abbreviation':'CHI'}}]}]}]}
            return football()
        with tempfile.TemporaryDirectory() as d,ub.using_directory(d):
            lf.import_active_rosters({'version':'nfl-active-rosters-v1','games':[roster()]})
            out=lf.collect('NFL','CHI','tackles','2026-10-02',fetch=fetch,lookback_days=2,id_map={'10':'00-0000001'})
        self.assertEqual(out['games'][0]['production']['00-0000002'],0)

if __name__=='__main__':unittest.main()
