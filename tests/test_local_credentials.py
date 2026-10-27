import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import local_credentials as lc
import odds_providers as op

class CredentialTests(unittest.TestCase):
    def test_local_file_and_explicit_environment_precedence(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config'/'credentials.local.json';p.parent.mkdir()
            self.assertEqual(lc.propline_api_key(root=d,environ={}), '')
            p.write_text(json.dumps({'PROPLINE_API_KEY':'example-token'}))
            self.assertEqual(lc.propline_api_key(root=d,environ={}), 'example-token')
            self.assertEqual(lc.propline_api_key(root=d,environ={'PROPLINE_API_KEY':'override'}),'override')
            self.assertEqual(lc.propline_api_key(root=d,environ={'PROPLINE_API_KEY':''}),'')

    def test_malformed_values_are_rejected_without_echoing_secret(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config'/'credentials.local.json';p.parent.mkdir()
            for text in ('{"PROPLINE_API_KEY":"secret-token",bad}', '{"PROPLINE_API_KEY":123}',
                         '{"PROPLINE_API_KEY":"secret token"}', '["secret-token"]',
                         '{"PROPLINE_API_KEY":"secret-token","unexpected":true}'):
                p.write_text(text)
                with self.assertRaises(ValueError) as error:lc.propline_api_key(root=d,environ={})
                self.assertNotIn('secret',str(error.exception))

    def test_provider_loads_local_key_but_explicit_argument_wins(self):
        with patch.object(op,'propline_api_key',return_value='local-token'):
            self.assertEqual(op.PropLineProvider().api_key,'local-token')
            self.assertEqual(op.PropLineProvider(api_key='').api_key,'')

    def test_local_key_is_removed_from_error_messages_and_source_urls(self):
        from urllib.error import URLError
        def fail(url,**kwargs):raise URLError(url)
        with patch.object(op,'propline_api_key',return_value='local-token'):
            provider=op.PropLineProvider(fetch=fail)
            self.assertEqual(provider.fetch('2026-10-26',['NBA']),[])
        self.assertNotIn('local-token',provider.note)
        self.assertNotIn('local-token',json.dumps(provider.source_urls))

    def test_bad_local_configuration_returns_failed_preflight_without_network(self):
        import fetch_slate as fs
        with patch.object(lc,'propline_api_key',side_effect=ValueError('invalid config')), \
             patch.object(fs,'probe_import',return_value=(True,'')), \
             patch.object(fs,'probe_host',return_value=(True,'')):
            report=fs.preflight()
        self.assertFalse(report['ok'])
        self.assertEqual(report['checks'][-1]['detail'],'invalid local credentials configuration')

if __name__=='__main__':unittest.main()
