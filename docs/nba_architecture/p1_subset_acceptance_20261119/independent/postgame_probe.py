"""Independent bounded native source reconstruction; never pregame features."""
import collections,hashlib,json,pathlib
from v2.nba_architecture.gamebook_v1 import read_final_box
from v2.nba_architecture.gamebook_identity_v1 import join_game_ids
from v2.nba_architecture.p1_subset_handoff_v1 import export_requests
ROOT=pathlib.Path(__file__).resolve().parents[4];P=pathlib.Path(__file__).resolve().parents[1];R=ROOT/'docs/nba_architecture/p1_overnight_20261119/raw';C=json.loads((ROOT/'docs/nba_architecture/p1_prospective_20261118/COHORT.json').read_bytes());pre=sorted(R.glob('pregame-*'))[-1];post=next(R.glob('morning-*'))
pr=json.loads((post/'official-gamebook/receipt.json').read_bytes());pr['retrieved_at']=pr['retrieval_started_at'];pdf=(post/'official-gamebook/body.raw').read_bytes();box=read_final_box(pdf,pr)
er=json.loads((post/'target-summary/receipt.json').read_bytes());er['retrieved_at']=er['retrieval_started_at'];raw=(post/'target-summary/body.raw').read_bytes();ids=join_game_ids(box,raw,er)['rows'];known={r['player_id']:b for r,b in zip(ids,box['rows'])};requests=export_requests(pre,C)['requests']['rows'];rows=[]
for r in requests:
 b=known.get(r['player_id']);rows.append(dict(player_id=r['player_id'],team_id=r['team_id'],name=r['name'],participation=b['state'] if b else 'UNKNOWN',exact_seconds=b['exact_seconds'] if b else None,legal_eligibility=None,genuine_participation_probability=None))
counts=collections.Counter(r['participation'] for r in rows);assert counts=={'PLAYED':22,'DNP':3,'UNKNOWN':11};assert len(rows)==len({r['player_id'] for r in rows})==36;assert len(known)==25
assert box['duration_minutes']=='48' and box['overtime_periods']==0;assert all(sum(r['exact_seconds'] or 0 for r in box['rows'] if r['team']==t)==14400 for t in box['teams'])
owner=json.loads((P/'owner/all_candidate_postgame_states.json').read_bytes());assert {r['player_id'] for r in owner}=={r['player_id'] for r in rows}
for a,b in zip(owner,rows):
 assert a['player_id']==b['player_id'] and a['exact_seconds']==b['exact_seconds'] and a['legal_eligibility'] is None and a['genuine_participation_probability'] is None
 if b['participation']!='UNKNOWN':assert a['participation']==b['participation']
 else:assert a['participation'].startswith('UNKNOWN')
print(json.dumps({'known_candidate_denominator':36,'source_listed_completed_rows':25,'reconstruction_counts':dict(counts),'printed_duration_minutes':'48','overtime_periods':0,'raw_pdf_sha256':hashlib.sha256(pdf).hexdigest(),'raw_espn_sha256':hashlib.sha256(raw).hexdigest(),'original_prefreeze_eligibility_inferred':False,'settlement_admission':False,'rows':rows},indent=2))
