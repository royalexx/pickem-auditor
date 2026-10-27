"""Daily request-cap guard prevents quota-exhausted bulk collection."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from odds_providers import PropLineProvider

class QuotaTests(unittest.TestCase):
    def test_insufficient_requests_block_bulk(self):
        p=PropLineProvider(api_key="test-secret",fetch=lambda *a,**kw:self.fail("bulk called"))
        with patch.dict(os.environ,{"PICKEM_ODDS_QUOTA_GUARD":"1"}):
            with patch.object(p,"_daily_quota_check",return_value=(2,None)):
                self.assertEqual(p.fetch("2026-10-27"),[])
        self.assertIn("PROPLINE_QUOTA_INSUFFICIENT",p.note)

    def test_unavailable_balance_never_fetches(self):
        p=PropLineProvider(api_key="test-secret",fetch=lambda *a,**kw:self.fail("bulk called"))
        with patch.dict(os.environ,{"PICKEM_ODDS_QUOTA_GUARD":"1"}):
            with patch.object(p,"_daily_quota_check",return_value=(None,"PROPLINE_QUOTA_CHECK_UNAVAILABLE")):
                self.assertEqual(p.fetch("2026-10-27"),[])
        self.assertIn("PROPLINE_QUOTA_CHECK_UNAVAILABLE",p.note)

    def test_header_and_auth_without_query_secret(self):
        class Response:
            status=200
            headers={"X-Daily-Remaining":"437"}
            def __enter__(self):return self
            def __exit__(self,*a):return None
        calls=[]
        def opener(req,timeout=0):
            calls.append(req)
            self.assertNotIn("test-secret",req.full_url)
            self.assertEqual(req.get_header("X-api-key"),"test-secret")
            return Response()
        remaining,error=PropLineProvider._daily_quota_check("test-secret",opener=opener)
        self.assertEqual((remaining,error),(437,None))
        self.assertEqual(len(calls),1)

if __name__=="__main__":
    unittest.main()
