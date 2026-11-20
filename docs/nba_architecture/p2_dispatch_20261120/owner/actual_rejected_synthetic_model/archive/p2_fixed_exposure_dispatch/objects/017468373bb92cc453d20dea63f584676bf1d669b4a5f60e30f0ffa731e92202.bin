"""Fixed-M0 exposure -> native S numerical dispatch, without new model admission.

The real registry is intentionally empty: no compatible genuine saved S model
was recovered. Structural engineering controls never register real artifacts.
The original subset P2/P3/P4/archive interfaces remain byte-identical.
"""
from dataclasses import asdict,dataclass
import math
from pathlib import Path
from types import MappingProxyType

from v2.nba_s_family import model as native
from v2.nba_opportunity import utc
from .p1_subset_handoff_v1 import canonical,digest,read_requests
from .subset_contract_v1 import strict_json
from .subset_p2_v1 import STATS
from .subset_p3_v1 import read_p3,require

VERSION='nba-subset-fixed-exposure-S/1.0.0'
EXPOSURE_VARIANT='M0'
CONDITIONING='conditional_on_participation_and_fixed_projected_exposure'


@dataclass(frozen=True)
class ModelContract:
    """Reviewed code entry, not a caller-issued credential or approval flag.

    Role mapping tuples: (source position, historical workload state, trained
    S role). Equivalence must be reviewed for each real artifact's taxonomy.
    The UTF-8 body map contains original raw source text, keyed by receipt hash.
    Binary source bundles require a different reviewed contract, not decoding
    guesses in this reader.
    """
    artifact_sha256:str
    manifest_raw_sha256:str
    raw_sources_sha256:str
    native_code_sha256:str
    cohort_sha256:str
    training_cutoff_at:str
    statistic:str
    family:str
    role_map:tuple
    target_membership:tuple
    source_contract_id:str


# Only a separately reviewed code change may add exact real model contracts.
ADMITTED_MODELS=MappingProxyType({})


def _finite(value,reason,positive=False):
    require(type(value) in (int,float) and math.isfinite(value)
        and (value>0 if positive else value>=0),reason)


def _binding_check(binding):
    require(isinstance(binding,dict),'S_BINDING_SCHEMA')
    require(binding['p3_variant']==EXPOSURE_VARIANT,'S_UNREVIEWED_EXPOSURE_VARIANT')
    require(binding['conditioning']==CONDITIONING,'S_CONDITIONING_MISMATCH')
    require(binding['participation_probability'] is None and binding['legal_eligibility'] is None,'S_UNSUPPORTED_PARTICIPATION_CLAIM')
    require(all(isinstance(binding[k],str) and binding[k] for k in ('game_id','player_id','team_id','opponent_id'))
        and binding['team_id']!=binding['opponent_id'],'S_TARGET_IDENTITY')
    require(utc(binding['input_freeze_at'])<=utc(binding['forecast_at'])<utc(binding['event_start_at']),'S_TARGET_CLOCK')
    _finite(binding['projected_exposure'],'S_PROJECTED_EXPOSURE',positive=True)
    require(binding['exposure_units']=='minutes','S_EXPOSURE_UNITS')


