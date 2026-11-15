"""Separate WS3 weather registry and conservative unchanged-control fallback.

No fitted weather-response coefficients exist in this version. This module never
claims WEATHER_ESTIMATED and never collects a source. See WEATHER.md for WS1's
proposed interchange (not a claim that the producer has published that schema).
"""
from copy import deepcopy
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re

from .models import (MODELS, OpportunityModel, ROLE_MULTIPLIERS, ROLE_WEIGHTS,
                     canonical, require, sha, stamp, strict_json, number)

VERSION = 'ws3-weather-fallback-v1'
WEATHER_MODELS = ('O1-W-weather-volume-v1', 'O2-W-weather-usage-v1',
                  'O3-W-weather-qb-v1', 'O4-W-weather-tackles-v1',
                  'O5-W-weather-role-v1')
PARAMETERS = {'version': VERSION, 'weather_effect': 'NOT_ESTIMATED',
              'team_volume_effect': 0., 'allocation_effect': 0.,
              'efficiency_effect': 0., 'defender_involvement_effect': 0.,
              'role_weights': list(ROLE_WEIGHTS),
              'role_multipliers': list(ROLE_MULTIPLIERS),
              'fitting_evidence': None, 'sensitivity': False}
PIN_FIELDS = {'schema', 'producer_workstream', 'source_certified', 'day',
              'input_freeze_at', 'sources', 'events'}
WX_FIELDS = {'game_id', 'event_start', 'source_id', 'retrieved_at', 'issued_at',
             'valid_at', 'kind', 'venue', 'roof_status', 'wind', 'gust',
             'wind_unit', 'temperature', 'temperature_unit',
             'precipitation_type', 'precipitation_intensity', 'precipitation_unit'}

def digest_file(path):
    import hashlib
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def hash_string(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value),
            'missing_dependency_sha256')
    return value

def read_bound(root, descriptor):
    root = Path(root).resolve()
    path = (root / descriptor['path']).resolve()
    require(path.is_relative_to(root) and path.is_file(), 'weather_path_escape_or_missing')
    require(digest_file(path) == hash_string(descriptor['sha256']), 'weather_sha256_mismatch')
    return path

def normalize_weather(row, event, freeze, now):
    require(set(row) <= WX_FIELDS, 'unknown_weather_field')
    require(row['game_id'] == event['game_id'] and
            stamp(row['event_start']) == stamp(event['event_start']), 'weather_event_mismatch')
    kickoff = stamp(event['event_start'])
    require(stamp(now) < kickoff, 'kickoff_passed')
    require(row.get('kind') == 'forecast', 'postgame_or_observed_weather_forbidden')
    require(stamp(row['issued_at']) <= stamp(row['retrieved_at']) <= stamp(freeze)
            <= stamp(now) < kickoff, 'weather_source_chronology')
    require(stamp(row['valid_at']) == kickoff, 'weather_valid_time_not_kickoff')
    require(row['venue'] in ('indoor', 'outdoor', 'retractable'), 'unknown_weather_venue')
    require(row['roof_status'] in ('open', 'closed', 'none', 'unknown'), 'unknown_roof_status')
    require(not (row['venue'] == 'outdoor' and row['roof_status'] == 'closed'),
            'inconsistent_roof_exposure')
    require(not (row['venue'] == 'indoor' and row['roof_status'] == 'open'),
            'inconsistent_roof_exposure')
    require(row['wind_unit'] in ('m/s', 'km/h', 'mph'), 'unknown_wind_unit')
    require(row['temperature_unit'] in ('C', 'F'), 'unknown_temperature_unit')
    require(row['precipitation_unit'] == 'mm/h', 'unknown_precipitation_unit')
    factor = {'m/s': 1., 'km/h': 1/3.6, 'mph': .44704}[row['wind_unit']]
    wind = number(row['wind'], 'wind', 0, 500) * factor
    gust = None if row.get('gust') is None else number(row['gust'], 'gust', 0, 500) * factor
    require(gust is None or gust >= wind, 'gust_less_than_sustained_wind')
    temp = number(row['temperature'], 'temperature', -150, 180)
    temp = temp if row['temperature_unit'] == 'C' else (temp - 32) * 5/9
    require(-80 <= temp <= 65 and wind <= 150, 'implausible_weather_units')
    require(row['precipitation_type'] in ('none', 'rain', 'snow', 'freezing_rain',
                                         'sleet', 'mixed', 'unknown'), 'unknown_precipitation_type')
    precip = number(row['precipitation_intensity'], 'precipitation_intensity', 0, 500)
    require(row['precipitation_type'] != 'none' or precip == 0, 'inconsistent_precipitation')
    exposure = ('sheltered' if row['venue'] == 'indoor' or row['roof_status'] == 'closed'
                else 'unknown' if row['venue'] == 'retractable' and row['roof_status'] == 'unknown'
                else 'exposed')
    return {**row, 'wind_m_s': wind, 'gust_m_s': gust, 'temperature_c': temp,
            'precipitation_mm_h': precip, 'exposure': exposure}

