import copy,hashlib,json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from v2.nhl_sog_daily_ledger import Ledger,canonical,law,atomic_blob
from v2.nhl_sog_pregame_schedule import capture_identity,official_games


def fixture(day):
    t=f'2030-01-{day:02d}'
    c=dict(official_game_id=str(day),player_id='1234567',team_id='TOR',opponent_id='BOS',
      event_id='provider'+str(day),event_start_at=t+'T23:00:00Z',quote_at=t+'T20:00:00Z',
      stat_key='shots on goal',period='full',book='original',line=2.5,
      settlement_policy='strict_gt_lt_equal_push')
    m=dict(rate_a=6.,rate_b=30.,plugin_rate=.2,plugin_exposure=18.,
      exposure_pmf=[[15.,.5],[20.,.5]],input_freeze_at=t+'T20:01:00Z',
      fit_data_cutoff_at=t+'T19:00:00Z',source_manifest=[{'received_at':t+'T19:00:00Z','content_sha256':'a'*64}],
      player_id=c['player_id'],current_team_id='TOR',target_event_id=c['event_id'],
      event_start_at=c['event_start_at'])
    return c,m,datetime.fromisoformat(t+'T21:00:00+00:00')


def outcome(gid,y=3,state='OFF',player='1234567',toi='18:10'):
    doc=dict(id=int(gid),gameState=state,homeTeam={'abbrev':'TOR'},awayTeam={'abbrev':'BOS'},
      playerByGameStats={'homeTeam':{'forwards':[dict(playerId=player,sog=y,toi=toi)]}})
    raw=canonical(doc)
    return doc,dict(raw=raw,sha256=hashlib.sha256(raw).hexdigest(),
      url='https://api-web.nhle.com/v1/gamecenter/'+gid+'/boxscore',received_at='2030-01-05T12:00:00Z')


