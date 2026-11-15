"""Offline integration against real pregame receipts, never external network."""
import json
from pathlib import Path
import unittest
from v2.nba_ws1.replay import replay
from v2.nba_ws1.store import NBAPregameFeatureSnapshot,instant

ROOT=Path(__file__).resolve().parents[2]

class RealPregameSampleTests(unittest.TestCase):
    def test_saved_sources_rebuild_byte_identical_package(self):
        folder=ROOT/'docs/nba_ws1/sample'
        receipt=json.loads((folder/'capture_receipt.json').read_text())
        a=replay(folder);b=replay(folder)
        self.assertEqual(a.to_json(),b.to_json())
        self.assertEqual(a.content_hash,receipt['snapshot_hash'])
        self.assertEqual(a.to_json(),(folder/receipt['snapshot_path']).read_text())
        self.assertEqual(NBAPregameFeatureSnapshot.from_json(a.to_json()).content_hash,a.content_hash)
        data=a.to_dict();self.assertEqual(len(data['players']),36)
        self.assertEqual(data['game']['game_id'],'espn:game:401909986')
        self.assertLess(instant(data['forecast_at']),instant(data['game']['event_start_at']))
        for r in data['receipts']:self.assertLessEqual(instant(r['source_available_at']),instant(data['input_freeze_at']))
        self.assertEqual(data['future_uncertainty']['overtime'],'unknown_future_outcome')
        self.assertEqual(data['status'],'blocked')
        self.assertIn('ELIGIBILITY_UNCERTAIN',data['abstention_codes'])
        self.assertFalse(data['market_context']['original_contracts'])

if __name__=='__main__':unittest.main()
