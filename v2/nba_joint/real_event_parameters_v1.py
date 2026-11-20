"""Closed-gate prospective working priors for a NEW residual-team J family.

These source-derived working priors do not claim to be the posterior of the
constrained event process, or to preserve original S1/S3 predictive marginals.
"""
from datetime import datetime,timezone
from pathlib import Path
import math
import re
import subprocess
import numpy as np
from v2.nba_s_family import model as native
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.subset_contract_v1 import strict_json
from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_architecture.prospective_s_sources_v1 import build_dataset,next_data
from v2.nba_architecture.pbp_evidence_v1 import read_population
from v2.nba_architecture.full_predictive_replay_v2 import read_issued_forecast
from v2.nba_opportunity import utc

PREFIT_APPROVAL_SHA=None
S3_ADMISSION_SHA='266096e230201ba65a4ea1f68f85e4bd7f76c0acef46ec6fe7a4f55a46e2111b'
FULL_ADMISSION_SHA='dd1e1b2b0663c4d889257cc17cceb160ea56df1c497f7bfb9046df96e3dfb2b2'
J_CARD_SHA='3a333aadf9061cf72d497c23a1576d02d9c9543c4907b5e0ff30c5f787b4e425'
DATASET_SHA='e5cb76ef446d6651b718c6279367a7078ffa86f01b621cfbfd9c7b4d74adbd1d'
NATIVE_SHA='a63a469d8df74f6e6f82c7480ee289da443452dd62f603859629a5d821d28cd6'


def _now():return datetime.now(timezone.utc).isoformat()


def _moments(rows,key):
    def value(r):
        c=r['official_counts']
        return c['fieldGoalsMade']-c['threePointersMade'] if key=='two_made' else (
            c['fieldGoalsAttempted']-c['threePointersAttempted'] if key=='two_attempts' else c[key])
    return math.fsum(value(r) for r in rows)


def _conversion(own,peers,made,attempts):
    pn=_moments(peers,attempts);require(pn>0,'J_EVENT_CONVERSION_PEERS')
    pm=_moments(peers,made);q=pm/pn
    om,on=_moments(own,made),_moments(own,attempts)
    require(0<=pm<=pn and 0<=om<=on,'J_EVENT_CONVERSION_SUPPORT')
    return dict(alpha=.5+40*q+om,beta=.5+40*(1-q)+on-om,
        working_prior_attempts=40.,own_attempts=on,own_makes=om,peer_attempts=pn,peer_makes=pm)


