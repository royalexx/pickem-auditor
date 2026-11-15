import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from v2.nba_ws1.store import Receipt, Record, NBAPregameFeatureSnapshot, build_snapshot, save_snapshot

RAW=b'{"source":"fixture"}'
T='2026-11-15T18:00:00Z'

def setup():
    receipt=Receipt.capture(RAW, source='fixture', observed_at=T, origin='original_capture')
    game=Record.make('schedule', receipt, dict(game_id='espn:game:1', home_team_id='espn:team:1', away_team_id='espn:team:2', event_start_at='2026-11-16T00:00:00Z', venue=None, status='scheduled'))
    past=Record.make('player_game',receipt,dict(game_id='espn:game:0',player_id='espn:player:1',team_id='espn:team:1',opponent_id='espn:team:2',game_date='2026-11-13',minutes=0,participation='played',starter=False,stats={'points':0}))
    roster=Record.make('roster',receipt,dict(game_id='espn:game:1',player_id='espn:player:1',team_id='espn:team:1',status='eligible',uncertainty='confirmed'))
    return receipt,game,past,roster

def build(records=None, receipts=None, **kwargs):
    r,g,p,a=setup()
    return build_snapshot(game_id='espn:game:1', forecast_at='2026-11-15T18:02:00Z',input_freeze_at='2026-11-15T18:01:00Z', model_training_cutoff_at=T,records=records or [g,p,a],receipts=receipts or [r],**kwargs)

