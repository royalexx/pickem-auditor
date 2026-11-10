#!/usr/bin/env python3
"""2025 retrospective chronological count replay; never an untouched holdout.

Parent retains the outcome oracle. Fresh child processes receive only earlier
weeks and schedule identity; predictions, lines and calibration maps are saved
before outcomes are scored. No current participation is inferred as verified.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,math,pathlib,platform,subprocess,sys
import numpy as np
from v25_opportunity_distribution import OpportunityModel,normalise_player_source,seed_for,GROUPS,DEFENSE,MARKETS,digest
from v25_opportunity_repair_replay import read,write_once,file_hash,sample_score,probability_score,metrics,paired
from v25_nfl_2024_all_volume_rolling_calibration import fit_from_past,ptransform,role_for
from nfl_contract_settlement import index_outcomes,settle

HERE=pathlib.Path(__file__).resolve().parent
COUNTS=tuple(m for m in MARKETS if 'yards' not in m)
MODELS=('expanding','frozen_2024')
METHODS=('raw','global','role')

def require(ok,why):
    if not ok:raise ValueError('REPLAY_2025_REJECTED:'+why)

def forecast(snapshot,n,seed):
    require(type(n) is int and 128<=n<=4096,'invalid_sample_count')
    require(set(snapshot)=={'schema','season','week','history','schedule'},'snapshot_hidden_outcome')
    require(snapshot['schema']=='v25-opportunity-2025-asof-v1' and snapshot['season']==2025,'snapshot_season')
    week=snapshot['week'];history=snapshot['history']
    expanding=OpportunityModel(history,week,forecast_season=2025)
    frozen=OpportunityModel([g for g in history if g['season']<2025],week,forecast_season=2025)
    out=[];seen=set()
    for g in snapshot['schedule']:
        require(set(g)=={'event_id','team','opponent','week'} and g['week']==week and g['team']!=g['opponent'],'schedule_outcome_or_identity')
        key=(g['event_id'],g['team']);require(key not in seen,'duplicate_schedule');seen.add(key)
        # Both controls see the SAME past-only candidate and synthetic-line
        # universe. Only expanding updates count parameters with 2025 boxes.
        for pid,role in sorted(expanding.candidates(g['team']).items()):
            for market in GROUPS.get(role,MARKETS[8:] if role in DEFENSE else ()):
                if market not in COUNTS:continue
                own=expanding._player_rows(pid,market)
                if not own:continue
                line=math.floor(float(np.median([p['values'][market] for _,p in own])))+.5
                draws={};abstentions={}
                for name,model in [('expanding',expanding),('frozen_2024',frozen)]:
                    rng=np.random.default_rng(seed_for(seed,week,g['event_id'],g['team'],pid,market,'control'))
                    arr=model.independent(g['team'],pid,role,market,rng,n)
                    if arr is None:abstentions[name]='no_prior_player_observation_or_role_prior'
                    else:draws[name]=arr.tolist()
                out.append({'season':2025,'week':week,'game_id':g['event_id'],'team':g['team'],
                    'player_id':pid,'role':role_for(role),'source_position':role,'market':market,
                    'research_line':line,'line_kind':'synthetic_prior_player_median_half_line',
                    'candidate_role_verified':False,'draws':draws,'abstentions':abstentions})
    require(bool(out),'empty_forecast')
    return {'schema':'v25-opportunity-2025-forecast-v1','week':week,'contracts':out,
       'input_content_sha256':digest(snapshot),'samples':n,'seed':seed,
       'source_capture_certified':False,'production_authorized':False}

def snapshot_for(past,schedule,week):
    games=[g for g in schedule if g['season']==2025 and g['week']==week]
    rows=[]
    for g in games:
        for team,opp in [(g['home_team'],g['away_team']),(g['away_team'],g['home_team'])]:
            rows.append({'event_id':g['game_id'],'team':team,'opponent':opp,'week':week})
    return {'schema':'v25-opportunity-2025-asof-v1','season':2025,'week':week,'history':past,'schedule':rows}

def game_paired(a,b,field):
    key=lambda r:(r['week'],r['game_id'],r['team'],r['player_id'],r['market'],r['line'])
    x={key(r):r for r in a if r.get(field) is not None};y={key(r):r for r in b if r.get(field) is not None}
    groups=collections.defaultdict(list)
    for k in sorted(x.keys()&y.keys()):groups[k[1]].append(x[k][field]-y[k][field])
    if not groups:return {'n':0}
    sums=np.array([sum(v) for v in groups.values()]);ns=np.array([len(v) for v in groups.values()])
    rng=np.random.default_rng(20261110);ix=rng.integers(0,len(ns),(2000,len(ns)))
    boot=sums[ix].sum(axis=1)/ns[ix].sum(axis=1)
    return {'n':int(ns.sum()),'games':len(ns),'new_minus_reference':float(sums.sum()/ns.sum()),
       'game_cluster_95':np.quantile(boot,[.025,.975]).tolist(),'descriptive_not_independent_holdout':True}

def confidence_bins(rows):
    bins={}
    for lo,hi in [(.5,.6),(.6,.7),(.7,.8),(.8,.9),(.9,1.00000001)]:
        xs=[r for r in rows if r.get('q') is not None and lo<=max(r['q'],1-r['q'])<hi]
        bins[f'{lo:.1f}-{min(hi,1.):.1f}']=metrics(xs)
    return bins

def run(a):
    require(not a.output_dir.exists(),'immutable_directory_exists')
    protocol=read(a.protocol)
    require(protocol['experiment_id']=='V25-OPPORTUNITY-2025-CHRONOLOGICAL-20261110','unregistered_protocol')
    require(protocol['2025_untouched_holdout'] is False and protocol['production_promotion_authorized'] is False,'invalid_release_claim')
    require(protocol['samples']==2048 and protocol['markets']==list(COUNTS),'protocol_mismatch')
    require(set(protocol['models'])==set(MODELS) and protocol['methods']==list(METHODS),'comparison_mismatch')
    prior=read(a.prior_source);future=read(a.oracle_source);schedule=read(a.schedule)['rows']
    require(all(r['season']<=2024 for r in prior['rows']),'prior_source_future_labels')
    require(all(r['season']==2025 for r in future['rows']),'oracle_source_wrong_year')
    require(len(schedule)==272 and len({g['game_id'] for g in schedule})==272,'incomplete_or_duplicate_schedule')
    rejected=[]
    past=normalise_player_source(prior['rows'],rejection_ledger=rejected)
    oracle=normalise_player_source(future['rows'],rejection_ledger=rejected,allowed_seasons=(2025,))
    require(set(g['week'] for g in oracle)==set(range(1,19)),'incomplete_oracle_weeks')
    a.output_dir.mkdir(parents=True);code=a.output_dir/'code';code.mkdir()
    names=['v25_opportunity_2025_replay.py','v25_opportunity_distribution.py','v25_opportunity_repair_replay.py',
       'v25_nfl_2024_all_volume_rolling_calibration.py','nfl_contract_settlement.py']
    hashes={}
    for name in names:
        raw=(HERE/name).read_bytes();(code/name).write_bytes(raw);hashes[name]=hashlib.sha256(raw).hexdigest()
    write_once(a.output_dir/'PROTOCOL.json',protocol);write_once(a.output_dir/'SOURCE_REJECTIONS.json',rejected)
    source_hashes={k:file_hash(getattr(a,k)) for k in ['prior_source','oracle_source','schedule','protocol']}
    write_once(a.output_dir/'PRE_RUN_FREEZE.json',{'source_hashes':source_hashes,'code_sha256':hashes,
       'no_new_run_2025_scores_examined_before_freeze':True,'policy':protocol,'numpy':np.__version__,'python':platform.python_version()})
    histories=collections.defaultdict(list);ledger=collections.defaultdict(list);weekly=[];manifest=[];coverage=collections.Counter()
    for week in range(1,19):
        prefix=f'week_{week:02d}'
        inp=a.output_dir/(prefix+'_asof_input.json.gz');pred=a.output_dir/(prefix+'_forecast.json.gz')
        snap=snapshot_for(past,schedule,week);ish=write_once(inp,snap)
        p=subprocess.run([sys.executable,str((code/pathlib.Path(__file__).name).resolve()),'forecast','--input',str(inp),'--output',str(pred),
           '--samples',str(protocol['samples']),'--seed',str(protocol['seed'])],capture_output=True,text=True,timeout=480)
        require(p.returncode==0,'forecast_child_failed:'+p.stderr[-1200:])
        f=read(pred);require(f['input_content_sha256']==digest(snap),'input_changed')
        fits={}
        for model in MODELS:
            for market in COUNTS:
                hs=histories[model,market];require(all(x['week']<week for x in hs),'future_calibration_label')
                fits[model+'|'+market]=fit_from_past(hs)
        offers=[]
        for c in f['contracts']:
            coverage['candidates']+=1
            for model in MODELS:
                if model in c['abstentions']:coverage[model+':ABSTAIN']+=1;continue
                arr=c['draws'][model];q=sum(v>c['research_line'] for v in arr)/len(arr)
                for method in METHODS:
                    offers.append({**{k:v for k,v in c.items() if k not in ('draws','abstentions')},'model':model,'method':method,
                       'q':ptransform(q,c['role'],fits[model+'|'+c['market']],method),'raw_q':q})
        cal=a.output_dir/(prefix+'_calibration.json.gz')
        csh=write_once(cal,{'week':week,'training_through_week':week-1,'full_parameter_preimages':fits,'offers':offers})
        # Only now reveal this week's labels to the scorer, then append them
        # to training history after the complete weekly settlement is frozen.
        fresh=[g for g in oracle if g['week']==week]
        labels=[{'game_id':g['event_id'],'team':g['team'],'player_id':pid,'stat':m,'value':v}
           for g in fresh for pid,p in g['players'].items() for m,v in p['values'].items() if m in COUNTS]
        truth=index_outcomes(labels)
        expected={(g['event_id'],g['team']) for g in fresh}
        require(expected=={(g['event_id'],g['team']) for g in snap['schedule']},'source_schedule_team_mismatch')
        index={(c['game_id'],c['team'],c['player_id'],c['market']):c for c in f['contracts']}
        current=[];states=[]
        for c in f['contracts']:
            state=settle(c,truth);coverage['candidate:'+state['state']]+=1
            states.append({**{k:v for k,v in c.items() if k not in ('draws',)},**state})
        offered_keys=set(index)
        coverage['observed_current_player_markets_not_in_prior_candidate_universe']+=sum(k not in offered_keys for k in truth)
        for offer in offers:
            st=settle(offer,truth);model=offer['model'];method=offer['method'];market=offer['market']
            coverage[model+'|'+method+':'+st['state']]+=1
            if st['state']!='SETTLED':continue
            arr=index[offer['game_id'],offer['team'],offer['player_id'],market]['draws'][model]
            score=sample_score(arr,st['actual'],offer['research_line'])
            row={**offer,**score,'line':offer['research_line']}
            row.update(probability_score(offer['q'],score['y']))
            current.append(row);ledger[model,method,market].append(row)
            if method=='raw':histories[model,market].append({'p':offer['raw_q'],'y':score['y'],'role':offer['role'],'week':week})
        settle_path=a.output_dir/(prefix+'_settled.json.gz');ssh=write_once(settle_path,{'states':states,'scores':current})
        manifest.append({'week':week,'input_file':inp.name,'input_sha256':ish,'forecast_file':pred.name,'forecast_sha256':file_hash(pred),
           'calibration_file':cal.name,'calibration_sha256':csh,'settled_file':settle_path.name,'settled_sha256':ssh})
        weekly.append({'week':week,'candidate_n':len(f['contracts']),'state_counts':dict(collections.Counter(s['state'] for s in states)),
           'metrics':{model:{method:metrics([x for x in current if x['model']==model and x['method']==method]) for method in METHODS} for model in MODELS}})
        past=past+fresh
        print('WEEK_FROZEN_AND_SCORED',week,'candidates',len(f['contracts']),flush=True)
    markets={}
    for market in COUNTS:
        x=ledger['expanding','raw',market];y=ledger['frozen_2024','raw',market]
        markets[market]={'models':{model:{method:metrics(ledger[model,method,market]) for method in METHODS} for model in MODELS},
           'expanding_minus_frozen':{metric:{'week':paired(x,y,metric),'game':game_paired(x,y,metric)} for metric in ('brier','log_loss','crps','bias')},
           'by_role':{role:{model:metrics([r for r in ledger[model,'role',market] if r['role']==role]) for model in MODELS} for role in sorted({r['role'] for r in x})},
           'confidence_bins':{method:confidence_bins(ledger['expanding',method,market]) for method in METHODS}}
    result={'schema':'v25-opportunity-2025-completed-v1','status':'COMPLETED_RETROSPECTIVE_RESEARCH',
       '2025_untouched_holdout':False,'2025_prior_exposure_confirmed':True,'source_capture_certified':False,
       'current_participation_verified':False,'production_authorized':False,'tier_authorized':False,
       'baseline_60_40':'UNAVAILABLE_no_original_same_contract_forecasts','market':'UNAVAILABLE_synthetic_lines',
       'source_hashes':source_hashes,'code_hashes':hashes,'protocol':protocol,'coverage':dict(coverage),'manifest':manifest,
       'markets':markets,'weekly':weekly}
    result['receipt_sha256']=digest(result)
    write_once(a.output_dir/'FINAL_REPORT.json',result)
    write_once(a.output_dir/'SCORED_LEDGER.json.gz',{'|'.join(k):v for k,v in ledger.items()})
    print('REPLAY_2025_COMPLETED',result['receipt_sha256'],flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);subs=p.add_subparsers(dest='mode',required=True)
    f=subs.add_parser('forecast');f.add_argument('--input',type=pathlib.Path,required=True);f.add_argument('--output',type=pathlib.Path,required=True)
    f.add_argument('--samples',type=int,required=True);f.add_argument('--seed',type=int,required=True)
    r=subs.add_parser('run')
    for name in ['prior-source','oracle-source','schedule','protocol','output-dir']:r.add_argument('--'+name,type=pathlib.Path,required=True)
    a=p.parse_args()
    if a.mode=='forecast':write_once(a.output,forecast(read(a.input),a.samples,a.seed))
    else:run(a)

if __name__=='__main__':main()
