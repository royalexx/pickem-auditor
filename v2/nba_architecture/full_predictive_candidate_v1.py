"""Original genuine S artifacts + exact new evidence -> explicit shadow model.

This candidate builder grants no source/model/J/C/release admission by labels.
It verifies the reviewed protocol's exact bytes and preserves every attempt.
"""
from datetime import datetime,timezone
from pathlib import Path
from .p1_subset_handoff_v1 import canonical,digest
from .subset_contract_v1 import strict_json
from .subset_p3_v1 import require
from .full_played_s_v1 import FullPlayedLaw
from .pbp_evidence_v1 import read_population
from .prospective_s_runtime_v1 import read_forecasts
from v2.nba_opportunity import utc

PBP_POPULATION_SHA='1d05830c44ee07fd89bbe7dcade95d70651a0cfae824e8f2edaadf30d4b20584'
PROTOCOL_DECISION_SHA='51c45b6aef179e7b4418b42e5af6f31753eadf01ecb09c49030e20514b4006fc'


def build_full_candidate(parent_raw,*,original_inputs,pbp_raw_dir,pbp_population_path,model_card_path,protocol_path):
    started=datetime.now(timezone.utc).isoformat()
    protocol_raw=Path(protocol_path).read_bytes();require(digest(protocol_raw)==PROTOCOL_DECISION_SHA,'FULL_PROTOCOL_BYTES')
    protocol=strict_json(protocol_raw)
    card_raw=Path(model_card_path).read_bytes();card=strict_json(card_raw)
    # Reviewed protocol holds the authoritative card pin; no caller flags.
    expected=protocol['exact_input_raw_sha256']['FULL_PLAYED_MODEL_CARD.json']
    require(expected is not None and digest(card_raw)==expected,'FULL_MODEL_CARD_BYTES')
    require(digest(Path(pbp_population_path).read_bytes())==PBP_POPULATION_SHA,'FULL_PBP_POPULATION_BYTES')
    parent=read_forecasts(parent_raw,**original_inputs)
    require(card['target']==parent['cohort']['game_id'] and card['source_candidates']==parent['candidate_denominator'],
        'FULL_MODEL_TARGET_POPULATION')
    evidence=read_population(pbp_raw_dir,pbp_population_path,original_inputs['raw_dir'])
    require(evidence['game_denominator']==20 and evidence['rejected_games']==0 and
        all(r['facts']['all_credited_event_counts_reconciled'] for r in evidence['rows']), 'FULL_PBP_FACT_RECONCILIATION')
    sources=strict_json(Path(pbp_population_path).read_bytes())['sources']
    available=max((r['ingested_at'] for r in sources.values()),key=utc)
    require(utc(available)<=utc(started)<utc(parent['cohort']['start']),'FULL_CANDIDATE_ACTUAL_CLOCK')
    minute={r['player_id']:r for r in parent['minutes']};rows=[];grid=card['true_zero_weight']['sensitivity_means']
    require(grid==[0.,.001,.01,.05,.1] and card['true_zero_weight']['mean']==.01,'FULL_PRIOR_PROTOCOL')
    for row in parent['rows']:
        full=None;sensitivity=[]
        if row['forecast']:
            f=row['forecast'];params=f['parameters'];distribution=minute[row['player_id']]['forecast']['distribution']
            full=FullPlayedLaw(params['alpha'],params['beta'],distribution).summary()
            for z in grid:
                law=FullPlayedLaw(params['alpha'],params['beta'],distribution,z)
                sensitivity.append(dict(chosen_zero_weight=z,moments=law.moments(),
                    pmf_queries=law.query([0,1,5,10,30,100]),
                    scenario_is_not_identified_bound=True))
        rows.append(dict(player_id=row['player_id'],team_id=row['team_id'],name=row['name'],statistic=row['statistic'],
            status='FULL_PLAYED_PRIOR_PREDICTIVE_CANDIDATE' if full else 'ABSTAIN',reason=row['reason'],
            model=full,sensitivity=sensitivity,participation_probability=None,legal_eligibility=None))
    payload=dict(schema='nba-new-full-predictive-candidate/1',kind='ASSUMPTION_DEFINED_SHADOW_CANDIDATE_NOT_NEW_FORECAST',
        parent_forecast_raw_sha256=digest(parent_raw),parent_forecast_at=parent['forecast_at'],
        protocol_raw_sha256=PROTOCOL_DECISION_SHA,model_card_raw_sha256=digest(card_raw),
        evidence_population_raw_sha256=PBP_POPULATION_SHA,evidence_payload_sha256=evidence['payload_sha256'],
        source_evidence_available_at=available,candidate_denominator=parent['candidate_denominator'],
        attempt_denominator=len(rows),full_model_candidates=sum(r['model'] is not None for r in rows),
        abstentions=sum(r['model'] is None for r in rows),sensitivity_scenarios=grid,
        sensitivity_attempt_denominator=len(rows)*len(grid),rows=rows,
        source_model_admission='PENDING_SEPARATE_SOURCE_READER_AND_MODEL_REVIEW',
        new_forecast_issued=False,empirical_zero_probability=None,genuine_participation_probability=None,
        J_admitted=False,C_scores=0,historical_predictive_validation=False,production_release=False)
    return dict(payload,payload_sha256=digest(canonical(payload)),computed_started_at=started,
        computed_completed_at=datetime.now(timezone.utc).isoformat())
