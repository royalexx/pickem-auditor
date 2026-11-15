"""Synthetic interface checks; no upstream real forecast is fabricated."""
import copy
import unittest
from . import frozen_research as f
from . import shadow as s
from .native_ws1 import EXACT

class ResearchTests(unittest.TestCase):
    def fixture(self):
        identity=dict(event_id='g',book='b',player_id='p',stat='receptions',line=4,period='full_game',quote_id='q')
        reference=dict(contract_id='c',candidate='C2',status='forecast',identity=identity,event_start_at='2026-11-15T18:00:00Z',model_id='C2:frozen',conditional_no_push={'over':.6,'under':.4})
        row=dict(identity,contract_id='c',model_id='S2-ew-empirical-hl4-v1',family='WS2_S2',
            forecast_id='upstream-id',event_start_at=reference['event_start_at'],
            forecast_at='2026-11-15T06:00:00Z',input_freeze_at='2026-11-15T05:00:00Z',
            model_training_cutoff_at='2026-11-14T05:00:00Z',feature_available_at='2026-11-15T04:00:00Z',
            feature_sha256='features',conditional_no_push={'over':.8,'under':.2},
            unconditional={'over':.72,'under':.18,'push':.1},stat_support='integer')
        packet=dict(artifact_sha256='artifact',feature_sha256='features',forecasts=[row])
        return packet,dict(forecasts=[reference])

    def test_fixed_values_pushes_and_new_identifiers(self):
        p,m=self.fixture();before=copy.deepcopy(m)
        out=f.transform(p,m,now='2026-11-15T07:00:00Z')
        self.assertEqual(len(out['forecasts']),5)
        self.assertTrue(all(r['status']=='forecast' for r in out['forecasts']))
        self.assertEqual(m,before)
        for r in out['forecasts']:
            self.assertIn('WS2_S2',r['model_id'])
            self.assertEqual(r['unconditional']['push'],.1)
        r=next(r for r in out['forecasts'] if r['model_id'].startswith('C4_WS2'))
        self.assertAlmostEqual(r['conditional_no_push']['over'],.725)

    def test_no_push_invention_and_identity_failures(self):
        p,m=self.fixture();p['forecasts'][0]['unconditional']=None
        self.assertTrue(all(r['unconditional'] is None for r in f.transform(p,m,now='2026-11-15T07:00:00Z')['forecasts']))
        for key,value in [('quote_id','other'),('forecast_at','2026-11-15T19:00:00Z'),('feature_sha256','wrong')]:
            p,m=self.fixture();p['forecasts'][0][key]=value
            self.assertTrue(all(r['status']=='abstain' for r in f.transform(p,m,now='2026-11-15T07:00:00Z')['forecasts']))

    def test_duplicates_and_started_games_abstain(self):
        p,m=self.fixture();p['forecasts']*=2
        self.assertTrue(all(r['status']=='abstain' for r in f.transform(p,m,now='2026-11-15T07:00:00Z')['forecasts']))
        p,m=self.fixture()
        self.assertTrue(all(r['status']=='abstain' for r in f.transform(p,m,now='2026-11-15T18:00:00Z')['forecasts']))

class NativeWS2BindingTests(unittest.TestCase):
    def test_actual_index_rows_and_feature_hash_binding(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            feature=s.canonical(dict(owner='workstream1',input_freeze_at='2026-11-15T05:00:00Z'))
            (root/'features.json').write_bytes(feature)
            native=dict(original_contract=dict(candidate_id='c',event_id='g',event_start_at='2026-11-15T18:00:00Z'),
                forecast_created_at='2026-11-15T06:00:00Z',models={'S2-ew-empirical-hl4-v1':dict(status='forecast',q_over=.72,q_under=.18,q_push=.1,p_over_given_no_push=.8)})
            rows=s.canonical([native]);(root/'forecast_rows.json').write_bytes(rows)
            index=dict(source_manifest_sha256=f.CANONICAL_SHA,forecast_rows_sha256=s.sha(rows),
                feature_packet=dict(path='features.json',sha256=s.sha(feature)),feature_freeze_at='2026-11-15T05:00:00+00:00',
                model_training_cutoff_at='2026-11-14T00:00:00Z',model_code_sha256={'module':'hash'},parameters={'half_life':4})
            raw=s.canonical(index);path=root/'INDEX.json';path.write_bytes(raw)
            bound=f.bind_ws2(path,s.sha(raw),source_root=root)
            self.assertEqual(bound['forecasts'][0]['unconditional']['push'],.1)
            self.assertEqual(bound['upstream_index']['parameters'],{'half_life':4})
            (root/'forecast_rows.json').write_bytes(b'[]')
            with self.assertRaisesRegex(ValueError,'rows_hash_mismatch'):
                f.bind_ws2(path,s.sha(raw),source_root=root)
