#!/usr/bin/env python3
"""Independent P6 finite adversarial/oracle audit; run in an exact owner checkout.

Usage: PYTHONPATH=.:tests/nba_architecture python /path/to/this.py P1|P2|P3|P4|P5
Only QA, disposable synthetic inputs and supplied prior-source fixtures. No owner
implementation mutation, historical forecast scoring or historical weight fit.
"""
import copy
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback

ROWS=[]
NUMERICAL={}

def case(name, fn):
    try:
        details=fn()
        ROWS.append(dict(case=name,status='PASS',details=details))
    except Exception as exc:
        ROWS.append(dict(case=name,status='FAIL',error=type(exc).__name__,reason=str(exc),traceback=traceback.format_exc()))

def reject(fn, contains=None):
    try: fn()
    except (ValueError,TypeError,KeyError) as exc:
        code=getattr(exc,'code',str(exc))
        if contains: assert contains in str(code),(contains,str(code))
        return str(code)
    raise AssertionError('ACCEPTED_ADVERSARIAL_INPUT')

def reseal(x):
    from v2.nba_architecture.v2_contracts import seal
    return seal({k:v for k,v in x.items() if k!='content_hash'})

def cross_process(code):
    results=[]
    for seed in ['3','8357']:
        r=subprocess.run([sys.executable,'-c',code],env=dict(os.environ,PYTHONHASHSEED=seed),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        assert r.returncode==0,r.stderr.decode()
        results.append(r.stdout)
    assert results[0]==results[1],results
    return dict(stdout=results[0].decode().strip(),sha256=hashlib.sha256(results[0]).hexdigest(),python_hash_seeds=[3,8357])

def p1():
    from tests.nba_architecture.test_p1_remediation import official_fixture,nba_entry,repair_opponent,official_build,NBA_GAME
    from tests.nba_architecture.test_p1_history import make_entry,build,P1VaultTest
    from v2.nba_architecture.p1_evidence import prior_game_exposure,duration
    from v2.nba_architecture.p1_vault import OfficialOutcomeVault
    from v2.nba_architecture.v2_contracts import canonical,digest
    def raw_edit(b,fn):
        d=json.loads(b['raw']);fn(d);b['raw']=canonical(d);b['capture']['raw_sha256']=hashlib.sha256(b['raw']).hexdigest();return b
    def caps():
        r=[]
        for ot in [0,2,6]:
            cap=48+5*ot
            data=json.loads(repair_opponent(nba_entry(cap))['record']['payload'])
            h=prior_game_exposure(data,official_fixture(ot,cap))
            assert h['exact_minutes']==cap
            data['minutes']=cap+.125
            r.append(reject(lambda:prior_game_exposure(data,official_fixture(ot,cap+.125,exact=f'PT{cap}M07.5S')),'EXCEED_GAME_DURATION'))
        return r
    case('independent_fractional_exposure_caps_0_2_6_OT',caps)
    def rounding():
        d=json.loads(repair_opponent(nba_entry(0))['record']['payload'])
        h=prior_game_exposure(d,official_fixture(minutes=0,exact='PT00M29.999S'))
        assert 0<h['exact_minutes']<.5 and h['displayed_minutes']==0 and h['stats']['points']==11
        return [reject(lambda:prior_game_exposure(d,official_fixture(minutes=0,exact=x)),'ZERO_MINUTE_CREDIT_UNRESOLVED') for x in ['PT00M30.000S','PT00M00S']]
    case('rounded_display_strict_half_minute_boundary',rounding)
    def source_chain():
        a=official_fixture(); b=official_fixture(2,56)
        b['capture'].update(revision=3,supersedes_receipt_sha256=digest(a['capture']),retrieved_at='2026-11-16T20:00:00Z');b['prior']=[a]
        x=reject(lambda:duration(b,game_id=NBA_GAME),'REVISION_CHAIN')
        b['capture']['revision']=2;b['prior'][0]['raw']=b['prior'][0]['raw'].replace(b'11',b'12')
        y=reject(lambda:duration(b,game_id=NBA_GAME),'SOURCE_SHA_MISMATCH')
        return [x,y]
    case('orphan_third_revision_and_corrupted_ancestor_bytes',source_chain)
    def duplicate_player():
        b=raw_edit(official_fixture(),lambda d:d['game']['awayTeam']['players'].append(copy.deepcopy(d['game']['homeTeam']['players'][0])))
        d=json.loads(repair_opponent(nba_entry())['record']['payload'])
        return reject(lambda:prior_game_exposure(d,b),'PLAYER_TEAM_CONFLICT')
    case('same_official_player_on_both_competing_teams',duplicate_player)
    def stats():
        out=[]
        for bad in [{'fgm':4,'fga':3},{'rebounds':7,'oreb':5,'dreb':5},{'points':6,'rebounds':2,'assists':1,'pra':8}]:
            out.append(reject(lambda:build([make_entry(stats=bad)])))
        return out
    case('independent_shooting_rebound_and_PRA_corruptions',stats)
    def unrelated_orphan():
        with tempfile.TemporaryDirectory() as td:
            v=OfficialOutcomeVault(td);h=P1VaultTest()._put(v)
            P1VaultTest()._put(v,revision=2,supersedes_sha256=h['content_hash'],observed_at='2023-02-11T05:00:00Z')
            (Path(td)/(h['content_hash']+'.json')).unlink()
            return reject(lambda:v.outcome_status('nba:game:unrelated','nba:player:unrelated'),'REVISION_GAP')
    case('unrelated_vault_read_cannot_hide_orphan_correction',unrelated_orphan)
    def blocked_real():
        from scripts.nba_p1_build_pregame import execute
        r=Path('docs/nba_architecture/p1_remediation_20261117')
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'strict.json'
            result=reject(lambda:execute(r/'real_ws1_manifest.json',out,source_root=r,require_official_evidence=True),'OFFICIAL_SOURCE_EVIDENCE_REQUIRED')
            assert not out.exists()
            return dict(status='BLOCKED',code=result,note='Integrated case stops at P1. No target result retrieved.')
    case('authentic_integrated_case_stops_at_missing_P1_duration',blocked_real)

def p2():
    from tests.nba_s_family.test_statistical import histories,manifest,CUTOFF,SRC_HASH,pregame
    from v2.nba_s_family.model import fit,predict,conditional_pmf
    def separate_duration():
        rows=histories();rows[0]['minutes']=56;m=manifest();r='8'*64
        m[r]=dict(raw_sha256='9'*64,available_at='2022-10-08T00:00:00Z',status='P1_VERIFIED')
        m[SRC_HASH]['games'][rows[0]['game_id']].update(overtime_periods=2,duration_receipt_sha256=r)
        f=fit(rows,source_manifest=m,asof_cutoff_utc=CUTOFF,stat='points')
        assert r in f.data['source_receipts']
        rows[0]['minutes']=58.00001
        return reject(lambda:fit(rows,source_manifest=m,asof_cutoff_utc=CUTOFF,stat='points'),'HISTORICAL_EXPOSURE_PHYSICS')
    case('56_minute_two_OT_separate_duration_receipt_positive_and_overcap',separate_duration)
    def removed_witness():
        m=manifest();rows=histories();rows[0]['minutes']=56;del m[SRC_HASH]['games'][rows[0]['game_id']]['duration_receipt_sha256']
        return reject(lambda:fit(rows,source_manifest=m,asof_cutoff_utc=CUTOFF,stat='points'),'DURATION')
    case('two_OT_duration_receipt_missing_no_default',removed_witness)
    def cutoff():
        m=manifest();m[SRC_HASH]['available_at']='2022-10-10T00:00:00.000001Z'
        return reject(lambda:fit(histories(),source_manifest=m,asof_cutoff_utc=CUTOFF,stat='points'))
    case('one_microsecond_post_cutoff_source',cutoff)
    def target():
        rows=histories(); rows[0]['target_actual_minutes']=35
        return reject(lambda:fit(rows,source_manifest=manifest(),asof_cutoff_utc=CUTOFF,stat='points'))
    case('extra_target_actual_minutes_training_injection',target)
    def analytic_recurrence():
        from v2.nba_s_family.integration import full_count_law
        result=[]
        for fam in ['S1','S2']:
            f=fit(histories(),source_manifest=manifest(),asof_cutoff_utc=CUTOFF,stat='points',family=fam)
            _,_,a=conditional_pmf(f,player_id='espn:player:10',role='wing',opportunity=37.25)
            r=a['alpha'] if fam=='S1' else a['dispersion'];mu=37.25*a['rate_mean'];p=r/(r+mu)
            law=full_count_law(f,player_id='espn:player:10',role='wing',projected_exposure=37.25)
            probs=[p**r]
            for k in range(1,200):probs.append(probs[-1]*(k+r-1)/k*(1-p))
            error=max(abs(law.pmf(k)-v) for k,v in enumerate(probs))
            assert error<1e-12,error
            result.append(dict(family=fam,max_pmf_error=error,total_mass=sum(probs),mean=law.mean(),variance=law.var()))
        NUMERICAL['P2_recurrence']=result;return result
    case('independent_NB_recurrence_fractional_projected_minutes',analytic_recurrence)
    def stricter_target_cutoff():
        from tests.nba_s_family.test_statistical import opportunity_fixture
        from v2.nba_s_family.integration import joint_conditional
        p=pregame();p['training_cutoff_at']='2022-10-09T00:00:00Z';p=reseal(p);g,o=opportunity_fixture(p)
        f=fit(histories(),source_manifest=manifest(),asof_cutoff_utc=CUTOFF,stat='points')
        regular=predict(f,frozen_pregame=p,target_player_id='espn:player:10',role='wing',game_state=g,opportunity=o,conditioning='conditional_on_participation')
        assert regular.abstain_reason=='MODEL_AFTER_DATA_CUTOFF',regular.abstain_reason
        return reject(lambda:joint_conditional(f,pregame=p,game_state=g,opportunity=o,scenario_id=o['scenarios'][0]['scenario_id'],player_id='espn:player:10',team_id='espn:team:1',role='wing'),'CUTOFF')
    case('conditional_S_to_J_must_honor_P_training_cutoff_not_just_freeze',stricter_target_cutoff)


def p3():
    from test_p3_o_family import build,inputs
    from v2.nba_o_family import validate_sidecar,build_opportunity
    from v2.nba_o_bridge import bind_p1_priors
    from test_p3_boundaries import bound_inputs
    def false_cert():
        p,g,a=inputs();pid=next(iter(a));a[pid]['participation_basis']='verified_pregame_fit';a[pid]['scenario_participation_prior']=1.
        return reject(lambda:build_opportunity(p,g,a,model=g['model'],seed=11,home_team_id=p['team_ids'][0],home_team_source_receipt_sha256=p['sources'][0]['receipt_sha256']),'ATTESTATION_REQUIRED')
    case('probability_one_does_not_authenticate_participation_fit',false_cert)
    def bytes_clock():
        p,g,a,raw,r=bound_inputs();raw[r]=raw[r]+b'\n'
        return reject(lambda:bind_p1_priors(p,a,raw_sources=raw,home_team_id=p['team_ids'][0],home_receipt=r),'RAW_BYTES_MISMATCH')
    case('valid_JSON_whitespace_still_changes_raw_source_digest',bytes_clock)
    def balanced_tamper():
        p,g,o,s=build('O2');b=copy.deepcopy(s);rows=b['scenarios'][0]['players'];team=next(x['team_id'] for x in p['players'] if x['player_id']==rows[0]['player_id']); ids={x['player_id'] for x in p['players'] if x['team_id']==team};same=[x for x in rows if x['player_id'] in ids];same[0]['possession_share']+=.005;same[1]['possession_share']-=.005
        pool=b['scenarios'][0]['teams'][team]['projected_possessions']
        for x in same:x['projected_possession_opportunity']=x['possession_share']*pool
        return reject(lambda:validate_sidecar(reseal(b),p,g,o),'REPLAY_MISMATCH')
    case('balanced_resealed_shares_and_opportunities_fail_replay',balanced_tamper)
    def floor_gap():
        p,g,o,s=build('O2');b=copy.deepcopy(s);team=p['team_ids'][0];segs=b['scenarios'][0]['teams'][team]['lineup_segments'];segs[0]['start']+=.0001
        return reject(lambda:validate_sidecar(reseal(b),p,g,o))
    case('tiny_unwitnessed_opening_clock_interval',floor_gap)
    case('O_cross_process_hash_seed_independence',lambda:cross_process("from test_p3_o_family import build; p,g,o,s=build('O2'); print(o['content_hash'],s['content_hash'])"))

def p4():
    from research.nba_p4_integration.prepare import prepare
    from research.nba_p4_integration.fixture import build
    from research.nba_p4_integration.benchmark import PARAMETERS
    from v2.nba_joint.integration import simulate_integrated,load_upstream,validate_event_ledger
    from v2.nba_joint.p4 import scenario_pmfs
    root=prepare();x=build(root);result=simulate_integrated(*x,upstream_root=root,evidence_mode='pinned_contract_fixture',event_parameters=PARAMETERS,seed=371)
    def real():
        return reject(lambda:simulate_integrated(*x,upstream_root=root,event_parameters=PARAMETERS),'REAL_INTEGRATION_BLOCKED')
    case('synthetic_P1_VERIFIED_manifest_cannot_enable_real_mode',real)
    def floor():
        z=list(x);b=copy.deepcopy(x[3]);t=x[0]['team_ids'][0];b['scenarios'][0]['teams'][t]['lineup_segments'][0]['end']-=.001;z[3]=reseal(b)
        return reject(lambda:simulate_integrated(*z,upstream_root=root,evidence_mode='pinned_contract_fixture',event_parameters=PARAMETERS))
    case('shortened_five_on_floor_witness_with_unchanged_total_minutes',floor)
    def replay_reordered():
        z=list(x);z[4]=dict(reversed(list(x[4].items())));z[6]=dict(reversed(list(x[6].items())))
        other=simulate_integrated(*z,upstream_root=root,evidence_mode='pinned_contract_fixture',event_parameters=PARAMETERS,seed=371)
        assert other['bundle']==result['bundle'];return other['bundle']['content_hash']
    case('dictionary_order_cannot_change_joint_draws',replay_reordered)
    def pmfs():
        laws=scenario_pmfs(result,x[0],frozen_at='2026-11-16T23:03:00Z',seed=371); n=0
        for pid,stats in laws.items():
            for stat,d in stats.items():
                manual={}
                for sc in result['bundle']['scenarios']:
                    person=next(p for p in sc['players'] if p['player_id']==pid)
                    y=person['stats']['points']+person['stats']['rebounds']+person['stats']['assists'] if stat=='pra' else person['stats'][stat]
                    manual[y]=manual.get(y,0)+sc['weight']
                assert {k['value']:k['mass'] for k in d['pmf'] if k['mass']}==manual
                assert abs(sum(manual.values())-1)<1e-12;n+=1
        return dict(pmfs=n,scenario_paths=len(result['bundle']['scenarios']),official_games=0)
    case('independent_weighted_histograms_including_same_draw_PRA',pmfs)
    def distort():
        flags=[a['integration']['marginal_laws_preserved_exactly'] for a in result['audit_rows']]
        assert not any(flags)
        return dict(status='BLOCKED',faithful_conditional_law_propagation=False,reason='S1/S2 PMFs retained in audit; event generation projects means/shares. No source-backed distortion acceptance.')
    case('distributional_propagation_limit_preserved',distort)
    case('J_cross_process_hash_seed_independence',lambda:cross_process("from research.nba_p4_integration.prepare import prepare; from research.nba_p4_integration.fixture import build; from research.nba_p4_integration.benchmark import PARAMETERS; from v2.nba_joint.integration import simulate_integrated; r=prepare(); x=simulate_integrated(*build(r),upstream_root=r,evidence_mode='pinned_contract_fixture',event_parameters=PARAMETERS,seed=371); print(x['bundle']['content_hash'])"))

def p5():
    import numpy as np
    from tests.nba_c.test_p5_c_family import fixture
    from v2.nba_c import scores as s,experiment as e
    from v2.nba_c.calibration import calibration_summary
    def nested_outcome():
        row=fixture();row['pipelines']['S0']['model_inputs']={'actual_minutes':37,'target_game_outcome':{'points':0}}
        return reject(lambda:e.CachedCohort([row],authorization='SYNTHETIC_UNIT_TEST'),'OUTCOME')
    case('nested_target_result_and_actual_minutes_in_forecast_pipeline',nested_outcome)
    def tiny_future():
        row=fixture();row['pipelines']['S0']['model']={'source_available_at':'2022-10-20T17:00:00.000001Z'}
        return reject(lambda:e.CachedCohort([row],authorization='SYNTHETIC_UNIT_TEST'),'POST_FREEZE')
    case('nested_one_microsecond_postfreeze_evidence',tiny_future)
    def valid_guard():
        cache=e.CachedCohort([fixture()],authorization='SYNTHETIC_UNIT_TEST');assert cache.game_count==1
        row=fixture();row['source_profile']='historical_reconstruction'
        return [reject(lambda:e.CachedCohort([row],authorization='SYNTHETIC_UNIT_TEST'),'ONLY_SYNTHETIC'),reject(lambda:e.CachedCohort([fixture()]),'NOT_AUTHORIZED')]
    case('valid_preholdout_fixture_and_historical_authorization_guards',valid_guard)
    def math_scores():
        pmf={0:.17,2:.31,7:.29,19:.23}; ys=[0,2,5,23]; reports=[]
        for y in ys:
            cdf=0.;ref=0.
            for k in range(max(max(pmf),y)+1):cdf+=pmf.get(k,0);ref+=(cdf-int(y<=k))**2
            got=s.diagnostics(pmf,y,seed=17,central=.8,tail_threshold=7)
            assert abs(got['crps']-ref)<1e-11
            mu=sum(k*p for k,p in pmf.items());assert abs(got['absolute_error']-abs(mu-y))<1e-12
            assert abs(got['squared_error']-(mu-y)**2)<1e-11
            assert got['zero_predicted']==.17 and got['tail_predicted']==.52
            assert s.randomized_pit(pmf,y,u=.43)==sum(p for k,p in pmf.items() if k<y)+.43*pmf.get(y,0)
            expected=-math.log(pmf[y]) if y in pmf else math.inf;assert got['nlpd']==expected
            reports.append(dict(y=y,CRPS=ref,NLPD=got['nlpd'],predictive_mean=mu,absolute_error=got['absolute_error']))
        NUMERICAL['sparse_full_count_scores']=reports;return reports
    case('independent_sparse_CDF_CRPS_NLPD_mean_error_zero_tail_PIT',math_scores)
    def joint():
        law=[((0,1,4),.2),((2,5,1),.35),((8,3,0),.45)];y=(1,4,2);dist=lambda a,b:math.sqrt(sum((i-j)**2 for i,j in zip(a,b)))
        es=sum(p*dist(a,y) for a,p in law)-sum(p*q*dist(a,b) for a,p in law for b,q in law)/2
        weights={(0,1):.4,(0,2):1.3,(1,2):.7};vs=sum(w*(abs(y[i]-y[j])**.5-sum(p*abs(a[i]-a[j])**.5 for a,p in law))**2 for (i,j),w in weights.items())
        assert abs(s.energy_score(law,y)-es)<1e-12;assert abs(s.variogram_score(law,y,pair_weights=weights)-vs)<1e-12
        NUMERICAL['joint_scores']=dict(ES=es,VS_05=vs);return NUMERICAL['joint_scores']
    case('independent_unequal_weight_three_dimensional_ES_VS',joint)
    def unnormalized():return reject(lambda:s.crps({0:.17,2:.31,7:.29,19:.2300001},2),'NORMALIZED')
    case('small_non_normalization_not_silently_renormalized',unnormalized)
    def optimizer():
        rng=np.random.default_rng(731);rows=[]
        for i in range(8):
            row=fixture(stat='points' if i<4 else 'rebounds',date=f'2022-09-{10+i:02d}T00:00:00Z',game=f'synthetic:qa:{i}',actual=i%3)
            for item in row['pipelines'].values():item['pmf']=dict(zip([0,1,4],map(float,rng.dirichlet([1.7,.9,1.2]))))
            rows.append(row)
        # Independent exhaustive active-face KKT oracle. CDFs are assembled from
        # primitive fixture masses, never read from the owner's cache/Gram.
        def reference(sub,lam,anchor):
            A=[];b=[]
            names=sorted(sub[0]['pipelines'])
            for row in sub:
                for k in range(4):A.append([sum(v for y,v in row['pipelines'][n]['pmf'].items() if y<=k) for n in names]);b.append(float(row['actual']<=k))
            A=np.array(A);b=np.array(b);Q=A.T@A/len(sub)+lam*np.eye(3);h=A.T@b/len(sub)+lam*np.array(anchor);best=None
            for size in range(1,4):
                for active in itertools.combinations(range(3),size):
                    ix=list(active);M=np.block([[Q[np.ix_(ix,ix)],np.ones((size,1))],[np.ones((1,size)),np.zeros((1,1))]])
                    sol=np.linalg.solve(M,np.r_[h[ix],1]);w=np.zeros(3);w[ix]=sol[:-1]
                    if min(w)<-1e-10:continue
                    val=np.mean((A@w-b)**2)*4+lam*sum((w-np.array(anchor))**2)
                    if best is None or val<best[0]:best=(float(val),w)
            return best[1]
        names=sorted(rows[0]['pipelines']);anchor=[.2,.5,.3];lam=.17;c=e.CachedCohort(rows,authorization='SYNTHETIC_UNIT_TEST')
        got=e.w2_global(c,lam=lam,prior=anchor);ref=reference(rows,lam,anchor);err=float(max(abs(np.array([got[k] for k in names])-ref)));assert err<2e-6,(got,ref,err)
        ws=e.w3_by_stat(rows,global_weights=got,lam=.61,min_games=3);errors={}
        for stat in ['points','rebounds']:
            ref3=reference([r for r in rows if r['stat']==stat],.61,[got[k] for k in names]);errors[stat]=float(max(abs(np.array([ws[stat][k] for k in names])-ref3)));assert errors[stat]<2e-6
        NUMERICAL['optimizer']=dict(W2=got,W2_reference=ref.tolist(),W2_max_error=err,W3=ws,W3_max_errors=errors,synthetic_games=8,historical_fitting=False);return NUMERICAL['optimizer']
    case('independent_active_face_KKT_W2_W3_reference',optimizer)
    def ess():
        scored=[]
        for game,y in [('synthetic:A',0),('synthetic:B',2)]:
            d=s.diagnostics({0:.4,2:.6},y,seed=1);scored.append(dict(d,scored=True,game_id=game))
        reports=[]
        for n in [1,5000,20000]:
            r=calibration_summary([copy.deepcopy(x) for x in scored for _ in range(n)])
            assert r['n_distinct_games']==2 and r['n_forecast_rows']==2*n
            reports.append(dict(replication=n,n_distinct_games=r['n_distinct_games'],n_forecast_rows=r['n_forecast_rows'],mean_crps=r['mean_crps']))
        assert len({r['mean_crps'] for r in reports})==1
        return reports
    case('replicated_paths_cannot_inflate_distinct_game_accounting',ess)
    def false_mc_ess():
        from v2.nba_architecture.v2_contracts import validate_distribution
        bundle=json.loads(Path('docs/nba_architecture/completion_20261116/coherent_joint.json').read_text())
        d=copy.deepcopy(bundle['points']);d['numerical']['effective_sample_size']=20000.
        return reject(lambda:validate_distribution(reseal(d),bundle['pregame'],bundle['scenarios']),'MC_EFFECTIVE_SAMPLE_SIZE')
    case('forged_twenty_thousand_ESS_on_two_joint_paths_rejected',false_mc_ess)

    case('C_cross_process_randomized_PIT_hash_seed_independence',lambda:cross_process("from v2.nba_c.scores import diagnostics; import json; print(json.dumps(diagnostics({0:.17,2:.31,7:.29,19:.23},7,seed=871),sort_keys=True))"))

if __name__=='__main__':
    family=sys.argv[1];globals()[family.lower()]()
    output=dict(schema='P6_G1_REMEDIATION_ADVERSARIAL_V3',family=family,owner_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),cases=ROWS,numerical_references=NUMERICAL,synthetic_only=True)
    def finite_json(value):
        if isinstance(value,float) and not math.isfinite(value): return 'Infinity' if value>0 else '-Infinity' if value<0 else 'NaN'
        if isinstance(value,dict):return {k:finite_json(v) for k,v in value.items()}
        if isinstance(value,(list,tuple)):return [finite_json(v) for v in value]
        return value
    print(json.dumps(finite_json(output),sort_keys=True,indent=2,allow_nan=False))
    sys.exit(2 if any(r['status']=='FAIL' for r in ROWS) else 0)
