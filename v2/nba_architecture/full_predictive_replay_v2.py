"""Post-event-safe verifier for the exact actually issued new shadow batch.

Verification never invokes the pre-event candidate/issuance clock gate. It
validates the frozen admitted model snapshot and all source/identity/clock
bindings. Neither replay time nor an outcome enters the forecast algorithm.
"""
from pathlib import Path
from .p1_subset_handoff_v1 import canonical,digest
from .subset_contract_v1 import strict_json
from .subset_p3_v1 import require
from .prospective_s_runtime_v1 import read_forecasts
from .pbp_evidence_v1 import read_population
from . import full_predictive_runtime_v1 as issuer
from v2.nba_opportunity import utc

FROZEN_FORECAST_SHA='a60ec92b970e6b417a1b9b48dceca3b2a1140dcf84f7f4ef24a8b57edcfc987f'


def read_issued_forecast(raw,parent_raw,*,law_snapshot_path,cohort,admission_path,original_inputs,
        pbp_raw_dir,pbp_population_path,model_card_path,protocol_path):
    require(digest(raw)==FROZEN_FORECAST_SHA,'FULL_REPLAY_FROZEN_FORECAST_BYTES')
    value=strict_json(raw);a_raw=Path(admission_path).read_bytes()
    require(digest(a_raw)==issuer.ADMISSION_SHA,'FULL_REPLAY_ADMISSION_BYTES');a=strict_json(a_raw)
    require(digest(canonical(cohort))==issuer.COHORT_SHA and value['cohort']==cohort,'FULL_REPLAY_COHORT')
    require(utc(a['model_admitted_at'])<=utc(cohort['freeze_at'])<=utc(value['forecast_at'])<utc(cohort['start']),
        'FULL_REPLAY_RECORDED_CLOCK_CHAIN')
    require(value['input_freeze_at']==cohort['freeze_at'] and value['event_start_at']==cohort['start'],
        'FULL_REPLAY_EVENT_CLOCK_SCOPE')
    require(digest(Path(issuer.__file__).read_bytes())==value['implementation_raw_sha256'],'FULL_REPLAY_ISSUER_CODE')
    for name,sha in a['source_code_raw_sha256'].items():
        require(digest(Path(__file__).with_name(name).read_bytes())==sha,'FULL_REPLAY_REVIEWED_CODE:'+name)
    for file,sha in ((model_card_path,a['model_card_raw_sha256']),(protocol_path,a['protocol_raw_sha256']),
        (pbp_population_path,a['population_raw_sha256'])):
        require(digest(Path(file).read_bytes())==sha,'FULL_REPLAY_REVIEWED_INPUT_BYTES')
    parent=read_forecasts(parent_raw,**original_inputs)
    require(parent['cohort']['game_id']==a['target']==cohort['game_id'] and
        parent['cohort']['frozen_candidates']==cohort['frozen_candidates'],'FULL_REPLAY_COMPLETE_CANDIDATES')
    snapshot_raw=Path(law_snapshot_path).read_bytes();require(digest(snapshot_raw)==a['candidate_raw_sha256'],
        'FULL_REPLAY_ADMITTED_LAW_SNAPSHOT_BYTES')
    snapshot=strict_json(snapshot_raw)
    semantic={k:v for k,v in snapshot.items() if k not in ('computed_started_at','computed_completed_at')}
    require(value['law_payload']==semantic and semantic['payload_sha256']==a['candidate_payload_sha256'],
        'FULL_REPLAY_LAW_SNAPSHOT_JOIN')
    plain={k:v for k,v in semantic.items() if k!='payload_sha256'}
    require(digest(canonical(plain))==semantic['payload_sha256'],'FULL_REPLAY_SEMANTIC_HASH')
    require(semantic['parent_forecast_raw_sha256']==digest(parent_raw),'FULL_REPLAY_PARENT_HASH')
    facts=read_population(pbp_raw_dir,pbp_population_path,original_inputs['raw_dir'])
    require(facts['payload_sha256']==semantic['evidence_payload_sha256'] and facts['rejected_games']==0,
        'FULL_REPLAY_PBP_SOURCE_FACTS')
    require(utc(semantic['source_evidence_available_at'])<=utc(cohort['freeze_at']),'FULL_REPLAY_LATE_SOURCE')
    require(value['source_model_admission_raw_sha256']==issuer.ADMISSION_SHA and
        value['source_model_admitted_at']==a['model_admitted_at'],'FULL_REPLAY_MODEL_LINEAGE')
    payload={k:v for k,v in value.items() if k!='payload_sha256'}
    require(digest(canonical(payload))==value['payload_sha256'],'FULL_REPLAY_PAYLOAD_HASH')
    return dict(status='VERIFIED_FROZEN_FORECAST_POST_EVENT_SAFE',new_forecast_issued=False,
        original_forecast_at=value['forecast_at'],forecast_raw_sha256=digest(raw),
        payload_sha256=value['payload_sha256'],attempts=semantic['attempt_denominator'],
        forecasts=semantic['full_model_candidates'],abstentions=semantic['abstentions'],
        release_approved=False)