def load_weather_pin(path, expected_sha256, events, now):
    """Verify a WS1-owned proposed weather manifest and all its original bytes."""
    path = Path(path).resolve()
    require(digest_file(path) == hash_string(expected_sha256), 'weather_pin_sha256_mismatch')
    pin = strict_json(path.read_bytes())
    require(set(pin) == PIN_FIELDS and pin.get('schema') == 'ws1-nfl-pregame-weather-v1',
            'unsupported_weather_schema')
    require(pin['producer_workstream'] == 1 and pin['source_certified'] is True
            and pin['day'] == '2026-11-15', 'weather_source_not_WS1_certified')
    require(stamp(pin['input_freeze_at']) <= stamp(now), 'weather_freeze_in_future')
    sources = {}
    for s in pin['sources']:
        require(s['source_id'] not in sources and s.get('original') is True
                and s.get('source_certified') is True, 'invalid_weather_source')
        read_bound(path.parent, s)
        require(stamp(s['issued_at']) <= stamp(s['retrieved_at']) <= stamp(pin['input_freeze_at']),
                'weather_receipt_after_freeze')
        sources[s['source_id']] = s
    em = {e['game_id']: e for e in events}
    out = {}
    for row in pin['events']:
        gid = row['game_id']
        require(gid in em and gid not in out, 'weather_unknown_or_duplicate_event')
        require(row['source_id'] in sources, 'unbound_weather_source')
        s = sources[row['source_id']]
        require(row['retrieved_at'] == s['retrieved_at'] and row['issued_at'] == s['issued_at'],
                'weather_row_source_clock_mismatch')
        out[gid] = normalize_weather(row, em[gid], pin['input_freeze_at'], now)
    return {'sha256': expected_sha256, 'input_freeze_at': pin['input_freeze_at'],
            'events': out, 'source_sha256': {k: s['sha256'] for k,s in sources.items()}}

def registry(dependencies, parameters=None):
    parameters = deepcopy(PARAMETERS if parameters is None else parameters)
    # No external artifact may turn the documented fallback into a purported fit.
    require(parameters == PARAMETERS, 'unvalidated_weather_parameters')
    for key in ('canonical_source', 'features', 'neutral_code', 'weather_code', 'parameters'):
        hash_string(dependencies.get(key))
    require(dependencies['parameters'] == sha(canonical(parameters)), 'weather_parameter_hash_mismatch')
    if dependencies.get('weather') is not None:
        hash_string(dependencies['weather'])
    frozen = {**dependencies, 'parameters_object': parameters}
    suffix = sha(canonical(frozen))
    return [{'model_id': name + '+' + suffix, 'base_model': neutral,
             'model_version': VERSION, 'frozen_dependencies': frozen,
             'dependency_sha256': suffix} for name,neutral in zip(WEATHER_MODELS, MODELS)]

