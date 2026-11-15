"""Exact registered-slot readiness and manual invocation; never schedules work."""
import argparse
from datetime import datetime,timedelta,timezone
import gzip
import json
from pathlib import Path
from dataclasses import asdict
from zoneinfo import ZoneInfo
from urllib.request import Request,urlopen
from v2.nba_ws1.capture import capture,BASE,now
from v2.nba_ws1.adapters import schedule_records
from v2.nba_ws1.store import Receipt,digest,instant
from v2.nba_joint.forecast import freeze
from .sources import acquire_supplements,build_game_ledger

REGISTRY=Path('research/nba_phase6/prospective_pilot/blocked_receipt.json')
REGISTRY_SHA='ab7795753e5ff0e98a4cbaa988897b95c2dc4d6e8371865f3af80cd9167bdf54'


def registered_slots():
    raw=REGISTRY.read_bytes()
    if digest(raw)!=REGISTRY_SHA:raise ValueError('FROZEN_PILOT_REGISTRATION_CHANGED')
    registry=json.loads(raw);slots=registry['slots']
    if len(slots)!=10 or len({s['game']['game_id'] for s in slots})!=10:raise ValueError('PILOT_IDENTITY_DENOMINATOR')
    for day in sorted({s['toronto_date'] for s in slots}):
        source=next(r for r in registry['source_receipts'] if r['receipt_id']==next(s['schedule_receipt_id'] for s in slots if s['toronto_date']==day))
        r=Receipt(**{k:source[k] for k in Receipt.__dataclass_fields__});raw=gzip.decompress((REGISTRY.parent/source['path']).read_bytes());r.verify(raw)
        records=schedule_records(json.loads(raw),r);games=sorted([x.data for x in records if x.data['status']=='scheduled' and instant(x.data['event_start_at']).astimezone(ZoneInfo('America/Toronto')).date().isoformat()==day],key=lambda x:(x['event_start_at'],x['game_id']))[:2]
        old=[s['game'] for s in slots if s['toronto_date']==day]
        if games!=old:raise ValueError('ORIGINAL_SELECTION_LOGIC_MISMATCH')
    for slot in slots:
        if instant(slot['scheduled_freeze_at'])!=instant(slot['game']['event_start_at'])-timedelta(minutes=30):raise ValueError('REGISTERED_FREEZE_MISMATCH')
    return slots


def window_state(slot,at):
    clock=instant(at);deadline=instant(slot['scheduled_freeze_at'])
    if clock<deadline-timedelta(minutes=10):return 'NOT_DUE'
    if clock>deadline:return 'MISSED_FREEZE'
    return 'ACQUISITION_WINDOW'


