"""WS1-only original NWS forecast capture; append-only research interchange v2.

Run from the existing Deepnote project root. Never calls a sportsbook endpoint.
No observations, fitted weather adjustments, or historical reconstruction.
"""
from __future__ import annotations
import hashlib
import json
import re
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path('reports/nfl_20261115_prospective')
OUT = ROOT / 'weather_v2'
CANONICAL = '5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71'
SCHEDULE = 'b9d720253f1e35b306867f4ebbbbfafc175f614da8e98ecda134f51027441471'
SCHEMA = 'ws1-nfl-pregame-weather-v2'
FIELDS = ('windSpeed', 'windDirection', 'windGust', 'temperature',
          'apparentTemperature', 'probabilityOfPrecipitation',
          'quantitativePrecipitation', 'snowfallAmount', 'iceAccumulation',
          'weather', 'hazards')

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
def stamp(s):
    d = datetime.fromisoformat(s.replace('Z', '+00:00'))
    if d.tzinfo is None: raise ValueError('NAIVE_TIME')
    return d.astimezone(timezone.utc)
def sha(b): return hashlib.sha256(b).hexdigest()
def canonical(x): return (json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
def save(path, b):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != b: raise ValueError('IMMUTABLE_CONFLICT:'+str(path))
    else:
        with path.open('xb') as f: f.write(b)
    return {'path': str(path), 'sha256': sha(b), 'size_bytes': len(b)}

def fetch(label, url):
    """Reuse original receipt on rerun, including failed attempts; never re-date."""
    rp = OUT / 'receipts' / (label+'.json')
    if rp.exists():
        rec = json.loads(rp.read_bytes())
        if rec['status'] != 'OK': return None, rec
        b = Path(rec['path']).read_bytes()
        if sha(b) != rec['sha256']: raise ValueError('SOURCE_TAMPER')
        return b, rec
    started = now()
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'PickemAuditor-WS1-research/2.0', 'Accept':'application/geo+json,application/json,text/html'})
        with urllib.request.urlopen(req, timeout=18) as response:
            b = response.read(12000000)
            if len(b) >= 12000000: raise ValueError('RESPONSE_TOO_LARGE')
            headers = dict(response.headers)
            resolved = response.url
        rec = dict(status='OK', requested_url=url, resolved_url=resolved,
                   request_started_at=started, retrieved_at=now(), headers=headers,
                   **save(OUT/'raw'/(sha(b)+'.bin'), b))
    except Exception as e:
        rec = dict(status='UNAVAILABLE', requested_url=url, request_started_at=started,
                   retrieved_at=now(), error=type(e).__name__+':'+str(e)[:300])
        b = None
        if isinstance(e, urllib.error.HTTPError):
            body = e.read()
            rec['error_response'] = save(OUT/'raw'/(sha(body)+'.bin'), body)
    save(rp, canonical(rec))
    return b, rec

def interval(s):
    start, duration = s.split('/')
    m = re.fullmatch(r'P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?', duration)
    if not m: raise ValueError('UNSUPPORTED_DURATION')
    d,h,mi,se = (float(v or 0) for v in m.groups())
    a = stamp(start)
    return a, a+timedelta(days=d,hours=h,minutes=mi,seconds=se)

def select_field(prop, kickoff):
    values = []
    for v in prop.get('values', []):
        a,b = interval(v['validTime'])
        if a <= kickoff < b:
            values.append(dict(v, valid_start_at=a.isoformat(), valid_end_at=b.isoformat(),
                               target_minus_kickoff_seconds=(a-kickoff).total_seconds()))
    if len(values) > 1: raise ValueError('AMBIGUOUS_FORECAST_INTERVAL')
    return {'unitCode':prop.get('uom'), 'selected':values[0] if values else None}

def normalize(field, target):
    s = field.get('selected')
    if not s or s.get('value') is None: return None
    v, u = s['value'], field['unitCode']
    if target == 'm/s':
        f = {'wmoUnit:km_h-1':1/3.6, 'wmoUnit:m_s-1':1., 'wmoUnit:mi_h-1':.44704, 'wmoUnit:kn':.514444}.get(u)
        if f is None: raise ValueError('UNKNOWN_WIND_UNIT:'+str(u))
        return v*f
    if target == 'C':
        if u == 'wmoUnit:degC': return v
        if u == 'wmoUnit:degF': return (v-32)*5/9
        raise ValueError('UNKNOWN_TEMPERATURE_UNIT:'+str(u))
    if target == 'mm/h':
        if u != 'wmoUnit:mm': raise ValueError('UNKNOWN_PRECIPITATION_UNIT:'+str(u))
        a,b = interval(s['validTime'])
        return v/((b-a).total_seconds()/3600)
    return v

