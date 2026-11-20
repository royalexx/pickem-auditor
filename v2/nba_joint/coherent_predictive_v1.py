"""One opportunity generative kernel, shared S4 and J projections.

Physics uses the unchanged audited chronological path. No independent points
or made-threes posterior is fitted, rejected, clipped or coupled afterwards.
Finite scenario estimates are never called full population count support.
"""
import gzip
import io
import math
from pathlib import Path
import numpy as np
from scipy.stats import beta as beta_distribution
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.subset_contract_v1 import strict_json
from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_joint.common import rng_for
from v2.nba_joint.residual_opportunity_v1 import draw_team,audit_team
from v2.nba_joint.residual_events_v1 import event_path,PathExecutionFailure,FixedExecutionFailure
from v2.nba_joint.residual_audit_v1 import audit_path

STATS=('points','rebounds','assists','threes','pr','pa','ra','pra')


def draw_parameters(spec,rng,*,capture=None):
    capture={} if capture is None else capture
    require(set(spec['rates'])=={'assists','rebounds'} and 'ft_non3_point_share' not in spec,
        'COHERENT_INDEPENDENT_POINTS_THREES_OR_FT_SHARE_FORBIDDEN')
    require(set(spec['attempt_posteriors'])=={'twoPA','threePA','FTA','TO'},'COHERENT_ATTEMPT_COMPONENTS')
    def gamma(v):
        require(all(type(v[k]) in (int,float) and math.isfinite(v[k]) and v[k]>0 for k in ('alpha','beta')),
            'COHERENT_GAMMA_PARAMETERS')
        x=float(rng.gamma(v['alpha'],1/v['beta']));require(math.isfinite(x) and x>0,'COHERENT_GAMMA_NUMERIC');return x
    def beta(v):
        require(all(type(v[k]) in (int,float) and math.isfinite(v[k]) and v[k]>0 for k in ('alpha','beta')),
            'COHERENT_BETA_PARAMETERS')
        x=float(rng.beta(v['alpha'],v['beta']));require(math.isfinite(x) and 0<x<1,'COHERENT_BETA_NUMERIC');return x
    attempts={};capture['attempt_rates']=attempts
    for key,value in spec['attempt_posteriors'].items():attempts[key]=gamma(value)
    probabilities={};capture['conversion_probabilities']=probabilities
    for key in ('conversion2','conversion3','conversion_ft'):probabilities[key]=beta(spec[key])
    p2,p3,pft=(probabilities[k] for k in ('conversion2','conversion3','conversion_ft'))
    non3=math.fsum((2*attempts['twoPA']*p2,attempts['FTA']*pft));three=attempts['threePA']*p3
    points=math.fsum((3*three,non3));ft_share=attempts['FTA']*pft/non3
    capture['derived_interface']=dict(non3=non3,points=points,threes=three,ft_share=ft_share)
    require(all(math.isfinite(x) and x>0 for x in (points,non3,three)) and 0<ft_share<1,'COHERENT_DERIVED_RATE_NUMERIC')
    params=dict(rates=dict(points=points,threes=three,turnovers=attempts['TO'],
        **{k:gamma(v) for k,v in spec['rates'].items()}),p2=p2,p3=p3,pft=pft,ft_share=ft_share,
        attempt_rates=attempts,points_and_threes_derived_not_independently_drawn=True)
    # The unchanged event selector must recover the same attempted-shot rates.
    recovered=(params['rates']['threes']/p3,(points-3*three)*(1-ft_share)/(2*p2),
        (points-3*three)*ft_share/pft)
    require(all(math.isclose(x,y,rel_tol=1e-10,abs_tol=0.) for x,y in
        zip(recovered,(attempts['threePA'],attempts['twoPA'],attempts['FTA']))),
        'COHERENT_SELECTOR_ROUNDTRIP_UNRESOLVED')
    return params


