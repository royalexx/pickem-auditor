"""One-shot current schedule parity; frozen registrations are never replaced."""
from dataclasses import asdict
import gzip
import json
from pathlib import Path
from urllib.request import Request,urlopen
from v2.nba_ws1.capture import BASE,now
from v2.nba_ws1.adapters import schedule_records
from v2.nba_ws1.store import Receipt
from v2.nba_joint.forecast import freeze
from .pilot import registered_slots


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();root=Path(a.output);root.mkdir(parents=True,exist_ok=False)
    slots=registered_slots();rows=[];sources=[]
    for day in sorted({s['toronto_date'] for s in slots}):
        try:
            url=BASE+'/scoreboard?dates='+day.replace('-','')+'&limit=100'
            with urlopen(Request(url,headers={'User-Agent':'pickem-phase7-frozen-slate-readiness/1'}),timeout=15) as response:raw=response.read()
            receipt=Receipt.capture(raw,source=url,observed_at=now(),origin='original_capture');filename=receipt.raw_sha256+'.gz'
            with (root/filename).open('xb') as f:f.write(gzip.compress(raw,mtime=0))
            sources.append(dict(receipt=asdict(receipt),path=filename));current={r.data['game_id']:r.data for r in schedule_records(json.loads(raw),receipt)}
            for s in slots:
                if s['toronto_date']!=day:continue
                actual=current.get(s['game']['game_id']);same=actual is not None and all(actual[k]==s['game'][k] for k in ('game_id','event_start_at','home_team_id','away_team_id','status'))
                rows.append(dict(slot=s['slot'],registered_game=s['game'],current_game=actual,same_identity_schedule=same,status='READY_FOR_LATER_MANUAL_INVOCATION' if same else 'BLOCKED_SCHEDULE_CHANGED',
                    game_day_capture_completed=False,original_roster=None,participation_probabilities=None))
        except Exception as exc:
            rows += [dict(slot=s['slot'],status='BLOCKED_SOURCE_UNAVAILABLE',reason=type(exc).__name__+':'+str(exc),game_day_capture_completed=False) for s in slots if s['toronto_date']==day]
    freeze(root/'receipt.json',dict(schema='NBAPhase7LiveSchedulePreflight/1',checked_at=now(),sources=sources,slots=rows,
        interpretation='Advance schedule source receipts only; zero game-day pilot captures, forecasts or settlements. No slot reselected.',scheduled_jobs_created=0))
    print(json.dumps({'registered_slots':len(rows),'unchanged_current_slots':sum(r.get('same_identity_schedule',False) for r in rows),'game_day_captures':0}))

if __name__=='__main__':main()
