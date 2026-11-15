"""Frozen-opportunity intervention through the existing J2 engine, no refit."""
import argparse
import copy
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import time
import numpy as np
from v2.nba_joint import simulate, audit
from v2.nba_joint.common import sha, STATS
from v2.nba_joint.forecast import freeze
from v2.nba_opportunity import capped_allocation, lineup_segments
from research.nba_joint_v01.data import box
from research.nba_joint_v01.evaluate import distribution_metrics, summarize, paired_ci
from research.nba_joint_v01.run import gzfreeze
from .roster import build_roster_contract

BASE=Path('research/nba_joint_v01/results')

def load(path):
    raw=Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if str(path).endswith('.gz') else raw)


def mean_metrics(rows):
    if not rows:return {'n':0,'status':'BLOCKED-BY-DATA'}
    return {**summarize(rows),'predicted_mean':float(np.mean([r['mean'] for r in rows])),
        'observed_mean':float(np.mean([r['actual'] for r in rows]))}


def project(raw,duration,indices,*,mask=None,reserve_per48=0):
    raw=np.asarray(raw);minutes=np.zeros_like(raw)
    for j,length in enumerate(duration):
        for ix in indices:
            active=np.ones(len(ix),dtype=bool) if mask is None else np.asarray(mask)[ix]
            if active.sum()<5:raise ValueError('ORACLE_FEWER_THAN_FIVE_SUPPORTED_PARTICIPANTS')
            caps=active.astype(float)*length
            lower=np.where(active,np.finfo(float).eps*length,0.)
            target=(5-reserve_per48/48)*length
            minutes[j,ix]=lower+capped_allocation(raw[j,ix]-lower,caps-lower,target-lower.sum())
            if reserve_per48==0:lineup_segments(minutes[j,ix],length)
    return minutes


