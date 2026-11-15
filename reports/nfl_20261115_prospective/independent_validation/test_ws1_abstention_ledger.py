"""Source-contract negative controls using fake WS1 only, never real quotes."""
import importlib.util,hashlib,json,pathlib,unittest
p=pathlib.Path(__file__).with_name('ws1_abstention_ledger.py')
spec=importlib.util.spec_from_file_location('ws1_abstention_ledger',p)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

def setup():
    c={'candidates':[{'original_quote':{'stat':'targets','player':'TEST','line':5.5,'book':'FAKE'}},{'original_quote':{'stat':'rush attempts','player':'TEST2','line':12,'book':'FAKE'}}]}
    raw=json.dumps(c).encode()
    a={'schema':'nfl_ws1_full_slate_independent_source_audit_v1','manifest_file_sha256':hashlib.sha256(raw).hexdigest(),
       'original_observations':2,'forecast_eligible_quotes':0,'source_certified_quotes':1,
       'source_rejection_reasons':{'PASS':1,'BAD_SOURCE':1}}
    return raw,json.dumps(a).encode()

class NativeAbstention(unittest.TestCase):
    def test_every_native_observation_all_three(self):
        raw,a=setup(); z=mod.freeze(raw,a)
        self.assertEqual(len(z['rows']),6)
        self.assertEqual(z['total_model_forecasts'],0)
        self.assertEqual(z['by_original_market'],{'rush attempts':1,'targets':1})
        self.assertTrue(all(q['p_over'] is None and q['status']=='ABSTAIN' for q in z['rows']))
    def test_original_quote_not_relabelled(self):
        raw,a=setup();z=mod.freeze(raw,a)
        self.assertEqual(z['rows'][0]['original_quote']['line'],5.5)
        self.assertNotIn('contract_id',z['rows'][0])
    def test_invalid_hash(self):
        raw,a=setup(); bad=json.loads(a);bad['manifest_file_sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'SHA_MISMATCH'):mod.freeze(raw,json.dumps(bad).encode())
    def test_nonzero_forecast_readiness_blocks_abstention(self):
        raw,a=setup(); bad=json.loads(a);bad['forecast_eligible_quotes']=1
        with self.assertRaisesRegex(ValueError,'ELIGIBILITY_CHANGED'):mod.freeze(raw,json.dumps(bad).encode())
    def test_wrong_denominator(self):
        raw,a=setup();bad=json.loads(a);bad['original_observations']=1
        with self.assertRaisesRegex(ValueError,'DENOMINATOR'):mod.freeze(raw,json.dumps(bad).encode())
    def test_quote_missing(self):
        raw,a=setup();bad=json.loads(raw);bad['candidates'][0].pop('original_quote')
        raw2=json.dumps(bad).encode();aud=json.loads(a);aud['manifest_file_sha256']=hashlib.sha256(raw2).hexdigest()
        with self.assertRaisesRegex(ValueError,'ORIGINAL_QUOTE'):mod.freeze(raw2,json.dumps(aud).encode())
    def test_wrong_source_schema(self):
        raw,a=setup();bad=json.loads(a);bad['schema']='UNRECOGNIZED'
        with self.assertRaisesRegex(ValueError,'SOURCE_AUDIT_SCHEMA'):mod.freeze(raw,json.dumps(bad).encode())

if __name__=='__main__':unittest.main()