class StoreTests(unittest.TestCase):
    def test_zero_played_and_dnp_distinct(self):
        r,g,p,a=setup(); d=Record.make('player_game',r,{**p.data,'game_id':'espn:game:d','game_date':'2026-11-12','participation':'dnp','minutes':None,'stats':{}})
        s=build([g,p,a,d]).to_dict(); player=s['players'][0]
        self.assertEqual(player['features']['games_played'],1)
        self.assertEqual(player['features']['minutes_recent']['values'],[0])
        self.assertEqual(player['history'][0]['participation'],'dnp')
    def test_deterministic_roundtrip_and_immutable(self):
        r,g,p,a=setup(); s=build(); self.assertEqual(s.content_hash,build([a,p,g]).content_hash)
        self.assertEqual(s.content_hash,NBAPregameFeatureSnapshot.from_json(s.to_json()).content_hash)
        d=s.to_dict();d['game']['venue']='altered';self.assertNotEqual(d,s.to_dict())
        with self.assertRaises(Exception):s.payload='changed'
    def test_hash_tamper(self):
        s=build().to_dict();s['game']['venue']='altered'
        with self.assertRaisesRegex(ValueError,'HASH'):NBAPregameFeatureSnapshot.from_json(json.dumps(s))
    def test_same_game_and_future_are_ledgered(self):
        r,g,p,a=setup(); bad=Record.make('player_game',r,{**p.data,'game_id':g.data['game_id']})
        future=Record.make('player_game',r,{**p.data,'game_id':'espn:game:f','game_date':'2026-11-16'})
        s=build([g,p,a,bad,future]).to_dict()
        self.assertEqual(s['ledger']['rejected'],2)
        self.assertNotIn(bad.record_id,{x['record_id'] for x in s['input_records']})
        self.assertNotIn(future.record_id,{x['record_id'] for x in s['input_records']})
        self.assertEqual({x['code'] for x in s['ledger']['rejections']},{'SAME_GAME_OUTCOME','FUTURE_OR_SAME_DAY_HISTORY'})
    def test_receipt_late_even_with_early_published_clock(self):
        r,g,p,a=setup(); late=Receipt.capture(RAW,source='fixture',observed_at='2026-11-15T18:03:00Z',source_available_at=T,origin='original_capture')
        bad=Record.make('player_game',late,p.data)
        s=build([g,a,bad],[r,late]).to_dict()
        self.assertEqual(s['ledger']['rejections'][0]['code'],'SOURCE_AFTER_FREEZE')
    def test_invalid_cutoffs(self):
        with self.assertRaisesRegex(ValueError,'TRAINING'):build_snapshot(game_id='x',forecast_at=T,input_freeze_at=T,model_training_cutoff_at='2026-11-16T00:00:00Z',records=[],receipts=[])
        with self.assertRaises(ValueError):Receipt.capture(RAW,source='x',observed_at='2026-11-15',origin='original_capture')
    def test_unknown_fields_rejected(self):
        r,g,p,a=setup()
        with self.assertRaisesRegex(ValueError,'FIELDS'):Record.make('schedule',r,{**g.data,'realized_possessions':100})
    def test_crosswalk_and_trade(self):
        r,g,p,a=setup(); old=Record.make('player_game',r,{**p.data,'game_id':'espn:game:old','game_date':'2026-11-11','team_id':'espn:team:3'})
        s=build([g,p,a,old]).to_dict();self.assertTrue(s['players'][0]['features']['historical_team_change'])
        collision=Record.make('roster',r,{**a.data,'team_id':'espn:team:2'})
        s=build([g,p,a,collision]).to_dict();self.assertIn('ROSTER_COLLISION',s['abstention_codes'])
    def test_correction_retains_versions_asof(self):
        r,g,p,a=setup(); correction=Record.make('player_game',r,{**p.data,'stats':{'points':2}},revision=2,supersedes=p.record_id)
        s=build([g,p,a,correction]).to_dict()
        self.assertEqual(s['players'][0]['history'][0]['stats']['points'],2)
        self.assertEqual(s['ledger']['superseded'],1)
        conflict=Record.make('player_game',r,{**p.data,'stats':{'points':3}})
        self.assertIn('CONFLICTING_RECORDS',build([g,p,a,conflict]).to_dict()['abstention_codes'])
    def test_duplicate_and_stale_quotes(self):
        r,g,p,a=setup()
        q=Record.make('contract',r,dict(contract_id='original-1',quote_id='quote-1',game_id=g.data['game_id'],player_id=p.data['player_id'],team_id=p.data['team_id'],stat='points',period='full_game',line=10.5,quoted_at='2026-11-15T17:00:00Z',book='fixture',prices={'over':1.9,'under':1.9},payout_terms=None))
        s=build([g,p,a,q,q]).to_dict();self.assertEqual(s['ledger']['duplicates'],1)
        self.assertEqual(s['ledger']['rejections'][0]['code'],'QUOTE_STALE')
    def test_later_correction_cannot_rewrite_past_freeze(self):
        r,g,p,a=setup()
        late=Receipt.capture(RAW,source='fixture',observed_at='2026-11-16T00:00:00Z',origin='fixture')
        correction=Record.make('player_game',late,{**p.data,'stats':{'points':99}},revision=2,supersedes=p.record_id)
        result=build([g,p,a,correction],[r,late]).to_dict()
        self.assertEqual(result['players'][0]['history'][0]['stats']['points'],0)
        self.assertEqual(result['ledger']['rejections'][0]['code'],'SOURCE_AFTER_FREEZE')

    def test_rehashed_forged_feature_rejected_on_load(self):
        data=build().to_dict();data.pop('content_hash')
        data['players'][0]['features']['minutes_recent']['mean']=99
        from v2.nba_ws1.store import canonical,digest
        data['content_hash']=digest(canonical(data).encode())
        with self.assertRaisesRegex(ValueError,'DERIVATION'):NBAPregameFeatureSnapshot.from_json(json.dumps(data))

    def test_correction_roundtrip_keeps_both_input_versions(self):
        r,g,p,a=setup();correction=Record.make('player_game',r,{**p.data,'stats':{'points':2}},revision=2,supersedes=p.record_id)
        snapshot=build([g,p,a,correction])
        self.assertEqual(NBAPregameFeatureSnapshot.from_json(snapshot.to_json()).content_hash,snapshot.content_hash)
        self.assertIn(p.record_id,{x['record_id'] for x in snapshot.to_dict()['input_records']})

    def test_blocked_snapshot_cannot_be_consumed(self):
        with self.assertRaisesRegex(ValueError,'SNAPSHOT_BLOCKED'):build().require_usable()

    def test_team_same_game_rejected(self):
        r,g,p,a=setup();team=Record.make('team_game',r,dict(game_id=g.data['game_id'],team_id=p.data['team_id'],opponent_id=p.data['opponent_id'],game_date='2026-11-13',possessions=110,pace_per_48=110,stats={'points':121},opponent_stats={'points':109}))
        data=build([g,p,a,team]).to_dict()
        self.assertEqual(data['ledger']['rejections'][0]['code'],'SAME_GAME_OUTCOME')
        self.assertNotIn(team.record_id,{x['record_id'] for x in data['input_records']})

    def test_append_only_write(self):
        with TemporaryDirectory() as tmp:
            path=save_snapshot(build(),Path(tmp));self.assertEqual(path,save_snapshot(build(),Path(tmp)))
            path.write_text('corrupt')
            with self.assertRaisesRegex(ValueError,'IMMUTABLE'):save_snapshot(build(),Path(tmp))
    def test_source_bytes_checked(self):
        r,g,p,a=setup()
        with self.assertRaisesRegex(ValueError,'SOURCE_HASH'):r.verify(b'wrong')

if __name__=='__main__':unittest.main()
