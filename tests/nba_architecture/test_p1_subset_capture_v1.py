from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from v2.nba_architecture.p1_subset_capture_v1 import capture_subset
from tests.nba_architecture.test_research_profile_v1 import COHORT

class CaptureTests(unittest.TestCase):
    def test_late_actual_freeze_is_recorded_without_network_or_backfill(self):
        with tempfile.TemporaryDirectory() as tmp,patch('v2.nba_architecture.p1_subset_capture_v1.capture',side_effect=AssertionError('NO_LATE_NETWORK')):
            p=Path(tmp)/'new';x=capture_subset(COHORT,p)
            self.assertEqual(x['status'],'MISSED_FREEZE');self.assertEqual(x['forecasted_rows'],0)
            self.assertIsNone(x['requests']);self.assertTrue((p/'receipt.json').exists())
            with self.assertRaises(FileExistsError):capture_subset(COHORT,p)