def _fixed_scenario(model,seed,index,capture):
    rng=rng_for(seed,model['target'],index,'coherent-fixed-G-O-components/1')
    players=model['named_players'];teams=sorted({p['team_id'] for p in players})
    require(len(teams)==2 and len({p['player_id'] for p in players})==14,'COHERENT_MODEL_POPULATION')
    ots={(p['minutes']['ot_probability'],p['minutes']['ot_continuation']) for p in players}
    require(len(ots)==1,'COHERENT_SHARED_OT')
    p,q=next(iter(ots));k=int(rng.geometric(1-q)) if rng.random()<p else 0
    length=48+5*k;draws={};actors={}
    capture.update(index=index,seed=seed,game_id=model['target'],overtime_count=k,length=length,O=draws,actors=actors)
    for team in teams:
        group=[x for x in players if x['team_id']==team];byid={x['player_id']:x for x in group}
        d=draw_team(group,length,rng);audit_team(d,length);draws[team]=d;actors[team]=[];residual=None
        for i,identity in enumerate(d['actors']):
            pending={};capture['pending_actor']=dict(team_id=team,index=i,identity=identity,parameter_draw=pending)
            if identity['player_id']:params=draw_parameters(byid[identity['player_id']],rng,capture=pending)
            else:
                if residual is None:residual=draw_parameters(model['residual_groups'][team],rng,capture=pending)
                params=residual.copy()
            actors[team].append(dict(identity=identity,index=i,**params))
    pace=float(rng.gamma(model['pace']['shape'],model['pace']['scale']))
    require(math.isfinite(pace) and pace>0,'COHERENT_PACE_NUMERIC')
    ep={key:float(rng.beta(v['alpha'],v['beta'])) for key,v in model['events'].items()}
    require(all(math.isfinite(x) and 0<x<1 for x in ep.values()),'COHERENT_EVENT_PROXY_NUMERIC')
    return dict(schema='coherent-fixed-G-O-components/1',index=index,seed=seed,game_id=model['target'],
        overtime_count=k,length=length,teams=teams,O=draws,actors=actors,pace=pace,event_probabilities=ep,
        rate_rejections=[],independent_points_threes_rejection=False,genuine_participation_probability=None,
        complete_legal_roster_claim=False)


def fixed_scenario(model,seed,index):
    partial={}
    try:return _fixed_scenario(model,seed,index,partial)
    except (ValueError,TypeError,KeyError) as exc:raise FixedExecutionFailure(exc,partial) from exc


def generate(model,cohort,trace_dir,*,seed=20261120,n=64,path_budget=4096,event_budget=4096):
    require(type(seed) is int and type(n) is int and n>0 and type(path_budget) is int and path_budget>0 and
        type(event_budget) is int and event_budget>0,'COHERENT_EXECUTION_BUDGET')
    require(cohort['game_id']==model['target'] and len(cohort['frozen_candidates'])==35 and
        len({p['player_id'] for p in cohort['frozen_candidates']})==35,'COHERENT_FROZEN_COHORT')
    candidates={p['player_id']:p['team_id'] for p in cohort['frozen_candidates']}
    require(all(candidates.get(p['player_id'])==p['team_id'] for p in model['named_players']),
        'COHERENT_MODEL_COHORT_TEAM_JOIN')
    root=Path(trace_dir);root.mkdir(parents=True,exist_ok=False);scenarios=[];failed=[];json_total=gzip_total=0
    for index in range(n):
        fixed=None;proposals=[];accepted=None;error=None;partial_fixed=None
        try:
            fixed=fixed_scenario(model,seed,index)
            for attempt in range(path_budget):
                try:proposal=event_path(fixed,seed,attempt,event_budget=event_budget)
                except PathExecutionFailure as exc:proposal=dict(status='REJECT_EXECUTION',error=str(exc),partial_path=exc.partial)
                raw=canonical(proposal);compressed=gzip.compress(raw,compresslevel=9,mtime=0);name=f's{index:04d}-p{attempt:05d}.json.gz'
                json_total+=len(raw);gzip_total+=len(compressed)
                if len(raw)>2097152 or len(compressed)>524288 or json_total>2147483648 or gzip_total>268435456:
                    proposals.append(dict(attempt=attempt,status='REJECT_TRACE_RESOURCE_CAP',
                        json_raw_sha256=digest(raw),json_bytes=len(raw),gzip_raw_sha256=digest(compressed),gzip_bytes=len(compressed),
                        source_regeneration=dict(seed=seed,scenario=index,attempt=attempt),raw_persisted=False))
                    error='COHERENT_TRACE_RESOURCE_CAP';break
                (root/name).write_bytes(compressed)
                proposals.append(dict(attempt=attempt,path=name,status=proposal['status'],
                    gzip_raw_sha256=digest(compressed),json_raw_sha256=digest(raw),json_bytes=len(raw),gzip_bytes=len(compressed)))
                if proposal['status']=='ACCEPTED_PATH_PROPOSAL':
                    audit_path(fixed,proposal);accepted=proposal;break
                if proposal['status']=='REJECT_EXECUTION':break
        except FixedExecutionFailure as exc:error=str(exc);partial_fixed=exc.partial
        except (ValueError,TypeError,KeyError) as exc:error=str(exc)
        if accepted is None or error:
            failed.append(dict(index=index,error=error or 'COHERENT_PATH_BUDGET_EXHAUSTED'))
        scenarios.append(dict(fixed=fixed,partial_fixed=partial_fixed,index=index,proposals=proposals,accepted=accepted,error=error))
    bank=dict(schema='shared-coherent-S4-J-bank/1',model_raw_sha256=digest(canonical(model)),cohort=cohort,
        seed=seed,scenario_denominator=n,scenarios=scenarios,failed=failed,status='FAILED_WHOLE_RUN' if failed else 'ENGINEERING_SAMPLE',
        path_budget=path_budget,event_budget=event_budget,scenarios_dropped=0,
        conditioning='ALL14_NAMED_PARTICIPATE_UNDER_DECLARED_PRIOR_NOT_IDENTIFIED_Q',
        statistical_law='S4_IS_J_PUSHFORWARD_NOT_AN_INDEPENDENT_VOTE',population_support='NONNEGATIVE_INTEGERS_NOT_TRUNCATED_TO_EMPIRICAL_MAXIMUM',
        finite_execution_failure_can_depend_on_latent_state=True,success_conditioning_not_a_convergence_certificate=True,
        trace_json_bytes=json_total,trace_gzip_bytes=gzip_total,new_family_zero_sensitivity='PENDING_NOT_VALIDATED_BY_OLD_S1_GRID',
        genuine_participation_probability=None,historical_validation=False,release=False)
    return dict(bank,payload_sha256=digest(canonical(bank)))


