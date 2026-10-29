"""All-market benchmark is exhaustive, fail-closed and source frozen."""
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import population_history as history
from full_backend_eval import MARKETS,WINDOWS,SEEDS,VERSION,build_plan

class AllMarketContracts(unittest.TestCase):
    def test_exhaustive_markets_from_source_registry(self):
        self.assertEqual(len(MARKETS),31)
        for sport in history.SPORTS:
            self.assertEqual(
                sum(1 for key in MARKETS if key.startswith(sport.lower()+'_')),
                len(history.COUNT[sport])+len(history.CONTINUOUS.get(sport,())))
    def test_frozen_windows_and_seeds(self):
        self.assertEqual(len(SEEDS),2)
        self.assertNotEqual(SEEDS[0],SEEDS[1])
        for start,cutoff,until in WINDOWS.values():
            self.assertLess(start,cutoff)
            self.assertLess(cutoff,until)
    def test_all_missing_sources_are_blocked(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as t:
            report=build_plan(t,archive_sha='source-locked')
            self.assertEqual(report['market_count'],31)
            self.assertEqual(report['ready_count'],0)
            self.assertEqual(report['blocked_count'],31)
            self.assertEqual(report['ready_matrix'],[])
            self.assertTrue(report['production_untouched'])
            self.assertFalse(report['publication_eligible'])
            for x in report['markets'].values():
                self.assertEqual(x['status'],'blocked')
                self.assertTrue(x['reason'])

if __name__=='__main__':
    unittest.main()
