#!/usr/bin/env python3
"""Fresh P6 adversarial/reference checks. Synthetic data only; read-only owners.

Run against the exact source-mapped assembly; evidence mode verifies the source
map before any imported owner code executes. No implementation is changed.
"""
import argparse
import copy
from fractions import Fraction
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import traceback

G0='59d28dc23be97de2a6a82d22be8338151e31f5b6'
ASSEMBLY='d46f5322b47367ba601b05197cef8404758da23d'


def encode(x):return json.dumps(x,sort_keys=True,indent=2,allow_nan=False)+'\n'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args])


def evidence(a):
    root=a.assembly;qa=Path(__file__).resolve().parents[1]
    assert git(root,'rev-parse','HEAD').decode().strip()==a.expected_assembly
    m=json.loads((root/'docs/nba_architecture/g1_exact_owner_assembly_v4_20261116.json').read_bytes())
    changed=set(git(root,'diff','--name-only',G0,a.expected_assembly).decode().splitlines())
    assert changed==set(m['files'])|{'docs/nba_architecture/g1_exact_owner_assembly_v4_20261116.json'}
    checked=[]
    for path,row in sorted(m['files'].items()):
        raw=(root/path).read_bytes()
        assert sha(raw)==row['raw_sha256']
        assert raw==git(root,'show',row['source_commit']+':'+path)
        assert git(root,'ls-tree','HEAD','--',path).decode().split()[0]==row['git_mode']
        assert row['source_commit'] in {m['pins'][owner] for owner in row['owners']}
        checked.append(dict(path=path,source=row['source_commit'],sha256=sha(raw),mode=row['git_mode']))
    inherited=git(root,'ls-tree','-r','--name-only',G0,'v2/nba_architecture','tests/nba_architecture').decode().splitlines()
    for path in inherited:
        assert (root/path).read_bytes()==git(root,'show',G0+':'+path)
        assert git(root,'ls-tree','HEAD','--',path).decode().split()[0]==git(root,'ls-tree',G0,'--',path).decode().split()[0]
    operational={}
    for owner,pin in m['pins'].items():
        diff=git(root,'diff','--name-only',G0,pin,'--','config/production_consensus.json','.training-control/PAUSED.json','.github/workflows')
        assert not diff
        operational[owner]=dict(sha=pin,production_pause_workflows_diff=[])
    probe=qa/'scripts/nba_p6_g1_owner_negative_probes_20261116.py'
    assert sha(probe.read_bytes())=='fa8012e260a21caacb2fcebadc02a2deddaf957bc4425b8128dcae2c83ba9e52'
    manifests=[]
    for name in ('docs/nba_architecture/p6_remediation_reaudit_v3_20261116/SHA256SUMS',
                 'docs/nba_architecture/g1_orchestration_v4_20261116/SHA256SUMS_PRE_P6_V2'):
        n=0
        for line in (qa/name).read_text().splitlines():
            expected,path=line.split('  ',1)
            assert sha((qa/path).read_bytes())==expected,(name,path)
            n+=1
        manifests.append(dict(path=name,sha256=sha((qa/name).read_bytes()),entries=n))
    return dict(exact_source_files=checked,inherited_g0_files=len(inherited),operational=operational,manifests=manifests,probe_raw_sha256=sha(probe.read_bytes()))


