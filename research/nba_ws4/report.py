"""Score independently replayed historical rows, preserving all model coverage."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from .evaluator import digest,json_safe
from .metrics import summary,binary,paired_bootstrap,mean,poisson_diagnostics


def build(replay):
    records=replay['records']; names=sorted({m for r in records for m in r['models']})
    results={}; matched={}; slices={}; distributions={}
    for model in names:
        rows=[dict(r,p=r['models'][model]['p']) for r in records if 'p' in r['models'].get(model,{})]
        results[model]=summary(rows)
        slices[model]={s:summary([r for r in rows if r['stat']==s]) for s in sorted({r['stat'] for r in rows})}
        pairs=[];ll=[];ref=[]
        for r in rows:
            if r['outcome'] not in ('over','under') or 'p' not in r['models']['Market']:continue
            y=int(r['outcome']=='over');b=r['models']['Market']['p'];a=binary(r['p'],y);control=binary(b,y)
            pairs.append(dict(r,delta=a['brier']-control['brier']));ll.append(dict(r,delta=a['log_loss']-control['log_loss']));ref.append(control['brier'])
        matched[model]={'n':len(pairs),'same_contract_market_brier':mean(ref),
            'paired_brier':{c:paired_bootstrap(pairs,cluster=c) for c in ('date','game')},
            'paired_log_loss':{c:paired_bootstrap(ll,cluster=c) for c in ('date','game')}}
        dist=[]
        for r in rows:
            d=r['models'][model].get('distribution')
            if d and d.get('kind')=='poisson':dist.append(dict(contract_id=r['contract_id'],stat=r['stat'],**poisson_diagnostics(d['rate'],r['actual'],identity=r['contract_id'])))
        if dist:
            distributions[model]={'n':len(dist),**{k:mean([r[k] for r in dist]) for k in ('count_crps','nlpd','predicted_zero','observed_zero','predicted_tail','observed_tail','interval_covered')},
                'interval_nominal':.9,'per_contract':dist}
    controls=('Engine_A','Engine_B','Bayesian_A','Bayesian_B','Consensus','Market')
    common=[r for r in records if all('p' in r['models'].get(m,{}) for m in controls)]
    common_scores={m:summary([dict(r,p=r['models'][m]['p']) for r in common]) for m in controls}
    return {'schema':'nba-ws4-source-matched-scores-v1','common_support_without_unavailable_nuts':{'n':len(common),'models':common_scores},'common_support_with_strict_nuts':{'n':0,'status':'BLOCKED-BY-DATA'},'replay_payload_sha256':digest(replay),'models':results,'matched_market':matched,
        'market_slices':slices,'distribution_diagnostics':distributions,
        'n_contracts':len(records),'n_games':replay['games'],'n_dates':replay['dates'],'n_players':replay['players'],
        'date_cluster_inference':'INCONCLUSIVE_ONE_DATE','predictive_superiority':'INCONCLUSIVE',
        'market_relative_skill':'DESCRIPTIVE_ONLY','product_economic_edge':'BLOCKED-BY-DATA',
        'calibration_improvement':'BLOCKED-BY-DATA_NO_PRIOR_OOF_DATES',
        'no_joint_score':'BLOCKED-BY-DATA_NO_ORIGINAL_JOINT_ENSEMBLE','release_allowed':False}


def save_chart(records,path):
    names=['Engine_A','Engine_B','Bayesian_A','Bayesian_B','NUTS','Consensus','Market','naive_recent_exposure_rate','pooled_peer_shrunk_rate','first_book_market','WS2','WS3']
    fields=['contract_id','event_id','player_id','player','team','opponent','stat','line','period','date','forecast_at','outcome','actual']
    with Path(path).open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields+names,lineterminator="\n");w.writeheader()
        for r in records:
            w.writerow({**{k:r[k] for k in fields},**{m:r['models'].get(m,{}).get('p',r['models'].get(m,{}).get('abstention','UNAVAILABLE_NO_ARTIFACT')) for m in names}})


def main():
    p=argparse.ArgumentParser();p.add_argument('--replay',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    a.output_dir.mkdir(parents=True,exist_ok=True);r=json.loads(a.replay.read_bytes());result=build(r)
    with (a.output_dir/'scores.json').open('x') as f:json.dump(json_safe(result),f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
    save_chart(r['records'],a.output_dir/'contract_comparison.csv')
    print(json.dumps({m:{'n':v['binary_scored'],'brier':v['brier'],'log_loss':v['log_loss']} for m,v in result['models'].items()},indent=2,sort_keys=True))

if __name__=='__main__':main()
