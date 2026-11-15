"""Adversarial weather source/time/unit tests; no external network calls."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('ws1_weather', Path(__file__).parents[1]/'scripts/nfl_sunday_weather.py')
w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)

@pytest.mark.parametrize('issued,retrieved,freeze,kickoff,valid', [
 ('2026-11-15T14:00Z','2026-11-15T15:00Z','2026-11-15T15:01Z','2026-11-15T18:00Z',True),
 ('2026-11-15T16:00Z','2026-11-15T15:00Z','2026-11-15T15:01Z','2026-11-15T18:00Z',False),
 ('2026-11-15T14:00Z','2026-11-15T15:02Z','2026-11-15T15:01Z','2026-11-15T18:00Z',False),
 ('2026-11-15T14:00Z','2026-11-15T15:00Z','2026-11-15T18:00Z','2026-11-15T18:00Z',False)])
def test_chronology(issued,retrieved,freeze,kickoff,valid):
    assert w.valid_clock(issued,retrieved,freeze,kickoff) is valid

def test_naive_clock_rejected():
    with pytest.raises(ValueError): w.stamp('2026-11-15T15:00:00')

def test_interval_does_not_invent_kickoff_validity():
    p={'uom':'wmoUnit:degC','values':[{'validTime':'2026-11-15T21:00Z/PT1H','value':10}]}
    f=w.select_field(p,w.stamp('2026-11-15T21:25Z'))
    assert f['selected']['target_minus_kickoff_seconds'] == -1500
    assert w.select_field(p,w.stamp('2026-11-15T22:00Z'))['selected'] is None

def test_overlapping_forecasts_rejected():
    v={'validTime':'2026-11-15T21:00Z/PT1H','value':10}
    with pytest.raises(ValueError): w.select_field({'values':[v,v]},w.stamp('2026-11-15T21:25Z'))

def test_native_wind_temperature_precipitation_units():
    f=lambda unit,v:{'unitCode':unit,'selected':{'value':v,'validTime':'2026-11-15T18:00Z/PT6H'}}
    assert w.normalize(f('wmoUnit:km_h-1',36),'m/s') == 10
    assert w.normalize(f('wmoUnit:degF',32),'C') == 0
    assert w.normalize(f('wmoUnit:mm',3),'mm/h') == .5
    assert w.normalize({'selected':None},'m/s') is None
    with pytest.raises(ValueError): w.normalize(f('unknown',12),'m/s')

@pytest.mark.parametrize('roof,evidence,expected',[
 ('unknown',None,'RETRACTABLE_ROOF_STATUS_UNKNOWN'),
 ('closed',None,'RETRACTABLE_ROOF_STATUS_UNKNOWN'),
 ('closed',{'source':'original'},'SHELTERED_CONFIRMED_CLOSED_ROOF')])
def test_no_fabricated_roof(roof,evidence,expected):
    assert w.exposure('retractable',roof,evidence)==expected

def test_already_started_makes_no_source_requests(monkeypatch):
    monkeypatch.setattr(w,'now',lambda:'2026-11-15T15:00:00Z')
    monkeypatch.setattr(w,'fetch',lambda *a:pytest.fail('postkickoff source request'))
    r=w.game({'espn_event_id':'original-id','scheduled_kickoff':'2026-11-15T14:30Z','fixture_key':'original'}, {})
    assert r['status']=='EXCLUDED_ALREADY_STARTED' and r['sources']==[]
    assert r['weather_feature_freeze_at'] is None

def test_source_bytes_cannot_be_overwritten(tmp_path):
    p=tmp_path/'original'; w.save(p,b'original')
    w.save(p,b'original')
    with pytest.raises(ValueError): w.save(p,b'replacement')

def test_pin_hash_tamper_rejected(tmp_path):
    p=tmp_path/'pin'; p.write_bytes(b'{}')
    with pytest.raises(AssertionError): w.load_weather_v2(p,'0'*64,'2026-11-15T15:00Z')