def physical(a):
    from v2.nba_architecture.p1_integer_accounting import partial_counts_feasible as p1
    from v2.nba_c.physical_counts import partial_counts_feasible as p5
    from v2.nba_s_family.source_accounting import validate_count_feasibility as p2
    from v2.nba_s_family.model import SFError
    rng=random.Random(617071);counts=dict(valid=0,invalid=0);inputs=[]
    # Independent complete enumeration of bounded primitive basketball events.
    # FGA/3PA/FTA and R/A bounds are always present, so finite enumeration is
    # complete even when observed shooting and combination fields are sparse.
    keys=['points','threes','fgm','ftm','pr','pa','ra','pra','oreb','dreb']
    for i in range(1200):
        fa=rng.randrange(5);ta=rng.randrange(fa+1);fta=rng.randrange(5)
        r=rng.randrange(5);assist=rng.randrange(5)
        worlds=[]
        for two,three,free,off in itertools.product(range(fa-ta+1),range(ta+1),range(fta+1),range(r+1)):
            pts=2*two+3*three+free
            worlds.append(dict(fga=fa,fg3a=ta,fta=fta,rebounds=r,assists=assist,
                points=pts,threes=three,fgm=two+three,ftm=free,oreb=off,dreb=r-off,
                pr=pts+r,pa=pts+assist,ra=r+assist,pra=pts+r+assist))
        source=rng.choice(worlds);selected=rng.sample(keys,rng.randrange(1,len(keys)+1))
        stats={k:source[k] for k in ['fga','fg3a','fta','rebounds','assists']+selected}
        if i%2:stats[rng.choice(selected)]=rng.randrange(20)
        reference=any(all(w[k]==v for k,v in stats.items()) for w in worlds)
        try:got2=p2(stats)
        except SFError as exc:
            assert str(exc)=='P1_NATIVE_INTEGER_ACCOUNTING_INFEASIBLE',(stats,str(exc))
            got2=False
        observed=(p1(stats),got2,p5(stats))
        assert observed==(reference,)*3,(stats,reference,observed)
        counts['valid' if reference else 'invalid']+=1
        inputs.append(dict(stats=stats,reference=reference))
    for bad in (True,1.0,-1):
        assert not p1({'points':bad}) and not p5({'points':bad})
    assert p1({'points':10**100,'ftm':10**100})
    assert p5({'points':10**100,'ftm':10**100})
    try:p2({'points':2**48+1})
    except SFError as exc:assert 'NUMERICAL_RANGE_UNRESOLVED' in str(exc)
    else:raise AssertionError('P2 range uncertainty erased')
    return dict(cases=len(inputs),counts=counts,inputs_sha256=sha(encode(inputs).encode()),inputs=inputs)


def scores(a):
    from v2.nba_c import scores as s
    rng=random.Random(170617);max_crps=0.;max_es=0.;max_vs=0.;sample=[]
    for i in range(350):
        values=sorted(rng.sample(range(251),rng.randrange(2,13)))
        numerators=[rng.randrange(1,11) for _ in values];total=sum(numerators)
        exact={k:Fraction(n,total) for k,n in zip(values,numerators)}
        law={k:float(p) for k,p in exact.items()};y=rng.randrange(270)
        reference=sum((sum(p for k,p in exact.items() if k<=t)-int(y<=t))**2 for t in range(max(max(values),y)+1))
        error=abs(s.crps(law,y)-float(reference));max_crps=max(max_crps,error)
        assert error<2e-10,(law,y,reference,s.crps(law,y))
        nll=s.nll(law,y)
        assert (math.isinf(nll) if y not in law else abs(nll+math.log(law[y]))<1e-12)
        for u in (.0,.137,1.):
            expected=float(sum(p for k,p in exact.items() if k<y)+Fraction(str(u))*exact.get(y,0))
            assert abs(s.randomized_pit(law,y,u=u)-expected)<1e-12
        d=s.diagnostics(law,y,seed=i,tail_threshold=177)
        mu=float(sum(k*p for k,p in exact.items()))
        assert abs(d['absolute_error']-abs(mu-y))<1e-11
        assert abs(d['squared_error']-(mu-y)**2)<1e-8
        assert abs(d['zero_predicted']-float(exact.get(0,0)))<1e-12
        assert abs(d['tail_predicted']-float(sum(p for k,p in exact.items() if k>=177)))<1e-12
        if i<3:sample.append(dict(law=law,y=y,crps=float(reference)))
    for i in range(90):
        x=[tuple(rng.randrange(15) for _ in range(4)) for _ in range(rng.randrange(2,10))]
        ns=[rng.randrange(1,10) for _ in x];ws=[n/sum(ns) for n in ns];y=tuple(rng.randrange(15) for _ in range(4))
        rows=list(zip(x,ws));norm=lambda v,w:sum((u-z)**2 for u,z in zip(v,w))**.5
        es=sum(w*norm(v,y) for v,w in rows)-sum(w*q*norm(v,z) for v,w in rows for z,q in rows)/2
        power=.73
        vs=sum((abs(y[j]-y[k])**power-sum(w*abs(v[j]-v[k])**power for v,w in rows))**2 for j in range(4) for k in range(j+1,4))
        max_es=max(max_es,abs(s.energy_score(rows,y)-es));max_vs=max(max_vs,abs(s.variogram_score(rows,y,power=power)-vs))
        assert max_es<1e-11 and max_vs<1e-10
    for bad in ({0:.8},{0:-.2,1:1.2},{False:1},{0:float('nan')},[(0,.5),(0,.5)]):
        try:s.validate_pmf(bad)
        except s.ScoreError:pass
        else:raise AssertionError(('invalid pmf accepted',str(bad)))
    return dict(sparse_full_count_cases=350,joint_cases=90,max_crps_error=max_crps,max_es_error=max_es,max_vs_error=max_vs,examples=sample)


