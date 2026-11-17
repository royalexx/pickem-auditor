"""Independent exact-candidate synthetic certificate probes; no fitting."""
import argparse,copy,json,sys,hashlib,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.candidate.resolve();sys.path[:0]=[str(root),str(root/'tests/nba_architecture')]
from tests.nba_architecture.test_exposure_certificate_v1 import build,reseal
from v2.nba_architecture.exposure_certificate_v1 import certify,verification_receipt
from v2.nba_architecture.exposure_v2 import validate_exposure_coupling as old
from v2.nba_architecture.v2_contracts import ContractError
p0,g0,o0=build(4);rows=[]
def scenario_fixture(mode):
 p,g,o=copy.deepcopy(p0),copy.deepcopy(g0),copy.deepcopy(o0)
 for sc in g['scenarios']:sc['overtime_periods']=0
 g=reseal(g);o['game_state_sha256']=g['content_hash']
 for team in p['team_ids']:
  persons=[x for x in o['players'] if x['team_id']==team];ids=[x['player_id'] for x in persons]
  assert len(ids)==6
  for i,person in enumerate(persons):
   person['minutes_law']['parameters']['support']=[dict(minutes=48.,mass=1.)]
   person['participation_probability']=.5 if mode=='known' and i<2 else None
   person['participation_evidence']='independently_estimated' if mode=='known' and i<2 else 'unknown'
  for j,sc in enumerate(o['scenarios']):
   sc['overtime_periods']=0
   for row in sc['players']:
    if row['player_id'] in ids:
     i=ids.index(row['player_id']);zero=i<2 and i==j%2
     row['minutes']=0. if zero else 48.;row['participation']='DNP' if zero else 'PLAYED'
 return p,g,reseal(o)
p,g,o=scenario_fixture('known');r=verification_receipt(o,p,g);reference=old(o,p,g)
assert r['route']=='EXACT_DECIMAL_FULL_MARGINAL_CERTIFICATE' and r['bounds']==reference
rows.append(dict(case='known_half_q_rotation',status='PASS',route=r['route'],bounds=r['bounds']))
query_pid=o['players'][0]['player_id']
for mass,valid in [(0,True),(.5,True),(.5000000000000001,False),(-1,False),(True,False),(float('nan'),False)]:
 try:certify(o,p,g,required_positive=(query_pid,mass));accepted=True
 except ContractError:accepted=False
 assert accepted==valid
 rows.append(dict(case='exact_required_positive_bound',mass=repr(mass),expected_valid=valid,status='PASS'))
p,g,o=scenario_fixture('unknown')
try:certify(o,p,g)
except ContractError as exc:assert exc.code=='CERT_BOUND_NOT_ATTAINED'
else:raise AssertionError('simultaneous q1 impossible when six48minute-only laws share240minutes')
r=verification_receipt(o,p,g);reference=old(o,p,g)
assert r['route']=='ORIGINAL_V2_COMPLETE_FLOAT_LP' and r['bounds']==reference
assert all(v[0]==1 for v in reference.values())
rows.append(dict(case='different_qmax_one_extrema_do_not_share_optimizer',status='PASS',route=r['route'],bounds=r['bounds'],numeric_contract=r['numeric_contract']))
# P1 known-out forces DNP and q0 without inventing an unconditional playing rate.
p,g,o=scenario_fixture('known');team=p['team_ids'][0];pid=next(x['player_id'] for x in o['players'] if x['team_id']==team)
# Use one permanently excluded player, all other five play48 every scenario.
for x in p['players']:
 if x['player_id']==pid:
  x['availability']='out';x['legal_eligibility']=False
  for field,value in [('availability','out'),('legal_eligibility',False)]:x['availability_evidence' if field=='availability' else 'eligibility_evidence']=dict(source_receipt_sha256=p['sources'][0]['receipt_sha256'],player_id=pid,game_id=p['game_id'],field=field,value=value)
p=reseal(p);g['source_snapshot_sha256']=p['content_hash'];g=reseal(g);o['source_snapshot_sha256']=p['content_hash'];o['game_state_sha256']=g['content_hash']
for x in o['players']:
 if x['team_id']==team:x['participation_probability']=0. if x['player_id']==pid else None;x['participation_evidence']='verified_out' if x['player_id']==pid else 'unknown'
for sc in o['scenarios']:
 for x in sc['players']:
  if x['team_id']==team:x['minutes']=0. if x['player_id']==pid else 48.;x['participation']='DNP' if x['player_id']==pid else 'PLAYED'
o=reseal(o);r=certify(o,p,g);assert r['exact_bounds'][pid]==['0','0']
rows.append(dict(case='excluded_q0_and_complete_atom_population',status='PASS',bound=r['exact_bounds'][pid]))
# Actual stochastic producer n128 demonstrates linear finite-column proof; all
# atoms are retained, and q remains null. This is not a general capacity claim.
p,g,o=build(128);r=certify(o,p,g);assert r['positive_certificate_columns']==128 and all(x['participation_probability'] is None for x in o['players'])
rows.append(dict(case='actual_O2_n128',status='PASS',columns=128,max_minute_residual=r['max_minute_residual'],exact_bounds=r['exact_bounds']))
# Tiny unavailable atom matters even when floating sum remains exactly1.
for tiny in [1e-50,1e-200,5e-324]:
 x=copy.deepcopy(o);x['players'][0]['minutes_law']['parameters']['support'].append(dict(minutes=0.,mass=tiny));x=reseal(x)
 try:certify(x,p,g)
 except ContractError as exc:assert exc.code=='CERT_FULL_ATOM_MARGINAL'
 else:raise AssertionError('missing tiny atom accepted')
 rows.append(dict(case='tiny_absent_atom',mass=tiny,status='PASS'))
result=dict(candidate=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip(),qa_source_raw_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),rows=rows,all_pass=True,synthetic_only=True,observed_games=0,source_admission=False)
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