class Daily(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.l=Ledger(Path(self.tmp.name)/'ledger.sqlite')
    def tearDown(self):self.l.db.close();self.tmp.cleanup()
    def freeze(self,day=1,mut=None):
        c,m,n=fixture(day)
        if mut:mut(c,m)
        return self.l.freeze(c,m,run_id='fixture',code_sha='a'*40,now=n)
    def test_three_slates_failure_recovery_multiple_mornings(self):
        failures=[]
        def down(*a):raise OSError('source unavailable')
        with self.assertRaises(OSError):capture_identity('2030-01-01',down,down,lambda *x:failures.append(x[0]))
        self.assertEqual(self.l.db.execute('select count(*) from forecasts').fetchone()[0],0)
        self.assertEqual(self.freeze(2)['newly_frozen'],5)
        self.assertEqual(self.l.settle(lambda g:outcome(g,state='LIVE'),run_id='pending')['pending'],5)
        a=self.l.settle(outcome,run_id='morning1');self.assertEqual(a['newly_settled'],5)
        self.assertEqual(self.freeze(3)['newly_frozen'],5)
        b=self.l.settle(outcome,run_id='morning2')
        self.assertEqual((b['newly_settled'],b['previously_settled'],b['unique_forecast_dates'],b['unique_settled_contracts']),(5,5,2,2))
        self.assertEqual(self.l.settle(outcome,run_id='retry')['previously_settled'],10)
    def test_future_actual_toi_forbidden(self):
        with self.assertRaises(ValueError):self.freeze(mut=lambda c,m:m.update(actual_toi=25))
    def test_three_minute_cutoff(self):
        c,m,n=fixture(1)
        with self.assertRaises(ValueError):self.l.freeze(c,m,run_id='late',code_sha='a'*40,
            now=datetime(2030,1,1,22,58,tzinfo=timezone.utc))
    def test_hash_tamper_blocks_settlement(self):
        self.freeze()
        row=self.l.db.execute('select id,body from forecasts limit 1').fetchone()
        f=json.loads(row[1]);f['over']=.99
        self.l.db.execute('update forecasts set body=? where id=?',(canonical(f),row[0]));self.l.db.commit()
        self.assertEqual(self.l.settle(outcome,run_id='tamper')['unresolved'],1)
    def test_real_transaction_process_crash_rollback(self):
        import subprocess,sys
        path=self.l.db.execute('pragma database_list').fetchone()[2]
        code="import sqlite3,sys,time; c=sqlite3.connect(sys.argv[1]); c.execute('BEGIN IMMEDIATE'); c.execute(\"INSERT INTO forecasts VALUES('partial','c','M0','2030-01-01','{}')\"); print('READY',flush=True); time.sleep(30)"
        p=subprocess.Popen([sys.executable,'-c',code,path],stdout=subprocess.PIPE,text=True)
        try:
            self.assertEqual(p.stdout.readline().strip(),'READY');p.kill();p.wait(timeout=5)
        finally:
            if p.poll() is None:p.kill();p.wait()
            p.stdout.close()
        self.assertEqual(self.l.db.execute('select count(*) from forecasts').fetchone()[0],0)
        self.assertEqual(self.freeze()['newly_frozen'],5)
    def test_filesystem_without_hardlinks_uses_verified_no_overwrite_objects(self):
        import errno
        with patch('os.link',side_effect=OSError(errno.EOPNOTSUPP,'unsupported')):
            self.assertEqual(self.freeze()['newly_frozen'],5)
            self.assertEqual(self.freeze()['newly_frozen'],0)
            self.assertEqual(self.l.settle(outcome,run_id='fallback')['newly_settled'],5)
    def test_incomplete_content_addressed_write_is_quarantined_and_retried(self):
        raw=b'complete expected source bytes';sha=hashlib.sha256(raw).hexdigest();p=Path(self.tmp.name)/sha
        p.write_bytes(b'partial');atomic_blob(p,raw)
        self.assertEqual(p.read_bytes(),raw);self.assertTrue(list(Path(self.tmp.name).glob(sha+'.incomplete.*')))
    def test_unconfirmed_freeze_is_never_settled(self):
        self.freeze();self.l.db.execute('DELETE FROM freeze_receipts');self.l.db.commit()
        result=self.l.settle(outcome,run_id='unconfirmed')
        self.assertEqual(result['newly_settled'],0);self.assertEqual(result['unresolved'],5)
        self.assertEqual(result['unique_forecast_dates'],0)
    def test_commit_finishing_after_cutoff_has_no_prospective_receipt(self):
        c,m,now=fixture(1)
        times=iter([now,now,now,datetime(2030,1,1,23,1,tzinfo=timezone.utc)])
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None):return next(times)
        with patch('v2.nhl_sog_daily_ledger.datetime',Clock):
            with self.assertRaisesRegex(ValueError,'FREEZE_COMMIT_AFTER_CUTOFF'):
                self.l.freeze(c,m,run_id='slow-write',code_sha='a'*40)
        self.assertEqual(self.l.db.execute('select count(*) from freeze_receipts').fetchone()[0],0)
        result=self.l.settle(outcome,run_id='after-slow-write')
        self.assertEqual(result['newly_settled'],0);self.assertEqual(result['unique_forecast_dates'],0)
    def test_rescheduled_game_is_not_silently_graded_as_original_market(self):
        self.freeze()
        def changed(g):
            d,r=outcome(g);d['startTimeUTC']='2030-01-03T23:00:00Z';r['raw']=canonical(d);r['sha256']=hashlib.sha256(r['raw']).hexdigest();return d,r
        result=self.l.settle(changed,run_id='rescheduled')
        self.assertEqual(result['newly_settled'],0);self.assertEqual(result['unresolved'],5)
        self.assertIn('RESCHEDULED_GAME_ORIGINAL_CONTRACT_REVIEW',result['reasons'])
    def test_after_start(self):
        c,m,n=fixture(1)
        with self.assertRaises(ValueError):self.l.freeze(c,m,run_id='x',code_sha='a'*40,now=datetime(2030,1,2,tzinfo=timezone.utc))
    def test_future_feature(self):
        with self.assertRaises(ValueError):self.freeze(mut=lambda c,m:m.update(fit_data_cutoff_at='2030-01-02T01:00:00Z'))
    def test_future_source(self):
        with self.assertRaises(ValueError):self.freeze(mut=lambda c,m:m.update(source_manifest=[dict(received_at='2030-01-02T01:00:00Z')]))
    def test_identity(self):
        with self.assertRaises(ValueError):self.freeze(mut=lambda c,m:m.update(player_id='wrong'))
    def test_trade(self):
        with self.assertRaises(ValueError):self.freeze(mut=lambda c,m:m.update(current_team_id='BOS'))
    def test_duplicate_freeze_unchanged(self):
        self.freeze();before=self.l.db.execute('select body from forecasts order by id').fetchall()
        self.assertEqual(self.freeze()['newly_frozen'],0)
        self.assertEqual(before,self.l.db.execute('select body from forecasts order by id').fetchall())
    def test_incomplete_pmf_atomic(self):
        with self.assertRaises(ValueError):self.freeze(mut=lambda c,m:m.update(exposure_pmf=[[20,.4]]))
        self.assertEqual(self.l.db.execute('select count(*) from forecasts').fetchone()[0],0)
    def test_nan_pmf(self):
        with self.assertRaises(ValueError):self.freeze(mut=lambda c,m:m.update(rate_a=float('nan')))
    def test_mid_compute_failure_no_partial_family(self):
        from v2.nhl_sog_daily_ledger import law as original
        def broken(m,k):
            if k=='nb2_fixed_shape4':raise RuntimeError('crash')
            return original(m,k)
        with patch('v2.nhl_sog_daily_ledger.law',side_effect=broken):
            with self.assertRaises(RuntimeError):self.freeze()
        self.assertEqual(self.freeze()['newly_frozen'],5)
    def test_missing_official(self):
        self.freeze()
        def down(g):raise OSError('missing')
        self.assertEqual(self.l.settle(down,run_id='x')['unresolved'],5)
    def test_dnp_not_zero(self):
        self.freeze();self.assertEqual(self.l.settle(lambda g:outcome(g,toi='00:00'),run_id='x')['unresolved'],5)
    def test_wrong_official_identity(self):
        self.freeze();self.assertEqual(self.l.settle(lambda g:outcome('999'),run_id='x')['unresolved'],5)
    def test_corrected_official_preserves_revision(self):
        self.freeze();self.l.settle(outcome,run_id='x')
        self.assertEqual(self.l.settle(lambda g:outcome(g,y=4),run_id='correction')['corrections'],5)
        self.assertEqual(self.l.db.execute('select count(*) from outcomes').fetchone()[0],10)
    def test_zero_tail_complete(self):
        self.freeze();self.l.settle(lambda g:outcome(g,y=0),run_id='zero')
        for (raw,) in self.l.db.execute('select body from forecasts'):
            f=json.loads(raw);d=f['distribution'];self.assertGreater(d['pmf_from_zero'][0],0)
            self.assertAlmostEqual(sum(d['pmf_from_zero'])+d['tail_mass'],1)
    def test_blob_crash_recovery_and_hash(self):
        p=Path(self.tmp.name)/'source';atomic_blob(p,b'original');atomic_blob(p,b'original')
        with self.assertRaises(ValueError):atomic_blob(p,b'overwrite')
        self.assertEqual(p.read_bytes(),b'original')
    def test_empty_ledger(self):
        r=self.l.settle(outcome,run_id='empty');self.assertEqual(r['newly_settled'],0)
    def test_scoreboard_failure_signed_schedule_recovery(self):
        day='2030-01-01';failures=[]
        def cap(url,kind,sid):
            if kind=='score':raise OSError('HTTP 503')
            return {'source_url':url},{'gameWeek':[{'date':day,'games':[{'id':1}]}]}
        r,d=capture_identity(day,cap,None,lambda *x:failures.append(x[0]))
        self.assertEqual(official_games(r['source_url'],d,day),[{'id':1}]);self.assertEqual(failures,['LIVE_SCORE_FETCH'])
    def test_bad_schedule_endpoint(self):
        with self.assertRaises(ValueError):official_games('https://fake/score/2030-01-01',{},'2030-01-01')
    def test_duplicate_schedule_ids(self):
        with self.assertRaises(ValueError):official_games('https://api-web.nhle.com/v1/score/2030-01-01',{'games':[{'id':1},{'id':1}]},'2030-01-01')

if __name__=='__main__':unittest.main()