def _verify_model(binding,contract,artifact_raw,manifest_raw,raw_sources_raw):
    _binding_check(binding)
    require(isinstance(contract,ModelContract),'S_MODEL_CONTRACT_SCHEMA')
    require(binding['cohort_sha256']==contract.cohort_sha256,'S_MODEL_COHORT_SCOPE')
    membership=dict(contract.target_membership)
    require(len(membership)==len(contract.target_membership) and membership.get(binding['player_id'])==binding['team_id'],'S_TARGET_MEMBERSHIP_SCOPE')
    require(binding['statistic']==contract.statistic,'S_MODEL_STAT_SCOPE')
    require(contract.family in ('S1','S2'),'S_MINUTES_PROFILE_REQUIRES_S1_OR_S2_NO_PROJECTED_3PA')
    require(digest(artifact_raw)==contract.artifact_sha256,'S_MODEL_BYTES')
    require(digest(manifest_raw)==contract.manifest_raw_sha256,'S_MANIFEST_BYTES')
    require(digest(raw_sources_raw)==contract.raw_sources_sha256,'S_TRAINING_BODY_MAP_BYTES')
    require(digest(Path(native.__file__).read_bytes())==contract.native_code_sha256,'S_EXECUTING_CODE_BYTES')
    artifact=strict_json(artifact_raw);manifest=strict_json(manifest_raw);raw_sources=strict_json(raw_sources_raw)
    require(isinstance(artifact,dict) and isinstance(manifest,dict) and isinstance(raw_sources,dict),'S_MODEL_OR_SOURCE_SCHEMA')
    require(artifact['version']=='nba-v25-S/1.1.0' and artifact['research_only'] is True,'S_MODEL_VERSION')
    require(artifact['family']==contract.family and artifact['stat']==contract.statistic,'S_MODEL_FAMILY_STAT')
    require(artifact['code_sha256']==contract.native_code_sha256,'S_ARTIFACT_CODE_BINDING')
    require(artifact['training_cutoff_at']==contract.training_cutoff_at,'S_REVIEWED_TRAINING_CUTOFF')
    cutoff=utc(artifact['training_cutoff_at'])
    require(cutoff<=utc(binding['input_freeze_at']),'S_MODEL_AFTER_FREEZE')
    keys=artifact['source_receipts']
    require(isinstance(keys,list) and len(set(keys))==len(keys) and bool(keys),'S_SOURCE_RECEIPT_POPULATION')
    require(all(key in manifest and key in raw_sources for key in keys),'S_SOURCE_RECEIPT_MISSING')
    used={key:manifest[key] for key in sorted(keys)}
    require(digest(native.canonical(used))==artifact['source_manifest_sha256'],'S_ARTIFACT_MANIFEST_JOIN')
    for key,source in used.items():
        require(isinstance(source,dict) and isinstance(raw_sources[key],str),'S_SOURCE_BODY_DOMAIN')
        require(digest(raw_sources[key].encode('utf-8'))==source['raw_sha256'],'S_TRAINING_SOURCE_BYTES')
        require(utc(source['available_at'])<=cutoff,'S_SOURCE_AFTER_MODEL_CUTOFF')
    rows=artifact['training_rows'];require(isinstance(rows,list) and bool(rows),'S_EMPTY_TRAINING_HISTORY')
    seen=set()
    for row in rows:
        key=(row['game_id'],row['player_id']);require(key not in seen,'S_DUPLICATE_TRAINING_IDENTITY');seen.add(key)
        require(row['game_id'] not in (binding['game_id'],'espn:game:'+binding['game_id']),'S_TARGET_IN_TRAINING')
        require(row['stat']==contract.statistic,'S_TRAINING_STAT')
        start,available=utc(row['game_start_at']),utc(row['outcome_available_at'])
        require(start<available<=cutoff and start<cutoff,'S_TRAINING_CLOCK')
        source=used.get(row['source_receipt_sha256']);require(source is not None,'S_TRAINING_RECEIPT_JOIN')
        require(row['source_raw_sha256']==source['raw_sha256'] and available<=utc(source['available_at']),'S_TRAINING_SOURCE_JOIN')
        game=source.get('games',{}).get(row['game_id']);require(isinstance(game,dict),'S_TRAINING_GAME_MISSING')
        require(utc(game['game_start_at'])==start and game['players'].get(row['player_id'])==row['team_id'],'S_DATED_TRAINING_MEMBERSHIP')
        require(game['duration_receipt_sha256'] in used,'S_DURATION_RECEIPT_MISSING')
        ot=game['overtime_periods'];require(type(ot) is int and ot>=0,'S_DURATION_OT')
        _finite(row['minutes'],'S_TRAINING_EXPOSURE',positive=True)
        require(row['minutes']<=48+5*ot,'S_TRAINING_DURATION_PHYSICS')
        require(type(row['count']) is int and row['count']>=0,'S_TRAINING_COUNT')
    require(utc(artifact['last_game_start_at'])==max(utc(r['game_start_at']) for r in rows)
        and utc(artifact['last_outcome_available_at'])==max(utc(r['outcome_available_at']) for r in rows),'S_TRAINING_EXTENT')
    roles={}
    for position,state,trained_role in contract.role_map:
        require((position,state) not in roles and isinstance(trained_role,str) and trained_role,'S_ROLE_CONTRACT_AMBIGUOUS')
        roles[(position,state)]=trained_role
    role=roles.get((binding['role_features']['position'],binding['role_features']['historical_workload_state']))
    require(role is not None,'S_TRAINED_ROLE_UNRESOLVED')
    require(any(r['role']==role for r in rows),'S_ROLE_OUTSIDE_TRAINING_TAXONOMY')
    # Historical team/role observations are not overwritten with current values.
    return native.FittedS(artifact_raw),role