def quarantine(a):
    from v2.nba_c import experiment as e
    from tests.nba_c.test_p5_c_family import fixture
    rng=random.Random(724611);negative=0;positive=0
    def wrap(value,depth):
        for _ in range(depth):
            kind=rng.randrange(3)
            value={'prefreeze_context':value} if kind==0 else [None,value] if kind==1 else (0.2,value)
        return value
    badkeys=['Actual Minutes','ACTUAL\tATTEMPTS','t-a-r-g-e-t-g-a-m-e-o-u-t-c-o-m-e',
             'RealizedPoints','final:roster','Target/Game/Final/Score','Official Available At','Event End At']
    for key,depth in itertools.product(badkeys,range(11)):
        row=fixture();row['pipelines']['S0']['model_inputs']=wrap({key:37},depth)
        try:e.CachedCohort([row],authorization='SYNTHETIC_UNIT_TEST')
        except e.ExperimentError as exc:assert str(exc)=='OUTCOME_IN_FORECAST_PIPELINE',(key,str(exc))
        else:raise AssertionError(('forbidden accepted',key,depth))
        negative+=1
    for depth in range(11):
        for stat in e.STATS:
            row=fixture(stat=stat)
            value={'projected_minutes':31.25,'projected_attempts':15,'participation_probability':None,
                'SourceAvailableAt':'2022-10-20T16:59:59.999999Z','GameId':row['game_id'],
                'prior_game_actual_minutes':0,'role_rates':[0,.2,.3]}
            row['pipelines']['S0']['model_inputs']=wrap(value,depth)
            cache=e.CachedCohort([row],authorization='SYNTHETIC_UNIT_TEST');assert cache.game_count==1
            positive+=1
    for key,bad,reason in [('source available at','2022-10-20T17:00:00.000001Z','POST_FREEZE'),
        ('target game id','wrong','LINKED_IDENTITY_MISMATCH'),('player-id','wrong','LINKED_IDENTITY_MISMATCH'),
        ('UnreviewedAt','2022-10-20T16:00:00Z','UNSUPPORTED_TIME_FIELD')]:
        row=fixture();row['pipelines']['S0']['model_inputs']=wrap({key:bad},9)
        try:e.CachedCohort([row],authorization='SYNTHETIC_UNIT_TEST')
        except e.ExperimentError as exc:assert reason in str(exc)
        else:raise AssertionError(('invalid linked input accepted',key))
        negative+=1
    return dict(nested_negative=negative,nested_valid=positive,max_depth=10,containers=['dict','list','tuple'])


def cutoff(a):
    from tests.nba_s_family.test_statistical import histories,manifest,pregame,opportunity_fixture
    from v2.nba_architecture.v2_contracts import seal
    from v2.nba_s_family import fit,predict,SFError
    from v2.nba_s_family.integration import joint_conditional
    rows=[]
    for stat,family,cut in itertools.product(('points','rebounds','assists','threes'),('S1','S2'),
        ('2022-10-09T23:59:59.999999Z','2022-10-10T00:00:00Z','2022-10-10T00:00:00.000001Z','2022-10-11T00:00:00Z')):
        p=pregame();p['training_cutoff_at']='2022-10-10T00:00:00Z';p=seal({k:v for k,v in p.items() if k!='content_hash'});g,o=opportunity_fixture(p)
        fitted=fit(histories(stat),asof_cutoff_utc=cut,source_manifest=manifest(),stat=stat,family=family)
        r=predict(fitted,frozen_pregame=p,target_player_id='espn:player:10',role='wing',opportunity=o,game_state=g)
        reason=None
        try:c=joint_conditional(fitted,pregame=p,game_state=g,opportunity=o,scenario_id=o['scenarios'][0]['scenario_id'],player_id='espn:player:10',team_id='espn:team:1',role='wing');assert c['pmf']
        except SFError as exc:reason=str(exc)
        expected='MODEL_AFTER_DATA_CUTOFF' if cut>'2022-10-10T00:00:00Z' and cut!='2022-10-09T23:59:59.999999Z' else None
        # Lexical datetime equality is not used by the implementation; these
        # fixed UTC literals make the independent expected cases explicit.
        if cut=='2022-10-10T00:00:00.000001Z':expected='MODEL_AFTER_DATA_CUTOFF'
        assert r.abstain_reason==expected and reason==expected,(stat,family,cut,r.abstain_reason,reason)
        rows.append(dict(stat=stat,family=family,cutoff=cut,regular=r.abstain_reason,conditional=reason))
    return rows