def validate_bank(bank,trace_dir=None,model=None):
    require(digest(canonical({k:v for k,v in bank.items() if k!='payload_sha256'}))==bank['payload_sha256'],'COHERENT_BANK_PAYLOAD')
    require(bank['status']=='ENGINEERING_SAMPLE' and not bank['failed'] and
        len(bank['scenarios'])==bank['scenario_denominator'],'COHERENT_FAILED_OR_DROPPED_BANK')
    require(model is None or digest(canonical(model))==bank['model_raw_sha256'],'COHERENT_BANK_MODEL_BYTES')
    candidates={p['player_id']:p['team_id'] for p in bank['cohort']['frozen_candidates']}
    require(len(candidates)==len(bank['cohort']['frozen_candidates'])==35,'COHERENT_BANK_CANDIDATE_DENOMINATOR')
    json_total=gzip_total=0;named_reference=None
    for i,s in enumerate(bank['scenarios']):
        require(s['index']==s['fixed']['index']==i and s['error'] is None and s['accepted'] is not None,'COHERENT_SCENARIO_JOIN')
        require(s['fixed']['game_id']==bank['cohort']['game_id'],'COHERENT_SCENARIO_GAME_JOIN')
        named_items=[(a['identity']['player_id'],team) for team,actors in s['fixed']['actors'].items()
            for a in actors if a['identity']['player_id']]
        named=dict(named_items)
        require(len(named_items)==len(named)==14 and all(candidates.get(pid)==team for pid,team in named.items()),'COHERENT_BANK_PLAYER_TEAM_JOIN')
        if named_reference is None:named_reference=named
        else:require(named_reference==named,'COHERENT_CHANGING_NAMED_POPULATION')
        if model is not None:require(canonical(fixed_scenario(model,bank['seed'],i))==canonical(s['fixed']),'COHERENT_FIXED_HANDOFF')
        require(bool(s['proposals']) and s['proposals'][-1]['status']==s['accepted']['status']=='ACCEPTED_PATH_PROPOSAL' and
            all(r['status']=='REJECT_OT_PATTERN' for r in s['proposals'][:-1]),'COHERENT_REJECTION_ANCESTRY')
        audit_path(s['fixed'],s['accepted'])
        if trace_dir is not None:
            for j,r in enumerate(s['proposals']):
                require(r['attempt']==j and r['path']==f's{i:04d}-p{j:05d}.json.gz','COHERENT_TRACE_IDENTITY')
                require(type(r['json_bytes']) is int and 0<r['json_bytes']<=2097152 and
                    type(r['gzip_bytes']) is int and 0<r['gzip_bytes']<=524288,'COHERENT_TRACE_BYTE_CAP')
                json_total+=r['json_bytes'];gzip_total+=r['gzip_bytes']
                require(json_total<=2147483648 and gzip_total<=268435456,'COHERENT_TRACE_TOTAL_CAP')
                packed=(Path(trace_dir)/r['path']).read_bytes()
                require(digest(packed)==r['gzip_raw_sha256'] and len(packed)==r['gzip_bytes'],'COHERENT_TRACE_BYTES')
                require(packed[:3]==b'\x1f\x8b\x08' and packed[3]==0 and packed[4:8]==b'\0'*4 and packed[8]==2,
                    'COHERENT_GZIP_FORMAT')
                with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:raw=stream.read(2097153)
                require(digest(raw)==r['json_raw_sha256'] and len(raw)==r['json_bytes'],'COHERENT_TRACE_JSON')
                value=strict_json(raw);require(value['status']==r['status'],'COHERENT_TRACE_STATUS')
                if j==len(s['proposals'])-1:require(canonical(value)==canonical(s['accepted']),'COHERENT_ACCEPTED_TRACE_JOIN')
    declared_json=sum(r['json_bytes'] for s in bank['scenarios'] for r in s['proposals'])
    declared_gzip=sum(r['gzip_bytes'] for s in bank['scenarios'] for r in s['proposals'])
    require(bank['trace_json_bytes']==declared_json and bank['trace_gzip_bytes']==declared_gzip,
        'COHERENT_TRACE_TOTAL_RECEIPTS')
    if trace_dir is not None:require(json_total==declared_json and gzip_total==declared_gzip,'COHERENT_TRACE_TOTAL_ACTUAL_BYTES')
    return dict(scenarios=len(bank['scenarios']),violations=0,all_physics_unchanged=True)


