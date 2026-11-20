"""Exact frozen sources -> admitted prospective S1 -> fixed-M0 shadow laws.

This additional MEM@MIN population is not a new general source root, a full
roster claim, a fitted-model quality acceptance or a joint minutes/stat law.
"""
from collections import Counter
from pathlib import Path

from v2 import nba_opportunity as minutes
from v2.nba_s_family import model as native
from v2.nba_s_family.prospective_fit_v1 import PARAMETERS, SEED
from . import prospective_s_admission_v1 as registry
from .p1_subset_handoff_v1 import canonical, digest, export_requests
from .prospective_s_sources_v1 import build_dataset, POSITIONS, SPEC_SHA
from .subset_contract_v1 import strict_json
from .subset_p3_v1 import require, _load_model, MODEL_SHA, NATIVE_SHA
from .subset_p2_dispatch_v1 import ModelContract, _execute, CONDITIONING

VERSION = 'nba-genuine-prospective-fixed-M0-S1/1.0.0'
STATS = ('points', 'rebounds', 'assists', 'threes')


def verify_bundle(raw_dir, spec_path, policy_path, model_dir, prefit_path, admission_path):
    """Reconstruct all training rows and fitted bytes, not hash labels alone."""
    require(all(x is not None for x in (registry.PREFIT_DECISION_SHA,
        registry.ARTIFACT_DECISION_SHA, registry.FIT_RECEIPT_SHA,
        registry.DATASET_SHA, registry.READER_SHA, registry.ARTIFACT_ADMITTED_AT)), 'GENUINE_S_ADMISSION_CLOSED')
    require(digest(Path(prefit_path).read_bytes()) == registry.PREFIT_DECISION_SHA,
        'GENUINE_S_PREFIT_DECISION_BYTES')
    require(digest(Path(admission_path).read_bytes()) == registry.ARTIFACT_DECISION_SHA,
        'GENUINE_S_ARTIFACT_DECISION_BYTES')
    dataset = build_dataset(raw_dir, spec_path, policy_path)
    require(dataset['reader_raw_sha256'] == registry.READER_SHA and
        dataset['payload_sha256'] == registry.DATASET_SHA, 'GENUINE_S_READER_DATASET')
    root = Path(model_dir); receipt_raw = (root/'fit_receipt.json').read_bytes()
    require(digest(receipt_raw) == registry.FIT_RECEIPT_SHA, 'GENUINE_S_FIT_RECEIPT_BYTES')
    receipt = strict_json(receipt_raw)
    require(receipt['prefit_approval_raw_sha256'] == registry.PREFIT_DECISION_SHA and
        receipt['source_dataset_sha256'] == registry.DATASET_SHA and
        receipt['source_reader_sha256'] == registry.READER_SHA and
        receipt['prefit_spec_raw_sha256'] == SPEC_SHA, 'GENUINE_S_FIT_LINEAGE')
    require(receipt['fixed_hyperparameters'] == PARAMETERS and receipt['seed'] == SEED,
        'GENUINE_S_FIXED_FIT_PROTOCOL')
    require(receipt['native_code_sha256'] == digest(Path(native.__file__).read_bytes()),
        'GENUINE_S_NATIVE_CODE')
    require(receipt['data_cutoff_at'] == dataset['data_cutoff_at'] and
        minutes.utc(receipt['data_cutoff_at']) <= minutes.utc(receipt['fit_started_at']) <=
        minutes.utc(receipt['fit_completed_at']) <= minutes.utc(receipt['artifact_bytes_verified_at']),
        'GENUINE_S_FIT_CLOCK_CHAIN')
    manifest_raw = (root/'source_manifest.json').read_bytes()
    bodymap_raw = (root/'raw_sources.json').read_bytes()
    require(manifest_raw == canonical(dataset['source_manifest']) and
        bodymap_raw == canonical(dataset['raw_sources']) and
        (root/'source_dataset.json').read_bytes() == canonical(dataset), 'GENUINE_S_SAVED_SOURCE_REPLAY')
    require(digest(manifest_raw) == receipt['source_manifest_raw_sha256'] and
        digest(bodymap_raw) == receipt['raw_sources_raw_sha256'], 'GENUINE_S_FIT_SOURCE_JOIN')
    require(set(registry.ARTIFACTS) == set(STATS) == set(receipt['artifacts']),
        'GENUINE_S_ARTIFACT_POPULATION')
    artifacts = {}
    for stat in STATS:
        raw = (root/(stat+'.json')).read_bytes()
        require(digest(raw) == registry.ARTIFACTS[stat] == receipt['artifacts'][stat]['sha256'],
            'GENUINE_S_ARTIFACT_BYTES:'+stat)
        replay = native.fit(dataset['histories'][stat], asof_cutoff_utc=dataset['data_cutoff_at'],
            source_manifest=dataset['source_manifest'], stat=stat, family='S1',
            hyperparameters=PARAMETERS, seed=SEED)
        require(replay.payload == raw, 'GENUINE_S_NATIVE_FIT_REPLAY:'+stat)
        artifacts[stat] = raw
    return dataset, receipt, artifacts, manifest_raw, bodymap_raw


