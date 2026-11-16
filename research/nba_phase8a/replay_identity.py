"""Reparse retained advance source bytes; observation clocks never change."""
import gzip,json
from pathlib import Path
from research.nba_phase7.evidence import build_crosswalk
from research.nba_phase7.sources import read_supplement
from research.nba_phase7.pilot import registered_slots
from v2.nba_ws1.store import Receipt
from v2.nba_ws1.capture import now
from v2.nba_joint.forecast import freeze

def replay(source,output):
    root=Path(source);out=Path(output);out.mkdir(parents=True,exist_ok=False);nba=[];espn=[]
    for folder in sorted(root.glob('*_supplements')):
        for item in json.loads((folder/'receipt.json').read_text())['items']:
            if item['kind']=='nba_team_roster':nba.append(read_supplement(folder,item))
    for p in root.glob('source_*.json'):
        item=json.loads(p.read_text());r=Receipt(**item['receipt'])
        if r.source.endswith('/roster'):
            raw=gzip.decompress((root/item['path']).read_bytes());r.verify(raw);espn.append((raw,r))
    walks={};errors=[]
    for raw,r in espn:
        tid='espn:team:'+str(json.loads(raw)['team']['id'])
        for nr,nreceipt in nba:
            try:w=build_crosswalk(nr,nreceipt,raw,r,freeze_at=max(r.observed_at,nreceipt.observed_at))
            except ValueError as exc:
                if str(exc)!='CROSS_PROVIDER_TEAM_UNRESOLVED':errors.append({'team_id':tid,'code':str(exc)})
            else:
                if tid not in walks:walks[tid]=w;freeze(out/('team_'+tid.split(':')[-1]+'.json'),w)
    rows=[]
    for s in registered_slots():
        for tid in (s['game']['home_team_id'],s['game']['away_team_id']):
            w=walks.get(tid)
            rows.append(dict(slot=s['slot'],game_id=s['game']['game_id'],team_id=tid,resolved=len(w['entries']) if w else 0,unresolved=w['unresolved'] if w else None,status='advance_original_identity_only' if w else 'BLOCKED_SOURCE',verified_eligible=0))
    result=dict(schema='NBAPhase8AIdentityReplay/1',parsed_at=now(),source_root=str(root),team_game_coverage=rows,unique_teams=len(walks),unique_resolved=sum(len(w['entries']) for w in walks.values()),errors=errors,game_day_capture_count=0)
    freeze(out/'coverage.json',result);return result
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args();r=replay(a.source,a.output);print(r['unique_teams'],r['unique_resolved'])
