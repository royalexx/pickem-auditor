"""Actual-clock issuance/replay for the exact newly admitted shadow S model."""
from pathlib import Path
from datetime import datetime,timezone
import subprocess
from .p1_subset_handoff_v1 import canonical,digest
from .subset_contract_v1 import strict_json
from .subset_p3_v1 import require
from .full_predictive_candidate_v1 import build_full_candidate
from v2.nba_opportunity import utc

ADMISSION_SHA='dd1e1b2b0663c4d889257cc17cceb160ea56df1c497f7bfb9046df96e3dfb2b2'
COHORT_SHA='ecd5d93685c90ecf7f1b6d31ba778982e6b23c0f748998747db9ca968dc16024'


def render_forecast(parent_raw,*,cohort,forecast_at,admission_path,**inputs):
    require(COHORT_SHA is not None and digest(canonical(cohort))==COHORT_SHA,'FULL_FORECAST_COHORT_NOT_ADMITTED')
    admission_raw=Path(admission_path).read_bytes();require(digest(admission_raw)==ADMISSION_SHA,'FULL_FORECAST_ADMISSION_BYTES')
    a=strict_json(admission_raw)
    for name,sha in a['source_code_raw_sha256'].items():
        require(digest(Path(__file__).with_name(name).read_bytes())==sha,'FULL_FORECAST_REVIEWED_CODE:'+name)
    require(utc(a['model_admitted_at'])<=utc(cohort['freeze_at'])<=utc(forecast_at)<utc(cohort['start']),
        'FULL_FORECAST_ACTUAL_CLOCK_CHAIN')
    value=build_full_candidate(parent_raw,**inputs)
    require(value['payload_sha256']==a['candidate_payload_sha256'],'FULL_FORECAST_APPROVED_LAW_REPLAY')
    require(utc(value['source_evidence_available_at'])<=utc(cohort['freeze_at']),'FULL_FORECAST_LATE_SOURCE')
    require(cohort['game_id']==a['target'] and cohort['candidate_denominator']==value['candidate_denominator'],
        'FULL_FORECAST_TARGET_SCOPE')
    parent=strict_json(parent_raw)
    require(cohort['frozen_candidates']==parent['cohort']['frozen_candidates'],'FULL_FORECAST_COMPLETE_POPULATION')
    semantic={k:v for k,v in value.items() if k not in ('computed_started_at','computed_completed_at')}
    payload=dict(schema='nba-full-played-shadow-forecast/1',status='UNCERTIFIED/SHADOW',
        forecast_at=forecast_at,input_freeze_at=cohort['freeze_at'],event_start_at=cohort['start'],
        forecast_horizon_seconds=(utc(cohort['start'])-utc(forecast_at)).total_seconds(),
        cohort=cohort,cohort_sha256=COHORT_SHA,source_model_admission_raw_sha256=ADMISSION_SHA,
        source_model_admitted_at=a['model_admitted_at'],
        implementation_raw_sha256=digest(Path(__file__).read_bytes()),
        law_payload=semantic,new_forecast_issued=True,
        conditioning='PARTICIPATION_UNDER_EXPLICIT_PRIOR_EXTRAPOLATION_PRODUCT_HYPOTHESES',
        genuine_zero_state_probability=None,genuine_participation_probability=None,legal_eligibility=None,
        J_admitted=False,C_scoring_admitted=False,historical_predictive_validation=False,production_release=False)
    return dict(payload,payload_sha256=digest(canonical(payload)))


def issue_forecast(output,parent_raw,**inputs):
    """Public issuer supplies actual clock; output creation is exclusive."""
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    forecast_at=datetime.now(timezone.utc).isoformat()
    try:
        result=render_forecast(parent_raw,forecast_at=forecast_at,**inputs)
        raw=canonical(result)
        with (out/'forecast.json').open('xb') as f:f.write(raw)
        receipt=dict(kind='ACTUAL_NEW_SHADOW_FORECAST_NOT_HISTORICAL_REPLACEMENT',
            implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            forecast_at=forecast_at,calculation_completed_at=datetime.now(timezone.utc).isoformat(),
            forecast_raw_sha256=digest(raw),forecast_payload_sha256=result['payload_sha256'],
            new_forecast_issued=True,parent_forecast_unchanged=True,
            candidates=result['law_payload']['candidate_denominator'],attempts=result['law_payload']['attempt_denominator'],
            forecasted=result['law_payload']['full_model_candidates'],abstentions=result['law_payload']['abstentions'])
        with (out/'ISSUANCE_RECEIPT.json').open('xb') as f:f.write(canonical(receipt))
        return receipt
    except Exception as error:
        with (out/'REJECTED_ISSUANCE.json').open('xb') as f:
            f.write(canonical(dict(forecast_at=forecast_at,error=str(error),new_forecast_issued=False)))
        raise


def read_forecast(raw,parent_raw,**inputs):
    value=strict_json(raw)
    require(canonical(value)==canonical(render_forecast(parent_raw,forecast_at=value['forecast_at'],**inputs)),
        'FULL_FORECAST_SOURCE_MODEL_OUTPUT_REPLAY_MISMATCH')
    return dict(status='VERIFIED_REPLAY_ONLY',new_forecast_issued=False,
        original_forecast_at=value['forecast_at'],payload_sha256=value['payload_sha256'],
        attempts=value['law_payload']['attempt_denominator'],forecasts=value['law_payload']['full_model_candidates'])