def _minutes_rows(dataset, handoff, raw_dir, spec_path, cohort, model_path, forecast_at):
    model = _load_model(model_path)
    require(minutes.utc(model.training_cutoff_at) <= minutes.utc(cohort['freeze_at']),
        'GENUINE_M0_MODEL_AFTER_FREEZE')
    raw = Path(raw_dir); spec = strict_json(Path(spec_path).read_bytes())
    require(digest(Path(spec_path).read_bytes()) == SPEC_SHA,
        'GENUINE_M0_SPEC_BYTES')
    board = strict_json((raw/'scoreboard/body.raw').read_bytes())
    event = next(e for e in board['events'] if str(e['id']) == cohort['game_id'])
    sides = {str(t['id']):t['homeAway'] for t in event['competitions'][0]['competitors']}
    output = []; observations = []
    for request in handoff['requests']['rows']:
        pid, team = request['player_id'], request['team_id']; tid = team.removeprefix('espn:team:')
        roster = strict_json((raw/('roster-'+tid)/'body.raw').read_bytes())
        person = next(p for p in roster['athletes'] if 'espn:player:'+str(p['id']) == pid)
        position = person.get('position', {}).get('abbreviation')
        games = sorted(spec['selected_espn_games'][tid], key=lambda g:(g['date'],g['id']))
        window = []; history = []; reason = None; features = None; gap = None; forecast = None
        for game in games:
            found = [r for r in dataset['records'] if r['game_id']=='espn:game:'+game['id']
                and r['team_id']==team and r.get('player_id')==pid]
            if len(found) == 1:
                record = found[0]
                state = 'PLAYED' if record['fit_included'] else 'DNP' if (
                    record['state']=='DNP' and record['reason']=='EXPLICIT_DNP_NO_TRAINING_EXPOSURE'
                    and record['role'] is not None) else 'UNKNOWN'
                sec = record['exact_seconds']; start = record['game_start_at']
            else:
                record = None; state = 'UNKNOWN'; sec = None; start = game['date']
            obs = dict(player_id=pid, team_id=team, game_id=game['id'], state=state,
                exact_seconds=sec, exclusion_reason=record['reason'] if record else 'MISSING_OR_AMBIGUOUS_DATED_PLAYER',
                game_start_at=start)
            window.append(obs); observations.append(obs)
            if state == 'PLAYED':
                history.append(dict(game_date=start[:10], game_id=game['id'], workload=sec/60., team=team))
        schedule = strict_json((raw/('schedule-'+tid)/'body.raw').read_bytes())
        unobserved = [dict(game_id=str(e['id']), start=e['date'], state='UNOBSERVED_AT_DATA_CUTOFF')
            for e in schedule['events'] if minutes.utc(dataset['data_cutoff_at']) <=
            minutes.utc(e['date']) < minutes.utc(cohort['start'])]
        try:
            require(request['source_request_status']=='SOURCE_READY_CONDITIONAL_REQUEST', 'P1_SOURCE_ABSTENTION')
            require(position in POSITIONS, 'GENUINE_S_CURRENT_POSITION_UNRESOLVED')
            require(len(history)>=5, 'INSUFFICIENT_PRIOR_APPEARANCES')
            first = next(i for i,r in enumerate(window) if r['game_id']==history[-10:][0]['game_id'])
            require(all(r['state'] in ('PLAYED','DNP') for r in window[first:]),
                'UNKNOWN_CONDITIONAL_HISTORY_WINDOW')
            last = next(i for i,r in enumerate(window) if r['game_id']==history[-1]['game_id'])
            require(all(r['state']=='DNP' for r in window[last+1:]), 'UNKNOWN_RETURN_GAP_POPULATION')
            gap = len(window[last+1:])
            features = minutes.causal_features(history, game_date=cohort['start'][:10], team=team,
                home=sides[tid]=='home', prior_team_games_missed=gap)
            native_input = minutes.PregameOpportunityInput(game_id=cohort['game_id'], player_id=pid,
                team_id=team, opponent_id='espn:team:'+next(t for t in cohort['teams'] if t!=tid),
                event_start_at=cohort['start'], forecast_at=forecast_at, input_freeze_at=cohort['freeze_at'],
                source_available_at=dataset['data_cutoff_at'], source_ingested_at=dataset['data_cutoff_at'],
                training_cutoff_at=model.training_cutoff_at,
                source_sha256=digest(canonical(dict(p1=handoff['payload_sha256'], dataset=dataset['payload_sha256']))),
                features=features, position=position,
                reliability_reasons=('CURRENT_TEAM_LAST_TEN_COMPLETED_WINDOW_ONLY',
                    'EXACT_SOURCE_REPORTED_SECONDS', 'PINNED_EXPLORATORY_WS2_MODEL',
                    'UTC_CALENDAR_AND_OBSERVED_HISTORY_PROXIES',
                    'FUTURE_INTERVENING_GAMES_UNOBSERVED' if unobserved else 'NO_LISTED_INTERVENING_GAME'))
            forecast = model.forecast('M0', native_input, seed=SEED)
        except ValueError as exc: reason = str(exc)
        output.append(dict(player_id=pid, team_id=team, name=request['name'], model='M0',
            forecast=forecast, reason=reason, features=features, position=position,
            observed_positive_appearances=len(history), explicit_observed_dnp_return_gap=gap,
            unobserved_intervening_scheduled_games=unobserved,
            participation_probability=None, legal_eligibility=None))
    return output, observations


