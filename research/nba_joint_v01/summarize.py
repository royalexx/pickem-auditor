"""Detailed audit tables from immutable simulation artifacts; no refitting."""
from collections import Counter,defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import platform
import sys
import numpy as np
import scipy
from .evaluate import paired_ci,summarize
from v2.nba_joint.forecast import freeze


def main():
    root=Path('research/nba_joint_v01/results')
    read=lambda name:json.loads((root/name).read_text())
    unpack=lambda name:json.loads(gzip.decompress((root/name).read_bytes()))
    scores=unpack('scores.json.gz');minutes=unpack('minute_scores.json.gz');markets=unpack('original_market_diagnostic.json.gz')
    ledger=read('denominator_ledger.json');result=read('results.json');states=read('state_diagnostics.json');distortion=read('opportunity_distortion.json')
    summary={'environment':{'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,'platform':platform.platform()},'denominators':{},'minutes':{},'states':{},'original_contracts':{},'conditional_event_audit':{},'limitations':[]}
    for split in ('test','original'):
        x=[r for r in ledger if r['split']==split]
        summary['denominators'][split]={k:sum(r[k] for r in x) for k in ('attempted_candidates','accepted_conditional_candidates','observed_appearances','matched_appearances','scored_player_games')}
        summary['denominators'][split].update(candidate_rejections=sum(len(r['rejected_candidates']) for r in x),prior_candidates_without_observed_appearance=sum(len(r['roster_without_observed_appearance']) for r in x),unforecasted_appearances=sum(len(r['unforecasted_appearances']) for r in x),team_identity_rejections=sum(len(r['team_identity_rejections']) for r in x))
        summary['minutes'][split]={}
        for label in ('J2','J2_M1','J2_M2'):
            x=[r for r in minutes if r['split']==split and r['model']==label]
            summary['minutes'][split][label]={'n':len(x),'raw_crps':float(np.mean([r['raw_crps'] for r in x])),'allocated_crps':float(np.mean([r['crps'] for r in x])),
                'predicted_minutes':float(np.mean([r['mean'] for r in x])),'observed_minutes':float(np.mean([r['actual'] for r in x])),
                'cover90':float(np.mean([r['cover90'] for r in x])),
                'low_minute_outcomes_le5':{'n':sum(r['actual']<=5 for r in x),'cover90':float(np.mean([r['cover90'] for r in x if r['actual']<=5])) if any(r['actual']<=5 for r in x) else None},
                'projection_mean_absolute_change':float(np.mean([r['mean_absolute_minute_change'] for r in distortion if r['model']==('M0' if label=='J2' else label[3:])]))}
        x=[r for r in states if r['split']==split]
        summary['states'][split]={'games':len(x),'observed_regulation_proxy_mean':float(np.mean([r['observed_proxy'] for r in x])),'observed_regulation_proxy_variance':float(np.var([r['observed_proxy'] for r in x])),
            'G0_proxy_mae':float(np.mean([abs(r['G0_mean']-r['observed_proxy']) for r in x])),'G1_proxy_mae':float(np.mean([abs(r['G1_mean']-r['observed_proxy']) for r in x])),
            'G1_mean_predicted_proxy_variance':float(np.mean([r['G1_variance'] for r in x])),'observed_ot_games':sum(r['overtime_actual'] for r in x),
            'G1_mean_ot_probability':float(np.mean([r['overtime_probability'] for r in x])),
            'G0_team_points_mae':float(np.mean([abs(a-b) for r in x for a,b in zip(r['observed_team_points'],r['G0_predicted_team_points'])])),
            'G1_team_points_mae':float(np.mean([abs(a-b) for r in x for a,b in zip(r['observed_team_points'],r['predicted_team_points'])]))}
    for model in ('Engine_A','Engine_B','Bayesian_A','Bayesian_B','NUTS','Consensus','Market','first_book_market','naive_recent_exposure_rate','pooled_peer_shrunk_rate'):
        x=[r for r in markets if r.get('J2_conditional_nonpush') is not None and r['models'].get(model,{}).get('p') is not None]
        if not x:summary['original_contracts'][model]={'n':0,'reason':'NO_ORIGINAL_FORECAST_AVAILABLE'};continue
        p=np.array([r['models'][model]['p'] for r in x]);q=np.array([r['J2_conditional_nonpush']['p'] for r in x]);y=np.array([r['outcome']=='over' for r in x],dtype=int)
        def metrics(p):
            losses=np.where(y,p,1-p)
            return dict(brier=float(np.mean((p-y)**2)),log_loss=None if np.any(losses<=0) else float(-np.log(losses).mean()),zero_likelihood_events=int(np.sum(losses<=0)),signed_over_residual=float(np.mean(p-y)),over_selected_fraction=float(np.mean(p>=.5)),
                side_conditional={side:{'n':int(mask.sum()),'predicted_over':float(p[mask].mean()) if mask.any() else None,'observed_over':float(y[mask].mean()) if mask.any() else None} for side,mask in [('over_selected',p>=.5),('under_selected',p<.5)]})
        summary['original_contracts'][model]=dict(n=len(x),games=len({r['game_id'] for r in x}),dates=1,original=metrics(p),J2_counterfactual=metrics(q),inference='one exposed date; no release-grade interval or market-edge claim')
    summary['original_contract_denominator']=dict(attempted=len(markets),counterfactual_distributions_available=sum(r['abstention'] is None for r in markets),rejected=Counter(r['abstention'] for r in markets if r['abstention']),pushes=sum(r['outcome']=='push' for r in markets),voids='not reconstructed; no DNP participation law',source_new_quotes=0)
    event_rejections=0;attempts=0;shifts=defaultdict(list);ties=0;players=0
    for path in sorted((root/'scenarios').glob('*.gz')):
        o=json.loads(gzip.decompress(path.read_bytes()));c=o['completed_game_conditioning'];event_rejections+=c['rejected_event_draws'];attempts+=c['event_attempts'];players+=o['n']*len(o['players'])
        for k,v in c['mean_absolute_marginal_change'].items():shifts[k].append(v)
        p=np.array(o['stats']['points']);ix=o['team_indices'];ties+=int(np.sum(p[:,ix[0]].sum(axis=1)==p[:,ix[1]].sum(axis=1)))
    summary['conditional_event_audit']=dict(accepted_game_scenarios=29*128,player_scenarios=players,event_attempts=attempts,rejected_event_draws=event_rejections,final_tied_scores=ties,mean_game_average_absolute_count_shift={k:float(np.mean(v)) for k,v in shifts.items()},interpretation='explicit rejection conditioning, not posthoc score adjustment; all rejected event vectors preserved')
    feature_map={}
    for path in (root/'inputs').glob('*.json'):
        game=json.loads(path.read_text())
        for player in game['players']:feature_map[game['game_id'],player['player_id']]=player['minute_features']
    state_map={r['game_id']:r for r in states};stress={}
    for label in ('J2','J2_M1','J2_M2'):
        rr=[r for r in minutes if r['model']==label and r['split']=='test']
        cohorts={'all':rr,'low_minute_outcome_le5':[r for r in rr if r['actual']<=5],
            'early_exit_outcome_proxy':[r for r in rr if r['actual']<10 and feature_map[r['game_id'],r['player_id']]['mean10']>=28],
            'low_historical_minutes':[r for r in rr if feature_map[r['game_id'],r['player_id']]['mean10']<14],
            'return_gap_ge2':[r for r in rr if feature_map[r['game_id'],r['player_id']]['return_gap']>=2],
            'role_change_proxy':[r for r in rr if abs(feature_map[r['game_id'],r['player_id']]['trend'])>=5 or feature_map[r['game_id'],r['player_id']]['team_change']],
            'observed_overtime':[r for r in rr if state_map[r['game_id']]['overtime_actual']]}
        stress[label]={k:summarize(v) if v else {'n':0,'status':'BLOCKED-BY-DATA'} for k,v in cohorts.items()}
    freeze(root/'stress_diagnostics.json',stress)
    if (root/'deepnote_receipt.json').exists() and (root/'local_fixture_receipt.json').exists():
        deep=read('deepnote_receipt.json');local=read('local_fixture_receipt.json')
        summary['cross_runtime_reproducibility']=dict(integer_event_count_hash_identical=deep['fixture']['counts_sha256']==local['counts_sha256'],counts_sha256=local['counts_sha256'],
            full_float_hash_identical=deep['fixture']['scenario_sha256']==local['scenario_sha256'],local_full_hash=local['scenario_sha256'],deepnote_full_hash=deep['fixture']['scenario_sha256'])
    summary['limitations']=['No authenticated participation law; prior-roster union is not a real eligible roster.','Previously exposed retrospective observations and post-result engineering amendments; not a blind holdout.','128 scenarios are insufficient for reliable unsmoothed empirical NLPD: zero sampled masses are reported as infinite, with no invented smoothing.','Empirical overtime duration is shared, but the within-game regulation tie and OT score paths are not modeled.','Five-on-court witnesses prove integrated feasibility, not learned real rotations or event-time lineup matching.','Opponent/team possession quantity is a reconstructed proxy, not an exact event accounting identity.','New WS4 compatibility code is author-written; external independent joint acceptance is pending.']
    freeze(root/'audit_summary.json',summary)
    print(json.dumps({'summary':str(root/'audit_summary.json'),'final_tied_scores':ties,'rejected_event_draws':event_rejections}))


if __name__=='__main__':main()
