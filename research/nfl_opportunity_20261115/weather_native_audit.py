"""Offline audit of the actual WS1 weather-v2 pin; never collects or forecasts."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from .models import canonical, require, sha, stamp, strict_json
from .feature_handoff_audit import bound, FEATURE_PIN_SHA
from .weather_run import CANONICAL

WEATHER_PIN_SHA = '273da5a6f5456e99e9b5bd4f2172abce1bf77c7bfbe82d38199886fcad612807'
BASE = 'reports/nfl_20261115_prospective/weather_v2/'


def audit_weather(root):
    root = Path(root).resolve()
    pin = strict_json(bound(root, BASE+'WEATHER_FEATURE_PIN.json', WEATHER_PIN_SHA).read_bytes())
    require(pin['schema'] == 'ws1-nfl-pregame-weather-v2' and
            pin['producer_workstream'] == 1 and pin['source_owner'] == 'WS1_ONLY', 'weather_owner')
    require(pin['canonical_ws1_manifest_sha256'] == CANONICAL, 'weather_canonical_binding')
    for d in pin['dependencies']:
        bound(root, d['path'], d['sha256'])
    require(any(d['sha256'] == FEATURE_PIN_SHA for d in pin['dependencies']), 'weather_feature_binding')
    table = pin['event_table']
    rows = [strict_json(l) for l in bound(root, table['path'], table['sha256']).read_bytes().splitlines()]
    require(rows == pin['events'], 'weather_table_mismatch')
    feature = strict_json((root/'reports/nfl_20261115_prospective/FORECAST_FEATURE_PIN.json').read_bytes())
    events = feature['tables']['events']
    events = {r['espn_event_id']: r for r in
              [strict_json(l) for l in bound(root, events['path'], events['sha256']).read_bytes().splitlines()]}
    require(len(rows) == len(events) == len({r['game_id'] for r in rows}), 'weather_event_denominator')
    # Import only pure validation/normalization helpers, never producer.main/game/fetch.
    import importlib.util
    path = root/'scripts/nfl_sunday_weather_v2.py'
    spec = importlib.util.spec_from_file_location('ws1_weather_helpers', path)
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    checks = []
    for r in rows:
        e = events[r['game_id']]
        require(stamp(r['kickoff_at']) == stamp(e['scheduled_kickoff']) and
                r['fixture_key'] == e['fixture_key'], 'weather_event_identity')
        require(r['kind'] == 'forecast', 'observed_weather_forbidden')
        for s in r['sources']:
            if s['status'] == 'OK':
                bound(root, s['path'], s['sha256'])
                require(stamp(s['retrieved_at']) <= stamp(r['weather_feature_freeze_at']), 'weather_source_after_freeze')
            if s.get('error_response'):
                bound(root, s['error_response']['path'], s['error_response']['sha256'])
        if r['status'] == 'EXCLUDED_ALREADY_STARTED':
            require(not r['normalized'] and r['weather_feature_freeze_at'] is None, 'backfilled_weather')
            continue
        require(stamp(r['weather_feature_freeze_at']) < stamp(r['kickoff_at']), 'weather_frozen_after_kickoff')
        if r['status'] in ('VERIFIED_FORECAST','PARTIAL_FORECAST'):
            require(helpers.valid_clock(r['forecast_issued_at'],r['retrieved_at'],
                    r['weather_feature_freeze_at'],r['kickoff_at']), 'weather_clock')
            for f in r['native'].values():
                if f['selected']:
                    a,b = helpers.interval(f['selected']['validTime'])
                    require(a <= stamp(r['kickoff_at']) < b, 'weather_valid_interval')
            for native, normalized, unit in [('windSpeed','wind_m_s','m/s'),
                    ('windGust','gust_m_s','m/s'),('temperature','temperature_c','C'),
                    ('quantitativePrecipitation','precipitation_interval_average_mm_h','mm/h')]:
                require(helpers.normalize(r['native'][native],unit) == r['normalized'][normalized], 'weather_unit_conversion')
        checks.append({'game_id':r['game_id'], 'exposure':r['exposure'], 'status':r['status'],
                       'freeze_at':r['weather_feature_freeze_at'], 'kickoff_at':r['kickoff_at']})
    sums = strict_json((root/(BASE+'SHA256SUMS.json')).read_bytes())
    failures = []
    for d in sums:
        try: bound(root, d['path'], d['sha256'])
        except (ValueError, OSError) as exc: failures.append({'path':d['path'], 'reason':str(exc)})
    return {'schema':'ws3-native-weather-v2-audit-v1','status':'WEATHER_EFFECT_NOT_ESTIMATED',
            'audit_at':datetime.now(timezone.utc).isoformat(),'weather_pin_sha256':WEATHER_PIN_SHA,
            'canonical_source_sha256':CANONICAL,'feature_pin_sha256':FEATURE_PIN_SHA,
            'summary_original':pin['summary'],'historical_weather_original':pin['historical_weather'],
            'event_checks':checks,'exposure_counts':dict(Counter(r['exposure'] for r in rows)),
            'checksum_files_checked':len(sums),'checksum_failures':failures,
            'producer_code_sha256':sha(path.read_bytes()),'audit_code_sha256':sha(Path(__file__).read_bytes()),
            'neutral_forecasts':0,'fitted_weather_forecasts':0,'unchanged_fallback_forecasts':0,
            'matched_pairs':0,'fitted_coefficients':0,'release_authority':False,
            'reason':'CURRENT_FORECAST_VINTAGES_ARE_NOT_HISTORICAL_TRAINING_DATA'}