def require_complete_oracle(game,actual):
    supported={(p['player_id'],p['team_id']) for p in game['players']}
    missing=[(p['player_id'],p['team']) for p in actual.values() if (p['player_id'],p['team']) not in supported]
    if missing:raise ValueError('ORACLE_MISSING_PARTICIPANT_LAW:'+json.dumps(sorted(missing)))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False);(out/'scenarios').mkdir()
    t=time.perf_counter();cpu=time.process_time()
    reproduction=load('work/phase6_baseline/reproduction_check.json')
    if reproduction['status']!='PASSED' or not reproduction['score_bytes_identical']:raise ValueError('BASELINE_NOT_REPRODUCED')
    model=load(BASE/'model.json');manifest=load(BASE/'input_manifest.json');frozen_scores=load(BASE/'scores.json.gz')
    if sha(model)!='e424c7f98bba50315dfde81a60978855d6ceb8c72aba8ad0af310eb31283326f':raise ValueError('MODEL_CHANGED')
    ledgers=[r for r in load(BASE/'denominator_ledger.json') if r['split']=='test']
    counts=[];minutes=[];candidates=[];integrity=[];source_blocks=[];team_diagnostics=[];oracle_blocks=[]
    for ledger in ledgers:
        gid=ledger['game_id'];game=load(BASE/'inputs'/(gid+'.json'));prior=load(BASE/'scenarios'/(gid+'.json.gz'))
        obs=box('work/joint_input/raw/'+gid+'.json');actual={p['player_id']:p for p in obs['players'] if p['minutes']>0}
        raw=np.asarray(prior['independent_minutes']);duration=np.asarray(prior['state']['duration']);ix=prior['team_indices']
        # A is rerun after the optional diagnostic hook and must remain identical.
        A=simulate(game,model,n=128,seed=20261115)
        if A['output_sha256']!=prior['output_sha256']:raise ValueError('DEFAULT_ENGINE_REGRESSION:'+gid)
        oracle=copy.deepcopy(game);mask=np.array([p['player_id'] in actual and actual[p['player_id']]['team']==p['team_id'] for p in game['players']])
        oracle['research_conditioning']='POSTGAME_APPEARANCE_ORACLE_NEVER_PREGAME'
        for i,p in enumerate(oracle['players']):
            if not mask[i]:p['eligible']=False
        C_raw=np.where(mask[None,:],raw,0.)
        C=None
        try:
            require_complete_oracle(game,actual)
            C_m=project(C_raw,duration,ix,mask=mask)
        except ValueError as exc:
            oracle_blocks.append(dict(game_id=gid,status='BLOCKED-BY-DATA',reason=str(exc),matched_appearances=int(mask.sum()),
                supported_participants_by_team={t:int(mask[tix].sum()) for t,tix in zip(game['teams'],ix)},attempted_scenarios=128,completed_scenarios=0))
        else:
            C=simulate(oracle,model,n=128,seed=20261115,research_minutes=dict(kind='postgame_appearance_oracle',minutes=C_m,raw_minutes=C_raw,parent_input_sha256=sha(oracle)))
        D=simulate(game,model,n=128,seed=20261115,research_minutes=dict(kind='raw_m0_diagnostic',minutes=raw,raw_minutes=raw,parent_input_sha256=sha(game)))
        outputs={'A':A,'D_RAW':D}
        if C is not None:outputs['C_ORACLE']=C
        partial={'E_POOL_24':project(raw,duration,ix,reserve_per48=24),'E_POOL_48':project(raw,duration,ix,reserve_per48=48)}
        pool_payload={label:dict(known_minutes=mat,unresolved_pool_by_team=np.tile((reserve*duration/48)[:,None],(1,2)),
            identities_assigned=False,lineup_witness=None,event_forecast_status='ABSTAIN_UNRESOLVED_LINEUP',scenario_ids=prior['scenario_ids']) for label,mat,reserve in
            [('E_POOL_24',partial['E_POOL_24'],24),('E_POOL_48',partial['E_POOL_48'],48)]}
        gzfreeze(out/'scenarios'/(gid+'_E_partial_pools.json.gz'),pool_payload)
        for label,o in outputs.items():
            if sha(o['model'])!=sha(model):raise ValueError('EVENT_OR_M0_MODEL_CHANGED')
            np.testing.assert_array_equal(o['state']['duration'],duration)
            if label=='C_ORACLE':np.testing.assert_array_equal(o['independent_minutes'][:,mask],raw[:,mask])
            if label in ('A','C_ORACLE'):audit(o)
            # Persist full events/witnesses for independent arithmetic inspection.
            gzfreeze(out/'scenarios'/(gid+'_'+label+'.json.gz'),o)
            integrity.append(dict(game_id=gid,model=label,input_sha256=o['input_sha256'],output_sha256=o['output_sha256'],
                model_sha256=o['model_sha256'],raw_minutes_sha256=sha(o['independent_minutes'].tolist()),
                event_parameters_sha256=sha(o['model']['events']),opportunity_policy=o.get('research_opportunity','frozen_default'),
                event_rejection_count=o['completed_game_conditioning']['rejected_event_draws']))
            for tix in ix:
                residual=o['minutes'][:,tix].sum(axis=1)-5*duration
                team_diagnostics.append(dict(game_id=gid,model=label,team=game['players'][tix[0]]['team_id'],
                    team_minute_max_abs_error=float(np.abs(residual).max()),team_minute_mae=float(np.abs(residual).mean()),
                    raw_team_minutes_mean=float(raw[:,tix].sum(axis=1).mean()),allocated_team_minutes_mean=float(o['minutes'][:,tix].sum(axis=1).mean()),
                    predicted_duration_mean=float(duration.mean()),observed_overtime=obs['period']>4,
                    overtime_scenarios=int(np.sum(duration>48)),lineup_witnesses=len(o['lineup_segments']) if label!='D_RAW' else 0,
                    interpretation='unconstrained exposure diagnostic; full rotation invalid' if label=='D_RAW' else 'valid five-player witness'))
        raw_box=load('work/joint_input/raw/'+gid+'.json');explicit_dnp=set();listed=set()
        for group in raw_box['boxscore']['players']:
            for cat in group['statistics']:
                for entry in cat['athletes']:
                    key=(str(entry['athlete']['id']),group['team']['abbreviation']);listed.add(key)
                    if entry.get('didNotPlay') is True:explicit_dnp.add(key)
        for i,p in enumerate(game['players']):
            correct=bool(mask[i]);settled=actual.get(p['player_id']);explicit=(p['player_id'],p['team_id']) in explicit_dnp
            candidate=dict(game_id=gid,date=game['game_date'],player_id=p['player_id'],team_id=p['team_id'],candidate_status='accepted_conditional',
                eligibility_pregame=None,availability_pregame='unknown',participation_probability=None,known_inactive_pregame=None,
                realized_appearance=correct,realized_explicit_dnp=explicit,postgame_box_listed=(p['player_id'],p['team_id']) in listed,
                absent_from_postgame_participant_set=not correct,oracle_retained=correct,source_certified_B=False,
                A_raw_mean=float(raw[:,i].mean()),A_allocated_mean=float(A['minutes'][:,i].mean()),
                C_oracle_mean=float(C['minutes'][:,i].mean()) if C is not None else None,C_oracle_game_abstained=C is None,D_raw_mean=float(D['minutes'][:,i].mean()))
            candidates.append(candidate)
            source_blocks.append(dict(game_id=gid,player_id=p['player_id'],team_id=p['team_id'],arm='B',status='BLOCKED-BY-DATA',
                reasons=['ORIGINAL_GAME_DAY_ELIGIBILITY_RECEIPT_UNAVAILABLE','PARTICIPATION_METHOD_UNAVAILABLE'],forecast_accepted=False))
            if not correct:continue
            y=settled['stats'];values={**y,'pr':y['points']+y['rebounds'],'pa':y['points']+y['assists'],'ra':y['rebounds']+y['assists'],'pra':y['points']+y['rebounds']+y['assists']}
            meta=dict(game_id=gid,date=game['game_date'],player_id=p['player_id'],team_id=p['team_id'],split='development_diagnostic',
                pregame_source_qualified=False,oracle=False)
            for label,o in outputs.items():
                for stat in STATS:
                    counts.append({**meta,'model':label,'oracle':label=='C_ORACLE','stat':stat,'actual':values[stat],**distribution_metrics(o['stats'][stat][:,i],values[stat])})
            for label,mat in [('RAW_M0',raw)]+[(k,o['minutes']) for k,o in outputs.items()]+list(partial.items()):
                r={**meta,'model':label,'oracle':label=='C_ORACLE','stat':'minutes','actual':settled['minutes'],**distribution_metrics(mat[:,i],settled['minutes']),
                    'raw_mean':float(raw[:,i].mean()),'raw_variance':float(raw[:,i].var()),'allocation_mean_shift':float(mat[:,i].mean()-raw[:,i].mean()),
                    'allocation_variance_shift':float(mat[:,i].var()-raw[:,i].var()),'actual_ot':obs['period']>4,
                    'low_outcome':settled['minutes']<=5,'early_exit_proxy':settled['minutes']<=5 and p['minute_features']['median5']>=25,
                    'low_prior':p['minute_features']['median5']<14,'incomplete_pool':label.startswith('E_')}
                minutes.append(r)
        for p in ledger['rejected_candidates']:
            candidates.append(dict(game_id=gid,date=game['game_date'],player_id=p['player_id'],team_id=p['team'],candidate_status='rejected',
                reason=p['reason'],eligibility_pregame=None,known_inactive_pregame=None,realized_appearance=p['player_id'] in actual and actual[p['player_id']]['team']==p['team']))
        for pid in ledger['unforecasted_appearances']:
            candidates.append(dict(game_id=gid,date=game['game_date'],player_id=pid,team_id=actual[pid]['team'],candidate_status='missed_actual_appearance',
                reason='NO_SUPPORTED_PRIOR_FORECAST',eligibility_pregame=None,known_inactive_pregame=None,realized_appearance=True))
        print(gid,'matched',int(mask.sum()),'DNP_or_nonappearance',int((~mask).sum()),flush=True)
    # Original controls are retained, not regenerated or renamed into new arms.
    for r in frozen_scores:
        if r['split']=='test' and r['model'] in ('J0','J1','J2'):
            counts.append({**r,'split':'development_diagnostic','pregame_source_qualified':False,'oracle':False})
    stat_summary={label:{stat:mean_metrics([r for r in counts if r['model']==label and r['stat']==stat]) for stat in STATS} for label in ('J0','J1','J2','A','C_ORACLE','D_RAW')}
    common={(r['game_id'],r['player_id']) for r in counts if r['model']=='C_ORACLE'}
    common_stat_summary={label:{stat:mean_metrics([r for r in counts if r['model']==label and r['stat']==stat and (r['game_id'],r['player_id']) in common]) for stat in STATS} for label in stat_summary}
    minute_summary={label:{name:mean_metrics([r for r in minutes if r['model']==label and (name=='all' or r[name])]) for name in ('all','low_outcome','early_exit_proxy','actual_ot','low_prior')} for label in ('RAW_M0','A','C_ORACLE','D_RAW','E_POOL_24','E_POOL_48')}
    common_minute_summary={label:mean_metrics([r for r in minutes if r['model']==label and (r['game_id'],r['player_id']) in common]) for label in minute_summary}
    comparisons={label:{stat:paired_ci([r for r in counts if r['stat']==stat],'A',label) for stat in STATS} for label in ('C_ORACLE','D_RAW','J0','J1')}
    minute_pairs={label:paired_ci(minutes,'RAW_M0',label) for label in ('A','C_ORACLE','D_RAW','E_POOL_24','E_POOL_48')}
    accepted=[r for r in candidates if r['candidate_status']=='accepted_conditional']
    denominator=dict(original_attempts=sum(r['attempted_candidates'] for r in ledgers),conditional_candidates=len(accepted),
        original_rejected_candidates=sum(len(r['rejected_candidates']) for r in ledgers),
        observed_appearances=sum(r['observed_appearances'] for r in ledgers),matched_appearances=sum(r['matched_appearances'] for r in ledgers),
        missed_actual_appearances=sum(len(r['unforecasted_appearances']) for r in ledgers),
        candidates_without_appearance=sum(len(r['roster_without_observed_appearance']) for r in ledgers),
        candidates_without_correct_team_appearance=sum(not r['realized_appearance'] for r in accepted),
        postgame_explicit_dnp_candidates=sum(r['realized_explicit_dnp'] for r in accepted),
        nonappearance_without_explicit_dnp=sum(not r['realized_appearance'] and not r['realized_explicit_dnp'] for r in accepted),
        team_identity_rejections=sum(len(r['team_identity_rejections']) for r in ledgers),known_inactive_pregame=None,
        known_inactive_status='UNMEASURED_NO_ORIGINAL_AVAILABILITY_RECEIPTS',unknown_eligibility=len(accepted),
        primary_source_qualified_matched=0,B_accepted=0,B_abstained=len(accepted),C_oracle_participants_scored=len(common),C_oracle_matched_abstentions=460-len(common),C_oracle_game_abstentions=len(oracle_blocks),
        C_oracle_masked=sum(not r['realized_appearance'] for r in accepted),E_full_game_forecasts_accepted=0,E_full_game_forecasts_abstained=len(accepted),
        source_certified_forecasts_all_arms=0,warning='Oracle masked nonappearances are not source-certified inactives. Rejected and missed ledgers overlap and must not be added as independent candidates.')
    if denominator['matched_appearances']!=460 or len(ledgers)!=24:raise ValueError('COHORT_CHANGED')
    # Exact baseline checkpoints, before interpreting interventions.
    checks={'matched':460,'dates':24,'raw_minutes_crps':minute_summary['RAW_M0']['all']['crps'],'allocated_minutes_crps':minute_summary['A']['all']['crps'],
        'allocated_mean':minute_summary['A']['all']['predicted_mean'],'observed_mean':minute_summary['A']['all']['observed_mean'],
        'J2_points_crps':stat_summary['A']['points']['crps'],'J0_points_crps':stat_summary['J0']['points']['crps'],
        'J2_PRA_crps':stat_summary['A']['pra']['crps'],'J0_PRA_crps':stat_summary['J0']['pra']['crps']}
    for k,v in {'raw_minutes_crps':4.061672,'allocated_minutes_crps':5.625994,'allocated_mean':17.989736,'observed_mean':23.710870,'J2_points_crps':3.993858,'J0_points_crps':3.707883,'J2_PRA_crps':5.462042,'J0_PRA_crps':4.840735}.items():
        if abs(checks[k]-v)>1e-6:raise ValueError('BASELINE_CHECKPOINT:'+k)
    summary=dict(schema='NBAPhase6Ablation/1.0.0',baseline_checks=checks,source_qualified_primary_n=0,development_matched_n=460,
        five_way_status={'A':'REPRODUCED_RESEARCH_ONLY','B':'BLOCKED-BY-DATA','C_ORACLE':'POSTGAME_DIAGNOSTIC_ONLY','D_RAW':'UNCONSTRAINED_DIAGNOSTIC_ONLY','E':'PARTIAL_POOL_SENSITIVITY_FULL_FORECAST_BLOCKED'},
        count_metrics=stat_summary,common_count_metrics=common_stat_summary,common_matched_n=len(common),minute_metrics=minute_summary,common_minute_metrics=common_minute_summary,count_paired_vs_A=comparisons,minute_paired_vs_raw=minute_pairs,denominators=denominator,
        common_random_numbers='Identical state and original A raw M0 arrays; same keyed event streams. Multinomial weights/rejections can change variate consumption. Not exact event-draw coupling.',
        E_interpretation='24/48 aggregate unresolved player-minute assumptions per regulation; known partial sums plus pool conserve. No full lineup or event probabilities. Broad-roster sensitivity is not a certified eligible roster.',
        recommendation='Keep J2 rejected for adoption; classify repair and event residuals using matched exposed diagnostics, obtain original prospective sources before new model investment.')
    gzfreeze(out/'count_scores.json.gz',counts);gzfreeze(out/'minute_scores.json.gz',minutes);gzfreeze(out/'candidate_ledger.json.gz',candidates)
    freeze(out/'summary.json',summary);freeze(out/'scenario_hashes.json',integrity);freeze(out/'team_diagnostics.json',team_diagnostics)
    freeze(out/'source_B_abstentions.json',source_blocks);freeze(out/'original_denominators.json',ledgers);freeze(out/'baseline_reproduction.json',reproduction)
    freeze(out/'C_oracle_abstentions.json',oracle_blocks)
    freeze(out/'retained_roster_contract.json',build_roster_contract('research/nba_joint_v01/prospective_canary',model))
    probe=Path('research/nba_phase6/current_source_probe/capture_receipt.json')
    if probe.exists() and load(probe).get('snapshot_path'):
        freeze(out/'current_roster_contract.json',build_roster_contract(probe.parent,model))
    receipt=dict(generated_at=datetime.now(timezone.utc).isoformat(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        model_sha256=sha(model),events_sha256=sha(model['events']),minutes_model_sha256=sha(model['minutes']),protocol_sha256=hashlib.sha256(Path('research/nba_phase6/PROTOCOL.md').read_bytes()).hexdigest(),
        wall_seconds=time.perf_counter()-t,cpu_seconds=time.process_time()-cpu,peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        source_hashes={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(Path('v2/nba_joint').glob('*.py'))},
        research_source_hashes={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(Path('research/nba_phase6').glob('*.py'))},
        artifacts={str(path.relative_to(out)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(out.rglob('*')) if path.is_file()},
        promotion=False,independent_review='PENDING; author-run evidence and upstream WS4 checks are not independent statistical approval')
    freeze(out/'run_receipt.json',receipt);print(json.dumps({k:receipt[k] for k in ('wall_seconds','cpu_seconds','peak_rss_mib')}))

if __name__=='__main__':main()
