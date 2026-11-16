"""Bounded checks for one scheduled NBA pilot worker and ESPN source fallback."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.nba_phase7.pilot import registered_slots
from research.nba_phase7 import sources
from research.nba_phase8c.daily import events_for_day, run


class NBADailyOrchestrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.slots = registered_slots()

    def test_registered_original_slots_unchanged(self):
        self.assertEqual(len(self.slots), 10)
        self.assertEqual([s["slot"] for s in self.slots], list(range(1, 11)))

    def test_capture_groups_are_exact(self):
        self.assertEqual([[s["slot"] for s in g] for _, g in events_for_day(self.slots, "2026-11-16")], [[1, 2]])
        self.assertEqual([[s["slot"] for s in g] for _, g in events_for_day(self.slots, "2026-11-17")], [[3], [4]])
        self.assertEqual([[s["slot"] for s in g] for _, g in events_for_day(self.slots, "2026-11-18")], [[5, 6]])
        self.assertEqual([[s["slot"] for s in g] for _, g in events_for_day(self.slots, "2026-11-19")], [[7, 8]])
        self.assertEqual([[s["slot"] for s in g] for _, g in events_for_day(self.slots, "2026-11-20")], [[9], [10]])

    def test_dry_run_never_uses_capture_or_claim(self):
        with patch("research.nba_phase8c.daily.capture_slot", side_effect=AssertionError("LIVE_CAPTURE")):
            plan = run(day="2026-11-17", dry_run=True)
        self.assertEqual(plan["mode"], "DRY_RUN_NO_CAPTURE_NO_CLAIM")
        self.assertEqual(plan["scheduled"][0]["slots"], [3])
        self.assertEqual(plan["scheduled"][1]["slots"], [4])

    def test_known_team_route_reused_only_as_navigation(self):
        comp = {"team": {"id": "2", "displayName": "Boston Celtics"}}
        url = sources._source_bound_team_route(comp)
        self.assertEqual(url, "https://www.nba.com/team/1610612738/celtics")

    def test_unknown_team_route_does_not_guess(self):
        with self.assertRaises(ValueError):
            sources._source_bound_team_route(
                {"team": {"id": "999999999", "displayName": "Unknown"}})

    def test_directory_http_403_does_not_block_espn_source_capture(self):
        """Our supplementary path records partial evidence; ESPN WS1 is independent."""
        import urllib.error
        urls = []
        def fake_urlopen(req, timeout=15):
            urls.append(req.full_url)
            if req.full_url.startswith("https://www.nba.com/"):
                raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)
            if req.full_url == "https://official.nba.com/nba-injury-report-2026-27-season/":
                return BytesIO(b"<html><body>Official index has no current PDF</body></html>")
            raise AssertionError("Unexpected endpoint " + req.full_url)
        board_event = {"competitions": [{"competitors": [
            {"team": {"id": "2", "displayName": "Boston Celtics"}}
        ]}]}
        deadline = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(sources, "urlopen", side_effect=fake_urlopen):
                report = sources.acquire_supplements(Path(temporary) / "test", board_event, deadline_at=deadline)
        self.assertEqual(report["status"], "captured_partial")
        self.assertTrue(any(e["code"] == "TEAM_SUPPLEMENT_UNAVAILABLE" for e in report["errors"]))
        self.assertTrue(any(e["code"] == "INJURY_SUPPLEMENT_UNAVAILABLE" for e in report["errors"]))
        self.assertTrue(any(i["kind"] == "official_injury_index" for i in report["items"]))
        self.assertNotIn("https://www.nba.com/players", urls)

    def test_late_runner_does_not_invoke_real_capture(self):
        from research.nba_phase8c import daily
        slot = self.slots[0]
        late = datetime.fromisoformat(slot["scheduled_freeze_at"]) + timedelta(seconds=1)
        with patch.object(daily, "clock", return_value=late):
            with patch.object(daily, "capture_slot", side_effect=AssertionError("LATE_CAPTURE")):
                rows = daily.run_group([slot], Path("/tmp/test_only_unused"), late)
        self.assertEqual(rows[0]["status"], "MISSED_FREEZE")

    def test_simultaneous_games_dispatch_independently(self):
        from research.nba_phase8c import daily
        pair = self.slots[:2]
        early = datetime.fromisoformat(pair[0]["scheduled_freeze_at"]) - timedelta(minutes=7)
        with patch.object(daily, "clock", return_value=early):
            with patch.object(daily, "capture_slot", side_effect=lambda s, out: {"slot": s["slot"], "status": "MOCKED"}):
                rows = daily.run_group(pair, Path("/tmp/test_only_unused"), early)
        self.assertEqual({r["slot"] for r in rows}, {1, 2})
        self.assertTrue(all(r["status"] == "MOCKED" for r in rows))

    def test_missing_optional_pdf_never_destroys_espn_capture_readiness(self):
        from research.nba_phase8c import daily
        with patch.object(daily, "preflight", side_effect=ValueError("PDF_RUNTIME_UNAVAILABLE")):
            ready = daily.safe_pregame_preflight(Path("/work/fixture_root_unused"))
        self.assertEqual(ready["status"], "ESPN_ONLY_OPTIONAL_PDF_PARSER_UNAVAILABLE")
        self.assertIn("legal eligibility", ready["restrictions"])

    def test_timed_out_optional_pdf_never_destroys_espn_readiness(self):
        from research.nba_phase8c import daily
        import subprocess
        with patch.object(daily, "preflight", side_effect=subprocess.TimeoutExpired("pdftotext -v", 10)):
            ready = daily.safe_pregame_preflight(Path("/work/fixture_root_unused"))
        self.assertEqual(ready["status"], "ESPN_ONLY_OPTIONAL_PDF_PARSER_UNAVAILABLE")
        self.assertIn("TimeoutExpired", ready["optional_pdf_failure"])

    def test_nonpdf_preflight_failure_must_remain_blocked(self):
        from research.nba_phase8c import daily
        with patch.object(daily, "preflight", side_effect=ValueError("FROZEN_MODEL_CHANGED")):
            with self.assertRaisesRegex(ValueError, "FROZEN_MODEL_CHANGED"):
                daily.safe_pregame_preflight(Path("/work/fixture_root_unused"))

    def test_missing_official_pdf_parser_keeps_original_espn_ledger_eligible_for_capture(self):
        class FakeReceipt:
            receipt_id = "original_byte_receipt"
        errors = []
        with patch.object(sources, "injury_pdf", side_effect=FileNotFoundError("pdftotext")):
            result = sources._read_optional_official_injury(
                b"%PDF-1.7", FakeReceipt(), "2026-11-16T18:25:00-05:00", errors)
        self.assertIsNone(result)
        self.assertEqual(errors[0]["code"], "OFFICIAL_INJURY_PARSER_UNAVAILABLE")
        self.assertTrue(errors[0]["no_eligibility_inference"])

    def test_official_pdf_timeout_is_explicitly_retained(self):
        import subprocess
        class FakeReceipt:
            receipt_id = "original_byte_receipt"
        errors = []
        with patch.object(sources, "injury_pdf",
                          side_effect=subprocess.TimeoutExpired("pdftotext", 15)):
            result = sources._read_optional_official_injury(
                b"%PDF-1.7", FakeReceipt(), "2026-11-16T18:25:00-05:00", errors)
        self.assertIsNone(result)
        self.assertIn("TimeoutExpired", errors[0]["cause"])

    def test_data_sources_explicitly_distinguish_eligibility(self):
        plan = run(day="2026-11-18", dry_run=True)
        self.assertIn("boxscores", plan["sources"]["ESPN"])
        self.assertIn("optional", plan["sources"]["NBA"])
        self.assertEqual([x["slots"] for x in plan["scheduled"]], [[5, 6]])


if __name__ == "__main__":
    unittest.main()
