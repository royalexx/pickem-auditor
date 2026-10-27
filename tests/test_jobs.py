"""Offline tests for scripts/jobs.py."""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import fetch_slate as fs_mod
import jobs
import odds_providers as op
import pickem_math as pm
import report as calibration_report


def _quote(**kwargs):
    defaults = {
        "sport": "NHL",
        "event_id": "evt-1",
        "team": "BOS",
        "opponent": "TOR",
        "player": "Example Skater",
        "stat": "shots on goal",
        "book": "Pinnacle",
        "line": 2.5,
        "over_odds": -115,
        "under_odds": -105,
        "retrieved_at": "2026-10-22T16:00:00Z",
        "source_url": "https://example.test/odds",
    }
    defaults.update(kwargs)
    return op.make_quote(**defaults)


class JobsHelperTests(unittest.TestCase):
    def test_game_started_uses_commence_time(self):
        now = datetime(2026, 10, 23, 1, 0, tzinfo=timezone.utc)
        self.assertFalse(jobs.game_started("2026-10-23T02:00:00Z", now))
        self.assertTrue(jobs.game_started("2026-10-23T00:30:00Z", now))

    def test_filter_started_pipeline_skips_live_games(self):
        slate = {
            ("NHL", "Patrik Laine", "shots on goal"): {
                "sport": "NHL",
                "team": "MTL",
                "opponent": "BUF",
                "player": "Patrik Laine",
                "stat": "shots on goal",
            }
        }
        pipeline = [
            {"id": "NHL|Patrik Laine|shots on goal|over", "side": "over", "line": 2.5},
        ]
        commence = {("NHL", "mtl", "buf"): "2026-10-23T00:00:00Z"}
        now = datetime(2026, 10, 23, 1, 0, tzinfo=timezone.utc)
        kept, skipped = jobs.filter_started_pipeline(pipeline, slate, commence, now)
        self.assertEqual(skipped, 1)
        self.assertEqual(kept, [])

    def test_shadow_run_id_is_stable(self):
        self.assertEqual(jobs.shadow_run_id("2026-10-22"), jobs.shadow_run_id("2026-10-22"))
        self.assertNotEqual(jobs.shadow_run_id("2026-10-22"), jobs.shadow_run_id("2026-10-23"))

    def test_enrich_pipeline_copies_reads_fields(self):
        slate = {
            "sport": "NFL",
            "stat": "receptions",
            "checkdown_target_share": 0.3,
            "checkdown_player_games": 8,
            "checkdown_team_games": 9,
            "def_matchup_factor": 1.05,
            "qb_checkdown_tendency": 0.12,
        }
        pipeline = {"id": "NFL|Player|receptions|over", "soft_flags": 0}
        out = jobs.enrich_pipeline_from_slate(pipeline, slate)
        self.assertEqual(out["checkdown_target_share"], 0.3)
        self.assertEqual(out["team_bucket_throw_share"], 0.12)
        self.assertEqual(out["sport"], "NFL")

    def test_pipeline_to_snapshot_marks_shadow(self):
        result = {
            "ok": True,
            "final_rank": "Watchlist",
            "project": {"shrunk_mean": 3.1, "current_role_n": 20, "q_win": 0.58, "q_push": 0.0},
            "grade": {
                "q_model": 0.58,
                "q_market": 0.55,
                "q_market_comparable": 0.55,
                "q_grade": 0.58,
                "q_gap": 0.03,
                "mechanisms": 0,
            },
            "market": {"q_market": 0.55, "retrieved_at": "2026-10-22T12:00:00Z"},
            "engine_a": {"mean": 3.1, "q_win": 0.58, "q_push": 0.0},
            "engine_b": {"abstain": True},
            "crosscheck": {"b_vote": "abstain"},
            "derived_flags": [],
            "soft_flags_passed": 0,
            "reason": "WATCH",
        }
        candidate = {
            "dist": "poisson",
            "side": "over",
            "line": 2.5,
            "soft_flags": 0,
            "mechanisms": 0,
        }
        raw = jobs.pipeline_to_snapshot(
            result,
            meta={
                "game_date": "2026-10-22",
                "sport": "NHL",
                "player": "Example",
                "stat": "shots on goal",
                "matchup": "BOS @ TOR",
            },
            run_id=jobs.shadow_run_id("2026-10-22"),
            run_at="2026-10-22 10:00 ET",
            candidate=candidate,
        )
        self.assertEqual(raw["run_type"], pm.RUN_TYPE_SHADOW)
        normalized = pm.normalize_snapshot(raw)
        self.assertEqual(normalized["run_type"], pm.RUN_TYPE_SHADOW)
        self.assertFalse(normalized["researched"])

    def test_snapshot_job_idempotent(self):
        slate_rows = [
            {
                "sport": "NHL",
                "game_date": "2026-10-22",
                "player": "Example Skater",
                "team": "BOS",
                "opponent": "TOR",
                "stat": "shots on goal",
                "suggested_dist": "poisson",
                "baseline_window_mean": 3.0,
                "baseline_n": 20,
                "season_n": 25,
                "recent_mean": 3.2,
                "recent_n": 5,
            }
        ]
        quotes = [_quote(), _quote(book="FanDuel", over_odds=-120, under_odds=100)]
        pipeline = fs_mod.prepare_pipeline(slate_rows, quotes, now="2026-10-22T16:05:00Z")
        self.assertTrue(pipeline)

        def fake_collect(_date, _slate, _quotes, fetch_json_fn=None):
            return slate_rows, {"retrieved_at": "2026-10-22T16:00:00Z"}

        now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            slate_path = Path(tmp) / "slate.jsonl"
            quotes_path = Path(tmp) / "odds.jsonl"
            snap_path = Path(tmp) / "snap.jsonl"
            fs_mod.write_jsonl(slate_rows, slate_path)
            fs_mod.write_jsonl(quotes, quotes_path)
            first = jobs.run_snapshot(
                game_date="2026-10-22",
                slate_path=slate_path,
                quotes_path=quotes_path,
                snapshot_path=snap_path,
                now=now,
                preflight_fn=lambda: {"ok": True},
                collect_fn=fake_collect,
                events_loader=lambda _d: [
                    {
                        "id": "evt-1",
                        "sport_key": "icehockey_nhl",
                        "commence_time": "2026-10-23T00:00:00Z",
                        "home_team": "TOR",
                        "away_team": "BOS",
                    }
                ],
            )
            self.assertGreaterEqual(first["rows_written"], 1)
            second = jobs.run_snapshot(
                game_date="2026-10-22",
                slate_path=slate_path,
                quotes_path=quotes_path,
                snapshot_path=snap_path,
                now=now,
                preflight_fn=lambda: {"ok": True},
                collect_fn=fake_collect,
                events_loader=lambda _d: [],
            )
            self.assertEqual(second["rows_written"], 0)
            self.assertGreater(second["skipped"], 0)

    def test_closing_fills_open_rows(self):
        row = {
            "run_at": "2026-10-22 10:00 ET",
            "game_date": "2026-10-22",
            "sport": "NHL",
            "matchup": "BOS @ TOR",
            "player": "Example Skater",
            "team": "BOS",
            "stat": "shots on goal",
            "side": "over",
            "reference_line": 2.5,
            "final_rank": "Watchlist",
            "status": "GRADED",
            "researched": True,
            "closing_line": None,
            "closing_q_market": None,
            "actual_stat": None,
            "run_id": "user-run",
        }
        quotes = [_quote(retrieved_at="2026-10-22T23:00:00Z", over_odds=-120, under_odds=100)]
        line, q = jobs.closing_consensus_for_row(
            row, quotes, "2026-10-22T23:30:00+00:00",
        )
        self.assertEqual(line, 2.5)
        self.assertIsNotNone(q)

    def test_report_excludes_shadow_from_tier_stats(self):
        user = {
            "run_at": "2026-10-01 12:00 ET",
            "game_date": "2026-10-01",
            "sport": "NFL",
            "matchup": "A @ B",
            "player": "User Player",
            "stat": "receptions",
            "side": "over",
            "reference_line": 3.5,
            "final_rank": "Tier 1",
            "status": "GRADED",
            "researched": True,
            "actual_stat": 5,
            "outcome": "win",
            "settled_at": "2026-10-02T12:00:00Z",
            "q_grade": 0.61,
        }
        shadow = dict(user)
        shadow.update(
            player="Shadow Player",
            run_type=pm.RUN_TYPE_SHADOW,
            researched=False,
            run_id=jobs.shadow_run_id("2026-10-01"),
        )
        report = calibration_report.build_report([user, shadow])
        self.assertEqual(report["n_settled_graded"], 1)


class UnderdogBanTests(unittest.TestCase):
    JOB_PATHS = (
        SKILL_DIR / "scripts" / "jobs.py",
        SKILL_DIR / ".github" / "workflows" / "pickem-daily.yml",
        SKILL_DIR / "legacy" / "crontab.shadow.disabled",
        SKILL_DIR / "legacy" / "workflows" / "shadow.yml.disabled",
    )

    def test_job_artifacts_have_no_underdog_domain_or_field(self):
        for path in self.JOB_PATHS:
            text = path.read_text(encoding="utf-8")
            lower = text.lower()
            self.assertNotIn("underdog.com", lower, msg=str(path))
            self.assertNotIn("underdogfantasy", lower, msg=str(path))
            scrubbed = lower.replace("team_is_underdog", "")
            self.assertNotIn("underdog", scrubbed, msg=str(path))


if __name__ == "__main__":
    unittest.main()
