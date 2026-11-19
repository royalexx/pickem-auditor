"""P1 subset -> native S boundary, without creating model admission.

No compatible saved S artifact has independently accepted provenance for this
profile. The production-research resolver therefore has no admitted entries.
The native control entrypoint exercises S's actual API but cannot mint forecasts
in the source-bound ledger. Adding a real model requires a reviewed code change.
"""
from pathlib import Path
from types import MappingProxyType

from .p1_subset_handoff_v1 import read_requests, canonical, digest
from .subset_contract_v1 import strict_json
from v2.nba_s_family import predict_conditional

VERSION = 'nba-subset-p2/1.0.0'
STATS = ('points', 'rebounds', 'assists', 'threes')
# Deliberately empty evidence result, not a caller-configurable approval switch.
ADMITTED_S_MODELS = MappingProxyType({})


def native_s_control(fitted, *, player_id, role, projected_exposure, statistic):
    """Actual native API control. Never admitted to run_p2's real ledger."""
    prediction = predict_conditional(fitted, player_id=player_id, role=role,
        projected_exposure=projected_exposure, statistic=statistic)
    return dict(kind='ENGINEERING_CONTROL_ONLY', admitted=False,
        parameters=prediction.parameters, uncertainty=prediction.uncertainty,
        abstain_reason=prediction.abstain_reason,
        artifact_sha256=fitted.artifact_sha256)


def run_p2(raw, capture_dir, cohort):
    """Replay P1 before enumerating every player/stat attempt, including rejects.

    No participation probability, role or exposure is inferred from roster status.
    A source-ready row with no saved model is distinct from a source rejection.
    """
    handoff = read_requests(raw, capture_dir, cohort)
    rows = []
    for request in handoff['requests']['rows']:
        for stat in STATS:
            source_ready = request['source_request_status'] == 'SOURCE_READY_CONDITIONAL_REQUEST'
            rows.append(dict(game_id=cohort['game_id'], player_id=request['player_id'],
                team_id=request['team_id'], statistic=stat,
                status='ABSTAIN', reason='SAVED_S_ARTIFACT_UNAVAILABLE' if source_ready else 'P1_SOURCE_ABSTENTION',
                source_issues=request['issues'], source_ready=source_ready,
                source_row_index=request['source_row_index'],
                source_handoff_sha256=handoff['payload_sha256'],
                conditioning='conditional_on_participation_and_exposure',
                participation_probability=None, legal_eligibility=None,
                model_artifact_sha256=None, role=None, projected_exposure=None,
                forecast=None, actual_native_model_executed=False))
    payload = dict(schema=VERSION, stage='P2', profile='source_listed_subset',
        implementation_sha256=digest(Path(__file__).read_bytes()),
        p1_handoff_sha256=handoff['payload_sha256'],
        candidate_denominator=len(handoff['requests']['rows']),
        statistics=list(STATS), attempt_denominator=len(rows),
        admitted_model_count=len(ADMITTED_S_MODELS), forecasted_rows=0,
        abstained_rows=len(rows), rows=rows,
        status='IMPLEMENTED_ABSTENTION_PATH_MODEL_INPUT_UNAVAILABLE',
        missing_evidence='Compatible immutable native FittedS artifact with independently reviewed training-source, player/stat/role, cutoff and exact reader-code lineage, plus a reviewed source-bound role/exposure resolver and numerical S dispatch in this real subset path; no replacement fitting authorized.')
    return dict(payload, payload_sha256=digest(canonical(payload)))


def read_p2(raw, *, source_raw, capture_dir, cohort):
    """A resealed hash or caller approval cannot substitute for source replay."""
    value=strict_json(raw)
    if canonical(value) != canonical(run_p2(source_raw, capture_dir, cohort)):
        raise ValueError('P2_SOURCE_OR_OUTPUT_MISMATCH')
    return value