def valid_clock(issued, retrieved, freeze, kickoff):
    return stamp(issued) <= stamp(retrieved) <= stamp(freeze) < stamp(kickoff)

def exposure(stadium_type, roof_status, evidence):
    if stadium_type == 'outdoor': return 'EXPOSED_OUTDOOR'
    if stadium_type == 'fixed_indoor': return 'SHELTERED_INDOOR'
    if stadium_type == 'retractable':
        return ('SHELTERED_CONFIRMED_CLOSED_ROOF' if roof_status == 'closed' and evidence
                else 'RETRACTABLE_ROOF_STATUS_UNKNOWN')
    return 'EXPOSURE_UNVERIFIED'

# Only a lookup request, never an assertion of game-day roof status.
VENUES = {
 'ATL': ('retractable', 'https://www.mercedesbenzstadium.com/'),
 'CLE': ('outdoor', 'https://www.clevelandbrowns.com/stadium/'),
 'GB': ('outdoor', 'https://www.packers.com/lambeau-field/'),
 'IND': ('retractable', 'https://www.lucasoilstadium.com/about/'),
 'NO': ('fixed_indoor', 'https://www.caesarssuperdome.com/about-us/stadium-facts'),
 'NYJ': ('outdoor', 'https://www.metlifestadium.com/stadium/venue-facts'),
 'TEN': ('outdoor', 'https://nissanstadium.com/stadium-information/'),
 'ARI': ('retractable', 'https://www.statefarmstadium.com/stadium/about'),
 'LV': ('fixed_indoor', 'https://www.allegiantstadium.com/stadium-information/stadium-facts'),
 'DAL': ('retractable', 'https://attstadium.com/stadium-info/'),
 'CIN': ('outdoor', 'https://www.bengals.com/stadium/'),
}

