import unittest,tempfile,os
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from tests.test_v25_sog_c03_signed_cross_module import signed_fixture,TEST_KEY
from v2.nhl_sog_daily_history_producer import import_signed_official_history,independent_verify_observation_lineage,_final_view,ExperimentBlocked

class DailyFinalTests(unittest.TestCase):
    def test_genuine_signed_daily_final_source_rechecks_full_lineage(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'PICKEM_C03_COLLECTOR_HMAC_KEY_HEX':TEST_KEY}):
            root=Path(tmp);now=datetime.now(timezone.utc);clock=now.isoformat();freeze=(now+timedelta(minutes=2)).isoformat();future=(now+timedelta(hours=4)).isoformat();base='https://api-web.nhle.com/v1/'
            profile=signed_fixture(root,source_url=base+'player/8470000/landing',document={'playerId':8470000,'position':'C'},clock=clock,source_id='profile')
            log=signed_fixture(root,source_url=base+'player/8470000/game-log/20262027/2',document={'gameLog':[{'gameId':2026020001,'gameDate':'2026-11-01','shots':3,'toi':'18:00'}]},clock=clock,source_id='log')
            score=signed_fixture(root,source_url=base+'score/2026-11-01',document={'games':[{'id':2026020001,'gameDate':'2026-11-01','gameState':'OFF'}]},clock=clock,source_id='score')
            entries=import_signed_official_history(player_id='8470000',position_group='F',gamelog_receipt=log,player_profile_receipt=profile,completed_game_receipts={'2026020001':score},archive_root=root,input_freeze_at=freeze,event_start_at=future)
            self.assertEqual(len(entries),1);self.assertEqual(entries[0]['raw_final_receipt']['body_sha256'],score['body_sha256'])
            independent_verify_observation_lineage(entries[0],archive_root=root,freeze=freeze,event_start=future)
    def test_wrong_day_cannot_be_relabelled(self):
        with self.assertRaises(ExperimentBlocked):_final_view({'source_url':'https://api-web.nhle.com/v1/score/2026-11-01'},{'games':[{'id':1,'gameDate':'2026-11-02','gameState':'OFF'}]},'1','2026-11-01')
    def test_pending_not_final(self):
        with self.assertRaises(ExperimentBlocked):_final_view({'source_url':'https://api-web.nhle.com/v1/score/2026-11-01'},{'games':[{'id':1,'gameDate':'2026-11-01','gameState':'LIVE'}]},'1','2026-11-01')
    def test_duplicate_game_identity_rejected(self):
        with self.assertRaises(ExperimentBlocked):_final_view({'source_url':'https://api-web.nhle.com/v1/score/2026-11-01'},{'games':[{'id':1,'gameDate':'2026-11-01','gameState':'OFF'}]*2},'1','2026-11-01')

if __name__=='__main__':unittest.main()
