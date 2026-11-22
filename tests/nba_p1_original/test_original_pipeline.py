"""P1 adversarial contract and scheduling tests. No network or gambling models."""
import copy
from datetime import datetime,timedelta,timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

# The canonical P0 package is imported directly in repository/Deepnote CI. A
# deliberately restricted local stand-in permits static local tests when the
# staged P0 branch is not mounted; CI must use the real P0 implementation.
try:
    from v2.p0_integrity.contracts import record as p0_record
    P0_STAGED = True
except ImportError:
    P0_STAGED = False
    v2=types.ModuleType('v2');v2.__path__=[];sys.modules['v2']=v2
    pkg=types.ModuleType('v2.p0_integrity');pkg.__path__=[]
    contracts=types.ModuleType('v2.p0_integrity.contracts')
    class AdmissionError(ValueError):pass
    def sha256(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def utc(x):
        dt=datetime.fromisoformat(x.replace('Z','+00:00'))
        if dt.utcoffset()!=timedelta(0):raise AdmissionError('UTC_REQUIRED')
        return dt
    def canonical_bytes(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    SCHEMAS={'SourceReceipt':['receipt_id'],'PregameFeatureSnapshot':['feature_snapshot_id']}
    def record(kind,**fields):return dict(record_type=kind,schema_version='PA-P0/1',**fields)
    p0_record=record
    def validate_record(kind,x):
        if x['record_type']!=kind:raise AdmissionError('KIND_MISMATCH')
        if kind=='PregameFeatureSnapshot' and x['feature_sha256']!=sha256(x['features']):raise AdmissionError('HASH_MISMATCH')
        return x
    for k,v in [('record',record),('validate_record',validate_record),('sha256',sha256),('utc',utc),('AdmissionError',AdmissionError),('canonical_bytes',canonical_bytes),('SCHEMAS',SCHEMAS)]:setattr(contracts,k,v)
    storage=types.ModuleType('v2.p0_integrity.storage')
    def blocked(*a,**k):raise AdmissionError('ATTESTATION_NOT_AVAILABLE_LOCAL')
    for k in ('attest_project_storage','append_immutable','verify_immutable_record'):setattr(storage,k,blocked)
    sys.modules['v2.p0_integrity']=pkg
    sys.modules['v2.p0_integrity.contracts']=contracts
    sys.modules['v2.p0_integrity.storage']=storage

from research.nba_p1_original.feature_store import build_feature_rows,verify_handoff,verify_dev_p0_record,FeatureAdmissionError,VERSION
from research.nba_p1_original.rolling import WindowPolicy,run_daily,atomic_once,AcquisitionError,P0ProjectVault

BASE=datetime(2026,11,22,0,0,tzinfo=timezone.utc)
def iso(x):return x.isoformat().replace('+00:00','Z')
def fixture():
    raw=b'{"team":{"id":"1"},"athletes":[{"id":"123"}]}';rid='synthetic-receipt-1'
    receipt={'receipt_id':rid,'source':'https://example.invalid/teams/1/roster','raw_sha256':hashlib.sha256(raw).hexdigest(),
             'observed_at':iso(BASE-timedelta(hours=1)),'source_available_at':iso(BASE-timedelta(hours=1)),'origin':'fixture'}
    pid='espn:player:123';tid='espn:team:1';opp='espn:team:2';gid='espn:game:401999111'
    history={'game_id':'espn:game:401900000','game_date':'2026-11-19','receipt_id':rid,
             'player_id':pid,'team_id':tid,'opponent_id':opp,'participation':'played',
             'minutes':31.2,'starter':True,'stats':{'points':21,'rebounds':8,'assists':6,'threes':3}}
    summary={'n':1,'mean':21,'values':[21]}
    teams=[{'team_id':x,'opponent_id':y,'home':x==tid,'history':[],
            'rest_days':1,'back_to_back':False,'possessions':{'n':0},'pace_per_48':{'n':0},
            'offensive_profile':{},'defensive_profile':{},'missing_feature_codes':['PACE_UNAVAILABLE']} for x,y in [(tid,opp),(opp,tid)]]
    snap={'schema_version':'nba-pregame-feature-snapshot/1.0.0',
          'game':{'game_id':gid,'home_team_id':tid,'away_team_id':opp,'event_start_at':iso(BASE),'status':'scheduled'},
          'input_freeze_at':iso(BASE-timedelta(minutes=25)),'forecast_at':iso(BASE-timedelta(minutes=25)),
          'source_available_at':receipt['observed_at'],'receipts':[receipt],
          'input_records':[{'record_id':'roster-1','kind':'roster','receipt_id':rid,
                           'payload':json.dumps({'player_id':pid,'team_id':tid,'game_id':gid,
                                                 'status':'membership_only','uncertainty':'reported'})}],
          'players':[{'player_id':pid,'team_id':tid,'opponent_id':opp,'home':True,'roster_record_id':'roster-1',
                      'history':[history],'availability':[],'missing_feature_codes':['AVAILABILITY_UNAVAILABLE'],
                      'features':{'games_played':1,'minutes_recent':{'values':[31.2]},'statistics':{'points':{'recent':summary}}}}],
          'teams':teams,'abstention_codes':['ELIGIBILITY_UNCERTAIN']}
    return snap,{rid:raw}

class FeatureCases(unittest.TestCase):
    def good(self):
        x,raw=fixture();rows,m=build_feature_rows(x,raw);self.assertEqual(len(rows),8);return x,raw,rows,m
    def test_good_source_listed_not_confirmed(self):
        _,raw,rows,m=self.good();self.assertTrue(verify_handoff(rows,m,raw))
        self.assertEqual(m['player_candidates_accepted'],1)
        self.assertEqual(m['unknown_availability'],1)
        self.assertEqual(rows[0]['features']['legal_eligibility'],'UNVERIFIED')
        self.assertIsNone(rows[0]['features']['participation_probability'])
        self.assertEqual(m['market_category'],'DISTRIBUTION_ONLY_NO_VERIFIED_QUOTE')
    def test_missing_optional_injury_keeps_player(self):self.good()
    def test_corrupt_original_source_rejected(self):
        x,r=fixture();r[next(iter(r))]=b'tampered'
        with self.assertRaisesRegex(FeatureAdmissionError,'SOURCE_SHA_MISMATCH'):build_feature_rows(x,r)
    def test_late_original_source_rejected(self):
        x,r=fixture();x['receipts'][0]['observed_at']=iso(BASE-timedelta(minutes=1))
        with self.assertRaisesRegex(FeatureAdmissionError,'SOURCE_AFTER_FREEZE'):build_feature_rows(x,r)
    def test_future_source_availability_rejected(self):
        x,r=fixture();x['receipts'][0]['source_available_at']=iso(BASE)
        with self.assertRaisesRegex(FeatureAdmissionError,'SOURCE_AFTER_FREEZE'):build_feature_rows(x,r)
    def test_postgame_builder_rejected(self):
        x,r=fixture();x['input_freeze_at']=iso(BASE+timedelta(minutes=1))
        with self.assertRaisesRegex(FeatureAdmissionError,'INPUT_NOT_PREGAME'):build_feature_rows(x,r)
    def test_target_minutes_field_rejected(self):
        x,r=fixture();x['players'][0]['features']['actual_minutes']=43
        with self.assertRaisesRegex(FeatureAdmissionError,'TARGET_OUTCOME_FIELD_FORBIDDEN'):build_feature_rows(x,r)
    def test_same_game_history_rejected(self):
        x,r=fixture();x['players'][0]['history'][0]['game_id']=x['game']['game_id']
        rows,m=build_feature_rows(x,r);self.assertEqual(len(rows),0)
        self.assertEqual(m['rejected'][0]['reason'],'HISTORY_TARGET_LEAKAGE_OR_IDENTITY')
    def test_wrong_history_player_rejected(self):
        x,r=fixture();x['players'][0]['history'][0]['player_id']='espn:player:321'
        rows,m=build_feature_rows(x,r);self.assertEqual(len(rows),0)
    def test_wrong_team_and_trade_identity_rejected(self):
        x,r=fixture();x['players'][0]['opponent_id']='espn:team:999'
        rows,m=build_feature_rows(x,r);self.assertEqual(len(rows),0)
    def test_traded_player_past_team_preserved(self):
        x,r=fixture();x['players'][0]['history'][0]['team_id']='espn:team:8'
        rows,m=build_feature_rows(x,r);self.assertEqual(rows[0]['features']['prior_player_history'][0]['team_id'],'espn:team:8')
    def test_duplicate_player_rejected(self):
        x,r=fixture();x['players'].append(copy.deepcopy(x['players'][0]));rows,m=build_feature_rows(x,r)
        self.assertEqual(len(rows),8);self.assertEqual(m['player_candidates_rejected'],1)
    def test_status_out_separate_from_dnp(self):
        x,r=fixture();x['players'][0]['availability']=[{'status':'out','receipt_id':'synthetic-receipt-1'}]
        rows,_=build_feature_rows(x,r);self.assertEqual(rows[0]['features']['availability_status'],'RULED_OUT_SOURCE_REPORTED')
        self.assertEqual(rows[0]['features']['prior_player_history'][0]['participation'],'played')
    def test_ambiguous_official_crosswalk_rejected(self):
        x,r=fixture();pid=x['players'][0]['player_id']
        e={'observed_at':iso(BASE-timedelta(hours=1)),'valid_from':iso(BASE-timedelta(days=1)),
           'valid_to':None,'source_receipt_id':'synthetic-receipt-1','nba_player_id':'nba:player:5'}
        rows,m=build_feature_rows(x,r,crosswalks={pid:[e,{**e,'nba_player_id':'nba:player:6'}]})
        self.assertEqual(len(rows),0)
    def test_unverified_crosswalk_proof_rejected(self):
        x,r=fixture();pid=x['players'][0]['player_id']
        e={'observed_at':iso(BASE-timedelta(hours=1)),'valid_from':iso(BASE-timedelta(days=1)),
           'valid_to':None,'source_receipt_id':'missing-proof','nba_player_id':'nba:player:5'}
        rows,m=build_feature_rows(x,r,crosswalks={pid:[e]});self.assertEqual(len(rows),0)
    def test_reconstruction_cannot_claim_original(self):
        x,r=fixture();rows,m=build_feature_rows(x,r,reconstruction_class='reconstructed')
        self.assertEqual(rows[0]['reconstruction_class'],'reconstructed')
        m['reconstruction_class']='original'
        with self.assertRaisesRegex(FeatureAdmissionError,'RECONSTRUCTION_CLASS_MISMATCH'):verify_handoff(rows,m,r)
    def test_wrong_target_game_day_history_rejected(self):
        x,r=fixture();x['players'][0]['history'][0]['game_date']='2026-11-21'
        rows,m=build_feature_rows(x,r)
        self.assertEqual(len(rows),0)
        self.assertEqual(m['rejected'][0]['reason'],'HISTORY_TARGET_LEAKAGE_OR_IDENTITY')
    def test_source_listed_questionable_not_confirmed(self):
        x,r=fixture();x['players'][0]['availability']=[{'status':'questionable','receipt_id':'synthetic-receipt-1'}]
        rows,m=build_feature_rows(x,r)
        self.assertEqual(rows[0]['features']['availability_status'],'QUESTIONABLE_SOURCE_REPORTED')
        self.assertEqual(rows[0]['features']['legal_eligibility'],'UNVERIFIED')
    def test_roster_record_player_collision_withheld(self):
        x,r=fixture();data=json.loads(x['input_records'][0]['payload'])
        data['player_id']='espn:player:999'
        x['input_records'][0]['payload']=json.dumps(data)
        rows,m=build_feature_rows(x,r)
        self.assertEqual(len(rows),0)
        self.assertEqual(m['rejected'][0]['reason'],'ROSTER_PAYLOAD_IDENTITY_COLLISION')
    def test_missing_player_in_original_roster_withheld(self):
        x,r=fixture();rid='synthetic-receipt-1'
        raw=b'{"team":{"id":"1"},"athletes":[{"id":"999"}]}'
        r[rid]=raw;x['receipts'][0]['raw_sha256']=hashlib.sha256(raw).hexdigest()
        rows,m=build_feature_rows(x,r)
        self.assertEqual(len(rows),0)
        self.assertEqual(m['rejected'][0]['reason'],'PLAYER_NOT_IN_ORIGINAL_ROSTER')
    def test_current_name_position_source_bound_not_joined_by_name(self):
        x,r=fixture();rid='synthetic-receipt-1'
        raw=json.dumps({'team':{'id':'1'},'athletes':[{'id':'123','displayName':'Synthetic Player One',
                      'position':{'abbreviation':'SG'}}]}).encode()
        r[rid]=raw
        x['receipts'][0]['source']='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/1/roster'
        x['receipts'][0]['raw_sha256']=hashlib.sha256(raw).hexdigest()
        x['input_records'][0]['payload']=json.dumps({'player_id':'espn:player:123','team_id':'espn:team:1',
                                                     'game_id':'espn:game:401999111','status':'membership_only','uncertainty':'reported'})
        rows,m=build_feature_rows(x,r)
        self.assertEqual(rows[0]['features']['current_name'],'Synthetic Player One')
        self.assertEqual(rows[0]['features']['position'],'SG')
        self.assertEqual(rows[0]['features']['listed_roster_status'],'membership_only')
        self.assertEqual(rows[0]['features']['legal_eligibility'],'UNVERIFIED')
        self.assertEqual(rows[0]['features']['espn_player_id'],'espn:player:123')
    def test_conflicting_roster_name_unresolved(self):
        x,r=fixture();rid='synthetic-receipt-1'
        raw=json.dumps({'team':{'id':'1'},'athletes':[{'id':'123','displayName':'One','position':{'abbreviation':'SG'}},
                                    {'id':'123','displayName':'Two','position':{'abbreviation':'SF'}}]}).encode()
        r[rid]=raw
        x['receipts'][0]['source']='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/1/roster'
        x['receipts'][0]['raw_sha256']=hashlib.sha256(raw).hexdigest()
        rows,m=build_feature_rows(x,r)
        self.assertEqual(len(rows),0)
        self.assertEqual(m['rejected'][0]['reason'],'ROSTER_NAME_POSITION_AMBIGUOUS')
    def test_no_crosswalk_does_not_invent_official_id(self):
        x,r=fixture();rows,m=build_feature_rows(x,r)
        self.assertIsNone(rows[0]['features']['official_nba_player_id'])
    def test_p3_rejects_late_manifest(self):
        x,r,rows,m=self.good();m['input_freeze_at']=iso(BASE+timedelta(minutes=10))
        with self.assertRaisesRegex(FeatureAdmissionError,'HANDOFF_AFTER_TIPOFF'):
            verify_handoff(rows,m,r)
    def test_p3_rejects_missing_statistic_records(self):
        x,r,rows,m=self.good()
        with self.assertRaisesRegex(FeatureAdmissionError,'FEATURE_DENOMINATOR_MISMATCH'):
            verify_handoff(rows[:-1],m,r)
    def test_feature_hash_mutation_rejected(self):
        x,r,rows,m=self.good();rows[0]['features']['legal_eligibility']='CONFIRMED'
        with self.assertRaises(ValueError):verify_handoff(rows,m,r)
    def test_handoff_source_missing_rejected(self):
        x,r,rows,m=self.good()
        with self.assertRaisesRegex(FeatureAdmissionError,'HANDOFF_SOURCE_BYTES_MISSING'):verify_handoff(rows,m,{})
    def test_receipt_id_remap_supported(self):
        x,r=fixture();rows,m=build_feature_rows(x,r,receipt_id_map={'synthetic-receipt-1':'p0-receipt'})
        self.assertEqual(rows[0]['source_receipt_ids'],['p0-receipt'])
        self.assertTrue(verify_handoff(rows,m,{'p0-receipt':next(iter(r.values()))}))
    def test_wrong_event_handoff_rejected(self):
        x,r,rows,m=self.good();m['event_id']='espn:game:other'
        with self.assertRaisesRegex(FeatureAdmissionError,'HANDOFF_IDENTITY_OR_CLOCK_MISMATCH'):verify_handoff(rows,m,r)

class WindowCases(unittest.TestCase):
    def test_early_and_final(self):
        p=WindowPolicy();a,b=p.window(BASE,'early');c,d=p.window(BASE,'final')
        self.assertEqual((BASE-a).total_seconds(),4200)
        self.assertEqual((BASE-b).total_seconds(),3000)
        self.assertEqual((BASE-c).total_seconds(),2100)
        self.assertEqual((BASE-d).total_seconds(),1200)
    def test_window_invalid(self):
        with self.assertRaisesRegex(AcquisitionError,'INVALID_WINDOW_POLICY'):WindowPolicy(10,20,15,5)
    def test_immutable_concurrent_write_one_content(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'claim.json';wins=[]
            def worker(i):
                try:wins.append(atomic_once(path,str(i).encode()))
                except AcquisitionError:wins.append('REJECTED')
            ts=[threading.Thread(target=worker,args=(i,)) for i in range(15)]
            for t in ts:t.start()
            for t in ts:t.join()
            self.assertEqual(wins.count('APPENDED'),1)
            self.assertEqual(wins.count('REJECTED'),14)
    def test_corrupt_existing_file_not_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';atomic_once(p,b'first')
            with self.assertRaisesRegex(AcquisitionError,'IMMUTABLE_COLLISION'):atomic_once(p,b'second')
    def test_reject_unverified_project_root(self):
        with self.assertRaisesRegex(AcquisitionError,'UNAPPROVED_STORAGE_ROOT'):
            P0ProjectVault('/tmp')

class DevRecordStorageCases(unittest.TestCase):
    def make_vault(self,root):
        vault=P0ProjectVault.__new__(P0ProjectVault)
        vault.root=Path(root)
        vault.dev_root=Path(root)/'research/nba_p1_original/dev_v1'
        vault.assert_verified=lambda: None
        return vault
    def record(self):
        at=iso(BASE-timedelta(minutes=40))
        return p0_record('SourceReceipt',receipt_id='fixture-source-id',
            source_id='https://example.invalid/schedule',source_kind='nba_schedule',
            source_available_at=at,collected_at=at,source_sha256=hashlib.sha256(b'example').hexdigest(),
            archive_path='research/nba_p1_original/dev_v1/source_bytes/example.raw',
            provenance_class='collector_possession')
    def test_dev_p0_records_immutable_and_sha_verifiable(self):
        with tempfile.TemporaryDirectory() as root:
            vault=self.make_vault(root);r=self.record();a=vault.append_p0('SourceReceipt',r)
            self.assertEqual(verify_dev_p0_record(root,'SourceReceipt',a['sha256']),r)
            self.assertEqual(vault.append_p0('SourceReceipt',r)['status'],'IDEMPOTENT_EXISTING')
            self.assertTrue(a['relative_path'].startswith('research/nba_p1_original/dev_v1/'))
    def test_dev_record_rejects_conflicting_logical_id(self):
        with tempfile.TemporaryDirectory() as root:
            vault=self.make_vault(root);r=self.record();vault.append_p0('SourceReceipt',r)
            second={**r,'source_kind':'new_source_kind'}
            with self.assertRaisesRegex(AcquisitionError,'IMMUTABLE_COLLISION'):
                vault.append_p0('SourceReceipt',second)
    def test_dev_record_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            vault=self.make_vault(root);r=self.record();a=vault.append_p0('SourceReceipt',r)
            (Path(root)/a['relative_path']).write_bytes(b'edited')
            with self.assertRaisesRegex(FeatureAdmissionError,'P1_P0_RECORD_CORRUPTED'):
                verify_dev_p0_record(root,'SourceReceipt',a['sha256'])

class FakeVault:
    def __init__(self):
        self.root=Path('/work');self.dev_root=Path('/dev/null');self.files={};self.claims=set();self.lock=threading.Lock()
    def claim(self,identity):
        with self.lock:
            if identity in self.claims:raise FileExistsError('prior original')
            self.claims.add(identity)
    def assert_verified(self):pass
    def source(self,url,raw,t,**kw):return {'receipt_id':'sim-schedule'}, {'path':'fixture','sha256':'a'}, {'sha256':'b'}
    def save_json(self,path,data):
        if path in self.files:
            if self.files[path]!=data:raise AcquisitionError('IMMUTABLE_COLLISION')
            return {'path':path,'sha256':hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()}
        self.files[path]=copy.deepcopy(data)
        return {'path':path,'sha256':hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()}

def fake_discover(day):return 'https://fixture.invalid/schedule',b'{"events":[]}',BASE-timedelta(minutes=40)
def no_games(raw,url,seen):return []
class DailyCases(unittest.TestCase):
    def test_empty_day_still_has_manifest(self):
        v=FakeVault();t=BASE-timedelta(minutes=40)
        result=run_daily(day='2026-11-21',clock=lambda:t,vault=v,discover=fake_discover,parse=no_games,wait=False)
        self.assertEqual(result['games_discovered'],0);self.assertTrue(result['daily_manifest_sha256']);self.assertEqual(result['model_forecasts'],0)
    def test_repeat_same_day_uses_immutable_per_run_manifests(self):
        v=FakeVault()
        t1=BASE-timedelta(minutes=40)
        t2=BASE-timedelta(minutes=39)
        x=run_daily(day='2026-11-21',clock=lambda:t1,vault=v,
                    discover=fake_discover,parse=no_games,wait=False)
        old=copy.deepcopy(v.files[x['daily_manifest_path']])
        y=run_daily(day='2026-11-21',clock=lambda:t2,vault=v,
                    discover=fake_discover,parse=no_games,wait=False)
        self.assertNotEqual(x['daily_manifest_path'],y['daily_manifest_path'])
        self.assertNotEqual(x['daily_manifest_sha256'],y['daily_manifest_sha256'])
        self.assertEqual(v.files[x['daily_manifest_path']],old)
        self.assertIn('/daily_manifests/',x['daily_manifest_path'])
        self.assertIn('/daily_manifests/',y['daily_manifest_path'])
        z=run_daily(day='2026-11-21',clock=lambda:t1,vault=v,
                    discover=fake_discover,parse=no_games,wait=False)
        self.assertEqual(z['daily_manifest_sha256'],x['daily_manifest_sha256'])
        self.assertEqual(z['daily_manifest_path'],x['daily_manifest_path'])

    def test_repeat_identical_claim_clock_keeps_both_attempts(self):
        v=FakeVault();t=BASE-timedelta(minutes=60)
        event={'game_id':'espn:game:42','event_start_at':iso(BASE),
          'home_team_id':'espn:team:1','away_team_id':'espn:team:2',
          'status':'scheduled'}
        summary={'input_freeze_at':iso(t),'feature_rows':8,'player_candidates_accepted':1}
        with patch('research.nba_p1_original.rolling._archive_ws1',return_value=summary):
            first=run_daily(day='2026-11-21',clock=lambda:t,vault=v,
                discover=fake_discover,parse=lambda *args:[event],
                capture=lambda *args:{'status':'captured_partial_shadow'},wait=False)
            again=run_daily(day='2026-11-21',clock=lambda:t,vault=v,
                discover=fake_discover,parse=lambda *args:[event],
                capture=lambda *args:{'status':'captured_partial_shadow'},wait=False)
        self.assertEqual(first['counts']['SOURCE_FEATURE_FROZEN'],1)
        self.assertEqual(again['counts']['BLOCKED_DUPLICATE_CAPTURE'],1)
        attempts=[path for path in v.files if path.startswith('attempts/')]
        self.assertEqual(len(attempts),2)

    def test_past_day_cannot_backfill_original(self):
        with self.assertRaisesRegex(AcquisitionError,'NONCURRENT_DAY_ORIGINAL_FORBIDDEN'):
            run_daily(day='2026-11-19',clock=lambda:BASE,vault=FakeVault(),discover=fake_discover,parse=no_games)
    def test_missed_final_window_recorded(self):
        v=FakeVault();t=BASE-timedelta(minutes=10)
        e={'game_id':'espn:game:42','event_start_at':iso(BASE),'home_team_id':'espn:team:1',
           'away_team_id':'espn:team:2','status':'scheduled'}
        r=run_daily(day='2026-11-21',clock=lambda:t,vault=v,discover=fake_discover,
                    parse=lambda *x:[e],wait=False)
        self.assertEqual(r['counts']['MISSED_FREEZE'],2)
    def test_postponed_not_captured(self):
        v=FakeVault();t=BASE-timedelta(minutes=60)
        e={'game_id':'espn:game:42','event_start_at':iso(BASE),'home_team_id':'espn:team:1',
           'away_team_id':'espn:team:2','status':'postponed'}
        r=run_daily(day='2026-11-21',clock=lambda:t,vault=v,discover=fake_discover,
                    parse=lambda *x:[e],wait=False)
        self.assertEqual(r['counts']['EVENT_NOT_SCHEDULED'],2)
    def test_simultaneous_games_have_independent_claims(self):
        v=FakeVault();t=BASE-timedelta(minutes=60)
        events=[{'game_id':'espn:game:'+str(i),'event_start_at':iso(BASE),
                 'home_team_id':'espn:team:1','away_team_id':'espn:team:2',
                 'status':'scheduled'} for i in (42,43)]
        summary={'input_freeze_at':iso(t),'feature_rows':8,'player_candidates_accepted':1}
        with patch('research.nba_p1_original.rolling._archive_ws1',return_value=summary):
            result=run_daily(day='2026-11-21',clock=lambda:t,vault=v,discover=fake_discover,
                parse=lambda *x:events,capture=lambda *a:{'status':'captured_partial_shadow'},wait=False)
        self.assertEqual(result['counts']['SOURCE_FEATURE_FROZEN'],2)
        self.assertEqual(result['counts']['NOT_DUE'],2)
        self.assertEqual(len(v.claims),2)
        self.assertEqual({x['event_id'] for x in result['attempts'] if x['status']=='SOURCE_FEATURE_FROZEN'},
                         {'espn:game:42','espn:game:43'})
    def test_repeated_claim_fails_closed(self):
        v=FakeVault();t=BASE-timedelta(minutes=60)
        e={'game_id':'espn:game:42','event_start_at':iso(BASE),'home_team_id':'espn:team:1',
           'away_team_id':'espn:team:2','status':'scheduled'}
        v.claim('2026-11-21|espn:game:42|early|PA-NBA-P1/1')
        x=run_daily(day='2026-11-21',clock=lambda:t,vault=v,discover=fake_discover,
                    parse=lambda *y:[e],capture=lambda *a:None,wait=False)
        self.assertEqual(x['counts']['BLOCKED_DUPLICATE_CAPTURE'],1)
    def test_source_capture_that_finishes_after_deadline_is_rejected(self):
        v=FakeVault();state={'calls':0};t=BASE-timedelta(minutes=60)
        def clock():
            state['calls']+=1
            return t if state['calls']<3 else BASE-timedelta(minutes=15)
        e={'game_id':'espn:game:42','event_start_at':iso(BASE),'home_team_id':'espn:team:1',
           'away_team_id':'espn:team:2','status':'scheduled'}
        summary={'input_freeze_at':iso(t),'feature_rows':8,'player_candidates_accepted':1}
        with patch('research.nba_p1_original.rolling._archive_ws1',return_value=summary):
            x=run_daily(day='2026-11-21',clock=clock,vault=v,discover=fake_discover,
                parse=lambda *y:[e],capture=lambda *a:{'status':'captured_partial_shadow'},wait=False)
        self.assertNotIn('SOURCE_FEATURE_FROZEN',x['counts'])
        self.assertTrue(x['counts'].get('MISSED_FREEZE',0)+x['counts'].get('BLOCKED_CAPTURE',0))
    def test_duplicate_game_ids_block(self):
        v=FakeVault();t=BASE-timedelta(minutes=60)
        e={'game_id':'espn:game:42','event_start_at':iso(BASE),'home_team_id':'espn:team:1',
           'away_team_id':'espn:team:2','status':'scheduled'}
        r=run_daily(day='2026-11-21',clock=lambda:t,vault=v,discover=fake_discover,
                    parse=lambda *x:[e,e],wait=False)
        self.assertEqual(r['counts']['SCHEDULE_DISCOVERY_BLOCKED'],1)

if __name__=='__main__':unittest.main()