def game(event, schedule):
    gid = event['espn_event_id']; kickoff = event['scheduled_kickoff']
    row = dict(schema=SCHEMA, game_id=gid, kickoff_at=kickoff,
               fixture_key=event['fixture_key'], status='MISSING_WEATHER',
               kind='forecast', weather_feature_freeze_at=None, sources=[],
               normalized={}, native={}, missingness=[], uncertainty=[],
               exposure='EXPOSURE_UNVERIFIED', roof_status='unknown')
    if stamp(now()) >= stamp(kickoff):
        row.update(status='EXCLUDED_ALREADY_STARTED', missingness=['KICKOFF_PASSED_NO_NEW_PREGAME_RECORD'])
        return row
    comp = schedule['competitions'][0]; venue = comp['venue']
    row['original_venue'] = venue
    row['venue_evidence'] = {'path':str(ROOT/'source_control/raw'/(SCHEDULE+'.bin')), 'sha256':SCHEDULE,
                             'json_pointer':'/events/'+gid+'/competitions/0/venue'}
    home = event['home']; proposed, url = VENUES[home]
    b, rec = fetch(gid+'_stadium', url); row['sources'].append(rec)
    text = re.sub('<[^>]+>', ' ', b.decode('utf8', errors='replace')) if b else ''
    text = re.sub(r'\s+', ' ', text)
    roof_quotes = [text[max(0,m.start()-140):m.end()+180]
                   for m in re.finditer(r'retractable|fixed.roof|domed|fully.enclosed|roof',text,re.I)][:20]
    row['roof_evidence'] = dict(source=rec, excerpts=roof_quotes, game_specific_status_evidence=None)
    # Explicit retractability evidence or original ESPN outdoor flag. Indoor alone
    # never certifies a fixed roof or a closed retractable roof.
    stadium_type = ('retractable' if proposed == 'retractable' and re.search('retractable',text,re.I)
                    else 'outdoor' if proposed == 'outdoor' and venue.get('indoor') is False
                    else 'fixed_indoor' if proposed == 'fixed_indoor' and re.search(r'fixed.roof|domed|fully.enclosed',text,re.I)
                    else 'unverified')
    row['stadium_type'] = stadium_type; row['proposed_stadium_type'] = proposed
    row['exposure'] = exposure(stadium_type, 'unknown', None)
    if proposed == 'retractable':
        row['uncertainty'].append('NO_GAME_SPECIFIC_ORIGINAL_ROOF_STATUS')
    if stadium_type == 'unverified': row['uncertainty'].append('STADIUM_TYPE_NOT_VERIFIED')
    # Original OpenStreetMap geocoder response supplies coordinate lineage.
    import urllib.parse
    query = venue['fullName']+', '+venue['address']['city']
    b, rec = fetch(gid+'_coordinates', 'https://nominatim.openstreetmap.org/search?'+urllib.parse.urlencode({'q':query,'format':'jsonv2','limit':1}))
    row['sources'].append(rec)
    locations = json.loads(b) if b else []
    if not locations:
        row['missingness'].append('NO_SOURCE_LINKED_COORDINATES')
        row['weather_feature_freeze_at'] = now()
        return row
    loc = locations[0]
    row['coordinates'] = dict(latitude=float(loc['lat']), longitude=float(loc['lon']),
                              source_sha256=rec['sha256'], original=loc)
    lat,lon = float(loc['lat']),float(loc['lon'])
    b, rec = fetch(gid+'_points', f'https://api.weather.gov/points/{lat:.4f},{lon:.4f}')
    row['sources'].append(rec)
    if not b:
        row['missingness'].append('NWS_POINTS_UNAVAILABLE'); row['weather_feature_freeze_at']=now(); return row
    points = json.loads(b)['properties']
    b, rec = fetch(gid+'_grid', points['forecastGridData']); row['sources'].append(rec)
    if not b:
        row['missingness'].append('NWS_GRID_UNAVAILABLE'); row['weather_feature_freeze_at']=now(); return row
    props = json.loads(b)['properties']
    row['forecast_issued_at'] = props.get('updateTime')
    row['issuance_semantics'] = 'NWS grid properties.updateTime; original product update timestamp'
    row['retrieved_at'] = rec['retrieved_at']; row['weather_source_sha256'] = rec['sha256']
    freeze = now(); row['weather_feature_freeze_at'] = freeze
    if not props.get('updateTime') or not valid_clock(props['updateTime'],rec['retrieved_at'],freeze,kickoff):
        row['missingness'].append('FORECAST_CHRONOLOGY_INVALID'); return row
    k = stamp(kickoff)
    native = {f:select_field(props.get(f,{}),k) for f in FIELDS}
    row['native'] = native
    row['missingness'] += [f for f,v in native.items() if not v['selected'] or v['selected'].get('value') is None]
    row['normalized'] = {
        'wind_m_s':normalize(native['windSpeed'],'m/s'),
        'wind_direction_degrees':normalize(native['windDirection'],'degree'),
        'gust_m_s':normalize(native['windGust'],'m/s'),
        'temperature_c':normalize(native['temperature'],'C'),
        'apparent_temperature_c':normalize(native['apparentTemperature'],'C'),
        'precipitation_probability_percent':normalize(native['probabilityOfPrecipitation'],'percent'),
        'precipitation_interval_average_mm_h':normalize(native['quantitativePrecipitation'],'mm/h'),
        'snow_interval_average_mm_h':normalize(native['snowfallAmount'],'mm/h'),
        'ice_interval_average_mm_h':normalize(native['iceAccumulation'],'mm/h')}
    gusts = [v for v in props.get('windGust',{}).get('values',[]) if v.get('value') is not None
             and interval(v['validTime'])[0] < k+timedelta(hours=3) and interval(v['validTime'])[1] > k]
    row['gust_window'] = {'start_at':kickoff,'end_at':(k+timedelta(hours=3)).isoformat(),
                           'native_values':gusts,'unitCode':native['windGust']['unitCode']}
    row['normalized']['max_gust_first_3h_m_s'] = max((normalize({'unitCode':native['windGust']['unitCode'],'selected':v},'m/s') for v in gusts),default=None)
    row['uncertainty'] += ['DETERMINISTIC_GRID_NO_CALIBRATED_FORECAST_INTERVALS',
                           'PRECIPITATION_RATE_IS_VALID_INTERVAL_AVERAGE_NOT_INSTANTANEOUS',
                           'OUTSIDE_STADIUM_FORECAST_NOT_ON_FIELD_MEASUREMENT']
    row['forecast_uncertainty_native'] = {f:props[f] for f in props if re.search('probabil|uncert|percentile',f,re.I) and f not in FIELDS}
    row['status'] = ('VERIFIED_FORECAST' if all(row['normalized'][f] is not None for f in
                     ('wind_m_s','temperature_c','precipitation_probability_percent')) else 'PARTIAL_FORECAST')
    return row

