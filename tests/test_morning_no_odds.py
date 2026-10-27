"""A morning history/settlement run must not spend The Odds API credits."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import fetch_slate as fs

class MorningNoPaidOddsTests(unittest.TestCase):
    def test_disables_provider_construction(self):
        with patch.dict(os.environ,{"PICKEM_DISABLE_ODDS":"1"}):
            with patch.object(fs,"TheOddsAPIProvider",side_effect=AssertionError("paid provider called")):
                quotes,note=fs.fetch_odds("2026-10-27")
        self.assertEqual(quotes,[])
        self.assertIn("ODDS_DISABLED_FOR_HISTORICAL_COLLECTION",note)

    def test_afternoon_still_fetches(self):
        class Provider:
            source_urls=[]
            note="fixture"
            def fetch(self,*args,**kwargs):return [{"source_url":"https://example.test"}]
        with patch.dict(os.environ,{"PICKEM_DISABLE_ODDS":"0"}):
            quotes,note=fs.fetch_odds("2026-10-27",provider=Provider())
        self.assertEqual(len(quotes),1)
        self.assertEqual(note,"fixture")

if __name__=="__main__":
    unittest.main()
