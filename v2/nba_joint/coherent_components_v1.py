"""Source-fitted modular opportunity components for one shared S/J law.

Conjugate posteriors are exact for the declared aggregate working likelihoods,
not the likelihood of the full chronological constrained event process.
Independent PTS/3PM posteriors are deliberately absent.
"""
from datetime import datetime,timezone
from pathlib import Path
import copy
import math
import subprocess
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.subset_contract_v1 import strict_json
from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_architecture.prospective_s_sources_v1 import build_dataset
from v2.nba_architecture.conditional_c_v1 import read_native_outcomes
from v2.nba_opportunity import utc

PREFIT_SHA='920e576767e4b6b19615f03ee9f141e72c29294943ac32357138753c6fa2b690'
PROTOCOL_SHA='e12290d9021c82340ed75dfe16647d7672c42cbfd581f67273bef40e0eb6d303'
ADDENDUM_SHA='545f3eb596a43299c01a5bb5f0169421e3df4ede364879a55a0f1324c15af1b1'
OLD_MODEL_SHA='85f27b2ce96a96e14449da3e10ab0d3bb7e9c4e60d7aa30bc5b311d46c48e46d'
OLD_ADMISSION_SHA='388e41fb537dc5e2c395078603473f8c8d524745c90f30957b672e2ed6015a42'
DATASET_SHA='e5cb76ef446d6651b718c6279367a7078ffa86f01b621cfbfd9c7b4d74adbd1d'


def component_count(row,key):
    c=row['official_counts']
    return c['fieldGoalsAttempted']-c['threePointersAttempted'] if key=='twoPA' else (
        c['fieldGoalsMade']-c['threePointersMade'] if key=='twoPM' else
        c[{'threePA':'threePointersAttempted','threePM':'threePointersMade','FTA':'freeThrowsAttempted',
            'FTM':'freeThrowsMade','TO':'turnovers'}[key]])


def sufficient(rows):
    require(bool(rows),'COHERENT_EMPTY_COMPONENT_SOURCE')
    counts={k:0 for k in ('twoPA','twoPM','threePA','threePM','FTA','FTM','TO')}
    for r in rows:
        for m,a in (('twoPM','twoPA'),('threePM','threePA'),('FTM','FTA')):
            require(component_count(r,m)<=component_count(r,a),'COHERENT_ROW_CONVERSION_SUPPORT')
        for k in counts:
            x=component_count(r,k);require(type(x) is int and x>=0,'COHERENT_COMPONENT_COUNT');counts[k]+=x
        require(type(r['exact_seconds']) in (int,float) and math.isfinite(r['exact_seconds']) and
            r['exact_seconds']>0,'COHERENT_REPORTED_EXPOSURE')
    for m,a in (('twoPM','twoPA'),('threePM','threePA'),('FTM','FTA')):
        require(counts[m]<=counts[a],'COHERENT_CONVERSION_SUPPORT')
    return dict(rows=len(rows),reported_minutes=math.fsum(r['exact_seconds']/60 for r in rows),counts=counts)


def posterior(own,peers=None):
    """Exact conditional Gamma-Poisson and Beta-Binomial updates.

    The fitted assembler excludes this player's own records from the peer
    prior. This generic numerical updater grants no source admission and does not
    claim independence of historical players, a learned clock or joint fitting.
    """
    a=sufficient(own);p=sufficient(peers) if peers is not None else None
    rates={};conversions={}
    for k in ('twoPA','threePA','FTA','TO'):
        alpha=.5+(180*p['counts'][k]/p['reported_minutes'] if p else 0.)
        beta=181. if p else 1.
        rates[k]=dict(alpha=alpha+a['counts'][k],beta=beta+a['reported_minutes'],
            prior_alpha=alpha,prior_beta=beta,observed_count=a['counts'][k],exposure_minutes=a['reported_minutes'])
    for name,made,attempts in (('conversion2','twoPM','twoPA'),('conversion3','threePM','threePA'),('conversion_ft','FTM','FTA')):
        require(p is None or p['counts'][attempts]>0,'COHERENT_NO_PEER_CONVERSION_OPPORTUNITIES')
        q=p['counts'][made]/p['counts'][attempts] if p else .5
        pa=.5+40*q if p else .5;pb=.5+40*(1-q) if p else .5
        conversions[name]=dict(alpha=pa+a['counts'][made],beta=pb+a['counts'][attempts]-a['counts'][made],
            prior_alpha=pa,prior_beta=pb,observed_makes=a['counts'][made],observed_attempts=a['counts'][attempts])
    return dict(attempt_posteriors=rates,**conversions,sufficient_statistics=a,peer_sufficient_statistics=p,
        likelihood_scope='CONDITIONAL_AGGREGATE_COMPONENT_LIKELIHOODS_MODULAR_USE_NOT_FULL_EVENT_POSTERIOR')