def validate(pin):
    assert pin['schema'] == SCHEMA and pin['canonical_ws1_manifest_sha256'] == CANONICAL
    rows = pin['events']; assert len({r['game_id'] for r in rows}) == len(rows) == 12
    for s in pin['dependencies']:
        assert sha(Path(s['path']).read_bytes()) == s['sha256'], 'DEPENDENCY_TAMPER'
    for row in rows:
        for s in row['sources']:
            if s['status'] == 'OK': assert sha(Path(s['path']).read_bytes()) == s['sha256'], 'SOURCE_TAMPER'
        if row['status'] == 'EXCLUDED_ALREADY_STARTED':
            assert not row['normalized'] and row['weather_feature_freeze_at'] is None
            continue
        assert stamp(row['weather_feature_freeze_at']) < stamp(row['kickoff_at'])
        if row['status'] in ('VERIFIED_FORECAST','PARTIAL_FORECAST'):
            assert valid_clock(row['forecast_issued_at'], row['retrieved_at'],row['weather_feature_freeze_at'],row['kickoff_at'])
            assert row['kind'] == 'forecast'
            for f in row['native'].values():
                if f['selected']:
                    a,b=interval(f['selected']['validTime']); assert a <= stamp(row['kickoff_at']) < b
        assert row['exposure'] != 'SHELTERED_CONFIRMED_CLOSED_ROOF', 'NO_CLOSURE_EVIDENCE'
    return True

def main():
    pinpath = OUT/'WEATHER_FEATURE_PIN.json'
    if pinpath.exists():
        pin=json.loads(pinpath.read_bytes()); validate(pin)
        print(json.dumps({'reused':True,'sha256':sha(pinpath.read_bytes()),'summary':pin['summary']})); return
    original = ROOT/'source_control/captures/ab2eebf29ea0dfcf9b2cc4ff5287b898e6b7b15238ea059a11df3ac399ccc6c8.json'
    assert sha(original.read_bytes()) == CANONICAL
    fp=ROOT/'FORECAST_FEATURE_PIN.json'; feature=json.loads(fp.read_bytes())
    ep=Path(feature['tables']['events']['path']); assert sha(ep.read_bytes()) == feature['tables']['events']['sha256']
    events=[json.loads(l) for l in ep.read_text().splitlines()]
    sp=ROOT/'source_control/raw'/(SCHEDULE+'.bin'); assert sha(sp.read_bytes()) == SCHEDULE
    schedule={e['id']:e for e in json.loads(sp.read_bytes())['events']}
    # Serial geocoding respects the public source's request budget.
    import time
    rows=[]
    for e in events:
        row=game(e,schedule[e['espn_event_id']]); rows.append(row); print(e['espn_event_id'],row['status'],flush=True)
        time.sleep(1.1)
    table=save(OUT/'events.jsonl',b''.join(canonical(r) for r in rows))
    pin=dict(schema=SCHEMA, producer_workstream=1, source_owner='WS1_ONLY',day='2026-11-15',timezone='America/Toronto',
             canonical_ws1_manifest_sha256=CANONICAL, events=rows, event_table=table,
             dependencies=[{'path':str(p),'sha256':sha(p.read_bytes())} for p in (original,fp,ep,sp)],
             summary={'total_events':len(rows),'verified_weather':sum(r['status']=='VERIFIED_FORECAST' for r in rows),
                      'partial_weather':sum(r['status']=='PARTIAL_FORECAST' for r in rows),
                      'already_started':sum(r['status']=='EXCLUDED_ALREADY_STARTED' for r in rows),
                      'roof_uncertainty':sum('ROOF' in ' '.join(r['uncertainty']) for r in rows),
                      'complete_native_fields':sum(not r['missingness'] for r in rows)},
             historical_weather={'status':'BLOCKED_NO_AUTHORIZED_VINTAGE_ARCHIVE_IDENTIFIED','authentic_training_rows':0,
                                 'observations_and_reconstruction_excluded':True},
             downstream_weather_neutral_permitted=True,release_authority=False)
    validate(pin); saved=save(pinpath,canonical(pin))
    save(OUT/'SHA256SUMS.json',canonical([{'path':str(p),'sha256':sha(p.read_bytes())} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.json']))
    print(json.dumps(dict(pin=saved,summary=pin['summary'])))

if __name__ == '__main__': main()