def pair_control(neutral, dependencies, weather=None, weather_failure=None):
    """Copy a just-generated neutral report; never mutate a frozen forecast.

    Sampling is deliberately shared exactly for this unchanged fallback: no
    independent Monte Carlo noise can masquerade as an atmospheric effect.
    """
    registrations = registry(dependencies)
    require((weather or {}).get('sha256') == dependencies.get('weather'), 'weather_dependency_mismatch')
    require(neutral['manifest_sha256'] == dependencies['features'], 'feature_dependency_mismatch')
    by_model = {r['base_model']: r for r in registrations}
    rows, pairs = [], []
    weather_events = (weather or {}).get('events', {})
    for original in neutral['rows']:
        row = deepcopy(original)
        row['neutral_model'] = original['model']
        row['model'] = by_model[original['model']]['model_id']
        wx = weather_events.get(row['contract']['game_id'])
        row['weather_status'] = 'WEATHER_EFFECT_NOT_ESTIMATED'
        row['weather_evidence'] = deepcopy(wx)
        row['weather_reason'] = ((weather_failure or 'MISSING_GAME_WEATHER') if wx is None else
                                 'SHELTERED_NEUTRAL_EQUIVALENCE' if wx['exposure'] == 'sheltered' else
                                 'NO_SOURCE_SUPPORTED_HISTORICAL_WEATHER_FIT')
        row['weather_channels'] = {'team_volume': 'unchanged', 'allocation': 'unchanged',
            'catch_and_yardage_efficiency': 'unchanged', 'defender_involvement': 'unchanged',
            'role_weights': 'unchanged; experimental assumptions, not injury probabilities'}
        rows.append(row)
        valid = original['status'] == 'forecast'
        s = original.get('workload_conditional')
        probs = original.get('probabilities_conditional')
        pairs.append({'contract': deepcopy(row['contract']), 'neutral_model': original['model'],
            'weather_model': row['model'], 'status': original['status'],
            'weather_status': row['weather_status'], 'reason': row.get('reason'),
            'neutral_mean': s['mean'] if s else None, 'weather_mean': s['mean'] if s else None,
            'neutral_variance': s['sd']**2 if s else None,
            'weather_variance': s['sd']**2 if s else None,
            'neutral_probabilities': deepcopy(probs), 'weather_probabilities': deepcopy(probs),
            'delta_mean': 0. if valid else None, 'delta_variance': 0. if valid else None,
            'delta_probabilities': {k: 0. for k in probs} if valid else None,
            'conditional_production_change': 0. if valid else None,
            'conditioning': original.get('conditioning'),
            'mc_uncertainty': original.get('max_mc_standard_error')})
    teams = deepcopy(neutral['team_opportunities'])
    for t in teams:
        t['neutral_model'] = t['model']; t['model'] = registrations[0]['model_id']
        t['weather'] = 'WEATHER_EFFECT_NOT_ESTIMATED; unchanged neutral opportunities'
        t['weather_delta_mean'] = {k: 0. if v is not None else None for k,v in t['opportunities'].items()}
    return {'schema': VERSION, 'status': 'SHADOW_ONLY_WEATHER_EFFECT_NOT_ESTIMATED',
            'forecast_at': neutral['forecast_at'], 'training_cutoff_at': neutral['training_cutoff_at'],
            'input_freeze_at': neutral['input_freeze_at'], 'weather_input_freeze_at': (weather or {}).get('input_freeze_at'),
            'manifest_sha256': neutral['manifest_sha256'], 'registry': registrations,
            'weather_source_sha256': (weather or {}).get('source_sha256'),
            'historical_fitting_evidence': None, 'weather_estimated_forecasts': 0,
            'unchanged_fallback_forecasts': sum(r['status'] == 'forecast' for r in rows),
            'abstentions': sum(r['status'] != 'forecast' for r in rows),
            'rows': rows, 'paired_contract_table': pairs, 'team_opportunities': teams,
            'counts_by_game_market_model_status': [dict(game_id=g, market=s, model=m,
                status=st, n=n) for (g,s,m,st),n in sorted(Counter((r['contract']['game_id'],
                r['contract']['stat'],r['model'],r['status']) for r in rows).items())],
            'draws': neutral['draws'], 'uncertainty_note': 'Monte Carlo precision inherited from neutral; no claim of calibrated weather-model uncertainty.',
            'limitations': neutral['limitations'] + ['No weather-response fit or direct weather effects estimated. O4 retains marginal pooled per-snap involvement; run/pass-specific involvement is not estimated.'],
            'release_authority': 'NONE'}

def run_pair(packet, canonical_source_sha256, weather=None, weather_failure=None, draws=8192):
    # Neutral execution is first and never depends on a weather packet.
    neutral = OpportunityModel(packet, draws).run()
    deps = {'canonical_source': canonical_source_sha256, 'features': packet['manifest_sha256'],
            'weather': (weather or {}).get('sha256'),
            'neutral_code': digest_file(Path(__file__).with_name('models.py')),
            'native_source_validator_code': digest_file(Path(__file__).with_name('native_ws1.py')),
            'weather_code': digest_file(__file__), 'parameters': sha(canonical(PARAMETERS))}
    return neutral, pair_control(neutral, deps, weather, weather_failure)
