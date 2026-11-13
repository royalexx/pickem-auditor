"""Prospective NHL SOG runner: genuine-source abstention, immutable ledger."""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from v2.nhl_sog_prospective_runner import prospective_shadow_attempt

class SOGProspectiveRunnerTests(unittest.TestCase):
    def test_absent_authentic_quote_abstains_and_pins_denominator(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            a=prospective_shadow_attempt({},source_root=root,output_root=root)
            self.assertEqual(a["attempt"]["status"],"ABSTAIN")
            self.assertIn("PROSPECTIVE_INPUT_MANIFEST_MISSING",a["attempt"]["reason"])
            self.assertTrue(Path(a["attempt_receipt"]["path"]).is_file())
            raw=Path(a["attempt_receipt"]["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),a["attempt_receipt"]["sha256"])
            b=prospective_shadow_attempt({"schema":"v25_sog_prospective_input_v1"},
                          source_root=root,output_root=root)
            self.assertIn("RAW_REAL_OFFER_RECEIPT_MISSING",b["attempt"]["reason"])
            self.assertNotIn("three_way_probabilities",b["attempt"])
            print("V25_SOG_NO_SOURCE_DRY_RUN "+json.dumps(b["attempt"],sort_keys=True))

    def test_real_quote_missing_original_archive_refuses_model(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            event=(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat()
            now=datetime.now(timezone.utc).isoformat()
            quote={
             "quote_id":"authentic-required","contract_id":"contract-required",
             "event_id":"official-required","event_start_at":event,
             "sport":"NHL","league":"NHL","season":2026,
             "team_id":"WSH","opponent_id":"BOS","player_id":"8478402",
             "stat_key":"shots on goal","period":"full","line":2.5,
             "book":"book-requires-original-receipt",
             "product_type":"sportsbook_two_sided","quote_at":now,
             "quote_receipt_sha256":"a"*64,
             "settlement_policy":"strict_gt_lt_equal_push","quote_kind":"real"
            }
            out=prospective_shadow_attempt(
                {"schema":"v25_sog_prospective_input_v1","quote":quote},
                 source_root=root,output_root=root)
            self.assertEqual(out["attempt"]["status"],"ABSTAIN")
            self.assertIn("ORIGINAL_REAL_QUOTE_ARCHIVE_NOT_DECLARED",out["attempt"]["reason"])
            self.assertEqual(out["attempt"]["contract_id"],quote["contract_id"])
            self.assertNotIn("three_way_probabilities",out["attempt"])

if __name__=="__main__":unittest.main()
