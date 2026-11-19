"""Actual native public-reader reconstruction; no new trust root or gate upgrade."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from v2.nba_architecture.gamebook_v1 import read_final_box
from v2.nba_architecture.gamebook_identity_v1 import join_game_ids
from v2.nba_architecture.admission_v1 import admit_gamebook
from v2.nba_architecture.v2_contracts import ContractError

P=Path(__file__).resolve().parent
morning=next((P/'raw').glob('morning*'))
pregame=sorted((P/'raw').glob('pregame*'))[-1]
initial=json.loads((P.parent/'p1_prospective_20261118/captures/initial-20261118T130032485295Z-9582658b/attempt.json').read_bytes())
pre=json.loads((pregame/'attempt.json').read_bytes());post=json.loads((morning/'attempt.json').read_bytes())
pdf=(morning/'official-gamebook/body.raw').read_bytes()
receipt=json.loads((morning/'official-gamebook/receipt.json').read_bytes());receipt['retrieved_at']=receipt['retrieval_started_at']
box=read_final_box(pdf,receipt)
eraw=(morning/'target-summary/body.raw').read_bytes();er=json.loads((morning/'target-summary/receipt.json').read_bytes());er['retrieved_at']=er['retrieval_started_at']
joined=join_game_ids(box,eraw,er)
by_id={r['player_id']:box['rows'][i] for i,r in enumerate(joined['rows'])}
# Printed inactive names have no external IDs; do not silently infer identity joins.
rows=[]
for r in pre['rows']:
    actual=by_id.get(r['player_id'])
    rows.append(dict(player_id=r['player_id'],name=r['name'],team_id=r['team_id'],
        final_box_state=actual['state'] if actual else 'UNKNOWN_NOT_IN_LISTED_BOX',
        exact_seconds=actual['exact_seconds'] if actual else None,
        legal_eligibility=None,genuine_participation_probability=None))
assert len(rows)==36
old={r['player_id']:r for r in initial['rows']};new={r['player_id']:r for r in pre['rows']}
try:
    admit_gamebook(pdf,receipt,required_capability='OFFICIAL_PRINTED_DURATION')
    admission='UNEXPECTED_ADMISSION'
except ContractError as error:admission=str(error)
out=dict(schema='nba-p1-overnight-reconciliation/1.0.0',input_roster_rows=36,initial_roster_rows=35,
    added_before_freeze=[new[k] for k in new.keys()-old.keys()],removed_before_freeze=list(old.keys()-new.keys()),
    final_box_listed_rows=25,played_rows=sum(r['final_box_state']=='PLAYED' for r in rows),
    dnp_rows=sum(r['final_box_state']=='DNP' for r in rows),
    unlisted_rows=sum(r['final_box_state']=='UNKNOWN_NOT_IN_LISTED_BOX' for r in rows),
    printed_inactive_text=box['inactive_text'],printed_inactive_external_identity_admitted=False,
    pdf_duration_minutes=box['duration_minutes'],pdf_overtime=box['overtime_periods'],
    positive_minimum_seconds=min(r['exact_seconds'] for r in box['rows'] if r['state']=='PLAYED'),
    target_eligible_roster_count=None,correction_history_complete=None,
    fixed_old_root_result=admission,rows=rows,B_P1_01='BLOCKED',B_P1_02='BLOCKED',G1='NO-GO')
(P/'reconciliation.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ('rows','added_before_freeze')},indent=2))
