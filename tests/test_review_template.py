"""No unreviewed research template ever constitutes source-backed attestation."""
import sys
from pathlib import Path
import unittest
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from test_pick_verification import build as fixture, DATE
from pick_verification import review_verified, forecast_digest
from review_template import make

NOW=datetime(2026,10,27,20,30,tzinfo=timezone.utc)


class TemplateTests(unittest.TestCase):
    def test_unreviewed_template_is_not_an_attestation(self):
        rows,q,_=fixture()
        template=make(rows,q,DATE,now=NOW)
        self.assertEqual(len(template["attestations"]),1)
        self.assertFalse(template["publication_eligible"])
        entry=template["attestations"][0]
        self.assertEqual(entry["forecast_sha256"],forecast_digest(rows[0]))
        self.assertFalse(entry["source_read"])
        self.assertEqual(entry["decision"],"pending")
        self.assertFalse(review_verified(entry,rows[0],forecast_digest(rows[0]),NOW)[0])

    def test_expired_game_not_in_review_queue(self):
        rows,q,_=fixture()
        rows[0]["event_start"]="2026-10-27T20:10:00Z"
        template=make(rows,q,DATE,now=NOW)
        self.assertEqual(template["attestations"],[])
        self.assertEqual(template["excluded"]["GAME_ALREADY_STARTED"],1)


if __name__=="__main__":
    unittest.main()