def _execute(binding,contract,artifact_raw,manifest_raw,raw_sources_raw):
    fitted,role=_verify_model(binding,contract,artifact_raw,manifest_raw,raw_sources_raw)
    prediction=native.predict_conditional(fitted,player_id=binding['player_id'],role=role,
        projected_exposure=binding['projected_exposure'],statistic=binding['statistic'])
    require(prediction.abstain_reason is None,'S_NATIVE_ABSTENTION:'+str(prediction.abstain_reason))
    return dict(schema=VERSION,kind='FIXED_EXPOSURE_STATISTIC_LAW',status='UNCERTIFIED/SHADOW',
        game_id=binding['game_id'],player_id=binding['player_id'],team_id=binding['team_id'],
        statistic=binding['statistic'],conditioning=CONDITIONING,participation_probability=None,
        legal_eligibility=None,projected_exposure=binding['projected_exposure'],exposure_units='minutes',
        exposure_variant=EXPOSURE_VARIANT,minute_uncertainty_integrated=False,
        trained_role=role,artifact_sha256=fitted.artifact_sha256,
        model_contract_sha256=digest(canonical(asdict(contract))),native_reader_sha256=contract.native_code_sha256,
        model_training_cutoff_at=contract.training_cutoff_at,source_contract_id=contract.source_contract_id,
        p3_forecast_id=binding['p3_forecast_id'],source_binding_sha256=digest(canonical(binding)),
        forecast_at=binding['forecast_at'],input_freeze_at=binding['input_freeze_at'],event_start_at=binding['event_start_at'],
        parameters=prediction.parameters,uncertainty=prediction.uncertainty,
        retained_support_conditioning=True,actual_native_model_executed=True)


def structural_dispatch_control(binding,contract,artifact_raw,manifest_raw,raw_sources_raw):
    """Public numerical control. No source/model admission, even if hashes match."""
    require(binding.get('game_id','').startswith('espn:game:synthetic-'),'S_CONTROL_REQUIRES_SYNTHETIC_TARGET')
    return dict(mode='SYNTHETIC_ENGINEERING_ONLY',admitted=False,
        result=_execute(binding,contract,artifact_raw,manifest_raw,raw_sources_raw))


def _candidate(model_dir,stat):
    result=dict(statistic=stat,status='ABSENT',reason='SAVED_S_ARTIFACT_UNAVAILABLE',files={})
    if model_dir is None:return result
    for suffix in ('.json','.sources.json','.raw_sources.json'):
        path=Path(model_dir)/(stat+suffix)
        if path.is_file():
            raw=path.read_bytes();result['files'][path.name]=dict(sha256=digest(raw),bytes=len(raw),byte_domain='EXACT_PROVIDED_MODEL_OR_TRAINING_EVIDENCE_BYTES')
    if stat+'.json' in result['files']:result.update(status='REJECTED',reason='S_ARTIFACT_NOT_ADMITTED')
    return result


def provided_inventory(model_dir):
    if model_dir is None:return 'NOT_PROVIDED',{}
    root=Path(model_dir)
    if not root.is_dir():return 'MISSING',{}
    files={}
    for path in sorted(root.rglob('*')):
        if path.is_file():
            require(not path.is_symlink(),'S_MODEL_SYMLINK_UNSUPPORTED')
            raw=path.read_bytes();name=path.relative_to(root).as_posix()
            known=name in {s+suffix for s in STATS for suffix in ('.json','.sources.json','.raw_sources.json')}
            files[name]=dict(sha256=digest(raw),bytes=len(raw),
                disposition='REQUIRED_MODEL_OR_EVIDENCE_SLOT' if known else 'REJECTED_UNMATCHED_PROVIDED_FILE')
    return 'PROVIDED',files


