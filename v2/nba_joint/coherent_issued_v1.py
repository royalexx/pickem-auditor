"""Closed exact-issuance replay root for the new coherent research family.

Pins are activated only after independent review of the actual source-backed
artifact. A supplied hash, reviewer label or caller flag cannot extend it.
"""
from pathlib import Path
import importlib.metadata
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.subset_contract_v1 import strict_json
from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_architecture.conditional_c_v1 import read_native_outcomes
from v2.nba_opportunity import utc
from .coherent_predictive_v1 import validate_bank,rows,SharedForecast

BANK_SHA=None
RECEIPT_SHA=None
MODEL_ADMISSION_SHA=None
MODEL_SHA='f1f6dd4a4d3753042c28b71fa9b7949628d69ccdad8f38ece47bb2ccdc6ffa2a'


def replay(directory,*,model_dir,source_inputs):
    require(BANK_SHA is not None and RECEIPT_SHA is not None and MODEL_ADMISSION_SHA is not None,'COHERENT_ISSUANCE_REVIEW_CLOSED')
    root=Path(directory);mr=Path(model_dir);repo=Path(__file__).parents[2]
    br=(root/'BANK.json').read_bytes();rr=(root/'EXECUTION_RECEIPT.json').read_bytes()
    require(digest(br)==BANK_SHA and digest(rr)==RECEIPT_SHA,'COHERENT_EXACT_ISSUANCE_BYTES')
    receipt=strict_json(rr);model_raw=(mr/'model.json').read_bytes();fit_raw=(mr/'FIT_RECEIPT.json').read_bytes()
    require(all(importlib.metadata.version(name)==receipt[name] for name in ('numpy','scipy')),'COHERENT_REPLAY_NUMERICAL_RUNTIME')
    ar=(mr.parent/'independent_artifact/ARTIFACT_ADMISSION.json').read_bytes()
    require(digest(ar)==MODEL_ADMISSION_SHA and digest(model_raw)==MODEL_SHA,'COHERENT_ADMITTED_MODEL_ROOT')
    admission=strict_json(ar);fit=strict_json(fit_raw);model=strict_json(model_raw);bank=strict_json(br)
    require(digest(fit_raw)==admission['fit_receipt_raw_sha256']==receipt['fit_receipt_raw_sha256'] and
        admission['model_raw_sha256']==receipt['model_raw_sha256']==MODEL_SHA and
        receipt['model_admission_raw_sha256']==MODEL_ADMISSION_SHA,'COHERENT_MODEL_ANCESTRY')
    required={'v2/nba_joint/coherent_predictive_v1.py','v2/nba_joint/coherent_components_v1.py',
        'v2/nba_joint/residual_events_v1.py','v2/nba_joint/residual_opportunity_v1.py','v2/nba_joint/residual_audit_v1.py',
        'v2/nba_joint/common.py','v2/nba_architecture/conditional_c_v1.py'}
    require(set(receipt['code_raw_sha256'])==required,'COHERENT_REPLAY_CODE_CLOSURE')
    for name,sha in receipt['code_raw_sha256'].items():require(digest((repo/name).read_bytes())==sha,'COHERENT_REPLAY_CODE:'+name)
    require(set(receipt['artifact_raw_sha256'])=={'BANK.json','COHORT.json','MARGINALS.json','COHERENCE.json','REFERENCE_COMPARISON.json'},
        'COHERENT_REPLAY_ARTIFACT_SCOPE')
    for name,sha in receipt['artifact_raw_sha256'].items():
        require(digest((root/name).read_bytes())==sha,'COHERENT_REPLAY_ARTIFACT:'+name)
    require(utc(fit['verified_at'])<=utc(admission['admitted_at'])<=utc(receipt['freeze_at'])<=utc(receipt['started_at'])<=
        utc(receipt['completed_at'])<utc(bank['cohort']['start']),'COHERENT_REPLAY_RECORDED_CLOCK_CHAIN')
    require(bank['cohort']['freeze_at']==receipt['freeze_at'] and bank['model_raw_sha256']==MODEL_SHA,
        'COHERENT_REPLAY_SOURCE_MODEL_JOIN')
    require(bank['scenario_denominator']==receipt['scenarios_requested']==64 and
        bank['status']==receipt['status']=='ENGINEERING_SAMPLE','COHERENT_REPLAY_DECLARED_EXECUTION')
    source=read_native_outcomes(**source_inputs)
    require(source['payload_sha256']==fit['source_outcome_payload_sha256'],'COHERENT_REPLAY_NATIVE_SOURCE_PAYLOAD')
    physics=validate_bank(bank,root/'trace',model);projected=rows(bank);view=SharedForecast(bank)
    pairs=0
    for r in projected:
        if r['samples'] is None:continue
        for kind,value in (('pmf',0),('cdf',10),('oup',10.5)):
            kw=dict(player_id=r['player_id'],statistic=r['statistic'],kind=kind,value=value)
            require(view.query(channel='S4',**kw)==view.query(channel='J',**kw),'COHERENT_REPLAY_QUERY_IDENTITY');pairs+=1
    require(pairs==receipt['exact_S4_J_query_pairs']==336,'COHERENT_REPLAY_COMPLETE_QUERIES')
    saved=strict_json((root/'MARGINALS.json').read_bytes())
    require(canonical(saved['rows'])==canonical(projected),'COHERENT_REPLAY_SAVED_PROJECTION')
    return dict(schema='coherent-S4-J-C-verified-replay/1',source_bank_raw_sha256=BANK_SHA,
        source_model_raw_sha256=MODEL_SHA,source_execution_receipt_raw_sha256=RECEIPT_SHA,
        scenarios=64,all_market_attempts=280,supported=112,abstentions=168,
        primitive_attempts=140,primitive_supported=56,primitive_abstentions=84,exact_S4_J_query_pairs=pairs,
        physics=physics,pending_outcomes=280,actual_scores=0,new_forecast_issued=False,
        participation_probability=None,legal_eligibility=None,zero_sensitivity_gate='PENDING',historical_validation=False,release=False)
