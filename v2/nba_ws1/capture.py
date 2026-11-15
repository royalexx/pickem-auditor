"""Explicit bounded research capture. No background collector or schedule.

python -m v2.nba_ws1.capture --day 2026-11-15 --output <new-directory>
"""
import argparse
from dataclasses import asdict
from datetime import datetime,timezone
import gzip
import json
from pathlib import Path
from urllib.request import Request,urlopen
from .adapters import (schedule_records,espn_id,espn_roster_records,espn_boxscore_records,espn_team_records,espn_injury_records)
from .store import Receipt,build_snapshot,save_snapshot,canonical,digest,instant

BASE='https://site.api.espn.com/apis/site/v2/sports/basketball/nba'


def now():return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')


def capture(day,output,*,game_id=None,freeze_deadline_at=None,model_training_cutoff_at=None,
            fetch_bytes=None,clock=None,fixture=False,expected_game=None):
    if (fetch_bytes is not None or clock is not None) and not fixture:raise ValueError('FIXTURE_TRANSPORT_REQUIRED')
    clock=clock or now
    output=Path(output);output.mkdir(parents=True,exist_ok=False);sources=output/'sources';sources.mkdir()
    receipts=[];manifest=[];records=[];errors=[]
    def fetch(path,origin):
        url=BASE+path
        if freeze_deadline_at is not None and instant(clock())>instant(freeze_deadline_at):raise ValueError('FREEZE_DEADLINE_MISSED')
        if fetch_bytes is None:
            with urlopen(Request(url,headers={'User-Agent':'pickem-nba-ws1-bounded-research/1'}),timeout=25) as response:
                raw=response.read()
                if response.status!=200:raise ValueError('SOURCE_HTTP_ERROR')
        else:raw=fetch_bytes(url)
        captured=clock();r=Receipt.capture(raw,source=url,observed_at=captured,origin='fixture' if fixture else origin)
        target=sources/(r.raw_sha256+'.json.gz');target.write_bytes(gzip.compress(raw,mtime=0))
        receipts.append(r);manifest.append(dict(receipt_id=r.receipt_id,path=str(target.relative_to(output)),encoding='gzip',raw_sha256=r.raw_sha256,bytes=len(raw)))
        if freeze_deadline_at is not None and instant(captured)>instant(freeze_deadline_at):raise ValueError('FREEZE_DEADLINE_MISSED_AFTER_RECEIPT')
        return json.loads(raw),r
    try:
        if freeze_deadline_at is not None and instant(clock())>instant(freeze_deadline_at):raise ValueError('FREEZE_DEADLINE_MISSED')
        board,r=fetch('/scoreboard?dates='+day.replace('-','')+'&limit=100','original_capture')
        future=[g for g in schedule_records(board,r) if g.data['status']=='scheduled' and instant(g.data['event_start_at'])>instant(clock())]
        if game_id is not None:
            future=[g for g in future if g.data['game_id']==game_id]
            if len(future)!=1:raise ValueError('EXACT_REGISTERED_GAME_NOT_PREGAME')
        if not future:raise ValueError('NO_ACCESSIBLE_UPCOMING_EVENT')
        game=min(future,key=lambda g:g.data['event_start_at']);gid=game.data['game_id'];records.append(game)
        if expected_game is not None and any(game.data.get(k)!=expected_game.get(k) for k in ('game_id','home_team_id','away_team_id','event_start_at')):
            raise ValueError('REGISTERED_SCHEDULE_CHANGED')
        summary,r=fetch('/summary?event='+gid.split(':')[-1],'original_capture')
        records.extend(espn_injury_records(summary,r,game_id=gid))
        past_ids=set()
        for tid in (game.data['home_team_id'],game.data['away_team_id']):
            roster,r=fetch('/teams/'+tid.split(':')[-1]+'/roster','original_capture')
            records.extend(espn_roster_records(roster,r,game_id=gid,team_id=tid))
            # Only discover past event IDs; do not use future season stats in features.
            schedule,sr=fetch('/teams/'+tid.split(':')[-1]+'/schedule?season='+str(int(day[:4])+(int(day[5:7])>=10))+'&seasontype=2','retrospective_retrieval')
            past=[e for e in schedule.get('events',[]) if instant(e['date'])<instant(clock()) and e.get('competitions',[{}])[0].get('status',{}).get('type',{}).get('completed') is True]
            past_ids.update(e['id'] for e in sorted(past,key=lambda e:e['date'])[-2:])
        for event_id in sorted(past_ids):
            box,r=fetch('/summary?event='+event_id,'retrospective_retrieval')
            records.extend(espn_boxscore_records(box,r));records.extend(espn_team_records(box,r))
        freeze=clock()
        if instant(freeze)>=instant(game.data['event_start_at']):raise ValueError('SOURCE_CAPTURE_AFTER_TIPOFF')
        if freeze_deadline_at is not None and instant(freeze)>instant(freeze_deadline_at):raise ValueError('FREEZE_DEADLINE_MISSED')
        snapshot=build_snapshot(game_id=gid,forecast_at=freeze,input_freeze_at=freeze,model_training_cutoff_at=model_training_cutoff_at or freeze,
            records=records,receipts=receipts)
        path=save_snapshot(snapshot,output/'snapshots')
        report=dict(status='captured_partial_shadow',game=game.data,snapshot_path=str(path.relative_to(output)),snapshot_hash=snapshot.content_hash,
            forecast_at=freeze,training_cutoff_semantics='supplied frozen model cutoff' if model_training_cutoff_at else 'consumer upper-bound only; no statistical model fitted',sources=manifest,errors=errors)
    except Exception as exc:
        report=dict(status='blocked',captured_at=clock(),errors=[dict(code=type(exc).__name__,detail=str(exc))],sources=manifest)
    if game_id is not None:report['requested_game_id']=game_id
    if freeze_deadline_at is not None:report['freeze_deadline_at']=freeze_deadline_at
    if fixture:report['evidence_kind']='synthetic_fixture_never_original'
    with (output/'capture_receipt.json').open('x') as f:json.dump(report,f,sort_keys=True,indent=2);f.write('\n')
    print(canonical({k:v for k,v in report.items() if k!='sources'}))
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--day',required=True);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--game-id');p.add_argument('--freeze-deadline-at');p.add_argument('--model-training-cutoff-at');a=p.parse_args()
    capture(a.day,a.output,game_id=a.game_id,freeze_deadline_at=a.freeze_deadline_at,model_training_cutoff_at=a.model_training_cutoff_at)

if __name__=='__main__':main()