def fit_event_parameters(*,approval_path,full_forecast_raw,parent_raw,full_replay_inputs,
        original_raw_dir,spec_path,policy_path,pbp_raw_dir,pbp_population_path,
        s3_path,s3_receipt_path,s3_admission_path,full_admission_path,j_card_path,output):
    require(PREFIT_APPROVAL_SHA is not None,'J_EVENT_PREFIT_REVIEW_CLOSED')
    require(digest(Path(approval_path).read_bytes())==PREFIT_APPROVAL_SHA,'J_EVENT_PREFIT_BYTES')
    require(digest(Path(s3_admission_path).read_bytes())==S3_ADMISSION_SHA and
        digest(Path(full_admission_path).read_bytes())==FULL_ADMISSION_SHA,'J_EVENT_UPSTREAM_ADMISSIONS')
    require(digest(Path(j_card_path).read_bytes())==J_CARD_SHA,'J_EVENT_PREREGISTERED_CARD')
    require(digest(Path(native.__file__).read_bytes())==NATIVE_SHA,'J_EVENT_NATIVE_CODE')
    read_issued_forecast(full_forecast_raw,parent_raw,**full_replay_inputs)
    full=strict_json(full_forecast_raw);parent=strict_json(parent_raw)
    full_admission=strict_json(Path(full_admission_path).read_bytes())
    require(digest(Path(pbp_population_path).read_bytes())==full_admission['population_raw_sha256'],
        'J_EVENT_EXACT_ADMITTED_PBP_POPULATION')
    data=build_dataset(original_raw_dir,spec_path,policy_path)
    require(data['payload_sha256']==DATASET_SHA,'J_EVENT_OLD_SOURCE_DATASET')
    facts=read_population(pbp_raw_dir,pbp_population_path,original_raw_dir)
    require(facts['payload_sha256']==full['law_payload']['evidence_payload_sha256'],
        'J_EVENT_EXACT_ADMITTED_PBP_FACTS')
    require(facts['game_denominator']==20 and facts['rejected_games']==0 and
        all(r['facts']['all_credited_event_counts_reconciled'] for r in facts['rows']), 'J_EVENT_PBP_SOURCE_FACTS')
    s3a=strict_json(Path(s3_admission_path).read_bytes());s3raw=Path(s3_path).read_bytes()
    require(digest(s3raw)==s3a['artifact_raw_sha256'] and
        digest(Path(s3_receipt_path).read_bytes())==s3a['fit_receipt_raw_sha256'],'J_EVENT_S3_BYTES')
    fitted=native.FittedS(s3raw)
    verification=native.fit(data['histories']['threes'],asof_cutoff_utc=data['data_cutoff_at'],
        source_manifest=data['source_manifest'],stat='threes',family='S3',
        hyperparameters=dict(prior_minutes=180.,prior_attempts=40.,dispersion=12.,min_player_games=2),seed=20261120)
    require(verification.payload==s3raw,'J_EVENT_S3_BYTE_REPLAY')
    included=[r for r in data['records'] if r['fit_included']]
    require(len(included)==456,'J_EVENT_ORDINARY_SOURCE_POOL')
    named={r['player_id']:r for r in full['law_payload']['rows'] if r['model']}
    require(len(named)==14 and set(named)==set(s3a['exact_current_target_role_map']),'J_EVENT_NAMED_ROLE_POPULATION')
    minute_rows={r['player_id']:r for r in parent['minutes']}
    started=_now()
    cutoff=strict_json(Path(pbp_population_path).read_bytes())['frozen_at']
    approval=strict_json(Path(approval_path).read_bytes())
    require(max(map(utc,(cutoff,s3a['admitted_at'],full['forecast_at'],
        full_admission['model_admitted_at'],approval['decided_at'])))<=utc(started),
        'J_EVENT_PRE_SOURCE_OR_MODEL_OR_REVIEW_CLOCK')
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    players=[]
    for pid,row in sorted(named.items()):
        role=s3a['exact_current_target_role_map'][pid]
        own=[r for r in included if r['player_id']==pid]
        peers=[r for r in included if r['player_id']!=pid and r['role']==role]
        require(len(own)>=5 and bool(peers),'J_EVENT_NAMED_HISTORY')
        prediction=native.predict_conditional(fitted,player_id=pid,role=role,projected_exposure=1,statistic='threes')
        require(prediction.abstain_reason is None,'J_EVENT_S3_PUBLIC_ABSTENTION')
        conversion3={k:prediction.parameters[k] for k in ('alpha','beta')}
        parent_stats={r['statistic']:r['forecast']['parameters'] for r in parent['rows'] if r['player_id']==pid and r['forecast']}
        require(set(parent_stats)=={'points','rebounds','assists','threes'},'J_EVENT_S1_PARAMETER_POPULATION')
        rates={k:{key:p[key] for key in ('alpha','beta')} for k,p in parent_stats.items()}
        exposure=math.fsum(r['exact_seconds']/60 for r in own)
        peer_exposure=math.fsum(r['exact_seconds']/60 for r in peers)
        peer_turnovers=_moments(peers,'turnovers')/peer_exposure
        rates['turnovers']=dict(alpha=.5+180*peer_turnovers+_moments(own,'turnovers'),beta=181.+exposure)
        peer_non3=2*_moments(peers,'two_made')+_moments(peers,'freeThrowsMade')
        require(peer_non3>0,'J_EVENT_FT_POINT_SHARE_SOURCE')
        share=_moments(peers,'freeThrowsMade')/peer_non3
        ft_share=dict(alpha=.5+40*share+_moments(own,'freeThrowsMade'),
            beta=.5+40*(1-share)+2*_moments(own,'two_made'),
            unit='POINT_CREDIT_WORKING_PRIOR_NOT_INDEPENDENT_BERNOULLI_EVIDENCE')
        players.append(dict(player_id=pid,name=row['name'],team_id=row['team_id'],role=role,
            minutes=minute_rows[pid]['forecast']['distribution'],rates=rates,
            conversion3=conversion3,conversion2=_conversion(own,peers,'two_made','two_attempts'),
            conversion_ft=_conversion(own,peers,'freeThrowsMade','freeThrowsAttempted'),
            ft_non3_point_share=ft_share,genuine_participation_probability=None,legal_eligibility=None))
    residual={}
    for team in sorted({r['team_id'] for r in players}):
        pool=[r for r in included if r['team_id']==team and r['player_id'] not in named]
        exposure=math.fsum(r['exact_seconds']/60 for r in pool);require(exposure>0,'J_EVENT_RESIDUAL_SOURCE_EXPOSURE')
        keys=dict(points='points',threes='threePointersMade',rebounds='reboundsTotal',assists='assists',turnovers='turnovers')
        rates={stat:dict(alpha=.5+_moments(pool,key),beta=1.+exposure) for stat,key in keys.items()}
        def conv(made,attempts):
            m,n=_moments(pool,made),_moments(pool,attempts)
            require(0<=m<=n,'J_EVENT_RESIDUAL_CONVERSION')
            return dict(alpha=.5+m,beta=.5+n-m)
        residual[team]=dict(kind='ANONYMOUS_GROUP_EXCHANGEABILITY_WORKING_PRIOR',source_rows=len(pool),
            source_reported_minutes=exposure,rates=rates,conversion3=conv('threePointersMade','threePointersAttempted'),
            conversion2=conv('two_made','two_attempts'),conversion_ft=conv('freeThrowsMade','freeThrowsAttempted'),
            ft_non3_point_share=dict(alpha=.5+_moments(pool,'freeThrowsMade'),beta=.5+2*_moments(pool,'two_made')),
            source_real_player_identity_claim=False,rate_dependence='ONE_SHARED_GROUP_RATE_VECTOR_PER_TEAM_SCENARIO')
    pace=[];totals={k:0 for k in ('fieldGoalsAttempted','fieldGoalsMade','freeThrowsAttempted','freeThrowsMade',
        'reboundsTotal','reboundsOffensive','reboundsDefensive','assists')};series={2:0,3:0}
    for row in facts['rows']:
        gid=row['game_id'];g=next_data((Path(original_raw_dir)/('nba-box-'+gid)/'body.raw').read_bytes())['game']
        game_proxy=[]
        for side in ('homeTeam','awayTeam'):
            c=g[side]['statistics'];proxy=c['fieldGoalsAttempted']+.44*c['freeThrowsAttempted']-c['reboundsOffensive']+c['turnovers']
            game_proxy.append(proxy)
            for key in totals:totals[key]+=c[key]
        pace.append(dict(game_id=gid,regulation_equivalent_proxy=sum(game_proxy)/2*48/(48+5*(g['period']-4))))
        for event in row['facts']['events']:
            if event['type']=='Free Throw':
                match=re.search(r'Free Throw 1 of ([23])',event['description'])
                if match:series[int(match.group(1))]+=1
    values=[r['regulation_equivalent_proxy'] for r in pace];mean=float(np.mean(values));variance=float(np.var(values,ddof=1))
    require(mean>0 and variance>0,'J_EVENT_PACE_MOMENTS')
    misses=totals['fieldGoalsAttempted']-totals['fieldGoalsMade']+totals['freeThrowsAttempted']-totals['freeThrowsMade']
    require(totals['reboundsTotal']<=misses and totals['assists']<=totals['fieldGoalsMade'],'J_EVENT_POOL_SOURCE_SUPPORT')
    model=dict(schema='new-conditional-residual-event-working-model/1',target=parent['cohort']['game_id'],
        source_candidate_denominator=35,primitive_attempt_denominator=140,named_players=players,residual_groups=residual,
        zero_prior=dict(alpha=.5,beta=49.5,empirically_updated=False,genuine_probability=None),
        pace=dict(shape=mean*mean/variance,scale=variance/mean,mean=mean,variance=variance,
            source='20_REGULATION_EQUIVALENT_FGA_PLUS_0.44_FTA_MINUS_OREB_PLUS_TO_PROXIES',observed_true_possessions=False),
        events=dict(assisted_fg=dict(alpha=.5+totals['assists'],beta=.5+totals['fieldGoalsMade']-totals['assists']),
            credited_rebound=dict(alpha=.5+totals['reboundsTotal'],beta=.5+misses-totals['reboundsTotal'],
                source_unit='ALL_MISS_PROXY_INCLUDES_NONTERMINAL_FT_NOT_TRUE_LIVE_REBOUND_OPPORTUNITY'),
            offensive_rebound=dict(alpha=.5+totals['reboundsOffensive'],beta=.5+totals['reboundsDefensive']),
            shooting_ft_three_series=dict(alpha=.5+series[3],beta=.5+series[2],
                source_unit='OBSERVED_TWO_OR_THREE_SHOT_SERIES_LENGTH_PROXY_NOT_SOURCE_CLASSIFIED_SHOOTING_FOUL',
                one_shot_series_excluded=True)),
        pace_source_rows=pace,source_count_totals=totals,source_ft_series=series,
        S3_use='WORKING_CONVERSION_PROBABILITY_POSTERIOR_PRIOR_NOT_UNCHANGED_BETA_BINOMIAL_AT_ENDOGENOUS_N',
        S1_use='WORKING_RATE_PRIORS_ALLOCATION_NEW_EVENT_LAW_NOT_UNCHANGED_S1_MARGINALS',
        fitting_is_new_prospective=True,posterior_of_joint_event_process=False,
        source_dataset_sha256=DATASET_SHA,pbp_payload_sha256=facts['payload_sha256'],
        s3_artifact_sha256=digest(s3raw),data_cutoff_at=cutoff,source_role_semantics=data['role_semantics'],
        genuine_participation_probability=None,source_model_admission='PENDING_SEPARATE_EVENT_MODEL_REVIEW',production_release=False)
    model_raw=canonical(model)
    with (out/'event_model.json').open('xb') as f:f.write(model_raw)
    completed=_now();require(utc(started)<=utc(completed),'J_EVENT_FIT_CLOCK')
    receipt=dict(schema='new-prospective-J-working-prior-fit/1',implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        compiler_raw_sha256=digest(Path(__file__).read_bytes()),approval_raw_sha256=PREFIT_APPROVAL_SHA,
        data_cutoff_at=cutoff,started_at=started,completed_at=completed,model_raw_sha256=digest(model_raw),
        original_ordinary_source_rows=456,original_source_observations=698,original_all_stat_attempts=2792,
        PBP_games=20,PBP_actions=sum(r['facts']['action_denominator'] for r in facts['rows']),
        full_forecast_raw_sha256=digest(full_forecast_raw),S3_admission_raw_sha256=S3_ADMISSION_SHA,
        source_full_admission_raw_sha256=FULL_ADMISSION_SHA,in_memory_S3_verification_replays=1,
        fit_kind='NEW_SOURCE_DERIVED_WORKING_PRIORS_NOT_JOINT_POSTERIOR_NOT_HISTORICAL_REPLACEMENT',
        heldout_scoring=False,weight_optimization=False,NUTS=False,release=False)
    (out/'FIT_RECEIPT.json').write_bytes(canonical(receipt))
    (out/'SHA256SUMS').write_text(''.join(digest(f.read_bytes())+'  '+f.name+'\n' for f in sorted(out.iterdir()) if f.name!='SHA256SUMS'))
    return receipt