def optimizer(a):
    import numpy as np
    from v2.nba_c import experiment as e
    from tests.nba_c.test_p5_c_family import fixture
    rng=random.Random(620171);results=[]
    for trial in range(12):
        rows=[]
        for j in range(8):
            row=fixture(date=f'2022-10-{20+j:02}T00:00:00Z',actual=j%3,game=f'nba:independent:{j}')
            for item in row['pipelines'].values():
                nums=[rng.randrange(1,11) for _ in range(5)]
                item['pmf']={k:n/sum(nums) for k,n in enumerate(nums)}
            rows.append(row)
        cache=e.CachedCohort(rows,authorization='SYNTHETIC_UNIT_TEST');ids=cache.pipeline_ids
        lam=.013*(trial+1);prior=np.array([.1,.3,.6])
        # Derive Hessian directly from independent full CDF evaluation. Do not
        # read cache.gram, cache.linear, or use the owner's optimizer as reference.
        features=[];targets=[]
        for row in rows:
            for t in range(5):
                features.append([sum(p for k,p in row['pipelines'][name]['pmf'].items() if k<=t) for name in ids])
                targets.append(int(row['actual']<=t))
        X=np.array(features);y=np.array(targets)
        H=X.T@X/len(rows)+lam*np.eye(3);b=X.T@y/len(rows)+lam*prior
        objective=lambda w:float(np.mean((X@w-y)**2)*5+lam*np.sum((w-prior)**2))
        options=[]
        for n in (1,2,3):
            for face in itertools.combinations(range(3),n):
                ix=list(face);K=np.block([[H[np.ix_(ix,ix)],np.ones((n,1))],[np.ones((1,n)),np.zeros((1,1))]])
                sol=np.linalg.solve(K,np.r_[b[ix],1.])[:n]
                if min(sol)>=-1e-12:
                    w=np.zeros(3);w[ix]=sol;options.append((objective(w),w))
        best,w=min(options,key=lambda q:q[0]);got=e.w2_global(cache,lam=lam,prior=prior)
        wgot=np.array([got[name] for name in ids]);delta=objective(wgot)-best
        assert abs(delta)<2e-10 and max(abs(wgot-w))<2e-5,(trial,delta,wgot,w)
        global_weights=dict(zip(ids,prior));w3=e.w3_by_stat(rows,global_weights=global_weights,lam=lam,min_games=3)['points']
        assert max(abs(np.array([w3[name] for name in ids])-w))<2e-5
        assert cache.game_count==8 and cache.cached_pmf_count==24
        results.append(dict(trial=trial,reference_weights=w.tolist(),weights=wgot.tolist(),objective_error=delta,synthetic_games=cache.game_count))
    return results


