import tempfile,unittest,json,hashlib
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
from v2.nhl_sog_history_refresh import refresh,load_current,canon
from v2.nhl_sog_daily_math import _clean_history,ExperimentBlocked


class HistoryRefreshTests(unittest.TestCase):
    def test_new_players_signed_import_and_no_market_calls(self):
        with tempfile.TemporaryDirectory() as d:
            calls=[];now=datetime.now(timezone.utc);cutoff=(now+timedelta(minutes=5)).isoformat();event=(now+timedelta(days=1)).isoformat()
            def capture(url):
                calls.append(url);r={'received_at':now.isoformat(),'source_url':url}
                if url.endswith('/landing') and '/player/' in url:return r,{'playerId':1234567,'position':'C','featuredStats':{'season':20262027}}
                if '/game-log/' in url:return r,{'gameLog':[{'gameId':1,'gameDate':'2026-01-01','shots':3,'toi':'18:00'}]}
                return r,{'id':1,'gameState':'OFF'}
            def imported(**kw):
                self.assertEqual(kw['player_id'],'1234567');self.assertIn('1',kw['completed_game_receipts'])
                p=Path(d)/'obs.json';p.write_text(json.dumps({'event_id':'1','source_game_log_row':{'gameDate':'2026-01-01'}}))
                return [{'observation_receipt':{'archive_path':'obs.json'}}]
            with patch('v2.nhl_sog_history_refresh.import_signed_official_history',side_effect=imported):
                result,ref=refresh({'1234567':'F'},pool=d,capture=capture,cutoff=cutoff,event_start=event)
            self.assertIn('1234567',result['player_records']);self.assertEqual(result['final_games_captured'],1)
            self.assertTrue(all('nhle.com' in x for x in calls));self.assertEqual(hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest(),ref['sha256'])
    def test_complete_signed_new_player_history_reaches_real_model_math(self):
        import os
        from tests.test_v25_sog_c03_signed_cross_module import signed_fixture,TEST_KEY
        from v2.nhl_sog_official_history_producer import import_signed_official_history,independent_verify_observation_lineage
        from v2.nhl_sog_daily_math import fit_model
        from v2.nhl_sog_daily_ledger import law,KINDS
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'PICKEM_C03_COLLECTOR_HMAC_KEY_HEX':TEST_KEY}):
            root=Path(tmp);now=datetime.now(timezone.utc);clock=now.isoformat();freeze=(now+timedelta(minutes=2)).isoformat();event=(now+timedelta(hours=4)).isoformat()
            finals={};base='https://api-web.nhle.com/v1/'
            for k in range(1,11):
                gid=str(2026020000+k)
                finals[gid]=signed_fixture(root,source_url=base+'gamecenter/'+gid+'/landing',
                    document={'id':int(gid),'gameState':'OFF'},clock=clock,source_id='final'+gid)
            histories={}
            for i in range(21):
                pid=str(8470000+i)
                profile=signed_fixture(root,source_url=base+'player/'+pid+'/landing',document={'playerId':int(pid),'position':'C'},clock=clock,source_id='profile'+pid)
                log=signed_fixture(root,source_url=base+'player/'+pid+'/game-log/20262027/2',
                    document={'gameLog':[{'gameId':2026020000+k,'gameDate':'2026-11-'+str(k).zfill(2),'shots':k,'toi':'20:00'} for k in reversed(range(1,11))]},clock=clock,source_id='log'+pid)
                entries=import_signed_official_history(player_id=pid,position_group='F',gamelog_receipt=log,player_profile_receipt=profile,completed_game_receipts=finals,archive_root=root,input_freeze_at=freeze,event_start_at=event)
                histories[pid]=[independent_verify_observation_lineage(x,archive_root=root,freeze=freeze,event_start=event) for x in entries]
            model=fit_model(histories['8470000'],[r for pid,rs in histories.items() if pid!='8470000' for r in rs],archive_root=root,player_id='8470000',position_group='F',input_freeze_at=freeze,event_start_at=event,target_event_id='future',current_team_id='TOR')
            self.assertEqual(model['own_played_games'],10);self.assertEqual(model['peer_players'],20)
            self.assertAlmostEqual(model['plugin_rate']*model['plugin_exposure'],5.5)
            for kind in KINDS.values():
                d=law(model,kind);self.assertAlmostEqual(sum(d['pmf_from_zero'])+d['tail_mass'],1,places=11)
    def test_missing_profile_stays_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            def fail(u):raise OSError('unavailable')
            r,_=refresh({'1234567':'F'},pool=d,capture=fail,cutoff='2099-01-01T01:00:00Z',event_start='2099-01-01T02:00:00Z')
            self.assertEqual(r['qualified_players'],0);self.assertEqual(len(r['failures']),1)
    def test_target_game_not_imported(self):
        with tempfile.TemporaryDirectory() as d:
            def cap(u):
                r={'received_at':'2026-01-01T00:00:00Z'}
                return r,({'playerId':1234567,'position':'C','featuredStats':{'season':20262027}} if '/landing' in u else {'gameLog':[{'gameId':99,'gameDate':'2025-01-01'}]})
            r,_=refresh({'1234567':'F'},pool=d,capture=cap,cutoff='2099-01-01T01:00:00Z',event_start='2099-01-01T02:00:00Z',target_games={'99'})
            self.assertEqual(r['player_records'],{});self.assertIn('TARGET_GAME_IN_HISTORY',r['failures'][0]['reason'])
    def test_expired_history_not_admitted(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'NO_FRESH'):load_current(d,day='2026-11-19',now=datetime.now(timezone.utc))
    def test_source_receive_after_cutoff_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            r,_=refresh({'1234567':'F'},pool=d,capture=lambda u:({'received_at':'2099-01-02T00:00:00Z'},{}),cutoff='2099-01-01T01:00:00Z',event_start='2099-01-01T02:00:00Z')
            self.assertIn('SOURCE_AFTER_REFRESH_CUTOFF',r['failures'][0]['reason'])
    def test_official_game_date_orders_latest_not_receipt_time(self):
        rows=[{'player_id':'1','event_id':'2','position_group':'F','event_ended_at':'2026-11-19T12:00:00Z','source_game_log_row':{'gameDate':'2026-11-18'}},
              {'player_id':'1','event_id':'1','position_group':'F','event_ended_at':'2026-11-19T13:00:00Z','source_game_log_row':{'gameDate':'2026-11-10'}}]
        with patch('v2.nhl_sog_daily_math.verify_observation',side_effect=rows):
            result=_clean_history([{},{}],root='.',freeze='2026-11-19T14:00:00Z')
        self.assertEqual([x['event_id'] for x in result],['1','2'])
    def test_missing_official_date_blocks_math(self):
        with patch('v2.nhl_sog_daily_math.verify_observation',return_value={'player_id':'1','event_id':'1','position_group':'F'}):
            with self.assertRaises(ExperimentBlocked):_clean_history([{}],root='.',freeze='2026-11-19T14:00:00Z')

if __name__=='__main__':unittest.main()
