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


def capture(day,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);sources=output/'sources';sources.mkdir()
    receipts=[];manifest=[];records=[];errors=[]
    def fetch(path,origin):
        url=BASE+path
        with urlopen(Request(url,headers={'User-Agent':'pickem-nba-ws1-bounded-research/1'}),timeout=25) as response:
            raw=response.read()
            if response.status!=200:raise ValueError('SOURCE_HTTP_ERROR')
        clock=now();r=Receipt.capture(raw,source=url,observed_at=clock,origin=origin)
        target=sources/(r.raw_sha256+'.json.gz');target.write_bytes(gzip.compress(raw,mtime=0))
        receipts.append(r);manifest.append(dict(receipt_id=r.receipt_id,path=str(target.relative_to(output)),encoding='gzip',raw_sha256=r.raw_sha256,bytes=len(raw)))
        return json.loads(raw),r
    try:
        board,r=fetch('/scoreboard?dates='+day.replace('-','')+'&limit=100','original_capture')
        future=[g for g in schedule_records(board,r) if g.data['status']=='scheduled' and instant(g.data['event_start_at'])>instant(now())]
        if not future:raise ValueError('NO_ACCESSIBLE_UPCOMING_EVENT')
        game=min(future,key=lambda g:g.data['event_start_at']);gid=game.data['game_id'];records.append(game)
        summary,r=fetch('/summary?event='+gid.split(':')[-1],'original_capture')
        records.extend(espn_injury_records(summary,r,game_id=gid))
        past_ids=set()
        for tid in (game.data['home_team_id'],game.data['away_team_id']):
            roster,r=fetch('/teams/'+tid.split(':')[-1]+'/roster','original_capture')
            records.extend(espn_roster_records(roster,r,game_id=gid,team_id=tid))
            # Only discover past event IDs; do not use future season stats in features.
            schedule,sr=fetch('/teams/'+tid.split(':')[-1]+'/schedule?season='+str(int(day[:4])+(int(day[5:7])>=10))+'&seasontype=2','retrospective_retrieval')
            past=[e for e in schedule.get('events',[]) if instant(e['date'])<instant(now()) and e.get('competitions',[{}])[0].get('status',{}).get('type',{}).get('completed') is True]
            past_ids.update(e['id'] for e in sorted(past,key=lambda e:e['date'])[-2:])
        for event_id in sorted(past_ids):
            box,r=fetch('/summary?event='+event_id,'retrospective_retrieval')
            records.extend(espn_boxscore_records(box,r));records.extend(espn_team_records(box,r))
        freeze=now();snapshot=build_snapshot(game_id=gid,forecast_at=freeze,input_freeze_at=freeze,model_training_cutoff_at=freeze,
            records=records,receipts=receipts)
        path=save_snapshot(snapshot,output/'snapshots')
        report=dict(status='captured_partial_shadow',game=game.data,snapshot_path=str(path.relative_to(output)),snapshot_hash=snapshot.content_hash,
            forecast_at=freeze,training_cutoff_semantics='consumer upper-bound only; no statistical model fitted',sources=manifest,errors=errors)
    except Exception as exc:
        report=dict(status='blocked',captured_at=now(),errors=[dict(code=type(exc).__name__,detail=str(exc))],sources=manifest)
    with (output/'capture_receipt.json').open('x') as f:json.dump(report,f,sort_keys=True,indent=2);f.write('\n')
    print(canonical({k:v for k,v in report.items() if k!='sources'}))
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--day',required=True);p.add_argument('--output',required=True,type=Path);a=p.parse_args();capture(a.day,a.output)

if __name__=='__main__':main()
