"""Independent actual raw source reconciliation; no new admission or repairs."""
import hashlib,json,pathlib,re,subprocess
from datetime import datetime
from v2.nba_architecture.gamebook_v1 import read_final_box
from v2.nba_architecture.gamebook_identity_v1 import join_game_ids
from v2.nba_architecture.p1_listed_source_v1 import listed_population_receipt
P=pathlib.Path(__file__).resolve().parents[1];R=P/'raw';attempts=[];receipt_count=0
for folder in sorted(R.iterdir()):
 a=json.loads((folder/'attempt.json').read_bytes());rows=a['rows'];assert len(rows)==len({r['player_id'] for r in rows})==36
 assert all(r['legal_eligibility'] is None and r['participation_probability'] is None and r['availability']=='UNKNOWN_UNADMITTED' for r in rows)
 for receiptpath in folder.glob('*/receipt.json'):
  r=json.loads(receiptpath.read_bytes());raw=(receiptpath.parent/'body.raw').read_bytes();assert hashlib.sha256(raw).hexdigest()==r['raw_sha256'];assert len(raw)==r['bytes'];receipt_count+=1
  if a['stage']=='pregame':assert datetime.fromisoformat(r['ingested_at'])<datetime.fromisoformat('2026-11-18T23:45:00+00:00')
 attempts.append((folder,a))
first=json.loads((pathlib.Path('docs/nba_architecture/p1_prospective_20261118/roster-initial-5/body.raw')).read_bytes());old={'espn:player:'+str(x['id']) for x in first['athletes']}
morning,a=next((f,a) for f,a in attempts if a['stage']=='morning');roster={r['player_id']:r for r in a['rows']}
pr=json.loads((morning/'official-gamebook/receipt.json').read_bytes());pr=dict(pr,retrieved_at=pr['retrieval_started_at']);pdf=(morning/'official-gamebook/body.raw').read_bytes();box=read_final_box(pdf,pr)
er=json.loads((morning/'target-summary/receipt.json').read_bytes());er=dict(er,retrieved_at=er['retrieval_started_at']);espn=(morning/'target-summary/body.raw').read_bytes();ids=join_game_ids(box,espn,er)['rows']
assert len(ids)==25;assert sum(r['state']=='PLAYED' for r in box['rows'])==22;assert sum(r['state']=='DNP' for r in box['rows'])==3
assert all(sum(r['exact_seconds'] or 0 for r in box['rows'] if r['team']==t)==14400 for t in box['teams']);assert box['duration_minutes']=='48' and box['overtime_periods']==0
outcomes={r['player_id']:dict(r,state=b['state'],exact_seconds=b['exact_seconds']) for r,b in zip(ids,box['rows'])}
unknown=[dict(player_id=k,name=r['name'],state='UNKNOWN_NOT_LISTED_IN_FINAL_BOX') for k,r in roster.items() if k not in outcomes];assert len(unknown)==11;assert not (set(outcomes)-set(roster))
# The prior installed identity root deliberately does not admit this new game.
blocked=listed_population_receipt(pdf,pr,espn,er);assert blocked['status']=='REJECTED_WHOLE_BUNDLE' and blocked['attempted_rows']==25 and blocked['rejected_rows']==25
injury=[]
for folder,a in attempts:
 if a['stage']!='pregame':continue
 html=(folder/'official-injury-index/body.raw').read_text();links=sorted(set(re.findall(r'https://ak-static\.cms\.nba\.com/[^\s\"<>]+\.pdf',html)));current=[u for u in links if '2026-11-18' in u or '2026-11-19' in u];times=[]
 for url in current:
  m=re.search(r'Injury-Report_(2026-11-18)_(\d{2})_(\d{2})(AM|PM)\.pdf',url)
  if m:times.append(((int(m[2])%12+(12 if m[4]=='PM' else 0))*60+int(m[3]),url))
 selected=[json.loads((s/'receipt.json').read_bytes())['url'] for s in sorted(folder.glob('injury-pdf-*'))];assert selected==current[-2:]
 printed=[subprocess.check_output(['pdftotext','-layout',str(s/'body.raw'),'-']).decode().splitlines()[0].strip() for s in sorted(folder.glob('injury-pdf-*'))]
 injury.append({'attempt':folder.name,'indexed_same_day_links':len(current),'lexically_selected':selected,'printed_headers':printed,'latest_indexed_filename_wallclock_before_1845':max(t for t in times if t[0]<=18*60+45),'scope':'Filename clock ordering only; no uncollected report body or verified publication claim.'})
print(json.dumps({'receipt_body_hash_checks':receipt_count,'cohort_union':36,'initial35_to_pregame36_added':[{k:r[k] for k in ['player_id','name','team_id']} for k,r in roster.items() if r['team_id']=='espn:team:5' and k not in old],'listed_final':25,'played':22,'explicit_DNP':3,'played_zero':0,'roster_not_listed_final':unknown,'official_printed_duration':box['duration_minutes'],'official_printed_OT':box['overtime_periods'],'played_min_seconds':min(r['exact_seconds'] for r in box['rows'] if r['exact_seconds']),'old_root_rejection':blocked,'injury_selection_gap':injury},indent=2))
