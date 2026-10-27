import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import network_receipt as nr

class NetworkReceiptTests(unittest.TestCase):
    def test_dns_failure_without_proxy_does_not_call_http(self):
        def denied(*args, **kwargs): raise socket.gaierror(-3,'No DNS')
        opener=Mock(side_effect=AssertionError('should not call'))
        result=nr.probe('nhl',nr.ENDPOINTS['nhl_schedule'],resolver=denied,opener=opener,proxies={})
        self.assertEqual(result['state'],'dns_unavailable')
        opener.assert_not_called()

    def test_schema_is_verified_after_http_success(self):
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,max_bytes):return b'{"events":[]}'
        result=nr.probe('nhl',nr.ENDPOINTS['nhl_schedule'],resolver=lambda *a,**k:[],opener=lambda *a,**k:Response(),proxies={})
        self.assertEqual(result['state'],'schema_mismatch')
        self.assertTrue(result['reachable'])

    def test_all_provider_dns_failures_classified_as_runtime(self):
        examples=[{'state':'dns_unavailable','reachable':False} for _ in nr.ENDPOINTS]
        self.assertEqual(nr.diagnose(examples),'RUNTIME_DNS_UNAVAILABLE')

    def test_auth_failure_is_not_misclassified_as_dns(self):
        from urllib.error import HTTPError
        def blocked(*args,**kwargs):raise HTTPError('test',401,'Unauthorized',{},None)
        result=nr.probe('odds',nr.ENDPOINTS['odds_transport'],resolver=lambda *a,**k:[],opener=blocked,proxies={})
        self.assertEqual(result['state'],'authentication_required')
        self.assertTrue(result['reachable'])

    def test_diagnostics_never_claims_rows_collected(self):
        def ok(name, entry, **kw):
            return {'name':name,'state':'ok','reachable':True}
        output=nr.run(probe_fn=ok)
        self.assertEqual(output['diagnosis'],'ENDPOINT_PROBES_PASSED')
        self.assertFalse(output['collection_performed'])
        self.assertEqual(output['rows_collected'],0)

if __name__=='__main__': unittest.main()
