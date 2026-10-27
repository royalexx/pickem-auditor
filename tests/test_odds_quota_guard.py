"""No extra Odds API credits may be consumed when the account cannot fund props."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from odds_providers import TheOddsAPIProvider

class QuotaTests(unittest.TestCase):
    def test_one_credit_blocks_paid_fetch(self):
        provider=TheOddsAPIProvider(api_key="test-secret",fetch=lambda *a,**kw: self.fail("Paid API call made"))
        with patch.dict(os.environ,{"PICKEM_ODDS_QUOTA_GUARD":"1"}):
            with patch.object(provider,"_free_quota_check",return_value=(1,None)):
                quotes=provider.fetch("2026-10-27")
        self.assertEqual(quotes,[])
        self.assertIn("ODDS_QUOTA_INSUFFICIENT",provider.note)

    def test_unavailable_balance_never_spends(self):
        provider=TheOddsAPIProvider(api_key="test-secret",fetch=lambda *a,**kw: self.fail("Paid API call made"))
        with patch.dict(os.environ,{"PICKEM_ODDS_QUOTA_GUARD":"1"}):
            with patch.object(provider,"_free_quota_check",return_value=(None,"ODDS_QUOTA_CHECK_UNAVAILABLE")):
                quotes=provider.fetch("2026-10-27")
        self.assertEqual(quotes,[])
        self.assertIn("ODDS_QUOTA_CHECK_UNAVAILABLE",provider.note)

    def test_free_endpoint_header_parsing(self):
        class Response:
            status=200
            headers={"x-requests-remaining":"1"}
            def __enter__(self):return self
            def __exit__(self,*a):return None
        calls=[]
        def fake_open(req, timeout=0):
            self.assertNotIn("test-secret",str(req.headers))
            calls.append(req.full_url)
            return Response()
        remaining,error=TheOddsAPIProvider._free_quota_check("test-secret",opener=fake_open)
        self.assertEqual((remaining,error),(1,None))
        self.assertEqual(len(calls),1)