def rows(bank):
    validate_bank(bank);samples={}
    for s in bank['scenarios']:
        for team,actors in s['fixed']['actors'].items():
            for a in actors:
                pid=a['identity']['player_id']
                if pid:
                    for stat in STATS:samples.setdefault((pid,stat),[]).append(s['accepted']['counts'][team][a['index']][stat])
    result=[]
    for p in bank['cohort']['frozen_candidates']:
        for stat in STATS:
            values=samples.get((p['player_id'],stat))
            require(values is None or len(values)==bank['scenario_denominator'],'COHERENT_EXACT_ONE_VALUE_PER_SCENARIO')
            result.append(dict(player_id=p['player_id'],team_id=p['team_id'],statistic=stat,samples=values,
                status='SHARED_S4_J_ESTIMATE' if values is not None else 'ABSTAINED_SOURCE_OR_MINUTE_MODEL',
                inherited_abstention_reasons=bank['cohort'].get('inherited_abstention_reasons',{}).get(p['player_id']) if values is None else None,
                scenario_ids=list(range(bank['scenario_denominator'])) if values is not None else None,
                genuine_participation_probability=None,legal_eligibility=None))
    require(len(result)==280 and sum(r['samples'] is not None for r in result)==112,'COHERENT_ALL_REQUESTS_RETAINED')
    return result


def _query(row,bank_payload,*,player_id,statistic,kind,value,channel='S4'):
    require(channel in ('S4','J') and statistic in STATS and kind in ('pmf','cdf','oup'),'COHERENT_QUERY_SCOPE')
    require(row is not None,'COHERENT_UNKNOWN_PLAYER')
    if row['samples'] is None:return dict(status='ABSTAINED',estimate=None,samples=None)
    require(type(value) in (int,float) and math.isfinite(value) and value>=0 and
        (kind=='oup' or type(value) is int),'COHERENT_QUERY_VALUE')
    x=row['samples'];n=len(x)
    hits={'pmf':[sum(a==value for a in x)],'cdf':[sum(a<=value for a in x)],
        'oup':[sum(a<value for a in x),sum(a==value for a in x),sum(a>value for a in x)]}[kind]
    alpha=.05/len(hits)
    intervals=[dict(lower=0. if h==0 else float(beta_distribution.ppf(alpha/2,h,n-h+1)),
        upper=1. if h==n else float(beta_distribution.ppf(1-alpha/2,h+1,n-h))) for h in hits]
    return dict(status='MONTE_CARLO_ESTIMATE_NOT_CERTIFIED_POPULATION_PROBABILITY',bank_payload_sha256=bank_payload,
        player_id=player_id,statistic=statistic,kind=kind,value=value,estimate=[h/n for h in hits],hits=hits,n=n,
        componentwise_MC_95_family_intervals=intervals,
        interval_assumptions='IID_IDEAL_KERNEL_SAMPLES_NOT_PROVEN_BY_FINITE_EXECUTION_OR_COMPLETED_RUN_SELECTION',
        intervals_simultaneous_across_queries=False,population_error_guarantee=False,
        validation_scope='STRUCTURAL_SHARED_BANK_ONLY_SOURCE_MODEL_CLOCK_ADMISSION_IS_SEPARATE',
        population_exact_zero_claim=False,count_support_truncated=False,S4_J_same_measure=True,independent_vote=False,
        score_admitted=False)


class SharedForecast:
    """Validate once; retain only immutable sample tuples for public queries.

    This numerical view grants no source/model/forecast admission. The issued
    artifact reader separately verifies exact independently reviewed roots.
    """
    def __init__(self,bank):
        self._payload=bank['payload_sha256']
        self._rows={(r['player_id'],r['statistic']):dict(r,samples=tuple(r['samples']) if r['samples'] is not None else None)
            for r in rows(bank)}

    def query(self,*,player_id,statistic,kind,value,channel='S4'):
        return _query(self._rows.get((player_id,statistic)),self._payload,
            player_id=player_id,statistic=statistic,kind=kind,value=value,channel=channel)


def query(bank,**kwargs):return SharedForecast(bank).query(**kwargs)
