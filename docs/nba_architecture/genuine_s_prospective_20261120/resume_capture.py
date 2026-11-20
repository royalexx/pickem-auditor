"""Resume only missing official page captures after schema discovery failure."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib,json,re,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from v2.nba_architecture.p1_capture_v1 import capture
root=Path(sys.argv[1]);selected=json.loads((root/'selected_espn_games.json').read_bytes());unique={e['id']:e for a in selected.values() for e in a}
def body(name):return json.loads((root/name/'body.raw').read_bytes())
def nextdata(name):
 s=(root/name/'body.raw').read_text();matches=re.findall(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',s,re.S)
 if len(matches)!=1:raise ValueError('DISCOVERY_NEXT_DATA_COUNT:'+name)
 return json.loads(matches[0])['props']['pageProps']
joins=[]
for eid,e in unique.items():
 date=datetime.fromisoformat(e['date'].replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')
 summary=body('summary-'+eid)
 team_names={str(t['team']['id']):t['team']['name'] for t in summary['boxscore']['players']}
 expected={t['homeAway']:team_names[str(t['id'])] for t in e['competitions'][0]['competitors']}
 cards=[c['cardData'] for m in nextdata('nba-index-'+date)['gameCardFeed']['modules'] for c in m.get('cards',[]) if 'gameId' in c.get('cardData',{})]
 matches=[c for c in cards if all(c[side+'Team']['teamName']==name for side,name in expected.items())]
 if len(matches)!=1:joins.append(dict(espn_id=eid,date=date,status='UNMATCHED_OR_AMBIGUOUS',matches=len(matches),expected=expected));continue
 c=matches[0];links=[a['resourceLocator']['resourceUrl'] for a in c['actions'] if a['title']=='Box Score']
 if len(links)!=1:raise ValueError('NBA_BOX_LINK:'+eid)
 joins.append(dict(espn_id=eid,date=date,status='DISCOVERY_MATCH_NOT_ADMISSION',nba_id=c['gameId'],official_start=c['gameTimeUtc'],espn_start=e['date'],url='https://www.nba.com'+links[0],index='nba-index-'+date))
(root/'game_joins.json').open('x').write(json.dumps(joins,indent=2)+'\n')
def acquire(j):
 p=root/('nba-box-'+j['nba_id'])
 if p.exists():return j['nba_id'],json.loads((p/'receipt.json').read_bytes())
 return j['nba_id'],capture(j['url'],p)
with ThreadPoolExecutor(max_workers=4) as pool:results=dict(pool.map(acquire,[j for j in joins if 'nba_id' in j]))
target=next(e for e in body('scoreboard')['events'] if e['id']=='401910026');(root/'target.json').open('x').write(json.dumps(target,indent=2)+'\n')
receipt=dict(completed_at=datetime.now(timezone.utc).isoformat(),target_game=target['id'],target_start=target['date'],selected_team_games={k:len(v) for k,v in selected.items()},unique_games=len(unique),official_matches=len(results),bad_sources=[dict(nba_id=k,status=v.get('status'),error=v.get('error')) for k,v in results.items() if v.get('status')!=200],scope='Discovery only; no admission or fitting. Initial schema failure preserved; native team names now joined from captured summary boxscore, not guessed from a missing schedule field.')
(root/'capture_receipt.json').open('x').write(json.dumps(receipt,indent=2)+'\n')
(root/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(root))+'\n' for p in sorted(root.rglob('*')) if p.is_file() and p!=root/'SHA256SUMS'))
print(json.dumps(receipt,indent=2))
