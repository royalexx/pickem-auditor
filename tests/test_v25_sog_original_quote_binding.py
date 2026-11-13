"""Independent quote-to-original-row tamper and contract matching tests."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from v2.contracts import MarketQuote
from v2.nhl_sog_quote_binding import verify_structured_original_sog_offer
from v2.nhl_sog_exposure_shadow import ExperimentBlocked


class NHLQuoteBindingTests(unittest.TestCase):
    def _fixture(self,root):
        row={"sport":"NHL","event_id":"ev-123","event_id_namespace":"propline",
             "player":"John A. Smith","stat":"shots on goal",
             "book":"Pinnacle","line":2.5,"over_odds":-110,"under_odds":100,
             "retrieved_at":"2026-11-13T14:00:00Z",
             "event_start":"2026-11-13T23:00:00Z",
             "source_url":"https://api.prop-line.com/v1/sports/icehockey_nhl/odds"}
        raw=(json.dumps(row)+"\n").encode()
        (root/"original_quotes.jsonl").write_bytes(raw)
        quote=MarketQuote(
             quote_id="q-a",contract_id="c-a",event_id="ev-123",
             event_start_at="2026-11-13T23:00:00Z",sport="NHL",league="NHL",
             season=2026,team_id="WSH",opponent_id="BOS",player_id="8470000",
             stat_key="shots on goal",period="full",line=2.5,book="Pinnacle",
             product_type="sportsbook_two_sided",quote_at="2026-11-13T14:00:00Z",
             quote_receipt_sha256=hashlib.sha256(raw).hexdigest(),
             quote_archive_path="original_quotes.jsonl",
             settlement_policy="strict_gt_lt_equal_push",quote_kind="real",
             over_decimal_odds=1+100/110,under_decimal_odds=2.0)
        return quote,row

    def test_exact_original_structured_quote_verified_not_raw_http(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);q,_=self._fixture(root)
            rec=verify_structured_original_sog_offer(
                q,source_root=root,source_bound_player_name="John A Smith")
            self.assertEqual(rec["contract_id"],q.contract_id)
            self.assertIn("not_raw_http_bytes",rec["source_semantics"])

    def test_altered_original_quote_tampering_and_mismatched_player_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);q,row=self._fixture(root)
            with self.assertRaises(ExperimentBlocked):
                verify_structured_original_sog_offer(q,source_root=root,
                    source_bound_player_name="Wrong Player")
            row["line"]=3.5
            (root/"original_quotes.jsonl").write_bytes((json.dumps(row)+"\n").encode())
            with self.assertRaisesRegex(ExperimentBlocked,"DIGEST_MISMATCH"):
                verify_structured_original_sog_offer(q,source_root=root,
                    source_bound_player_name="John A Smith")

if __name__=="__main__":unittest.main()