def native(a):
    from tests.nba_architecture.test_p3_p1_native_v4 import native_fixture
    from v2.nba_o_p1_native import consume_p1_context
    from v2.nba_architecture.v2_contracts import ContractError
    p,x=native_fixture();positive=consume_p1_context(x,frozen_pregame=p)
    assert positive['scenario_generation']=='NOT_ATTEMPTED' and positive['players'][0]['participation_probability'] is None
    attacks=[('forged_auth',lambda v:v['players'][0].update(participation_authentication={'verified':True,'sha256':'a'*64})),
        ('posterior_frequency',lambda v:v['players'][0].update(participation_probability=.999999)),
        ('resealed_team',lambda v:v['players'][0].update(team_id=p['team_ids'][1])),
        ('one_microsecond_postfreeze',lambda v:v['sources'][0]['clocks'].update(adapter_asserted_available_at=p['input_freeze_at'].replace('Z','.000001Z'))),
        ('false_full_population',lambda v:v['candidate_denominator'].update(complete_population=len(p['players']))),
        ('bool_candidates',lambda v:v['candidate_denominator'].update(observed_candidates=True)),
        ('numeric_eligibility',lambda v:v['players'][0].update(legal_eligibility=1)),
        ('wrong_raw_ancestry',lambda v:v['sources'][0].update(raw_sha256='f'*64))]
    result=[]
    for name,mutate in attacks:
        y=copy.deepcopy(x);mutate(y)
        try:consume_p1_context(y,frozen_pregame=p)
        except ContractError as exc:result.append(dict(attack=name,rejection=str(exc)))
        else:raise AssertionError(('forged native admission accepted',name,y))
    return dict(positive_unknown_preserved=True,attacks=result)


def joint(a):
    from research.nba_p4_latest.fixture import build
    from research.nba_p4_latest.benchmark import PARAMETERS
    from v2.nba_joint.latest_upstream import prepare
    from v2.nba_joint.integration_v2 import simulate_latest
    from v2.nba_joint.p4 import scenario_pmfs
    from v2.nba_architecture.v2_contracts import ContractError
    root=prepare();inputs=build(root);p,g,o=inputs[:3]
    output=simulate_latest(*inputs,upstream_root=root,evidence_mode='latest_synthetic_engineering',event_parameters=PARAMETERS,seed=617170)
    laws=scenario_pmfs(output,p,frozen_at=p['forecast_at'],seed=617170)
    weights=[x['weight'] for x in o['scenarios']];ess=1/sum(w*w for w in weights)
    n=0
    for player,stats in laws.items():
        for stat,law in stats.items():
            reference={}
            for sc in output['bundle']['scenarios']:
                value=next(x for x in sc['players'] if x['player_id']==player)['stats'][stat]
                reference[value]=reference.get(value,0)+sc['weight']
            got={x['value']:x['mass'] for x in law['pmf']}
            assert got==reference and abs(sum(got.values())-1)<1e-12
            assert abs(law['numerical']['effective_sample_size']-ess)<1e-12
            assert law['numerical']['scenario_count']==len(weights)
            n+=1
    assert n==96
    for actual,prior in zip(output['bundle']['scenarios'],o['scenarios']):
        assert (actual['scenario_id'],actual['weight'])==(prior['scenario_id'],prior['weight'])
        for player in actual['players']:
            s=player['stats']
            assert s['points']>=3*s['threes']
            assert (s['pr'],s['pa'],s['ra'],s['pra'])==(s['points']+s['rebounds'],s['points']+s['assists'],s['rebounds']+s['assists'],s['points']+s['rebounds']+s['assists'])
    controls=[]
    for n in (4,8,32):
        try:built=build(root,n=n,variant='O2')
        except ContractError as exc:
            assert n==32 and exc.code=='O_COUPLING_VERIFICATION_BUDGET'
            controls.append(dict(n=n,status='BLOCKED',reason=exc.code))
        else:
            assert n!=32 and len(built[2]['scenarios'])==n
            controls.append(dict(n=n,status='POSITIVE_SYNTHETIC_CONTROL'))
    try:simulate_latest(*inputs,upstream_root=root,event_parameters=PARAMETERS,seed=617170)
    except ContractError as exc:assert 'INDEPENDENT_SOURCE_AND_FIT_ADMISSION_REQUIRED' in exc.code
    else:raise AssertionError('Real J admitted synthetic bytes')
    return dict(complete_pmfs=96,observed_games=0,weighted_ess=ess,O2_controls=controls,bundle_sha256=output['bundle']['content_hash'],real_mode_blocked=True)