def assemble(old_model,records):
    """Numerical assembly only; admission is the separately reviewed fit path."""
    included=[r for r in records if r['fit_included']]
    require(len(included)==456 and len(records)==698,'COHERENT_COMPLETE_SOURCE_DENOMINATOR')
    model=copy.deepcopy(old_model);named={p['player_id'] for p in model['named_players']}
    require(len(named)==14,'COHERENT_NAMED_POPULATION')
    for player in model['named_players']:
        own=[r for r in included if r['player_id']==player['player_id']]
        peers=[r for r in included if r['player_id']!=player['player_id'] and r['role']==player['role']]
        require(len(own)>=5,'COHERENT_MINIMUM_HISTORY')
        player.update(posterior(own,peers));player['rates']={s:player['rates'][s] for s in ('assists','rebounds')}
        player.pop('ft_non3_point_share',None)
    for team,group in model['residual_groups'].items():
        own=[r for r in included if r['team_id']==team and r['player_id'] not in named]
        group.update(posterior(own));group['rates']={s:group['rates'][s] for s in ('assists','rebounds')}
        group.pop('ft_non3_point_share',None)
    model.update(schema='coherent-modular-opportunity-model/1',family='S4_J_SHARED_GENERATIVE_KERNEL',
        old_working_model_raw_sha256=OLD_MODEL_SHA,independent_points_or_threes_posteriors=False,
        S_definition='PUSHFORWARD_OF_SAME_J_LAW_NOT_AN_INDEPENDENT_VOTE',
        source_candidate_denominator=35,primitive_attempt_denominator=140,
        original_source_rows=698,ordinary_fit_rows=456,excluded_rows_retained=242,
        fitting_is_new_prospective=True,posterior_of_joint_event_process=False,
        component_posterior_scope='GAMMA_POISSON_COUNTS_GIVEN_REPORTED_MINUTES_AND_BETA_BINOMIAL_MAKES_GIVEN_ATTEMPTS',
        source_model_admission='PENDING_SEPARATE_COHERENT_MODEL_REVIEW')
    model.pop('S1_use',None);model.pop('S3_use',None)
    if 's3_artifact_sha256' in model:model['legacy_S3_comparator_raw_sha256']=model.pop('s3_artifact_sha256')
    return model


def fit(*,approval_path,protocol_path,old_model_path,old_admission_path,source_inputs,
        original_raw_dir,spec_path,policy_path,output):
    require(PREFIT_SHA is not None,'COHERENT_PREFIT_REVIEW_CLOSED')
    require(digest(Path(approval_path).read_bytes())==PREFIT_SHA,'COHERENT_PREFIT_BYTES')
    require(digest(Path(protocol_path).read_bytes())==PROTOCOL_SHA,'COHERENT_PROTOCOL_BYTES')
    require(digest(Path(protocol_path).with_name('PROTOCOL_ADDENDUM.json').read_bytes())==ADDENDUM_SHA,'COHERENT_ADDENDUM_BYTES')
    old_raw=Path(old_model_path).read_bytes();a_raw=Path(old_admission_path).read_bytes()
    require(digest(old_raw)==OLD_MODEL_SHA and digest(a_raw)==OLD_ADMISSION_SHA,'COHERENT_EXACT_UPSTREAM_ARTIFACT')
    admission=strict_json(a_raw);require(admission['model_raw_sha256']==OLD_MODEL_SHA,'COHERENT_UPSTREAM_JOIN')
    require(digest((Path(__file__).parents[1]/'nba_architecture/conditional_c_v1.py').read_bytes())==
        'a6e2aa7d540d01e2492ce4984a20fc2d6e40a1778d2228d89598632e4ab03687','COHERENT_NATIVE_C_READER_CODE')
    outcomes=read_native_outcomes(**source_inputs)
    require(Path(original_raw_dir).resolve()==Path(source_inputs['original_raw_dir']).resolve() and
        Path(spec_path).read_bytes()==Path(source_inputs['spec_path']).read_bytes(),'COHERENT_SAME_DIRECT_SOURCE_PATH')
    data=build_dataset(original_raw_dir,spec_path,policy_path)
    require(data['payload_sha256']==DATASET_SHA,'COHERENT_EXACT_DATASET')
    started=datetime.now(timezone.utc).isoformat();approval=strict_json(Path(approval_path).read_bytes())
    require(max(utc(approval['decided_at']),utc(admission['admitted_at']),
        *(utc(r['ingested_at']) for r in outcomes['rows']))<=utc(started),'COHERENT_PRE_SOURCE_MODEL_OR_REVIEW_CLOCK')
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    model=assemble(strict_json(old_raw),data['records']);model['protocol_raw_sha256']=PROTOCOL_SHA
    model['protocol_addendum_raw_sha256']=ADDENDUM_SHA
    raw=canonical(model);(out/'model.json').write_bytes(raw)
    completed=datetime.now(timezone.utc).isoformat()
    require(digest((out/'model.json').read_bytes())==digest(raw),'COHERENT_PERSISTED_MODEL_BYTES')
    verified=datetime.now(timezone.utc).isoformat()
    require(utc(started)<=utc(completed)<=utc(verified),'COHERENT_FIT_CLOCK_REVERSAL')
    receipt=dict(schema='coherent-prospective-component-fit/1',started_at=started,
        completed_at=completed,verified_at=verified,implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        compiler_raw_sha256=digest(Path(__file__).read_bytes()),approval_raw_sha256=PREFIT_SHA,protocol_raw_sha256=PROTOCOL_SHA,
        old_model_raw_sha256=OLD_MODEL_SHA,old_admission_raw_sha256=OLD_ADMISSION_SHA,
        source_dataset_sha256=DATASET_SHA,source_outcome_payload_sha256=outcomes['payload_sha256'],
        model_raw_sha256=digest(raw),source_rows=698,ordinary_fit_rows=456,excluded_rows=242,
        new_prospective_artifact=True,historical_replacement=False,holdout_scoring=False,weight_optimization=False,NUTS=False,release=False)
    (out/'FIT_RECEIPT.json').write_bytes(canonical(receipt));return receipt
