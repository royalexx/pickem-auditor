"""Execute finite scoped P1 acceptance on actual frozen source bytes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from v2.nba_architecture.p1_subset_handoff_v1 import export_requests,canonical,conditional_requests
from v2.nba_architecture.gamebook_v1 import read_final_box
from v2.nba_architecture.gamebook_identity_v1 import join_game_ids

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent/'owner';OUT.mkdir(exist_ok=True)
COHORT_PATH=ROOT/'docs/nba_architecture/p1_prospective_20261118/COHORT.json'
cohort=json.loads(COHORT_PATH.read_bytes());rawroot=ROOT/'docs/nba_architecture/p1_overnight_20261119/raw'
ledger=[];hashes={};tested=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
for capture in sorted(rawroot.glob('pregame*')):
    export=export_requests(capture,cohort);wire=canonical(export);consumed=conditional_requests(wire,capture,cohort)
    (OUT/(capture.name+'.handoff.json')).write_bytes(wire)
    (OUT/(capture.name+'.consumer.json')).write_text(json.dumps(consumed,indent=2)+'\n')
    for name,files in export['source_file_hashes'].items():
        for f,h in files.items():
            if h:hashes[str((capture/name/f).relative_to(ROOT))]=h
    ledger.append({'interface':'source_to_requests_to_serialized_consumer','capture':capture.name,'status':'PASS','candidate_rows':consumed['candidate_denominator'],'requests':len(consumed['requests']),'abstained':consumed['source_abstentions'],'actual_forecasts':0,'model_executed':False})
post=next(rawroot.glob('morning*'));receipt=json.loads((post/'official-gamebook/receipt.json').read_bytes());receipt['retrieved_at']=receipt['retrieval_started_at']
box=read_final_box((post/'official-gamebook/body.raw').read_bytes(),receipt)
er=json.loads((post/'target-summary/receipt.json').read_bytes());er['retrieved_at']=er['retrieval_started_at'];joined=join_game_ids(box,(post/'target-summary/body.raw').read_bytes(),er)
(OUT/'postgame_box.json').write_text(json.dumps(box,indent=2)+'\n');(OUT/'postgame_identities.json').write_text(json.dumps(joined,indent=2)+'\n')
for name in ['official-gamebook','target-summary']:
    for f in ['body.raw','receipt.json']:p=post/name/f;hashes[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
by_id={row['player_id']:box['rows'][i] for i,row in enumerate(joined['rows'])}
all_candidates=export['requests']['rows']
resolved=[dict(player_id=r['player_id'],team_id=r['team_id'],name=r['name'],
    participation=by_id[r['player_id']]['state'] if r['player_id'] in by_id else 'UNKNOWN_NOT_LISTED',
    exact_seconds=by_id[r['player_id']]['exact_seconds'] if r['player_id'] in by_id else None,
    legal_eligibility=None,genuine_participation_probability=None) for r in all_candidates]
(OUT/'all_candidate_postgame_states.json').write_text(json.dumps(resolved,indent=2)+'\n')
ledger.append({'interface':'all_candidate_postgame_reconstruction','status':'PASS_BOUNDED_RECONSTRUCTION',
    'candidate_rows':len(resolved),'played':sum(r['participation']=='PLAYED' for r in resolved),
    'dnp':sum(r['participation']=='DNP' for r in resolved),'unknown':sum(r['participation']=='UNKNOWN_NOT_LISTED' for r in resolved)})
ledger.append({'interface':'native_postgame_printed_content_identity_exposure','status':'PASS_BOUNDED_RECONSTRUCTION','listed_rows':len(box['rows']),'played':sum(r['state']=='PLAYED' for r in box['rows']),'dnp':sum(r['state']=='DNP' for r in box['rows']),'duration':box['duration_minutes'],'legal_eligibility_inferred':False})
for name in ['actual_S_O_J_model_inference','actual_model_consumer_integration','C_scoring_or_settlement_admission','tonight_live_default_producer_execution']:
    ledger.append({'interface':name,'status':'NOT_EXERCISED','reason':'No supplied model/scoring run; future execution separate from retrospective source engineering'})
receipt={'tested_sha':tested,'authority':'PA-V25-MASTER-2026-11-09 / v1.1 + Nov19 user subset amendment','profile':'source_listed_subset','observed_games':1,'original_frozen_forecasts_generated_here':0,'interface_ledger':ledger,'input_hashes_exact_file_bytes':hashes,'source_snapshot_not_prospective_validation':True,'commands':[]}
for label,cmd in [('public',[sys.executable,'-m','unittest','tests.nba_architecture.test_research_profile_v1','tests.nba_architecture.test_p1_subset_handoff_v1','-v']),('architecture',[sys.executable,'-m','unittest','discover','-s','tests/nba_architecture','-v'])]:
    r=subprocess.run(cmd,cwd=ROOT,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONPATH':'.:tests/nba_architecture'},capture_output=True);(OUT/(label+'.stdout')).write_bytes(r.stdout);(OUT/(label+'.stderr')).write_bytes(r.stderr);receipt['commands'].append({'argv':cmd,'exit':r.returncode,'stdout':label+'.stdout','stderr':label+'.stderr'});print(label,r.returncode,flush=True)
(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(ledger,indent=2))
