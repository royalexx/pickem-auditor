"""Independent output-level numerical audit: does not import simulator implementation."""
from __future__ import annotations
import argparse,collections,hashlib,json,math,pathlib,statistics


def audit(path128:pathlib.Path,path512:pathlib.Path,fixture:pathlib.Path)->dict:
    raw=fixture.read_bytes(); frozen=json.loads(raw)
    old=json.loads(path128.read_bytes());new=json.loads(path512.read_bytes())
    result=dict(status='FAILED',inputs={'fixture_file_sha256':hashlib.sha256(raw).hexdigest(),
                     'old_file_sha256':hashlib.sha256(path128.read_bytes()).hexdigest(),
                     'new_file_sha256':hashlib.sha256(path512.read_bytes()).hexdigest()},
                classification='SYNTHETIC_FIXTURE_NOT_AUTHENTIC_PREGAME_EVIDENCE')
    checks=collections.Counter();errors=[];stability=collections.defaultdict(list)
    offered={c['contract_id']:c for c in frozen['contracts']}
    by_run=[]
    for z,expected_n in ((old,128),(new,512)):
        expected=len(offered)*3
        if len(z['contracts'])!=expected:errors.append('COVERAGE_DENOMINATOR');continue
        if z['classification']!='SYNTHETIC_FIXTURE':errors.append('SYNTHETIC_CLASSIFICATION_LOST')
        seen=set()
        for r in z['contracts']:
            ident=(r['model_id'],r['contract_id'])
            if ident in seen:errors.append('DUPLICATE_MODEL_CONTRACT')
            seen.add(ident)
            if r['status']!='FORECAST':errors.append('SYNTHETIC_EXPECTED_FORECAST')
            orig=offered[r['contract_id']]
            for field in ('line','original_quote_id','stat_key','event_id','player_id','period'):
                if r[field]!=orig[field]:errors.append('ALTERED_OFFER_'+field)
            p=[r['p_over'],r['p_under'],r['p_push']]
            if abs(sum(p)-1)>1e-12 or any(q<0 or q>1 for q in p):errors.append('BROKEN_PROBABILITY')
            if r['draws']!=expected_n:errors.append('WRONG_DRAW_COUNT')
            if r['mc_se_over']>math.sqrt(.25/expected_n)+1e-12:errors.append('IMPOSSIBLE_MC_SE')
            if r['variance']<0:errors.append('NEGATIVE_VARIANCE')
            if r['stat']!=r['stat_key']:errors.append('CHANGED_STAT_IDENTITY')
            if r['pmf'] is not None:
                mass=sum(r['pmf'].values());lt=sum(v for k,v in r['pmf'].items() if float(k)<r['line'])
                gt=sum(v for k,v in r['pmf'].items() if float(k)>r['line'])
                eq=sum(v for k,v in r['pmf'].items() if float(k)==r['line'])
                if abs(mass-1)>1e-10:errors.append('INVALID_PMF_MASS')
                if abs(lt-r['p_under'])>1e-10 or abs(gt-r['p_over'])>1e-10 or abs(eq-r['p_push'])>1e-10:
                    errors.append('INCONSISTENT_CDF_TO_MARGINAL')
            elif r['stat_key'].endswith('yards') and float(r['line'])==int(r['line']):
                checks['signed_yards_integer_push_supported']+=1
            if r['model_id']=='J3':
                if set(r['scenario_conditional'])!={'neutral','pass_heavy_underdog','run_heavy_favorite','low_tempo'}:
                    errors.append('MISSING_SCENARIO_CONDITIONAL')
            checks['row_numerically_checked']+=1
        checks['run_coverage_checked']+=1
        by_run.append({(r['model_id'],r['contract_id']):r for r in z['contracts']})
    if len(by_run)==2:
        for key,r in by_run[1].items():
            p=by_run[0][key]['p_over'];stability[r['model_id']].append((abs(p-r['p_over']),r['mc_se_over']))
    result['checks']=dict(checks)
    result['errors']=sorted(set(errors));result['n_unique_errors']=len(result['errors'])
    result['stability_128_to_512']={k:{'contracts':len(v),'mean_abs_over_change':statistics.mean(x[0] for x in v),
                       'max_abs_over_change':max(x[0] for x in v),'max_mcse_over_512':max(x[1] for x in v)}
                       for k,v in sorted(stability.items())}
    result['status']='PASS_SYNTHETIC_NUMERICAL_ONLY' if not errors else 'FAIL'
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--small',type=pathlib.Path,required=True)
    ap.add_argument('--large',type=pathlib.Path,required=True)
    ap.add_argument('--fixture',type=pathlib.Path,required=True)
    ap.add_argument('--output',type=pathlib.Path,required=True)
    a=ap.parse_args();out=audit(a.small,a.large,a.fixture)
    with a.output.open('x') as w:json.dump(out,w,indent=2,sort_keys=True)
    print(json.dumps({k:v for k,v in out.items() if k not in ('inputs','stability_128_to_512')},sort_keys=True))
    if out['status'].startswith('FAIL'):raise SystemExit(1)