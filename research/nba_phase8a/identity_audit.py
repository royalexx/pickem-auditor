"""Bounded advance identity audit using Phase 7 source contracts, never a pilot capture."""
from dataclasses import asdict
from datetime import timedelta
import gzip,json
from pathlib import Path
from urllib.request import Request,urlopen
from research.nba_phase7.pilot import registered_slots
from research.nba_phase7.sources import acquire_supplements,read_supplement
from research.nba_phase7.evidence import build_crosswalk,injury_pdf,resolve_injuries
from v2.nba_ws1.capture import BASE,now
from v2.nba_ws1.store import Receipt,instant
from v2.nba_joint.forecast import freeze


def audit(output):
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    sources=[];errors=[];boards={};walks={};rows=[];reports=[]
    def fetch(url):
        with urlopen(Request(url,headers={'User-Agent':'pickem-phase8a-advance-identity-audit/1'}),timeout=20) as r:raw=r.read(4*1024*1024+1)
        if len(raw)>4*1024*1024:raise ValueError('SOURCE_SIZE_BOUND')
        receipt=Receipt.capture(raw,source=url,observed_at=now(),origin='original_capture')
        path=receipt.raw_sha256+'.gz'
        if not (root/path).exists():
            with (root/path).open('xb') as f:f.write(gzip.compress(raw,mtime=0))
        sources.append(dict(path=path,receipt=asdict(receipt)));freeze(root/('source_%03d.json'%len(sources)),sources[-1])
        return raw,receipt
    for slot in registered_slots():
        day=slot['toronto_date'];gid=slot['game']['game_id']
        try:
            if day not in boards:boards[day]=json.loads(fetch(BASE+'/scoreboard?dates='+day.replace('-','')+'&limit=100')[0])
            event=next(e for e in boards[day]['events'] if 'espn:game:'+str(e['id'])==gid)
            from v2.nba_ws1.adapters import schedule_records
            # Fresh identity check against the original registration; no substitution.
            board_source=next(s for s in sources if s['receipt']['source'].endswith('dates='+day.replace('-','')+'&limit=100'))
            current=next(r.data for r in schedule_records(boards[day],Receipt(**board_source['receipt'])) if r.data['game_id']==gid)
            if any(current[k]!=slot['game'][k] for k in ('game_id','event_start_at','home_team_id','away_team_id')):raise ValueError('REGISTERED_SCHEDULE_CHANGED')
            needed=[c for c in event['competitions'][0]['competitors'] if c['team']['id'] not in walks]
            if needed:
                folder=root/('slot_%02d_supplements'%slot['slot'])
                acquire_supplements(folder,{**event,'competitions':[{**event['competitions'][0],'competitors':needed}]},deadline_at=(instant(now())+timedelta(minutes=5)).isoformat())
                supplement=json.loads((folder/'receipt.json').read_text());errors.extend(supplement['errors'])
                nba=[]
                for item in supplement['items']:
                    raw,r=read_supplement(folder,item)
                    if item['kind']=='nba_team_roster':nba.append((raw,r))
                    if item['kind']=='official_injury_pdf':
                        try:reports.append(injury_pdf(raw,r,freeze_at=now()))
                        except Exception as exc:errors.append({'code':str(exc)})
                for comp in needed:
                    tid=comp['team']['id'];eraw,er=fetch(BASE+'/teams/'+tid+'/roster');success=[]
                    for nraw,nr in nba:
                        try:success.append(build_crosswalk(nraw,nr,eraw,er,freeze_at=now()))
                        except ValueError as exc:
                            if str(exc)!='CROSS_PROVIDER_TEAM_UNRESOLVED':errors.append({'team_id':tid,'code':str(exc)})
                    if len(success)!=1:raise ValueError('UNIQUE_TEAM_BRIDGE_UNAVAILABLE:'+tid)
                    walks[tid]=success[0];freeze(root/('team_'+tid+'_crosswalk.json'),success[0])
            for comp in event['competitions'][0]['competitors']:
                tid=comp['team']['id'];w=walks.get(tid)
                rows.append(dict(slot=slot['slot'],game_id=gid,team_id='espn:team:'+tid,team_name=comp['team']['displayName'],resolved=len(w['entries']) if w else 0,unresolved=w['unresolved'] if w else None,observation_kind='advance_original_roster_identity_not_game_day',eligibility_verified=0))
        except Exception as exc:errors.append(dict(slot=slot['slot'],code=type(exc).__name__,detail=str(exc)))
        freeze(root/('slot_%02d_progress.json'%slot['slot']),dict(rows=[r for r in rows if r['slot']==slot['slot']],errors=errors))
    availability=[resolve_injuries(r,list(walks.values()),freeze_at=now()) for r in reports]
    result=dict(schema='NBAPhase8AAdvanceAudit/1',observed_at=now(),sources=sources,team_game_coverage=rows,unique_teams=len(walks),unique_team_identity_rows=sum(len(w['entries']) for w in walks.values()),errors=errors,injury_reports=reports,availability=availability,genuine_pilot_captures=0,game_day_candidate_rows=0,eligible_denominator_established=False)
    freeze(root/'audit.json',result)
    return {k:result[k] for k in ('unique_teams','unique_team_identity_rows','genuine_pilot_captures','errors')}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);print(json.dumps(audit(p.parse_args().output)))