def capture_slot(slot,output,*,fixture=False,fixture_fetch=None,fixture_clock=None,fixture_supplement=None):
    if (fixture_fetch or fixture_clock or fixture_supplement) and not fixture:raise ValueError('FIXTURE_ONLY_INPUT')
    clock=fixture_clock or now;actual=clock();root=Path(output)/('slot_%02d_'%slot['slot']+slot['game']['game_id'].split(':')[-1]);root.mkdir(parents=True,exist_ok=True)
    attempt=root/'attempts'/instant(actual).strftime('%Y%m%dT%H%M%S%fZ');attempt.mkdir(parents=True,exist_ok=False)
    state=window_state(slot,actual);receipt=dict(schema='NBAPhase7PilotAttempt/1',slot=slot,actual_invocation_at=actual,source_attempted=0,
        fixture=fixture,status=state,forecast_count=0,settled_count=0,registered_manifest_sha256=REGISTRY_SHA)
    if (root/'FIRST_CAPTURE.json').exists():receipt.update(status='BLOCKED_ALREADY_CAPTURED',reason='FIRST_ORIGINAL_CAPTURE_IMMUTABLE')
    elif state=='ACQUISITION_WINDOW':
        try:
            # Persistent single-owner claim prevents concurrent/repeated collectors.
            # A failed claimed attempt is retained and requires operator review;
            # this runner never silently retries or replaces its source universe.
            freeze(root/'ACQUISITION_CLAIM.json',dict(attempt=str(attempt.relative_to(root)),invoked_at=actual,fixture=fixture))
            receipt['source_attempted']=1
            receipt['ws1_capture_attempted']=0
            # Supplements precede the final WS1 freeze so their real clocks can be
            # checked against it. No supplemental source is retroactively attached.
            if fixture:
                supplement=fixture_supplement
                if supplement is None:raise ValueError('FIXTURE_SUPPLEMENT_REQUIRED')
            else:
                url=BASE+'/scoreboard?dates='+slot['toronto_date'].replace('-','')+'&limit=100'
                with urlopen(Request(url,headers={'User-Agent':'pickem-phase7-slot-preflight/1'}),timeout=15) as response:raw=response.read()
                sr=Receipt.capture(raw,source=url,observed_at=now(),origin='original_capture');freeze(attempt/'preflight_receipt.json',asdict(sr))
                with (attempt/'preflight_raw.json.gz').open('xb') as f:f.write(gzip.compress(raw,mtime=0))
                event=next((e for e in json.loads(raw)['events'] if 'espn:game:'+str(e['id'])==slot['game']['game_id']),None)
                if event is None:raise ValueError('REGISTERED_GAME_ABSENT')
                matches=[r.data for r in schedule_records(json.loads(raw),sr) if r.data['game_id']==slot['game']['game_id']]
                if len(matches)!=1 or any(matches[0][k]!=slot['game'][k] for k in ('game_id','event_start_at','home_team_id','away_team_id')):raise ValueError('REGISTERED_SCHEDULE_CHANGED')
                supplement=attempt/'supplements';acquire_supplements(supplement,event,deadline_at=slot['scheduled_freeze_at'])
            receipt['ws1_capture_attempted']=1
            model=json.loads(Path('research/nba_joint_v01/results/model.json').read_text())
            cap=capture(slot['toronto_date'],attempt/'ws1',game_id=slot['game']['game_id'],freeze_deadline_at=slot['scheduled_freeze_at'],model_training_cutoff_at=model['training_cutoff_at'],
                expected_game=slot['game'],fixture=fixture,fetch_bytes=fixture_fetch,clock=fixture_clock)
            receipt['capture_receipt']=str((attempt/'ws1/capture_receipt.json').relative_to(root))
            if cap['status']=='blocked':receipt.update(status='BLOCKED_CAPTURE',reasons=cap['errors'])
            else:
                ledger=build_game_ledger(attempt/'ws1',supplement,model);freeze(attempt/'game_day_ledger.json',ledger)
                receipt.update(status='CAPTURED_F_BLOCKED',actual_input_freeze_at=ledger['input_freeze_at'],denominators=ledger['denominators'],
                    ledger_sha256=digest((attempt/'game_day_ledger.json').read_bytes()),reasons=ledger['reasons'])
                freeze(root/'FIRST_CAPTURE.json',dict(attempt=str(attempt.relative_to(root)),receipt_kind='fixture' if fixture else 'original_capture',ledger_sha256=receipt['ledger_sha256'],
                    input_freeze_at=ledger['input_freeze_at'],model_sha256=ledger['model_sha256']))
        except Exception as exc:receipt.update(status='BLOCKED_CAPTURE',reason=type(exc).__name__+':'+str(exc))
    freeze(attempt/'attempt_receipt.json',receipt);return receipt


def prepare(output):
    root=Path(output);root.mkdir(parents=True,exist_ok=False);slots=registered_slots();at=now();rows=[]
    for s in slots:
        rows.append(dict(slot=s['slot'],game=s['game'],toronto_date=s['toronto_date'],deadline=s['scheduled_freeze_at'],
            acquisition_open=(instant(s['scheduled_freeze_at'])-timedelta(minutes=10)).isoformat(),state=window_state(s,at),
            command='OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase7.pilot capture --slot '+str(s['slot'])+' --output reports/nba_phase7_pilot',
            future_capture_completed=False,future_settlement_completed=False,original_candidates=None,F_forecasts=0,
            blocks=['COMPLETE_ELIGIBILITY_UNAVAILABLE','VALIDATED_PARTICIPATION_UNAVAILABLE'],separate_pregame_invocation_required=True))
    freeze(root/'readiness.json',dict(registered_source_sha256=REGISTRY_SHA,verified_original_slots=10,verified_original_dates=5,checked_at=at,slots=rows,
        unattended_execution_available=False,new_schedule_created=False,credentials=dict(ESPN='public; no credential required',NBA='public HTTPS; no credential required',PropLine='not invoked; original contracts unavailable; secret presence not assumed from integration name')))
    return rows


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','capture']);p.add_argument('--slot',type=int);p.add_argument('--output',required=True);a=p.parse_args()
    if a.action=='prepare':r=prepare(a.output)
    else:
        if a.slot not in range(1,11):p.error('--slot must be 1 through 10')
        r=capture_slot(registered_slots()[a.slot-1],a.output)
    print(json.dumps(r,sort_keys=True))

if __name__=='__main__':main()
