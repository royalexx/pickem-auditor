"""Regression: original pregame probability metadata must never be rewritten."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / 'scripts/verify_history_invariants.py'
spec=importlib.util.spec_from_file_location('verify_history_invariants', PATH)
validator=importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

class IdentityTests(unittest.TestCase):
    def test_settlement_and_future_append_preserve_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'snapshots.jsonl'
            a={'forecast_at':'2026-10-26T12:00:00Z','game_date':'2026-10-26',
               'player':'Example','sport':'NBA','stat':'points','side':'Over',
               'reference_line':20.5,'engine_a':{'p':0.66}}
            digest=hashlib.sha256((json.dumps(a,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()).hexdigest()
            p.write_text(json.dumps(a)+'\n')
            self.assertEqual(validator.check(p,digest,1)['status'],'verified')
            p.write_text(json.dumps({**a,'actual_stat':22,'settled_at':'2026-10-27T12:00:00Z'})+'\n'+json.dumps({'game_date':'2026-10-27'})+'\n')
            r=validator.check(p,digest,1)
            self.assertEqual(r['status'],'verified')
            self.assertEqual(r['total_forecasts'],2)
            self.assertEqual(r['verified_outcomes'],1)
            p.write_text(json.dumps({**a,'reference_line':21.5})+'\n')
            self.assertEqual(validator.check(p,digest,1)['status'],'ORIGINAL_FORECAST_INPUT_CHANGED')

if __name__=='__main__':unittest.main()