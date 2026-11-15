"""Independent sealed-draw verifier. Does not import simulator or its summaries."""
import hashlib,json,pathlib,math
import numpy as np


def audit(path):
    raw=pathlib.Path(path).read_bytes();o=json.loads(raw)
    assert hashlib.sha256(raw).hexdigest()==pathlib.Path(path).stem
    e=o['input_packet']['events'][0]
    from datetime import datetime
    cutoff=datetime.fromisoformat(o['input_packet']['model_training_cutoff_at'].replace('Z','+00:00'))
    for par in e['all_market_parameters'].values():
        for receipt in par.get('current_source_receipts',[]):
            assert datetime.fromisoformat(receipt['available_at'].replace('Z','+00:00'))<=cutoff, 'CURRENT_HISTORY_AFTER_TRAINING_CUTOFF'
    assert datetime.fromisoformat(o['forecast_created_at'].replace('Z','+00:00'))<datetime.fromisoformat(e['event_start_at'].replace('Z','+00:00'))
    pids=[p['player_id'] for par in e['all_market_parameters'].values() for p in par['players']]
    gids=[p['gsis_id'] for par in e['all_market_parameters'].values() for p in par['players']]
    assert len(pids)==len(set(pids)) and len(gids)==len(set(gids)), 'PLAYER_TEAM_JOIN_COLLISION'
    checks=0;maxse=0.;composites=[]
    for model,d in o['draw_records'].items():
        series={k:np.asarray(v) for k,v in d['series'].items()}
        assert all(len(v)==4096 and np.all(np.isfinite(v)) for v in series.values())
        for row in o['distributions']:
            if row['model_id']!=model:continue
            a=series['|'.join(row[k] for k in ('team_id','player_id','stat_key'))]
            assert np.isclose(a.mean(),row['mean']) and np.isclose(a.var(),row['variance'])
            for q,v in row['quantiles'].items():assert np.isclose(np.quantile(a,float(q)),v)
            stat=row['stat_key'];tid=row['team_id'];pid=row['player_id']
            if stat in ('pass_attempts','completions','rushing_attempts','targets','receptions'):
                assert np.all(a>=0) and np.all(a==a.astype(int))
            if stat in ('passing_rushing_yards','rushing_receiving_yards'):
                left='passing_yards' if stat=='passing_rushing_yards' else 'receiving_yards'
                x=series[tid+'|'+pid+'|'+left];y=series[tid+'|'+pid+'|rushing_yards']
                assert np.array_equal(a,x+y)
                cov=float(np.cov(x,y,ddof=0)[0,1]);diag=row['composite_diagnostics']
                assert np.isclose(cov,diag['covariance'])
                assert np.isclose(a.var(),x.var()+y.var()+2*cov)
                if diag['correlation'] is not None:assert abs(diag['correlation'])<=1+1e-12
                permuted=np.random.default_rng(20261115).permutation(y)
                nullcov=float(np.cov(x,permuted,ddof=0)[0,1])
                composites.append(dict(model=model,player_id=pid,stat=stat,independent_permutation_covariance=nullcov,independent_permutation_variance=float(np.var(x+permuted)),**diag))
            checks+=1
        for c in o['contracts']:
            if c['model_id']!=model or c['status']!='FORECAST':continue
            mapping={'pass attempts':'pass_attempts','completions':'completions','passing yards':'passing_yards','rush attempts':'rushing_attempts','rushing yards':'rushing_yards','receiving yards':'receiving_yards','receptions':'receptions'}
            a=series[c['team']+'|'+c['player_id']+'|'+mapping[c['stat']]]
            assert abs(c['p_over']+c['p_under']+c['p_push']-1)<1e-12
            for label,mask in [('over',a>c['line']),('under',a<c['line']),('push',a==c['line'])]:
                p=float(mask.mean());assert p==c['p_'+label]
                assert math.isclose(math.sqrt(p*(1-p)/len(a)),c['mc_se_'+label],abs_tol=1e-15)
                maxse=max(maxse,c['mc_se_'+label])
        for t in e['teams']:
            tid=t['team_id'];q=t['starter_qb_id'];st={k:np.array(v) for k,v in d['team_states'][tid].items()}
            pids=[p['player_id'] for p in e['all_market_parameters'][tid]['players']]
            def total(stat):return sum((series.get(tid+'|'+p+'|'+stat,np.zeros(4096,dtype=int)) for p in pids))
            assert np.array_equal(st['plays'],st['pass_attempts']+st['sacks']+st['rush_attempts'])
            assert np.array_equal(total('targets')+st['residual_targets'],st['pass_attempts'])
            assert np.array_equal(total('receptions')+st['residual_receptions'],st['team_completions'])
            assert np.all(st['team_completions']<=st['pass_attempts'])
            assert np.array_equal(total('rushing_attempts')+st['residual_rush_attempts'],st['rush_attempts'])
            assert np.array_equal(total('rushing_yards')+st['residual_rushing_yards'],st['team_rushing_yards'])
            assert np.array_equal(total('receiving_yards')+st['residual_receiving_yards'],st['team_passing_yards'])
            assert np.all(series[tid+'|'+q+'|completions']<=series[tid+'|'+q+'|pass_attempts'])
            checks+=4096
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),status='PASS_INDEPENDENT_DRAW_ARITHMETIC',checks=checks,max_mc_se=maxse,composites=composites)
