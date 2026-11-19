"""Independent genuine native inference; no fitting, scoring or new source fetch."""
import collections,hashlib,json,pathlib,subprocess,sys
from datetime import datetime,timezone
from unittest.mock import patch
from v2.nba_architecture import subset_p3_v1 as p3
from v2.nba_architecture.p1_subset_handoff_v1 import export_requests,canonical
ROOT=pathlib.Path(__file__).resolve().parents[5];PACK=ROOT/'docs/nba_architecture/p1_p5_handoffs_20261119';OUT=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else pathlib.Path(__file__).resolve().parent/'new_execution';OUT.mkdir(parents=True,exist_ok=False);CAP=ROOT/'docs/nba_architecture/p1_subset_acceptance_20261119/initial_tonight_capture';C=json.loads((PACK/'PROSPECTIVE_COHORT.json').read_bytes());H=PACK/'prospective_inputs';M=ROOT/'research/nba_ws2/results/model.json'
s=canonical(export_requests(CAP,C));(OUT/'p1.json').write_bytes(s);clock=datetime.now(timezone.utc).isoformat();(OUT/'forecast_at.txt').write_text(clock+'\n');calls=[];original=p3.native.MinutesModel.forecast
def count(model,name,item,seed):calls.append((name,item.player_id));return original(model,name,item,seed)
with patch.object(p3.native.MinutesModel,'forecast',count):x=p3.run_p3(s,CAP,C,history_dir=H,model_path=M,forecast_at=clock)
assert len(calls)==x['forecasted_rows']==36;assert (x['candidate_denominator'],x['attempt_denominator'],x['observation_denominator'],x['abstained_rows'])==(36,108,540,72)
wire=canonical(x);(OUT/'p3.json').write_bytes(wire);p3.read_p3(wire,source_raw=s,capture_dir=CAP,cohort=C,history_dir=H,model_path=M,forecast_at=clock)
reasons=collections.Counter(r['reason'] for r in x['rows'] if r['forecast'] is None)
assert all(r['participation_probability'] is None and r['legal_eligibility'] is None for r in x['rows']);assert not x['team_allocation_performed'];assert not x['production_release']
for r in x['rows']:
 if r['forecast']:
  f=r['forecast'];assert f['participation_probability'] is None and f['active_roster_eligible'] is None;assert f['status']=='UNCERTIFIED/SHADOW';assert 'UNCONDITIONAL_OPPORTUNITY_UNAVAILABLE' in f['abstention_reasons']
receipt={'tested_checkout':subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),'implementation_raw_sha256':hashlib.sha256(pathlib.Path(p3.__file__).read_bytes()).hexdigest(),'forecast_at':clock,'candidate_denominator':36,'attempt_denominator':108,'observations':540,'actual_native_forward_calls':len(calls),'readback_native_replay':True,'positive_native_conditional_laws':36,'distinct_positive_players':len(set(p for _,p in calls)),'abstained_attempts':72,'reasons':dict(reasons),'model_raw_sha256':hashlib.sha256(M.read_bytes()).hexdigest(),'native_raw_sha256':hashlib.sha256(pathlib.Path(p3.native.__file__).read_bytes()).hexdigest(),'p3_canonical_wire_sha256':hashlib.sha256(wire).hexdigest()};(OUT/'actual_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