def run_dispatch(source_raw,p3_raw,*,capture_dir,cohort,history_dir,model_path,forecast_at,model_dir=None):
    p1=read_requests(source_raw,capture_dir,cohort)
    p3=read_p3(p3_raw,source_raw=source_raw,capture_dir=capture_dir,cohort=cohort,
        history_dir=history_dir,model_path=model_path,forecast_at=forecast_at)
    m0=[r for r in p3['rows'] if r['model']==EXPOSURE_VARIANT]
    require(len(m0)==p1['requests']['source_candidate_rows'],'S_M0_POPULATION')
    minutes={(r['player_id'],r['team_id']):r for r in m0}
    require(len(minutes)==len(m0),'S_DUPLICATE_M0_IDENTITY')
    directory_status,provided_files=provided_inventory(model_dir)
    candidates={s:_candidate(model_dir,s) for s in STATS};rows=[]
    for request in p1['requests']['rows']:
        minute=minutes[(request['player_id'],request['team_id'])];f=minute['forecast']
        for stat in STATS:
            binding=None;forecast=None;reason=None;role=None
            if request['source_request_status']!='SOURCE_READY_CONDITIONAL_REQUEST':reason='P1_SOURCE_ABSTENTION'
            elif not f:reason='P3_MINUTES_UNAVAILABLE:'+str(minute['reason'])
            else:
                binding=dict(game_id=cohort['game_id'],player_id=request['player_id'],team_id=request['team_id'],
                    opponent_id=f['opponent_id'],statistic=stat,cohort_sha256=digest(canonical(cohort)),
                    conditioning=CONDITIONING,participation_probability=None,legal_eligibility=None,
                    p3_variant=EXPOSURE_VARIANT,p3_forecast_id=f['forecast_id'],
                    projected_exposure=f['expected_minutes_given_played'],exposure_units='minutes',
                    role_features=dict(position=f['role']['position'],historical_workload_state=f['role']['historical_workload_state']),
                    forecast_at=forecast_at,input_freeze_at=cohort['freeze_at'],event_start_at=cohort['start'])
                contract=ADMITTED_MODELS.get(stat)
                if contract is None:reason=candidates[stat]['reason']
                else:
                    try:
                        require(model_dir is not None,'S_MODEL_DIRECTORY_UNAVAILABLE')
                        require(set(contract.target_membership)=={(r['player_id'],r['team_id']) for r in p1['requests']['rows']},'S_REVIEWED_TARGET_POPULATION')
                        root=Path(model_dir)
                        forecast=_execute(binding,contract,(root/(stat+'.json')).read_bytes(),
                            (root/(stat+'.sources.json')).read_bytes(),(root/(stat+'.raw_sources.json')).read_bytes())
                        role=forecast['trained_role']
                    except (OSError,ValueError,KeyError,TypeError,AttributeError,OverflowError) as exc:reason=type(exc).__name__+':'+str(exc)
            rows.append(dict(game_id=cohort['game_id'],player_id=request['player_id'],team_id=request['team_id'],statistic=stat,
                status='FIXED_EXPOSURE_STATISTIC_RESEARCH' if forecast else 'ABSTAIN',reason=reason,
                binding=binding,trained_role=role,participation_probability=None,legal_eligibility=None,
                forecast=forecast,actual_native_model_executed=forecast is not None))
    payload=dict(schema=VERSION,kind='SOURCE_REPLAYED_P2_FIXED_EXPOSURE_DISPATCH',profile='source_listed_subset',
        implementation_sha256=digest(Path(__file__).read_bytes()),source_handoff_sha256=p1['payload_sha256'],
        p3_handoff_sha256=p3['payload_sha256'],exposure_variant=EXPOSURE_VARIANT,conditioning=CONDITIONING,
        minute_uncertainty_integrated=False,candidate_denominator=len(p1['requests']['rows']),
        attempt_denominator=len(rows),model_candidate_denominator=len(STATS),model_candidates=list(candidates.values()),
        model_directory_status=directory_status,provided_file_denominator=len(provided_files),provided_files=provided_files,
        exposure_bound_rows=sum(r['binding'] is not None for r in rows),
        forecasted_rows=sum(r['forecast'] is not None for r in rows),abstained_rows=sum(r['forecast'] is None for r in rows),
        admitted_model_count=len(ADMITTED_MODELS),forecast_at=forecast_at,rows=rows,
        genuine_participation_probability=None,production_release=False,
        missing_evidence='Independently reviewed compatible genuine saved S artifact and its exact source/cutoff/trained-role contract. Real registry is empty; numerical engine implementation does not manufacture model admission.')
    return dict(payload,payload_sha256=digest(canonical(payload)))


def read_dispatch(raw,**inputs):
    value=strict_json(raw)
    require(canonical(value)==canonical(run_dispatch(**inputs)),'S_DISPATCH_SOURCE_MODEL_OR_OUTPUT_MISMATCH')
    return value
