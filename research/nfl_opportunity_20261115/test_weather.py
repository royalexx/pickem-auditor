"""Acceptance tests use explicitly synthetic inputs; no actual Sunday forecasts."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from .models import GateError, OpportunityModel, canonical, sha
from .test_models import fixture, NOW
from .weather import (PARAMETERS, digest_file, load_weather_pin, normalize_weather,
                      pair_control, registry, run_pair)

def weather_row():
    return dict(game_id='target', event_start='2026-11-15T18:00:00+00:00',
        source_id='wx', retrieved_at='2026-11-15T03:00:00+00:00',
        issued_at='2026-11-15T02:00:00+00:00', valid_at='2026-11-15T18:00:00+00:00',
        kind='forecast', venue='outdoor', roof_status='none', wind=10., gust=20.,
        wind_unit='mph', temperature=32., temperature_unit='F',
        precipitation_type='rain', precipitation_intensity=2., precipitation_unit='mm/h')

def bound_weather(root, events):
    raw=b'SYNTHETIC WEATHER FORECAST SOURCE ONLY'; (root/'raw').write_bytes(raw)
    row=weather_row()
    pin=dict(schema='ws1-nfl-pregame-weather-v1', producer_workstream=1,
        source_certified=True,day='2026-11-15',input_freeze_at='2026-11-15T04:00:00+00:00',
        sources=[dict(source_id='wx', path='raw',sha256=sha(raw),original=True,
            source_certified=True, issued_at=row['issued_at'], retrieved_at=row['retrieved_at'])],
        events=[row])
    data=canonical(pin);path=root/'WEATHER_FEATURE_PIN.json';path.write_bytes(data)
    return path,sha(data)

class WeatherTests(unittest.TestCase):
    def normalize(self, row):
        return normalize_weather(row,fixture()['events'][0], '2026-11-15T04:00:00+00:00',NOW)

    def test_units(self):
        wx=self.normalize(weather_row())
        self.assertAlmostEqual(wx['wind_m_s'],4.4704)
        self.assertAlmostEqual(wx['gust_m_s'],8.9408)
        self.assertAlmostEqual(wx['temperature_c'],0)
        r=weather_row();r.update(wind=36,gust=72,wind_unit='km/h',temperature=10,temperature_unit='C')
        wx=self.normalize(r);self.assertAlmostEqual(wx['wind_m_s'],10)
        self.assertAlmostEqual(wx['temperature_c'],10)

    def test_invalid_units_and_weather(self):
        for change in [dict(wind_unit='knots'),dict(temperature_unit='Kelvin'),
                       dict(precipitation_unit='inch/h'),dict(wind=-1),dict(gust=1),
                       dict(temperature=float('nan')),dict(precipitation_type='none'),
                       dict(venue='outdoor',roof_status='closed')]:
            with self.subTest(change=change), self.assertRaises(GateError):
                self.normalize({**weather_row(),**change})

    def test_no_future_observed_or_hindsight_weather(self):
        for change in [dict(issued_at='2026-11-15T20:00:00+00:00'),
                       dict(retrieved_at='2026-11-15T06:00:00+00:00'),dict(kind='observation'),
                       dict(valid_at='2026-11-16T18:00:00+00:00'),dict(final_weather='rain')]:
            with self.subTest(change=change), self.assertRaises(GateError):
                self.normalize({**weather_row(),**change})
        with self.assertRaisesRegex(GateError,'kickoff_passed'):
            normalize_weather(weather_row(),fixture()['events'][0],NOW,'2026-11-15T18:00:00+00:00')

    def test_roof_exposure(self):
        for venue,roof,expected in [('indoor','closed','sheltered'),
                ('retractable','closed','sheltered'),('retractable','open','exposed'),
                ('retractable','unknown','unknown'),('outdoor','none','exposed')]:
            wx=self.normalize({**weather_row(),'venue':venue,'roof_status':roof})
            self.assertEqual(wx['exposure'],expected)

    def test_original_hash_and_pin_hash(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p,h=bound_weather(root,fixture()['events'])
            w=load_weather_pin(p,h,fixture()['events'],NOW)
            self.assertEqual(w['sha256'],h)
            with self.assertRaisesRegex(GateError,'pin_sha256'):
                load_weather_pin(p,'0'*64,fixture()['events'],NOW)
            (root/'raw').write_bytes(b'TAMPERED')
            with self.assertRaisesRegex(GateError,'weather_sha256'):
                load_weather_pin(p,h,fixture()['events'],NOW)

    def test_duplicate_event_source_clock_and_path_escape(self):
        for mutation in [lambda m:m['events'].append(copy.deepcopy(m['events'][0])),
                         lambda m:m['sources'][0].update(path='../raw'),
                         lambda m:m['events'][0].update(issued_at=NOW),
                         lambda m:m['events'][0].update(game_id='other'),
                         lambda m:m.update(source_certified=False)]:
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);p,h=bound_weather(root,fixture()['events']);m=__import__('json').loads(p.read_bytes())
                mutation(m);data=canonical(m);p.write_bytes(data)
                with self.assertRaises(GateError):load_weather_pin(p,sha(data),fixture()['events'],NOW)

    def pair(self, wx=None):
        p=fixture();p['manifest_sha256']='1'*64
        return run_pair(p,'2'*64,wx,draws=1024)

    def test_missing_weather_is_identical_control(self):
        before=canonical(fixture());n,w=self.pair()
        self.assertEqual(canonical(fixture()),before)
        self.assertEqual(w['weather_estimated_forecasts'],0)
        self.assertGreater(w['unchanged_fallback_forecasts'],0)
        for a,b in zip(n['rows'],w['rows']):
            self.assertEqual(a['contract'],b['contract'])
            self.assertEqual(a.get('predictive_distribution_conditional'),b.get('predictive_distribution_conditional'))
            self.assertEqual(a.get('conditioning'),b.get('conditioning'))
            self.assertEqual(b['weather_status'],'WEATHER_EFFECT_NOT_ESTIMATED')
        self.assertTrue(all(p['delta_mean']==0 for p in w['paired_contract_table'] if p['status']=='forecast'))

    def test_indoor_and_exposed_zero_effect_equivalence(self):
        for venue,roof in [('indoor','closed'),('outdoor','none')]:
            wx=self.normalize({**weather_row(),'venue':venue,'roof_status':roof})
            n,w=self.pair({'sha256':'3'*64,'events':{'target':wx}})
            for p in w['paired_contract_table']:
                self.assertEqual(p['neutral_probabilities'],p['weather_probabilities'])
                self.assertEqual(p['neutral_variance'],p['weather_variance'])

    def test_no_doubled_effects_and_role_mixture_preserved(self):
        n,w=self.pair()
        for a,b in zip(n['team_opportunities'],w['team_opportunities']):
            self.assertEqual(a['distributions'],b['distributions'])
            self.assertEqual(b['conservation_max_error'],0)
        self.assertEqual(w['registry'][4]['frozen_dependencies']['parameters_object']['role_weights'],[.2,.6,.2])
        for row in w['rows']:
            if row['status']=='forecast':
                self.assertAlmostEqual(sum(row['probabilities_conditional'].values()),1)
                self.assertEqual(set(row['weather_channels'].values())-{'unchanged'},
                                 {'unchanged; experimental assumptions, not injury probabilities'})

    def test_backup_qb_and_official_tackle_accounting_unchanged(self):
        n,w=self.pair()
        self.assertTrue(all(r['status']=='abstain' for r in w['rows'] if 'backup' in r['contract']['player_id']))
        for a,b in zip(n['rows'],w['rows']):
            self.assertEqual(a.get('reason'),b.get('reason'))
        # Existing neutral suite exercises the actual three-component draw identity.

    def test_registry_hashes_change_with_dependencies_reject_nonzero(self):
        n,w=self.pair();deps=w['registry'][0]['frozen_dependencies'].copy();deps.pop('parameters_object')
        a=registry(deps);deps['weather']='4'*64;b=registry(deps)
        self.assertNotEqual(a[0]['model_id'],b[0]['model_id'])
        with self.assertRaisesRegex(GateError,'unvalidated_weather_parameters'):
            registry(deps,{**PARAMETERS,'team_volume_effect':-.1})
        deps['parameters']='0'*64
        with self.assertRaisesRegex(GateError,'parameter_hash'):registry(deps)

    def test_exact_line_and_books_preserved_and_input_not_mutated(self):
        n,w=self.pair();before=canonical(n)
        deps=w['registry'][0]['frozen_dependencies'].copy();deps.pop('parameters_object')
        w=pair_control(n,deps)
        self.assertEqual(canonical(n),before)
        for a,b in zip(n['rows'],w['paired_contract_table']):
            self.assertEqual(a['contract'],b['contract'])
        self.assertEqual(len(n['rows']),len(w['paired_contract_table']))

    def test_runner_freezes_neutral_before_invalid_optional_weather(self):
        from . import weather_run
        from .models import stamp, strict_json
        packet=fixture();packet['manifest_sha256']='1'*64
        packet['manifest']['canonical_source_manifest_sha256']=weather_run.CANONICAL
        candidates=[{**c,'candidate_id':c['contract_id'],'source_certified':True,
                     'event_start_at':packet['events'][0]['event_start']} for c in packet['contracts']]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'source_control').mkdir()
            (root/'source_control/HANDOFF_PIN.json').write_bytes(canonical(dict(
                source_control_manifest_sha256=weather_run.CANONICAL,
                source_control_manifest_relative_path='native.json')))
            src=root/'native.json';src.write_bytes(canonical({'candidates':candidates}))
            def invalid_weather(*args):
                self.assertEqual(len(list((root/'opportunity_models/weather/neutral_control').rglob('report.json'))),1)
                raise GateError('weather_sha256_mismatch')
            with patch.object(weather_run,'datetime',Mock(now=lambda tz:stamp(NOW))), \
                 patch.object(weather_run,'read_bound',return_value=src), \
                 patch.object(weather_run,'consume',return_value={'source_checks':[]}), \
                 patch.object(weather_run,'load_packet',return_value=packet), \
                 patch.object(weather_run,'load_weather_pin',side_effect=invalid_weather):
                receipts=weather_run.execute(root,src,'1'*64,root/'bad_weather','2'*64,1024)
            neutral=strict_json((Path(receipts['neutral']['directory'])/'report.json').read_bytes())
            weather=strict_json((Path(receipts['weather']['directory'])/'report.json').read_bytes())
            self.assertGreater(weather['unchanged_fallback_forecasts'],0)
            self.assertEqual(weather['rows'][0]['weather_reason'],'WEATHER_REJECTED:weather_sha256_mismatch')
            self.assertEqual(neutral['rows'][0]['contract'],weather['rows'][0]['contract'])

if __name__=='__main__': unittest.main(verbosity=2)
