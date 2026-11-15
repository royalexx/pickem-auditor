"""One-shot pilot preregistration; not an automation or a future-game forecast."""
import argparse
from datetime import datetime, timedelta, timezone
import gzip
import json
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from v2.nba_ws1.capture import BASE, now
from v2.nba_ws1.store import Receipt, digest, canonical, instant
from v2.nba_ws1.adapters import schedule_records
from v2.nba_joint.forecast import freeze


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    root=Path(a.output);root.mkdir(parents=True,exist_ok=False);(root/'sources').mkdir()
    rows=[];sources=[];errors=[]
    for offset in range(5):
        day=(datetime(2026,11,16)+timedelta(days=offset)).date().isoformat()
        url=BASE+'/scoreboard?dates='+day.replace('-','')+'&limit=100'
        try:
            with urlopen(Request(url,headers={'User-Agent':'pickem-phase6-bounded-source-audit/1'}),timeout=20) as response:raw=response.read()
            r=Receipt.capture(raw,source=url,observed_at=now(),origin='original_capture')
            path=root/'sources'/(r.raw_sha256+'.json.gz');path.write_bytes(gzip.compress(raw,mtime=0))
            from dataclasses import asdict
            sources.append({**asdict(r),'path':str(path.relative_to(root))})
            records=schedule_records(json.loads(raw),r)
            games=sorted([x.data for x in records if x.data['status']=='scheduled' and instant(x.data['event_start_at']).astimezone(ZoneInfo('America/Toronto')).date().isoformat()==day],key=lambda x:(x['event_start_at'],x['game_id']))[:2]
        except Exception as exc:
            errors.append(dict(day=day,error=type(exc).__name__,detail=str(exc)));games=[]
        for i in range(2):
            g=games[i] if i<len(games) else None
            freeze_at=(instant(g['event_start_at'])-timedelta(minutes=30)).isoformat() if g else None
            rows.append(dict(slot=len(rows)+1,toronto_date=day,game=g,scheduled_freeze_at=freeze_at,
                schedule_receipt_id=r.receipt_id if g else None,status='BLOCKED-BY-DATA',
                reasons=['FUTURE_GAME_DAY_CAPTURE_NOT_YET_OBSERVED','GAME_DAY_ELIGIBILITY_UNAVAILABLE','PARTICIPATION_METHOD_UNAVAILABLE','FUTURE_OFFICIAL_SETTLEMENT_UNAVAILABLE']+([] if g else ['SCHEDULE_SLOT_UNRESOLVED']),
                original_candidate_universe=None,forecasts_generated=0,forecasts_certified=0,settlements=0,
                capture_attempt_status='not_yet_due' if g else 'schedule_unresolved',market_performance_claim=False))
    report=dict(schema='NBAPhase6ProspectivePilot/1.0.0',registered_at=now(),protocol_sha256=digest(Path('research/nba_phase6/PROTOCOL.md').read_bytes()),
        target_games=10,target_toronto_dates=5,slots=rows,source_receipts=sources,errors=errors,
        retrospective_evidence_mixed=False,new_scheduler_created=False,completed_games=0,
        current_status='BLOCKED-BY-DATA',interpretation='Feasibility/mechanism pilot only; current receipts are advance readiness, not ten completed game-day attempts or forecasts.',
        next_action='Use existing WS1 capture manually before each scheduled freeze, retain all candidates and abstentions; never backfill. Current adapter cannot certify game-active eligibility or participation. Independent official settlement follows the game.')
    freeze(root/'blocked_receipt.json',report)
    print(canonical({'slots':len(rows),'resolved_games':sum(r['game'] is not None for r in rows),'errors':errors,'status':report['current_status']}))

if __name__=='__main__':main()
