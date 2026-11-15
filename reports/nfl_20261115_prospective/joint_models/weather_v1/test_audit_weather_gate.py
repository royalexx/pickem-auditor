"""Synthetic gate tests, no claims about real weather or prospective skill."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import audit_weather_gate_v2 as gate

class GateTests(unittest.TestCase):
    def fixture(self):
        c=dict(contract_id='synthetic',event_id='fixture',player_id='qb',team_id='A',
               stat_key='pass_attempts',period='full_game',line=30.5,original_quote_id='q')
        row=dict(c,model_id='J1',draws=4096,mean=31.,variance=20.,p_over=.5,
                 p_under=.5,p_push=0.,mc_se_over=.0078125)
        o={'canonical_ws1_sha256':gate.SOURCE_SHA,
           'input_packet':{'events':[{'event_start_at':'2099-01-01T18:00:00Z'}],'contracts':[c]},
           'model_output':{'forecast_created_at':'2099-01-01T15:00:00Z','contracts':[row]}}
        return o,{'synthetic':{'book':'synthetic-book'}}
    def test_unavailable_is_null_not_zero(self):
        o,c=self.fixture();r=gate.pair_rows(o,'a'*64,c)[0]
        self.assertIsNone(r['weather_distribution']);self.assertIsNone(r['delta_mean'])
        self.assertIsNone(r['paired_mc_uncertainty'])
        self.assertTrue(r['pair_status'].startswith('ABSTAIN'))
    def test_copy_is_exact_and_does_not_mutate_neutral(self):
        o,c=self.fixture();before=deepcopy(o);r=gate.pair_rows(o,'a'*64,c)[0]
        self.assertEqual(r['neutral_distribution'],o['model_output']['contracts'][0])
        r['neutral_distribution']['mean']=999
        self.assertEqual(o,before)
    def test_contract_mismatch_rejected(self):
        o,c=self.fixture();o['model_output']['contracts'][0]['line']=31.5
        with self.assertRaisesRegex(ValueError,'EXACT_CONTRACT_CHANGED'):gate.pair_rows(o,'a'*64,c)
    def test_draw_count_change_rejected(self):
        o,c=self.fixture();o['model_output']['contracts'][0]['draws']=8192
        with self.assertRaises(ValueError):gate.pair_rows(o,'a'*64,c)
    def test_j3_cannot_be_rebranded_as_control(self):
        o,c=self.fixture();o['model_output']['contracts'][0]['model_id']='J3'
        with self.assertRaises(ValueError):gate.pair_rows(o,'a'*64,c)
    def test_frozen_tamper_rejected(self):
        o,_=self.fixture()
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/('a'*64+'.json');p.write_bytes(gate.canonical(o))
            with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):gate.load_frozen(p)
    def test_weather_receipt_hash_and_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'weather.bin';p.write_bytes(b'original')
            with self.assertRaises(ValueError):
                gate.bound_file(Path(t),{'path':'weather.bin','sha256':'0'*64})
            with self.assertRaises(ValueError):
                gate.bound_file(Path(t),{'path':'../escape','sha256':'0'*64})
    def test_weather_naive_timestamp_rejected(self):
        with self.assertRaisesRegex(ValueError,'NAIVE_WEATHER_CLOCK'):
            gate.stamp('2026-11-15T12:00:00')
    def test_seal_never_overwrites(self):
        with tempfile.TemporaryDirectory() as t:
            p,h=gate.seal_new(Path(t),{'x':1})
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),h)
            with self.assertRaises(FileExistsError):gate.seal_new(Path(t),{'x':1})

if __name__=='__main__':unittest.main()
