"""Quote-level Phase 0R regressions: original PropLine API, not bookmaker URL."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from phase0_pre_eval import pin
from phase0r_contract import strict_snapshot_status
from test_phase0r_pre_eval import START, build_row, make_inputs

API = ("https://api.prop-line.com/v1/sports/americanfootball_nfl/odds"
       "?markets=player_receptions&bookmakers=pinnacle")


def source_quote():
    return {
        "sport": "NFL",
        "event_id": "event-1",
        "event_id_namespace": "propline",
        "event_start": "2026-11-09T18:00:00Z",
        "player": "Darius Acuff",
        "player_norm": "darius acuff",
        "stat": "receptions",
        "book": "Pinnacle",
        "line": 4.5,
        "over_odds": -110,
        "under_odds": -110,
        "retrieved_at": "2026-11-09T14:10:00Z",
        "source_url": API,
    }


class OriginalQuoteOriginTests(unittest.TestCase):
    def audit_case(self, *, mutate=None, duplicate=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            candidate, _ = make_inputs(data)
            candidate["player"] = "Darius Acuff Jr."
            candidate["event_id_namespace"] = "propline"
            candidate["books"][0]["book"] = "Pinnacle"
            quote = source_quote()
            if mutate is not None:
                mutate(quote)
            quotes = [quote, dict(quote)] if duplicate else [quote]
            (data / "odds_quotes.jsonl").write_text(
                "".join(json.dumps(q) + "\n" for q in quotes),
                encoding="utf-8",
            )
            with pin(
                candidate, data_root=data,
                archive_root=data / "source_archives",
                policy_root=root, clock=lambda: START,
            ) as (evidence, _frozen, frozen_candidate):
                row = build_row(frozen_candidate, evidence)
                row["player"] = "Darius Acuff Jr."
                row["event_id_namespace"] = "propline"
                row["market"]["books"] = [{
                    "book": "Pinnacle",
                    "line": 4.5,
                    "over": -110,
                    "under": -110,
                    "retrieved_at": "2026-11-09T14:10:00Z",
                }]
                return strict_snapshot_status(
                    row, archive_root=data / "source_archives"
                )

    def test_valid_original_prop_line_quote_with_jr_alias(self):
        ok, reason = self.audit_case()
        self.assertTrue(ok, reason)

    def test_original_wrapper_needs_no_bookmaker_url_or_publication_clock(self):
        # The upstream URL is INSIDE the immutable quote bytes, not the
        # source-level wrapper receipt; provider publication time is unknown.
        ok, reason = self.audit_case()
        self.assertTrue(ok, reason)

    def test_wrong_api_source_is_rejected(self):
        ok, reason = self.audit_case(
            mutate=lambda q: q.update(source_url="https://fake.invalid/odds")
        )
        self.assertEqual((ok, reason), (False, "original_quote_api_origin_invalid"))

    def test_missing_api_source_is_rejected(self):
        ok, reason = self.audit_case(
            mutate=lambda q: q.pop("source_url")
        )
        self.assertEqual((ok, reason), (False, "original_quote_api_origin_invalid"))

    def test_wrong_player_price_cannot_cross_match(self):
        ok, reason = self.audit_case(
            mutate=lambda q: q.update(player="Another Player", player_norm="another player")
        )
        self.assertEqual((ok, reason), (
            False, "original_quote_event_player_stat_price_not_unique"))

    def test_quote_for_other_stat_cannot_cross_match(self):
        ok, reason = self.audit_case(
            mutate=lambda q: q.update(stat="rushing yards")
        )
        self.assertEqual((ok, reason), (
            False, "original_quote_event_player_stat_price_not_unique"))

    def test_quote_for_other_event_cannot_cross_match(self):
        ok, reason = self.audit_case(
            mutate=lambda q: q.update(event_id="different-event")
        )
        self.assertEqual((ok, reason), (
            False, "original_quote_event_player_stat_price_not_unique"))

    def test_different_book_prices_cannot_cross_match(self):
        ok, reason = self.audit_case(
            mutate=lambda q: q.update(over_odds=-112)
        )
        self.assertEqual((ok, reason), (
            False, "original_quote_event_player_stat_price_not_unique"))

    def test_duplicate_indistinguishable_quotes_are_rejected(self):
        ok, reason = self.audit_case(duplicate=True)
        self.assertEqual((ok, reason), (
            False, "original_quote_event_player_stat_price_not_unique"))

    def test_fake_quote_player_normalization_is_rejected(self):
        ok, reason = self.audit_case(
            mutate=lambda q: q.update(player_norm="different person")
        )
        self.assertEqual((ok, reason), (
            False, "original_quote_player_normalization_inconsistent"))

    def test_quote_after_original_freeze_is_rejected(self):
        ok, _reason = self.audit_case(
            mutate=lambda q: q.update(retrieved_at="2026-11-09T15:01:00Z")
        )
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
