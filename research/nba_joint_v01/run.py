"""Execute the preregistered bounded experiment and immutable research evidence."""
import argparse
from collections import defaultdict
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import time
import numpy as np
from scipy.spatial.distance import pdist
from v2.nba_joint import simulate,synthetic_fixture,audit,extract_forecast,freeze
from v2.nba_joint.common import sha,canonical,STATS
from v2.nba_joint.sources import canary
from .data import fit_model,reconstruct
from .prepare import population
from .controls import marginals,independent_permutation
from .evaluate import distribution_metrics,summarize,energy,variogram,paired_ci,VERSION


def serialize(obj):
    if isinstance(obj,np.ndarray):return obj.tolist()
    if isinstance(obj,np.generic):return obj.item()
    raise TypeError(type(obj).__name__)


def gzfreeze(path,obj):
    raw=json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False,default=serialize).encode()
    # Deterministic gzip; exclusive creation protects every run.
    with Path(path).open('xb') as f:f.write(gzip.compress(raw,mtime=0))
    return hashlib.sha256(raw).hexdigest()


def engineering():
    results=[];bench=[]
    for index,n in enumerate((128,512,2048)):
        game,model=synthetic_fixture()
        # Stress OT and a low-cap participant without pretending fitted exit risk.
        model['state']['ot_probability']=.6;game['players'][0]['scenario_exit_cap']=3.
        t=time.process_time();out=simulate(game,model,n=n,seed=20261115+index);cpu=time.process_time()-t
        a=audit(out);raw=out['independent_minutes'];m=out['minutes']
        total_errors=np.concatenate([np.abs(raw[:,ix].sum(axis=1)-5*out['state']['duration']) for ix in out['team_indices']])
        f=extract_forecast(out,1,'pra',line=40.5)
        tail=extract_forecast(out,1,'points',line=60.5)
        results.append(dict(n=n,seed=out['seed'],audit=a,input_sha256=out['input_sha256'],output_sha256=out['output_sha256'],
            overtime_scenarios=int(np.sum(out['state']['overtime']>0)),max_ot=int(out['state']['overtime'].max()),
            independent_team_minutes_mae=float(total_errors.mean()),allocated_team_minutes_max_abs_error=float(max(np.abs(m[:,ix].sum(axis=1)-5*out['state']['duration']).max() for ix in out['team_indices'])),
            marginal_projection_mean_absolute_change=float(np.abs(m-raw).mean()),combo_probability=f['probabilities'],combo_mc=f['monte_carlo'],rare_tail_probability=tail['probabilities'],rare_tail_mc=tail['monte_carlo']))
        bench.append(dict(n=n,cpu_seconds=cpu,**out['timing'],scenarios_per_second=n/out['timing']['wall_seconds'],array_bytes=sum(v.nbytes for v in out['stats'].values())+m.nbytes+raw.nbytes,peak_process_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024))
    return results,bench


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--scenarios',type=int,default=128);p.add_argument('--generated-at');a=p.parse_args()
    dest=Path(a.output);dest.mkdir(parents=True,exist_ok=False);(dest/'scenarios').mkdir();(dest/'inputs').mkdir()
    started=time.perf_counter();cpu=time.process_time();generated=a.generated_at or datetime.now(timezone.utc).isoformat()
    manifest=json.loads(Path('work/joint_input/manifest.json').read_text());rows,pop_exclusions=population('work/joint_input');model=fit_model(manifest['raw'],rows)
    freeze(dest/'experiment.json',json.loads(Path('research/nba_joint_v01/experiment.json').read_text()));freeze(dest/'input_manifest.json',manifest);freeze(dest/'model.json',model)
    e1,bench=engineering();freeze(dest/'engineering.json',e1);freeze(dest/'benchmarks.json',bench)
    score_rows=[];joint_rows=[];ledgers=[];distortion=[];states=[];hashes=[];market_rows=[];team_scores=[];dependence=[];minute_scores=[]
    ws4=json.loads(Path('work/ws4_original_replay.json').read_text())
    official={h:Path(path).name.split('_')[1] for path,h in ws4['source_hashes'].items() if '/official_source_raw/nba_' in path and 'boxscore' in path}
    for target in [r for r in manifest['raw'] if r['split']!='train']:
        if 'error' in target:
            ledgers.append({**target,'status':'BLOCKED_SOURCE'});continue
        game,actual,observed,ledger=reconstruct(target,rows,model,generated);ledger['split']=target['split'];ledgers.append(ledger)
        if any(sum(p['team_id']==t for p in game['players'])<5 for t in game['teams']):
            ledger['status']='BLOCKED_FEWER_THAN_FIVE_CANDIDATES';continue
        freeze(dest/'inputs'/(game['game_id']+'.json'),game)
        outputs={};ensembles={};ensemble_start=time.perf_counter()
        ensembles['F0']=marginals(game,model,a.scenarios,20261115,empirical=True)
        ensembles['J0']=marginals(game,model,a.scenarios,20261115)
        for dep,name in [('J1','M0'),('J2','M0'),('J2','M1'),('J2','M2')]:
            label=dep if name=='M0' else dep+'_'+name
            try:
                o=simulate(game,model,n=a.scenarios,seed=20261115,dependence=dep,exposure=name)
            except ValueError as exc:
                freeze(dest/('failed_'+game['game_id']+'_'+label+'.json'),dict(reason=str(exc),input_sha256=sha(game),model_sha256=sha(model),attempted=a.scenarios,certified=0))
                raise
            outputs[label]=o;ensembles[label]=o['stats'];hashes.append(dict(game_id=game['game_id'],model=label,input_sha256=o['input_sha256'],output_sha256=o['output_sha256'],timing=o['timing']))
            if dep=='J2':
                distortion.append(dict(game_id=game['game_id'],date=game['game_date'],model=name,mean_absolute_minute_change=float(np.abs(o['minutes']-o['independent_minutes']).mean()),
                    player_mean_shift=(o['minutes'].mean(axis=0)-o['independent_minutes'].mean(axis=0)).tolist(),
                    player_variance_shift=(o['minutes'].var(axis=0)-o['independent_minutes'].var(axis=0)).tolist()))
        ensembles['J0_shuffle']=independent_permutation(ensembles['J2'],game['game_id'],20261115)
        o=outputs['J2'];gzfreeze(dest/'scenarios'/(game['game_id']+'.json.gz'),o)
        forecasts=[extract_forecast(o,i,k) for i in range(len(game['players'])) for k in STATS]
        gzfreeze(dest/('forecasts_'+game['game_id']+'.json.gz'),forecasts)
        matched=[(i,actual[p['player_id']]) for i,p in enumerate(game['players']) if p['player_id'] in actual and actual[p['player_id']]['team']==p['team_id']]
        ledger['scored_player_games']=len(matched)
        ledger['status']='RESEARCH_CONDITIONAL_ONLY';ledger['simulator_violations']=audit(o)['violations']
        for label,output in outputs.items():
            if label=='J1':continue
            for i,obs in matched:
                minute_scores.append(dict(model=label,game_id=game['game_id'],date=game['game_date'],split=target['split'],player_id=obs['player_id'],stat='minutes',
                    actual=obs['minutes'],raw_crps=distribution_metrics(output['independent_minutes'][:,i],obs['minutes'])['crps'],
                    **distribution_metrics(output['minutes'][:,i],obs['minutes'])))
        for label,samples in ensembles.items():
            for i,obs in matched:
                y=obs['stats'];values={**y,'pr':y['points']+y['rebounds'],'pa':y['points']+y['assists'],'ra':y['rebounds']+y['assists'],'pra':y['points']+y['rebounds']+y['assists']}
                meta=dict(model=label,game_id=game['game_id'],date=game['game_date'],player_id=obs['player_id'],split=target['split'])
                for stat in STATS:score_rows.append({**meta,'stat':stat,'actual':values[stat],**distribution_metrics(samples[stat][:,i],values[stat])})
                x=np.column_stack([samples[k][:,i] for k in STATS[:3]]);yv=[values[k] for k in STATS[:3]]
                thresholds=np.array([np.median(game['players'][i]['history_stats'][k]) for k in STATS[:3]])
                event=np.all(x>thresholds,axis=1);event_y=int(np.all(np.array(yv)>thresholds))
                joint_rows.append({**meta,'stat':'PTS_REB_AST','energy':energy(x,yv),'variogram':variogram(x,yv),'joint_event_probability':float(event.mean()),'joint_event_outcome':event_y,'joint_event_brier':float((event.mean()-event_y)**2)})
            # Prespecified top-prior-minutes pair on same team, and opponents.
            top=[]
            for team in game['teams']:
                candidates=[i for i,_ in matched if game['players'][i]['team_id']==team]
                top.append(sorted(candidates,key=lambda i:game['players'][i]['minute_features']['median5'],reverse=True)[:2])
            for kind,pair in [('teammates',top[0]),('opponents',[t[0] for t in top if t])]:
                if len(pair)!=2:continue
                x=np.column_stack([samples['points'][:,i] for i in pair]);yv=[actual[game['players'][i]['player_id']]['stats']['points'] for i in pair]
                team_scores.append(dict(model=label,game_id=game['game_id'],date=game['game_date'],player_id=kind,stat='points_pair',split=target['split'],energy=energy(x,yv),variogram=variogram(x,yv)))
            # Export within-player modeled correlations, never infer observed joint skill from sign.
            correlations=[]
            for i,_ in matched:
                x=np.column_stack([samples[k][:,i] for k in STATS[:3]])
                if np.all(x.std(axis=0)>0):correlations.append(np.corrcoef(x,rowvar=False)[np.triu_indices(3,1)].tolist())
            dependence.append(dict(model=label,game_id=game['game_id'],split=target['split'],mean_same_player_correlations=np.mean(correlations,axis=0).tolist() if correlations else None))
        # State G0/G1 diagnostic uses held-out observed proxy only as outcome.
        duration=48+5*max(0,observed['period']-4);proxy=[];points=[]
        for team in game['teams']:
            x=observed['totals'][team];proxy.append((x['two_pa']+x['three_pa']+.44*x['fta']-x['oreb']+x['tov'])*48/duration);points.append(x['points'])
        states.append(dict(game_id=game['game_id'],date=game['game_date'],split=target['split'],observed_proxy=float(np.mean(proxy)),G0_mean=model['state']['pace_mean'],G0_variance=0.,G1_mean=float(o['state']['regulation_possession_proxy'].mean()),G1_variance=float(o['state']['regulation_possession_proxy'].var()),
            overtime_actual=int(duration>48),overtime_probability=float(np.mean(o['state']['overtime']>0)),observed_team_points=points,predicted_team_points=[float(o['stats']['points'][:,ix].sum(axis=1).mean()) for ix in o['team_indices']],
            scenario_runtime=time.perf_counter()-ensemble_start))
        if target['split']=='original':
            pid_index={p['player_id']:i for i,p in enumerate(game['players'])}
            for r in ws4['records']:
                if official[r['source_hash']]!=game['game_id']:continue
                row={k:r[k] for k in ('contract_id','event_id','player_id','stat','line','period','outcome','actual')}
                row.update(game_id=game['game_id'],source_hash=r['source_hash'],original_over_hash=r['original_over_hash'],original_under_hash=r['original_under_hash'],
                    counterfactual=True,not_original_joint_forecast=True,models=r['models'])
                if r['player_id'] not in pid_index:row['abstention']='NOT_IN_PRIOR_CANDIDATES'
                elif r['stat'] not in STATS:row['abstention']='UNSUPPORTED'
                else:
                    i=pid_index[r['player_id']];f=extract_forecast(o,i,r['stat'],line=r['line']);row['joint_probabilities']=f['probabilities'];row['monte_carlo']=f['monte_carlo'];row['abstention']=None
                    if r['outcome']!='push' and f['probabilities']['push']<1:
                        pp=f['probabilities']['over']/(1-f['probabilities']['push']);y=int(r['outcome']=='over')
                        row['J2_conditional_nonpush']=dict(p=pp,brier=(pp-y)**2,log_loss=None if pp in (0,1) and pp!=y else float(-np.log(max(1e-300,pp if y else 1-pp))))
                market_rows.append(row)
        print(f"{target['split']} {game['game_id']} matched={len(matched)} candidates={len(game['players'])}",flush=True)
    summary={}
    for split in ('test','original'):
        subset=[r for r in score_rows if r['split']==split];js=[r for r in joint_rows if r['split']==split]
        metrics={label:{stat:summarize([r for r in subset if r['model']==label and r['stat']==stat]) for stat in STATS} for label in sorted({r['model'] for r in subset})}
        paired={label:{stat:paired_ci([r for r in subset if r['stat']==stat],'J0',label) for stat in STATS} for label in ('F0','J1','J2','J2_M1','J2_M2','J0_shuffle')}
        joint={label:{metric:float(np.mean([r[metric] for r in js if r['model']==label])) for metric in ('energy','variogram','joint_event_brier','joint_event_probability','joint_event_outcome')} for label in sorted({r['model'] for r in js})}
        joint_paired={label:{metric:paired_ci(js,'J0',label,metric) for metric in ('energy','variogram','joint_event_brier')} for label in ('J1','J2','J0_shuffle')}
        opportunity_ablation={label:{stat:paired_ci([r for r in subset if r['stat']==stat],'J2',label) for stat in STATS} for label in ('J2_M1','J2_M2')}
        summary[split]=dict(distribution=metrics,paired_vs_J0=paired,joint=joint,joint_paired=joint_paired,opportunity_ablation=opportunity_ablation,
            player_games=len({(r['game_id'],r['player_id']) for r in subset}),players=len({r['player_id'] for r in subset}),games=len({r['game_id'] for r in subset}),dates=len({r['date'] for r in subset}),acceptance='INCONCLUSIVE')
    gzfreeze(dest/'scores.json.gz',score_rows);gzfreeze(dest/'joint_scores.json.gz',joint_rows);gzfreeze(dest/'original_market_diagnostic.json.gz',market_rows);gzfreeze(dest/'minute_scores.json.gz',minute_scores)
    freeze(dest/'results.json',summary);freeze(dest/'denominator_ledger.json',ledgers);freeze(dest/'opportunity_distortion.json',distortion);freeze(dest/'state_diagnostics.json',states);freeze(dest/'dependence.json',dependence);freeze(dest/'team_pair_scores.json',team_scores);freeze(dest/'scenario_hashes.json',hashes)
    snapshot=next(Path('docs/nba_ws1/sample/snapshots').glob('*.json'));freeze(dest/'prospective_existing_sample.json',canary(snapshot))
    receipt=dict(schema='NBAJointExperimentRun/1',evaluator=VERSION,generated_at=generated,code_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        executed_source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('v2/nba_joint','research/nba_joint_v01') for p in sorted(Path(folder).glob('*.py'))},
        model_sha256=sha(model),scenario_count=a.scenarios,seed=20261115,wall_seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu,peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        population_rows=len(rows),excluded_nonfranchise_stat_rows=len(pop_exclusions),files={str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dest.rglob('*')) if p.is_file()},
        independent_review='WS4 original benchmark verified; new joint adapter and engine acceptance pending external review',production_promotion_authorized=False)
    freeze(dest/'run_receipt.json',receipt);print(json.dumps({k:receipt[k] for k in ('wall_seconds','cpu_seconds','peak_rss_mib','code_commit')}))


if __name__=='__main__':main()
