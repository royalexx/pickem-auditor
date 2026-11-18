"""Independent frozen raw profile inspection, no admission authority."""
import hashlib,json,pathlib,datetime
P=pathlib.Path(__file__).resolve().parents[1]
c=json.loads((P/'COHORT.json').read_bytes());sr=json.loads((P/'schedule-initial/receipt.json').read_bytes());b=(P/'schedule-initial/body.raw').read_bytes()
assert hashlib.sha256(b).hexdigest()==c['source_schedule_sha256']==sr['raw_sha256']
def dt(s):return datetime.datetime.fromisoformat(s.replace('Z','+00:00'))
events=[e for e in json.loads(b)['events'] if e['status']['type']['state']=='pre' and dt(e['date'])>dt(sr['retrieval_completed_at'])]
selected=min(events,key=lambda e:(dt(e['date']),int(e['id'])))
assert selected['id']==c['game_id'] and dt(selected['date'])==dt(c['start'])
assert (dt(c['start'])-dt(c['freeze_at'])).total_seconds()==900
assert {str(t['team']['id']) for t in selected['competitions'][0]['competitors']}==set(c['teams'])
counts={};rosters={}
for tid in c['teams']:
 folder=P/f'roster-initial-{tid}';receipt=json.loads((folder/'receipt.json').read_bytes());raw=(folder/'body.raw').read_bytes();x=json.loads(raw)
 assert hashlib.sha256(raw).hexdigest()==receipt['raw_sha256']
 assert str(x['team']['id'])==tid and receipt['url'].endswith('/teams/'+tid+'/roster')
 assert dt(receipt['ingested_at'])<dt(c['freeze_at'])
 ids=[str(a['id']) for a in x['athletes']];assert len(ids)==len(set(ids));counts[tid]=len(ids);rosters[tid]=ids
assert len(set(rosters['5'])&set(rosters['29']))==0
print(json.dumps({'game':c['game_id'],'listed_roster_counts':counts,'listed_total':sum(counts.values()),'legal_eligible_count':None,'correction_history_complete':None,'original_sources_admitted':False},indent=2))
