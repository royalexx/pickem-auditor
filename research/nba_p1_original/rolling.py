"""One callable rolling NBA original acquisition worker (no scheduler/forecasting).

Reuse WS1 capture and ESPN adapters. DO NOT edit registered November 16–20
pilot slots. Output is development-only until P6 authorizes live cutover.
"""
from __future__ import annotations
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from itertools import groupby
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.request import Request,urlopen
import gzip
import hashlib
import json
import os
import time
from v2.p0_integrity.contracts import record, sha256, utc, canonical_bytes, validate_record, SCHEMAS
from v2.p0_integrity.storage import attest_project_storage
from .feature_store import build_feature_rows,verify_handoff,verify_dev_p0_record,VERSION,FeatureAdmissionError

TORONTO=ZoneInfo('America/Toronto')
ROOT='research/nba_p1_original/dev_v1'

class AcquisitionError(ValueError):pass

def now():return datetime.now(timezone.utc)
def stamp(t):return t.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')
def digest(b):return hashlib.sha256(b).hexdigest()
def canonical(obj):return json.dumps(obj,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()

def atomic_once(path,data):
    """O_EXCL + fsync + hash-readback; never clean an interrupted claim."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != Path('/work')):
        raise AcquisitionError('UNSAFE_SYMLINK')
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)
    try:fd=os.open(path,flags,0o640)
    except FileExistsError:
        if path.read_bytes()!=data:raise AcquisitionError('IMMUTABLE_COLLISION:'+str(path))
        return 'IDEMPOTENT_EXISTING'
    with os.fdopen(fd,'wb') as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    if path.read_bytes()!=data:raise AcquisitionError('IMMUTABLE_WRITE_READBACK_FAILED')
    return 'APPENDED'

@dataclass(frozen=True)
class WindowPolicy:
    early_open_minutes:int=70
    early_deadline_minutes:int=50
    final_open_minutes:int=35
    final_deadline_minutes:int=20
    def __post_init__(self):
        if not (self.early_open_minutes>self.early_deadline_minutes>self.final_open_minutes>self.final_deadline_minutes>=1):
            raise AcquisitionError('INVALID_WINDOW_POLICY')
    def window(self,tip,phase):
        o,d=(self.early_open_minutes,self.early_deadline_minutes) if phase=='early' else (self.final_open_minutes,self.final_deadline_minutes)
        return tip-timedelta(minutes=o),tip-timedelta(minutes=d)

class P0ProjectVault:
    """Actual Deepnote path admission delegated to accepted P0 gateway."""
    def __init__(self,root='/work',dev_relative=ROOT):
        self.root=Path(root)
        if str(self.root)!='/work' or Path(dev_relative).is_absolute() or '..' in Path(dev_relative).parts:
            raise AcquisitionError('UNAPPROVED_STORAGE_ROOT')
        self.dev_relative=dev_relative
        self.attestation=attest_project_storage(str(self.root))
        self.dev_root=self.root/self.dev_relative
    def assert_verified(self):
        attest_project_storage(str(self.root))
    def save_bytes(self,relative,data):
        self.assert_verified()
        dest=self.dev_root/relative
        if not dest.resolve(strict=False).is_relative_to(self.dev_root.resolve(strict=False)):
            raise AcquisitionError('PATH_ESCAPE')
        status=atomic_once(dest,data)
        return {'path':str(dest.relative_to(self.root)),'sha256':digest(data),'status':status}
    def save_json(self,relative,data):return self.save_bytes(relative,canonical(data)+b'\n')
    def claim(self,identity):
        # Distinct attempt identities, never overwrite prior claim.
        self.assert_verified()
        safe=digest(identity.encode())
        p=self.dev_root/'claims'/(safe+'.json')
        blob=canonical({'schema':'NBA-P1-CLAIM/1','identity':identity})
        p.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o640)
        with os.fdopen(fd,'wb') as file:
            file.write(blob);file.flush();os.fsync(file.fileno())
        # A pre-existing identical claim cannot represent a new capture right.
        return p
    def append_p0(self,kind,obj):
        """P0-compatible append-only DEV records, never the shared P0 production root.

        P0 may later adopt records after P6 approval. No global
        /work/research/p0_integrity_store writes occur on this research path.
        """
        self.assert_verified()
        if kind not in ('SourceReceipt','PregameFeatureSnapshot'):
            raise AcquisitionError('DEV_P0_KIND_NOT_ALLOWED')
        validate_record(kind,obj)
        body=canonical_bytes(obj)
        sha=digest(body)
        logical_id=obj[SCHEMAS[kind][0]]
        claim_key=digest((kind+'\x00'+logical_id).encode())
        base='p0_records/'+kind+'/'
        claim=canonical({'kind':kind,'id':logical_id,'record_sha256':sha})
        self.save_bytes(base+'_ids/'+claim_key+'.json',claim)
        stored=self.save_bytes(base+sha+'.json',body)
        reread=verify_dev_p0_record(self.root,kind,sha)
        if reread!=obj:raise AcquisitionError('P0_DEV_READBACK_DIFFERENT')
        return {'status':stored['status'],'relative_path':stored['path'],'sha256':sha}
    def source(self,source_id,raw,collected_at,*,label='original_capture'):
        if not isinstance(raw,bytes) or not raw:raise AcquisitionError('SOURCE_EMPTY_OR_INVALID')
        at=stamp(collected_at)
        key=digest((source_id+'\x00'+at+'\x00'+digest(raw)).encode())
        stored=self.save_bytes('source_bytes/'+digest(raw)+'.raw',raw)
        obj=record('SourceReceipt',receipt_id='nba-p1-source:'+key,
            source_id=source_id,source_kind=label,
            source_available_at=at,collected_at=at,source_sha256=digest(raw),
            archive_path=stored['path'],provenance_class='collector_possession')
        cert=self.append_p0('SourceReceipt',obj)
        return obj,stored,cert


def default_discover(day):
    """Only one original discovery request; WS1 owns parsing and all other sources."""
    from v2.nba_ws1.capture import BASE
    url=BASE+'/scoreboard?dates='+day.replace('-','')+'&limit=100'
    with urlopen(Request(url,headers={'User-Agent':'pickem-p1-source-discovery/1'}),timeout=20) as response:
        if response.status!=200:raise AcquisitionError('SCHEDULE_SOURCE_HTTP_ERROR')
        raw=response.read(8*1024*1024+1)
    seen=now()
    if len(raw)>8*1024*1024:raise AcquisitionError('SCHEDULE_SOURCE_OVERSIZE')
    return url,raw,seen

def default_parse(raw,source_id,collected_at):
    from v2.nba_ws1.adapters import schedule_records
    from v2.nba_ws1.store import Receipt
    r=Receipt.capture(raw,source=source_id,observed_at=stamp(collected_at),origin='original_capture')
    return [x.data for x in schedule_records(json.loads(raw),r)]

def default_capture(game,phase,out,deadline):
    """Reuse existing WS1 capture; NEVER replicate its roster/boxscore logic."""
    try:from v2.nba_ws1.capture import capture
    except ImportError as exc:raise AcquisitionError('BLOCKED_UPSTREAM_WS1_NOT_INTEGRATED') from exc
    tip=datetime.fromisoformat(game['event_start_at'].replace('Z','+00:00'))
    day=tip.astimezone(TORONTO).date().isoformat()
    return capture(day,out,game_id=game['game_id'],freeze_deadline_at=stamp(deadline),
                   expected_game=game,history_games_per_team=10)

def _archive_ws1(cap,out,vault,deadline):
    from v2.nba_ws1.store import NBAPregameFeatureSnapshot,Receipt
    snap_path=Path(out)/cap['snapshot_path']
    snapshot=NBAPregameFeatureSnapshot.from_json(snap_path.read_text()).to_dict()
    if datetime.fromisoformat(snapshot['input_freeze_at'].replace('Z','+00:00'))>deadline:
        raise AcquisitionError('MISSED_FREEZE_AFTER_SOURCES')
    raws={};sources=[];retained=[];receipt_id_map={}
    expected={x['receipt_id']:x for x in snapshot['receipts']}
    for item in cap['sources']:
        rid=item['receipt_id']
        if rid not in expected:raise AcquisitionError('SOURCE_RECEIPT_NOT_IN_SNAPSHOT')
        r=Receipt(**expected[rid]);raw=gzip.decompress((Path(out)/item['path']).read_bytes());r.verify(raw)
        if r.origin=='fixture':raise AcquisitionError('FIXTURE_CANNOT_BE_ORIGINAL')
        if datetime.fromisoformat(r.observed_at.replace('Z','+00:00'))>deadline:
            raise AcquisitionError('SOURCE_AFTER_FREEZE')
        obj,stored,cert=vault.source(r.source,raw,datetime.fromisoformat(r.observed_at.replace('Z','+00:00')),
                                       label=r.origin)
        raws[rid]=raw
        receipt_id_map[rid]=obj['receipt_id']
        sources.append({'receipt_id':obj['receipt_id'],'ws1_receipt_id':rid,**stored,'p0_sha256':cert['sha256']})
    if set(raws)!=set(expected):raise AcquisitionError('WS1_RECEIPT_ARCHIVE_INCOMPLETE')
    # Byte verification precedes feature construction, P0 source closure follows.
    rows,summary=build_feature_rows(snapshot,raws,reconstruction_class='original',receipt_id_map=receipt_id_map)
    verify_handoff(rows,{**summary,'schema':VERSION},{receipt_id_map[k]:v for k,v in raws.items()})
    for obj in rows:
        cert=vault.append_p0('PregameFeatureSnapshot',obj)
        retained.append({'player_id':obj['player_id'],'stat_key':obj['stat_key'],
                         'sha256':cert['sha256'],'path':cert['relative_path'],
                         'source_receipt_ids':obj['source_receipt_ids']})
    summary['sources']=sources
    summary['features']=retained
    summary['ws1_snapshot_sha256']=digest(snap_path.read_bytes())
    summary['ws1_content_hash']=snapshot['content_hash']
    summary['accepted_market_quotes']=[]
    summary['market_status']='NO_ORIGINAL_TWO_SIDED_QUOTE_REUSED'
    return summary

def _clock(t):
    if t.tzinfo is None or t.utcoffset() is None:raise AcquisitionError('CLOCK_MUST_BE_AWARE')
    return t.astimezone(timezone.utc)

def run_daily(*,day=None,clock=now,policy=None,vault=None,discover=default_discover,
              parse=default_parse,capture=default_capture,wait=True,sleep=time.sleep,
              max_wait_seconds=None):
    """One daily invocation, no scheduler; genuine original allowed on current day only.

    The injected implementations are ONLY for test canaries; using an injected
    transport never constitutes genuine-original certification.
    """
    policy=policy or WindowPolicy();now_utc=_clock(clock());today=now_utc.astimezone(TORONTO).date().isoformat()
    day=day or today
    if day!=today:raise AcquisitionError('NONCURRENT_DAY_ORIGINAL_FORBIDDEN')
    vault=vault or P0ProjectVault()
    vault.assert_verified()
    run_key=digest((day+'\x00'+VERSION+'\x00'+repr(policy)).encode())[:20]
    run_prefix='runs/'+day+'/'+run_key
    observations=[];events=[];source_info=None
    try:
        url,raw,seen=discover(day)
        if not isinstance(raw,bytes):raise AcquisitionError('DISCOVERY_BYTES_REQUIRED')
        seen=_clock(seen)
        sched,where,proof=vault.source(url,raw,seen,label='nba_schedule')
        source_info={'receipt_id':sched['receipt_id'],'p0_sha256':proof['sha256'],**where}
        schedules=parse(raw,url,seen)
        for e in schedules:
            tip=datetime.fromisoformat(e['event_start_at'].replace('Z','+00:00'))
            if tip.astimezone(TORONTO).date().isoformat()!=day:continue
            events.append(e)
        events.sort(key=lambda e:(e['event_start_at'],e['game_id']))
        if len({e['game_id'] for e in events})!=len(events):
            events=[]
            raise AcquisitionError('DUPLICATE_EVENT_ID')
    except Exception as exc:
        observations.append({'status':'SCHEDULE_DISCOVERY_BLOCKED','reason':type(exc).__name__+':'+str(exc),
                             'observed_at':stamp(_clock(clock()))})
    # Global phase-deadline queue; all games (including simultaneous tipoffs)
    # are ordered by actual event-relative source windows, not discovery order.
    queue=[]
    for game in events:
        tip=datetime.fromisoformat(game['event_start_at'].replace('Z','+00:00'))
        for phase in ('early','final'):
            opened,deadline=policy.window(tip,phase)
            queue.append((opened,deadline,game['game_id'],phase,game))
    def _execute_window(entry):
        opened,deadline,gid,phase,game=entry
        t=_clock(clock())
        if game['status']!='scheduled':
            return {'event_id':gid,'phase':phase,'status':'EVENT_NOT_SCHEDULED',
                    'event_status':game['status'],'observed_at':stamp(t)},t
        if t>deadline:
            return {'event_id':gid,'phase':phase,'status':'MISSED_FREEZE',
                    'observed_at':stamp(t),'deadline':stamp(deadline)},t
        if t<opened:
            delay=(opened-t).total_seconds()
            if not wait or max_wait_seconds is not None and delay>max_wait_seconds:
                return {'event_id':gid,'phase':phase,'status':'NOT_DUE','observed_at':stamp(t)},t
            sleep(delay);t=_clock(clock())
        if t>deadline:
            return {'event_id':gid,'phase':phase,'status':'MISSED_FREEZE',
                    'observed_at':stamp(t),'deadline':stamp(deadline)},t
        claim_id=day+'|'+gid+'|'+phase+'|'+VERSION
        try:
            # O_EXCL is the actual concurrency guard. Do not trust an exists() precheck.
            vault.claim(claim_id)
            output=vault.dev_root/'ws1'/(digest(claim_id.encode()))
            cap=capture(game,phase,output,deadline)
            if cap.get('status')=='blocked':raise AcquisitionError('WS1_BLOCKED:'+str(cap.get('errors')))
            summary=_archive_ws1(cap,output,vault,deadline)
            if _clock(clock())>deadline:raise AcquisitionError('MISSED_FREEZE_AFTER_BUILD')
            info=vault.save_json('handoffs/'+digest(claim_id.encode())+'.json',summary)
            outcome={'event_id':gid,'phase':phase,'status':'SOURCE_FEATURE_FROZEN',
                     'at':summary['input_freeze_at'],'receipt_sha256':info['sha256'],
                     'handoff_path':info['path'],
                     'feature_rows':summary['feature_rows'],
                     'player_candidates_accepted':summary['player_candidates_accepted']}
        except FileExistsError:
            outcome={'event_id':gid,'phase':phase,'status':'BLOCKED_DUPLICATE_CAPTURE',
                     'observed_at':stamp(_clock(clock())),'reason':'ORIGINAL_CLAIM_ALREADY_EXISTS'}
        except Exception as exc:
            outcome={'event_id':gid,'phase':phase,'status':'BLOCKED_CAPTURE',
                     'observed_at':stamp(_clock(clock())),
                     'reason':type(exc).__name__+':'+str(exc)}
        # Immutable attempt journal, including blocked and failed acquisition attempts.
        # A rerun at an identical clock instant may have a different valid
        # outcome (e.g., original capture won before, duplicate claim now).
        # Both attempts are immutable and independently addressable.
        attempt_id=digest(canonical({'claim_id':claim_id,
                                     'attempt_at':stamp(t),'outcome':outcome}))
        vault.save_json('attempts/'+attempt_id+'.json',outcome)
        return outcome,t

    # Simultaneous source windows are separate workers with disjoint event claims.
    # Keep completion timestamps attached to each actual execution, never scheduler time.
    queue.sort(key=lambda x:(x[0],x[1],x[2],x[3]))
    for opened,bucket in groupby(queue,key=lambda x:x[0]):
        batch=list(bucket)
        with ThreadPoolExecutor(max_workers=min(8,len(batch))) as pool:
            observations.extend(record for record,at in pool.map(_execute_window,batch))
    manifest={'schema':'PA-NBA-P1-DAILY/1','day_toronto':day,'research_profile':'source_listed_subset',
              'created_at':stamp(_clock(clock())),'collector':'NBA_P1_REUSE_WS1','games_discovered':len(events),
              'source_schedule':source_info,'events':events,'attempts':observations,
              'counts':{x:sum(a['status']==x for a in observations) for x in sorted({a['status'] for a in observations})},
              'genuine_original_certified':False,'model_forecasts':0,'market_quotes_generated':0,
              'production_automation_changed':False}
    # A day/policy may be invoked more than once: separate immutable per-run
    # manifests rather than overwriting the former fixed daily_manifest.json.
    # Old fixed manifests, including previously failed attempts, remain intact.
    manifest_id=digest(canonical(manifest)+bytes([10]))
    saved=vault.save_json(run_prefix+'/daily_manifests/'+manifest_id+'.json',manifest)
    return {**manifest,'daily_manifest_sha256':saved['sha256'],'daily_manifest_path':saved['path']}

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--day');p.add_argument('--no-wait',action='store_true')
    a=p.parse_args()
    print(json.dumps(run_daily(day=a.day,wait=not a.no_wait),sort_keys=True,indent=2))

if __name__=='__main__':main()
