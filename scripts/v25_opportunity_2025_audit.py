#!/usr/bin/env python3
"""Independent no-fit rescore of completed 2025 frozen weekly files."""
from __future__ import annotations
import argparse,collections,gzip,hashlib,json,math,pathlib
import numpy as np

FIELDS={'pass attempts':'attempts','completions':'completions','targets':'targets','receptions':'receptions','carries':'carries',
        'solo tackles':'def_tackles_solo','tackle assists':'def_tackle_assists'}
DEFENSIVE_POSITIONS={'LB','MLB','OLB','ILB','DE','DT','NT','CB','DB','S','FS','SS','DL','EDGE'}
def read(p):
    raw=p.read_bytes();return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def content_sha(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def need(ok,why):
    if not ok:raise AssertionError('INDEPENDENT_2025_AUDIT_REJECTED:'+why)
def empirical_crps(values,y):
    x=sorted(values);n=len(x)
    return sum(abs(v-y) for v in x)/n-sum((2*i-n+1)*v for i,v in enumerate(x))/(n*n)

def audit(folder,oracle_source):
    r=read(folder/'FINAL_REPORT.json');need(r['source_hashes']['oracle_source']==sha(oracle_source),'oracle_source_changed')
    need(content_sha({k:v for k,v in r.items() if k!='receipt_sha256'})==r['receipt_sha256'],'report_digest')
    need(r['2025_untouched_holdout'] is False and r['production_authorized'] is False,'invalid_holdout_or_release_claim')
    for name,expected in r['code_hashes'].items():need(sha(folder/'code'/name)==expected,'frozen_code_changed')
    truth={}
    for row in read(oracle_source)['rows']:
        if not row.get('player_id'):continue
        for market,field in {**FIELDS,'tackles + assists':None}.items():
            role=row.get('position')
            allowed=(role=='QB' if market in ('pass attempts','completions') else
                     role in {'RB','WR','TE'} if market in ('targets','receptions') else
                     role in {'RB','QB'} if market=='carries' else role in DEFENSIVE_POSITIONS)
            if not allowed:continue
            v=row.get(field) if field else None
            if field is None:
                parts=[row.get(f) for f in ['def_tackles_solo','def_tackles_with_assist','def_tackle_assists']]
                if all(isinstance(x,(int,float)) for x in parts):v=sum(parts)
            if v is not None:
                k=(row['week'],row['game_id'],row['team'],row['player_id'],market)
                need(k not in truth,'duplicate_truth');truth[k]=v
    need(len(r['manifest'])==18,'missing_week')
    checks=collections.Counter();training=collections.defaultdict(list);aggregates=collections.defaultdict(list);week1=[]
    for manifest in r['manifest']:
        w=manifest['week']
        for kind in ['input','forecast','calibration','settled']:
            need(sha(folder/manifest[kind+'_file'])==manifest[kind+'_sha256'],'changed_'+kind)
            checks[kind+'_hash']+=1
        inp=read(folder/manifest['input_file']);pred=read(folder/manifest['forecast_file'])
        cal=read(folder/manifest['calibration_file']);settled=read(folder/manifest['settled_file'])
        need(content_sha(inp)==pred['input_content_sha256'],'forecast_input_binding')
        need(inp['season']==2025 and inp['week']==w,'wrong_origin')
        need(all(g['season']<2025 or g['season']==2025 and g['week']<w for g in inp['history']),'future_training')
        need(all(set(g)=={'event_id','team','opponent','week'} and g['week']==w for g in inp['schedule']),'schedule_outcome')
        need(cal['training_through_week']==w-1,'future_calibration_cutoff')
        for name,fit in cal['full_parameter_preimages'].items():
            need(fit['trained_n']==len(training[name]),'wrong_prior_label_n')
            need(fit['latest_week']==max(training[name],default=0) and fit['latest_week']<w,'wrong_prior_label_cutoff')
        checks['weekly_prior_only_cutoff']+=1
        prior_values=collections.defaultdict(list)
        for g in sorted(inp['history'],key=lambda g:(g['season'],g['week'],g['event_id'])):
            for pid,p in g['players'].items():
                for market,value in p['values'].items():prior_values[pid,market].append(value)
        contracts={}
        for c in pred['contracts']:
            k=(c['game_id'],c['team'],c['player_id'],c['market'],c['research_line'])
            need(k not in contracts,'duplicate_contract');contracts[k]=c
            if w==1:
                need(c['draws']['expanding']==c['draws']['frozen_2024'],'week1_control_differs')
                checks['week1_identical_controls']+=1
            # Independently reconstruct the synthetic line from prior inputs.
            vals=prior_values[c['player_id'],c['market']][-8:]
            need(c['research_line']==math.floor(float(np.median(vals)))+.5,'line_not_prior_only')
            checks['prior_only_line']+=1
        pending=collections.defaultdict(list);seen=set()
        for row in settled['scores']:
            k=(row['game_id'],row['team'],row['player_id'],row['market'],row['line'])
            unique=(row['model'],row['method'],*k);need(unique not in seen,'duplicate_scored_contract');seen.add(unique)
            need(truth[w,*k[:4]]==row['actual'],'wrong_exact_truth')
            values=contracts[k]['draws'][row['model']];q=sum(x>row['line'] for x in values)/len(values)
            raw=q
            fit=cal['full_parameter_preimages'][row['model']+'|'+row['market']]
            if row['method']!='raw' and fit['active']:
                p=max(.0005,min(.9995,q));z=fit['a']+fit['b']*math.log(p/(1-p))
                if row['method']=='role':z+=fit['offset'].get(row['role'],0.)
                q=1/(1+math.exp(-max(-30.,min(30.,z))))
            y=int(row['actual']>row['line'])
            need(row['y']==y and abs(row['q']-q)<1e-12 and abs(row['brier']-(q-y)**2)<1e-12,'wrong_probability_score')
            checks['independent_probability_score']+=1
            if row['method']=='raw':
                need(abs(empirical_crps(values,row['actual'])-row['crps'])<1e-10,'wrong_crps')
                need(abs(sum(values)/len(values)-row['mean'])<1e-12,'wrong_count_mean')
                pending[row['model']+'|'+row['market']].append(w);checks['independent_crps']+=1
            aggregates[row['model'],row['method'],row['market']].append(row)
        for state in settled['states']:
            k=(w,state['game_id'],state['team'],state['player_id'],state['market'])
            expected='UNMATCHED' if k not in truth else 'PUSH' if truth[k]==state['research_line'] else 'SETTLED'
            need(state['state']==expected,'wrong_missing_push_state');checks['settlement_state']+=1
        for name,ws in pending.items():training[name].extend(ws)
    for market,group in r['markets'].items():
        for model,methods in group['models'].items():
            for method,expected in methods.items():
                rows=aggregates[model,method,market];need(len(rows)==expected['n'],'wrong_aggregate_n')
                for field in ['brier','log_loss','bias','crps','coverage80']:
                    need(abs(float(np.mean([x[field] for x in rows]))-expected[field])<1e-10,'wrong_aggregate_'+field)
                checks['market_method_aggregate']+=1
    result={'schema':'v25-2025-independent-no-fit-audit-v1','passed':True,'checks':dict(checks),
       'source_receipt':r['receipt_sha256'],'audit_code_sha256':sha(pathlib.Path(__file__)),
       '2025_independent_holdout':False,'source_capture_certified':False,'production_authorized':False}
    result['receipt_sha256']=content_sha(result);return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['folder','oracle-source','output']:p.add_argument('--'+name,type=pathlib.Path,required=True)
    a=p.parse_args();result=audit(a.folder,a.oracle_source)
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