def run_forecasts(*, raw_dir, spec_path, policy_path, model_dir, prefit_path, admission_path,
        cohort, model_path, forecast_at):
    """Public genuine path: no caller rows, training labels or approval flags."""
    require(registry.COHORT_SHA is not None and digest(canonical(cohort))==registry.COHORT_SHA,
        'GENUINE_S_UNREVIEWED_FORECAST_COHORT')
    dataset, receipt, artifacts, manifest_raw, bodymap_raw = verify_bundle(
        raw_dir, spec_path, policy_path, model_dir, prefit_path, admission_path)
    require({k:cohort[k] for k in ('game_id','start','teams')}==
        {k:dataset['target'][k] for k in ('game_id','start','teams')}, 'GENUINE_S_TARGET_SCOPE')
    require(minutes.utc(receipt['artifact_bytes_verified_at'])<=minutes.utc(registry.ARTIFACT_ADMITTED_AT)<=minutes.utc(cohort['freeze_at'])<=
        minutes.utc(forecast_at)<minutes.utc(cohort['start']), 'GENUINE_S_FORECAST_CLOCK_CHAIN')
    require(minutes.utc('2026-11-20T01:30Z')<=minutes.utc(forecast_at)<=minutes.utc('2026-11-20T04:00Z'),
        'GENUINE_S_PREREGISTERED_FORECAST_WINDOW')
    handoff = export_requests(raw_dir, cohort)
    members = [dict(player_id=r['player_id'],team_id=r['team_id'],name=r['name'])
        for r in handoff['requests']['rows']]
    require(members==dataset['frozen_candidates']==cohort['frozen_candidates'],
        'GENUINE_S_COMPLETE_FROZEN_CANDIDATES')
    m0, observations = _minutes_rows(dataset, handoff, raw_dir, spec_path, cohort, model_path, forecast_at)
    membership = tuple((r['player_id'],r['team_id']) for r in members)
    roles = tuple((p,state,'ESPN_POSITION_BIN_AT_CAPTURE:'+group) for p,group in POSITIONS.items()
        for state in ('low','mid','high'))
    contracts = {stat:ModelContract(registry.ARTIFACTS[stat],digest(manifest_raw),digest(bodymap_raw),
        receipt['native_code_sha256'],registry.COHORT_SHA,dataset['data_cutoff_at'],stat,'S1',roles,
        membership,'EXACT_FROZEN_NBA_HTML_ESPN_JOIN_PROSPECTIVE_S1_V1') for stat in STATS}
    rows = []
    for minute in m0:
        for stat in STATS:
            prediction = None; binding = None; reason = minute['reason']
            if minute['forecast'] is not None:
                f = minute['forecast']
                binding = dict(game_id=cohort['game_id'],player_id=minute['player_id'],team_id=minute['team_id'],
                    opponent_id=f['opponent_id'],statistic=stat,cohort_sha256=registry.COHORT_SHA,
                    conditioning=CONDITIONING,participation_probability=None,legal_eligibility=None,
                    p3_variant='M0',p3_forecast_id=f['forecast_id'],projected_exposure=f['expected_minutes_given_played'],
                    exposure_units='minutes',role_features=f['role'],forecast_at=forecast_at,
                    input_freeze_at=cohort['freeze_at'],event_start_at=cohort['start'])
                try: prediction = _execute(binding,contracts[stat],artifacts[stat],manifest_raw,bodymap_raw)
                except (ValueError,KeyError,TypeError,OverflowError) as exc: reason = str(exc)
            rows.append(dict(player_id=minute['player_id'],team_id=minute['team_id'],name=minute['name'],
                statistic=stat,status='FIXED_EXPOSURE_STATISTIC_RESEARCH' if prediction else 'ABSTAIN',
                reason=reason,forecast=prediction,binding=binding,participation_probability=None,legal_eligibility=None))
    payload = dict(schema=VERSION,status='UNCERTIFIED/SHADOW',profile='source_listed_subset',
        source_admission_scope='EXACT_FROZEN_60_CAPTURE_POPULATION_ONLY',
        source_dataset_sha256=dataset['payload_sha256'],fit_receipt_raw_sha256=registry.FIT_RECEIPT_SHA,
        prefit_decision_raw_sha256=registry.PREFIT_DECISION_SHA,artifact_decision_raw_sha256=registry.ARTIFACT_DECISION_SHA,
        implementation_sha256=digest(Path(__file__).read_bytes()),admission_code_sha256=digest(Path(registry.__file__).read_bytes()),
        cohort=cohort,cohort_sha256=registry.COHORT_SHA,forecast_at=forecast_at,
        forecast_horizon_seconds=(minutes.utc(cohort['start'])-minutes.utc(forecast_at)).total_seconds(),
        data_cutoff_at=dataset['data_cutoff_at'],fit_started_at=receipt['fit_started_at'],
        fit_completed_at=receipt['fit_completed_at'],artifact_bytes_verified_at=receipt['artifact_bytes_verified_at'],
        artifact_independently_admitted_at=registry.ARTIFACT_ADMITTED_AT,
        candidate_denominator=len(members),attempt_denominator=len(rows),
        source_ready_candidates=handoff['requests']['source_ready_rows'],
        source_abstained_candidates=handoff['requests']['abstained_source_rows'],
        minute_forecasted_candidates=sum(r['forecast'] is not None for r in m0),
        forecasted_rows=sum(r['forecast'] is not None for r in rows),abstained_rows=sum(r['forecast'] is None for r in rows),
        abstention_reasons=dict(Counter(r['reason'] for r in rows if r['forecast'] is None)),
        source_observation_denominator=dataset['source_observation_denominator'],
        training_attempt_denominator=dataset['training_attempt_denominator'],
        included_training_attempts=dataset['included_training_attempts'],excluded_training_attempts=dataset['excluded_training_attempts'],
        source_requests=handoff['requests'],minutes=m0,minute_history_observation_denominator=len(observations),
        minute_history_observations=observations,rows=rows,
        minute_model_raw_sha256=MODEL_SHA,minute_reader_raw_sha256=NATIVE_SHA,
        admitted_S_artifacts=registry.ARTIFACTS,conditioning=CONDITIONING,
        minute_uncertainty_integrated=False,team_allocation_performed=False,
        genuine_participation_probability=None,legal_eligible_population_count=None,
        source_publication_at=None,original_historical_pregame_availability=None,correction_history_complete=None,
        accuracy_validated=False,full_G1_accepted=False,production_release=False)
    return dict(payload,payload_sha256=digest(canonical(payload)))


def read_forecasts(raw, **inputs):
    result = strict_json(raw)
    require(canonical(result)==canonical(run_forecasts(**inputs)), 'GENUINE_S_SOURCE_MODEL_OUTPUT_REPLAY')
    return result
