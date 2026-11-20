"""Exact new-J engineering sample -> C transport, with target scores pending.

This does not grant J-family/fidelity admission. Immutable candidate bytes,
source artifact, chronology, deterministic G/O/rate joins and event accounting
are checked before exposing any empirical marginal or same-draw combination.
"""
import hashlib
from pathlib import Path
from .p1_subset_handoff_v1 import canonical,digest
from .subset_contract_v1 import strict_json
from .subset_p3_v1 import require
from .full_predictive_replay_v2 import read_issued_forecast
from .conditional_c_v1 import read_native_outcomes
from v2.nba_joint.residual_events_v1 import fixed_scenario
from v2.nba_joint.residual_audit_v1 import audit_run
from v2.nba_opportunity import utc

RUN_SHA='2b8a88ab928519011788e3737385155b2d240017c01df34b9a08e404f26d7c72'
RECEIPT_SHA='f350a70b84abb479edfce3390a59a06fc234619e8ae3c8aaf3259db722d2c402'
MODEL_SHA='85f27b2ce96a96e14449da3e10ab0d3bb7e9c4e60d7aa30bc5b311d46c48e46d'
MODEL_ADMISSION_SHA='388e41fb537dc5e2c395078603473f8c8d524745c90f30957b672e2ed6015a42'
J_CODE_SHA={
    'residual_events_v1.py':'75be57a993360b693d61dfd5acde07dad92a28e831ed6b781c068b793fce01ee',
    'residual_opportunity_v1.py':'d53627276ba972cd23ce91bd4d9cb212f28fa141e45d44ea6f5a276b41215803',
    'residual_audit_v1.py':'5d99e90df7f9b5164d66f92e70b0e894d3e0d5540131354d8f85cd89560f5197'}


def read_J_for_C(*,run_raw,receipt_raw,model_raw,model_admission_raw,full_raw,parent_raw,
        full_inputs,outcome_inputs):
    require(digest(run_raw)==RUN_SHA and digest(receipt_raw)==RECEIPT_SHA,'J_C_FROZEN_EXECUTION_BYTES')
    require(digest(model_raw)==MODEL_SHA and digest(model_admission_raw)==MODEL_ADMISSION_SHA,'J_C_ADMITTED_PARAMETER_BYTES')
    for name,sha in J_CODE_SHA.items():
        require(hashlib.sha256((Path(__file__).parents[1]/'nba_joint'/name).read_bytes()).hexdigest()==sha,'J_C_REVIEWED_RUNTIME_CODE:'+name)
    read_issued_forecast(full_raw,parent_raw,**full_inputs);read_native_outcomes(**outcome_inputs)
    run=strict_json(run_raw);receipt=strict_json(receipt_raw);model=strict_json(model_raw)
    a=strict_json(model_admission_raw);full=strict_json(full_raw)
    require(receipt['input_full_forecast_raw_sha256']==digest(full_raw) and receipt['input_model_raw_sha256']==MODEL_SHA and
        receipt['run_raw_sha256']==RUN_SHA and receipt['model_admission_sha256']==MODEL_ADMISSION_SHA,'J_C_LINEAGE_JOIN')
    require(utc(a['admitted_at'])<=utc(receipt['freeze_at'])<=utc(receipt['started_at'])<=utc(receipt['completed_at'])<
        utc(receipt['event_start_at'])==utc(full['event_start_at']),'J_C_ACTUAL_CLOCK_CHAIN')
    require(model['target']==full['cohort']['game_id'] and run['model_raw_sha256']==MODEL_SHA and
        run['seed']==receipt['seed']==20261120 and run['n_requested']==receipt['scenario_denominator']==32,
        'J_C_TARGET_AND_DECLARED_EXECUTION')
    audit=audit_run(run);samples={}
    for index,s in enumerate(run['scenarios']):
        regenerated=fixed_scenario(model,run['seed'],index)
        require(canonical(regenerated)==canonical(s['fixed']),'J_C_EXACT_FIXED_G_O_RATE_HANDOFF')
        path=s['proposals'][-1]
        for team,actors in s['fixed']['actors'].items():
            for actor in actors:
                pid=actor['identity']['player_id']
                if pid:
                    for stat in ('points','rebounds','assists','threes','pr','pa','ra','pra'):
                        samples.setdefault((pid,stat),[]).append(path['counts'][team][actor['index']][stat])
    supported={r['player_id'] for r in full['law_payload']['rows'] if r['model']}
    rows=[]
    for player in full['cohort']['frozen_candidates']:
        for stat in ('points','rebounds','assists','threes','pr','pa','ra','pra'):
            key=(player['player_id'],stat);values=samples.get(key)
            require((values is not None)==(player['player_id'] in supported),'J_C_UNSUPPORTED_OR_MISSING_PLAYER')
            if values is not None:require(len(values)==32,'J_C_DROPPED_SCENARIO')
            rows.append(dict(player_id=player['player_id'],team_id=player['team_id'],statistic=stat,
                status='ENGINEERING_EMPIRICAL_LAW_OUTCOME_PENDING' if values is not None else 'FORECAST_ABSTAINED',
                samples=values,scenario_ids=list(range(32)) if values is not None else None,
                outcome=None,score=None,participation_probability=None,legal_eligibility=None,
                conditioning='ALL14_NAMED_PLAYED_UNDER_MODEL_ASSUMPTIONS',
                genuine_participation_probability_identified=False))
    require(len(rows)==280 and sum(r['samples'] is not None for r in rows)==112,'J_C_COMPLETE_DENOMINATOR')
    result=dict(schema='new-residual-J-to-C-engineering-transport/1',game_id=model['target'],
        source_run_sha256=RUN_SHA,source_execution_receipt_sha256=RECEIPT_SHA,source_model_sha256=MODEL_SHA,
        C_J_reader_raw_sha256=digest(Path(__file__).read_bytes()),source_candidate_denominator=35,
        primitive_attempts=140,primitive_supported=56,primitive_abstained=84,
        all_market_attempts=280,all_market_supported=112,all_market_abstained=168,scenario_denominator=32,
        rows=rows,physics=audit,all_stats_same_draw=True,actual_scores=0,pending_outcomes=280,
        J_family_admitted=False,marginal_fidelity_accepted=False,historical_predictive_validation=False,
        classification='ACCEPTANCE_PENDING_ENGINEERING_TRANSPORT_ONLY_NOT_A_RELEASE_FORECAST',release=False)
    return dict(result,payload_sha256=digest(canonical(result)))