def replay(a):
    code='''
import json,sys
from research.nba_p4_latest.fixture import build
from research.nba_p4_latest.benchmark import PARAMETERS
from v2.nba_joint.latest_upstream import prepare
from v2.nba_joint.integration_v2 import simulate_latest
r=prepare();x=list(build(r))
if sys.argv[1]=='reverse':
 for i in (4,5,6):x[i]=dict(reversed(list(x[i].items())))
y=simulate_latest(*x,upstream_root=r,evidence_mode='latest_synthetic_engineering',event_parameters=PARAMETERS,seed=617170)
print(json.dumps({'bundle':y['bundle']['content_hash'],'scenarios':y['scenario_hashes']},sort_keys=True))
'''
    rows=[]
    for seed,order in [('1','original'),('777773','reverse')]:
        r=subprocess.run([sys.executable,'-c',code,order],cwd=a.assembly,
            env=dict(os.environ,PYTHONPATH=str(a.assembly),PYTHONHASHSEED=seed,OPENBLAS_NUM_THREADS='1'),capture_output=True)
        assert r.returncode==0,r.stderr.decode()
        rows.append(dict(hash_seed=seed,input_dict_order=order,raw_stdout_sha256=sha(r.stdout),output=json.loads(r.stdout)))
    assert rows[0]['output']==rows[1]['output']
    return rows


def incompatibility(a):
    import mpmath as mp
    from research.nba_p4_latest.fixture import build
    from v2.nba_joint.latest_upstream import prepare,load_upstream
    mp.mp.dps=70
    root=prepare();x=build(root);p2,_=load_upstream(root)
    sc=x[2]['scenarios'][0];row=next(y for y in sc['players'] if y['player_id']=='espn:player:15')
    parameters={}
    for stat in ('points','threes'):
        r=p2.predict_conditional(x[4][stat],player_id=row['player_id'],role=x[6][row['player_id']],projected_exposure=row['minutes'],statistic=stat)
        assert r.abstain_reason is None
        d=r.parameters;family=x[4][stat].data['family']
        shape=mp.mpf(str(d['alpha'] if family=='S1' else d['dispersion']))
        mean=mp.mpf(str(d['rate_mean']))*mp.mpf(str(row['minutes']))
        probability=(mp.mpf(str(d['beta']))/(mp.mpf(str(d['beta']))+mp.mpf(str(row['minutes']))) if family=='S1' else shape/(shape+mean))
        parameters[stat]=dict(shape=str(shape),probability=str(probability),serialization_bound=d['tail_mass_upper_bound'])
    def tail(stat,threshold):
        p=parameters[stat]
        return mp.betainc(threshold,mp.mpf(p['shape']),0,1-mp.mpf(p['probability']),regularized=True)
    pt=tail('points',60);tt=tail('threes',20);gap=tt-pt
    assert gap>0 and gap>10*sum(mp.mpf(str(y['serialization_bound'])) for y in parameters.values())
    return dict(reference='P>=3*T almost surely implies Pr(P>=3*k)>=Pr(T>=k). High-precision incomplete-beta evaluation of the actual conditional negative-binomial kernels violates this necessary condition at k=20.',
        precision_decimal_digits=70,player_id=row['player_id'],scenario_id=sc['scenario_id'],points_tail_60=str(pt),threes_tail_20=str(tt),necessary_condition_gap=str(gap),parameters=parameters,
        classification='MATERIAL_VERSIONED_CONSTRAINED_LAW_REQUIRED_NOT_A_SOURCE_OR_SOFTWARE_CERTIFICATE',proposal_accepted=False)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--assembly',type=Path,required=True);ap.add_argument('--expected-assembly',default=ASSEMBLY);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--section',choices=['evidence','physical','scores','quarantine','cutoff','optimizer','native','joint','replay','incompatibility','all'],default='all');a=ap.parse_args()
    sys.path[:0]=[str(a.assembly),str(a.assembly/'tests/nba_architecture')]
    sections=['evidence','physical','scores','quarantine','cutoff','optimizer','native','joint','replay','incompatibility'] if a.section=='all' else [a.section]
    result={'schema':'NBA_P6_INDEPENDENT_NEW_CHECKS_V4','qa_source_sha256':sha(Path(__file__).read_bytes()),'assembly':a.expected_assembly,'synthetic_only':True,'historical_outcomes_accessed':False,'sections':{}}
    for name in sections:
        try:result['sections'][name]={'status':'PASS','result':globals()[name](a)}
        except Exception as exc:
            result['sections'][name]={'status':'FAIL','error':str(exc),'traceback':traceback.format_exc()}
        print(name,result['sections'][name]['status'],flush=True)
    result['all_pass']=all(x['status']=='PASS' for x in result['sections'].values())
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as handle:handle.write(encode(result))
    return int(not result['all_pass'])


if __name__=='__main__':raise SystemExit(main())
