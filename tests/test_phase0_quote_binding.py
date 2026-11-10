"""Phase0R original quote and event-binding adversarial regression tests."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from phase0_quote_binding import bind_original_quotes


class QuoteBindingTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {
            "id": "NFL|Example Player|receptions|over", "sport":"NFL",
            "event_id":"real-event","event_id_namespace":"propline",
            "team":"BUF","stat":"receptions",
            "side":"over","line":4.5, "market_retrieved_at":"2026-11-09T14:10:00Z",
            "books":[{"book":"ExampleBook", "line":4.5, "target":-110,
                      "other":-110, "book_side":"over"}]
        }
        self.quote = {
            "sport":"NFL","event_id":"real-event",
            "event_id_namespace":"propline",
            "event_start":"2026-11-09T18:00:00Z","team":"BUF",
            "player":"Example Player","stat":"receptions","book":"ExampleBook",
            "line":4.5,"over_odds":-110,"under_odds":-110,
            "retrieved_at":"2026-11-09T14:10:00Z"
        }
        self.freeze="2026-11-09T15:00:00Z"

    def bind(self, candidate=None, quotes=None):
        q=self.quote if quotes is None else quotes
        payload="\n".join(json.dumps(item) for item in (q if isinstance(q,list) else [q]))
        return bind_original_quotes(self.candidate if candidate is None else candidate,
                                    payload.encode(), freeze_at=self.freeze)

    def test_exact_original_quote_passes(self):
        self.assertEqual(len(self.bind()),64)
        swapped={**self.candidate, "side":"under",
                 "id":"NFL|Example Player|receptions|under",
                 "books":[{**self.candidate["books"][0], "book_side":"under"}]}
        self.assertEqual(self.bind(swapped), self.bind())

    def test_event_forgery_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"market_original_offer_missing"):
            self.bind({**self.candidate,"event_id":"fake-event"})

    def test_event_namespace_and_start_are_source_bound(self):
        with self.assertRaisesRegex(ValueError,"market_original_offer_missing"):
            self.bind({**self.candidate, "event_id_namespace":"other-api"})
        with self.assertRaisesRegex(ValueError,"market_binding_event_namespace_missing"):
            self.bind({**self.candidate, "event_id_namespace":None})
        raw=json.dumps(self.quote).encode()
        with self.assertRaisesRegex(ValueError,"market_original_event_start_mismatch"):
            bind_original_quotes(self.candidate,raw,freeze_at=self.freeze,
                                 event_start_at="2026-11-09T19:00:00Z")

    def test_player_team_stat_and_price_forgery_rejected(self):
        for mutation in ({"player":"Another Player"}, {"team":"NYJ"},
                         {"stat":"targets"},{"over_odds":-130}):
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(ValueError,"market_original_offer_missing|market_book_original_offer"):
                    self.bind(quotes={**self.quote, **mutation})

    def test_book_or_price_not_in_original_quote_rejected(self):
        for mutation in ({"book":"DifferentBook"},{"target":-150},{"line":5.5}):
            with self.subTest(mutation=mutation):
                c={**self.candidate,"books":[{**self.candidate["books"][0],**mutation}]}
                with self.assertRaisesRegex(ValueError,"market_book_"):
                    self.bind(c)

    def test_future_or_naive_original_receipt_rejected(self):
        for timestamp in ("2026-11-09T16:00:00Z","2026-11-09T14:10:00"):
            with self.subTest(timestamp=timestamp):
                with self.assertRaises(ValueError):
                    self.bind(quotes={**self.quote,"retrieved_at":timestamp})

    def test_candidate_backdated_clock_rejected(self):
        with self.assertRaisesRegex(ValueError,"market_original_retrieval_clock_mismatch"):
            self.bind({**self.candidate, "market_retrieved_at":"2026-11-09T13:00:00Z"})

    def test_duplicate_books_rejected(self):
        with self.assertRaisesRegex(ValueError,"market_book_duplicate_or_missing"):
            self.bind({**self.candidate,"books":self.candidate["books"]*2})

    def test_missing_event_and_missing_original_rows_rejected(self):
        with self.assertRaisesRegex(ValueError,"market_binding_event_missing"):
            self.bind({**self.candidate,"event_id":None})
        with self.assertRaisesRegex(ValueError,"market_original_offer_missing"):
            self.bind(quotes=[])

    def test_unrelated_quote_rows_do_not_change_matched_digest(self):
        decoy={**self.quote,"event_id":"elsewhere","player":"Other"}
        self.assertEqual(self.bind(quotes=[self.quote,decoy]),
                         self.bind(quotes=[self.quote]))

    def test_malformed_json_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"market_original_jsonl_invalid"):
            bind_original_quotes(self.candidate,b'{"bad",',
                                 freeze_at=self.freeze)


if __name__=="__main__":
    unittest.main()
