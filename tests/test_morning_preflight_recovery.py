"""Regression tests for independently usable source feeds and failure logs."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_slate as fs
import jobs

class RecoveryTests(unittest.TestCase):
    def test_optional_nhlpy_does_not_block_nhl_and_odds(self):
        r=fs.preflight(import_check=lambda name:(name not in ("nhlpy", "nba_api", "nflreadpy", "polars"), "missing"),
                       reach_check=lambda host:(host not in ("github.com", "stats.nba.com"), "ok"))
        self.assertFalse(r["ok"])
        self.assertTrue(r["feeds_ready"]["nhl"])
        self.assertTrue(r["feeds_ready"]["odds"])
        self.assertTrue(r["operational"])
    def test_no_provider_reachability_is_blocked(self):
        r=fs.preflight(import_check=lambda name:(True,""),reach_check=lambda host:(False,"dns blocked"))
        self.assertFalse(r["operational"])
        with self.assertRaisesRegex(jobs.JobError,"preflight blocked: feeds="):
            jobs.run_snapshot(game_date="2026-10-27",slate_path=Path("/tmp/never"),
                              quotes_path=Path("/tmp/never-quotes"),snapshot_path=Path("/tmp/never-snap"),
                              preflight_fn=lambda:r)
    def test_no_odds_while_sources_ready_is_blocked_for_snapshot(self):
        r=fs.preflight(import_check=lambda name:(True,""),
                       reach_check=lambda host:(host!="api.prop-line.com",""))
        self.assertTrue(r["feeds_ready"]["nhl"])
        self.assertFalse(r["operational"])
    def test_settle_outage_is_structured_and_preserves_history(self):
        import tempfile
        import json
        from settle import Fetchers
        row={"sport":"NHL","game_date":"2026-10-26","player":"Test Player",
             "stat":"shots on goal","side":"under","reference_line":1.5,
             "actual_stat":None}
        def unavailable(*_args):
            raise OSError("name resolution unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"history.jsonl"
            original=json.dumps(row)+"\n"
            target.write_text(original)
            with self.assertRaisesRegex(jobs.JobError,"SETTLEMENT_SOURCE_UNAVAILABLE"):
                jobs.run_settle(snapshot_path=target,as_of="2026-10-27",
                                fetchers=Fetchers(lookup=unavailable))
            self.assertEqual(target.read_text(), original)

    def test_missing_nhl_api_but_espn_ready_keeps_other_sources(self):
        r=fs.preflight(import_check=lambda name:(True,""),
                       reach_check=lambda host:(host!="api-web.nhle.com",""))
        self.assertFalse(r["feeds_ready"]["nhl"])
        self.assertTrue(r["feeds_ready"]["nba"])
        self.assertTrue(r["operational"])
if __name__=="__main__": unittest.main()
