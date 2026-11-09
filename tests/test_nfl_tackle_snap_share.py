"""Offline tests: measured NFL defensive snap exposure, safe roster evidence, OOS clock."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import nfl_tackle_snap_share as sn


START=datetime(2025,9,7,17,tzinfo=timezone.utc)


def game_time(i):
    return START+timedelta(days=7*i)


def fixture(n=15, *, high_from=7, team_plays=65):
    teams=[];players=[]
    for i in range(n):
        t=game_time(i);gid=f"2025_test_{i:02d}_A_B"
        event={"game_id":gid,"start_time":t.isoformat(),
               "available_at":(t+timedelta(hours=18)).isoformat(),
               "season":"2025"}
        teams.extend([
            {**event,"team":"A","opponent":"B","plays":61},
            {**event,"team":"B","opponent":"A","plays":team_plays}])
        # p1 is a full-time LB after promotion; snapshots are historical only.
        target_snaps=60 if i>=high_from else 30
        actual=8 if i>=high_from else 4
        for pid,snaps,value in (("p1",target_snaps,actual),
                                ("p2",50,6),("p3",55,5),("p4",40,4)):
            players.append({
                **event,"game_date":t.date().isoformat(),
                "game_id":gid,"sport":"NFL","stat":"tackles + assists",
                "position":"LB","player_id":pid,"team":"A","opponent":"B",
                "workload":snaps,"value":value})
    return [{
        "schema":"nfl-context-data-v1","season":2025,
        "availability_policy":"retrospective_start_plus_18h",
        "source_digest":"fixture_source_digest",
        "teams":teams,"players":players}]


def future_args(history):
    return dict(history=history,player_id="p1",team="A",
                game_id="FUTURE-TEAM-A",
                forecast_at=(game_time(16)-timedelta(hours=1)).isoformat(),
                event_start=game_time(16).isoformat(),
                expected_defensive_plays=66.,line=5.5)


def receipt(root, name, at, *, status, game_id, teammate, delay_minutes=0):
    """Verify bytes of source-owned, exact-contract structured fixture."""
    path=Path(root)/name
    path.write_text(json.dumps({
        "schema":"verified-nfl-teammate-status-v1",
        "game_id":game_id,"team":"A","teammate_id":teammate,
        "event_start":at.isoformat(),"status":status}),encoding="utf-8")
    published=at-timedelta(hours=2)
    return {
        "source_id":f"provider:{name}","status":"verified",
        "source_url":"https://example.org/official-nfl-injury-availability",
        "observed_at":(published-timedelta(minutes=3)).isoformat(),
        "published_at":published.isoformat(),
        "retrieved_at":(published+timedelta(minutes=delay_minutes)).isoformat(),
        "content_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
        "archive_path":name}


def status(root, i, state, *, teammate="mate", event_time=None):
    t=event_time or game_time(i)
    game_id=f"2025_test_{i:02d}_A_B" if i<15 else "FUTURE-TEAM-A"
    return {
        "game_id":game_id,
        "team":"A","teammate_id":teammate,
        "event_start":t.isoformat(),"status":state,
        "source_receipt":receipt(root,f"verified_{i}_{state}_{teammate}.txt",t,
                                 status=state,game_id=game_id,teammate=teammate)}


class TackleOpportunityTest(unittest.TestCase):
    def setUp(self):
        self.history=sn.normalize_bundles(fixture())

    def test_separates_snap_share_and_per_snap_tackle_rate(self):
        result=sn.predict(**future_args(self.history))
        self.assertEqual(result["status"],"research_forecast")
        parts=result["projection_components"]
        self.assertAlmostEqual(
            parts["expected_team_defensive_plays"]*
            parts["estimated_defensive_snap_share"]*
            parts["estimated_credited_tackles_per_snap"],
            parts["expected_tackles_assists"])
        self.assertGreater(parts["estimated_defensive_snap_share"],.65)
        self.assertGreater(parts["expected_tackles_assists"],0)
        self.assertNotEqual(parts["expected_tackles_assists"],
                            parts["team_play_rate_control_expected_tackles"])
        self.assertEqual(result["model_family"],"snap_share_times_per_snap_conversion")
        self.assertFalse(result["production_eligible"])
        self.assertFalse(result["ranking_allowed"])
        self.assertFalse(result["training_started"])

    def test_uses_offense_pbp_not_sum_of_player_snaps(self):
        player=self.history["rows"][0]
        self.assertEqual(player["team_defensive_plays"],65)
        self.assertIn(player["player_defensive_snaps"],(30,40,50,55))
        self.assertNotEqual(sum(x["player_defensive_snaps"] for x in
                           self.history["rows"][:4]),65)

    def test_future_player_result_never_enters_prior(self):
        prior=sn.predict(**future_args(self.history))
        changed=copy.deepcopy(self.history)
        changed["rows"].append({
            **changed["rows"][-1],"player_id":"p1","game_id":"FUTURE",
            "start_time":game_time(16).isoformat(),
            "available_at":(game_time(16)+timedelta(hours=18)).isoformat(),
            "tackles_assists":50,"player_defensive_snaps":60})
        after=sn.predict(**future_args(changed))
        self.assertEqual(prior["q_over"],after["q_over"])
        self.assertEqual(
            prior["statistical_support"]["prior_player_game_ids"],
            after["statistical_support"]["prior_player_game_ids"])

    def test_wins_and_push_are_coherent_not_independent_side_draws(self):
        for line in (5,5.5,8.5):
            output=sn.score_probability(7.3,line)
            self.assertAlmostEqual(sum(output[k] for k in
                                   ("q_over","q_under","q_push")),1.,places=12)
            self.assertGreaterEqual(output["q_under"],0)
            self.assertGreaterEqual(output["q_over"],0)
            if float(line).is_integer():self.assertGreater(output["q_push"],0)
            else:self.assertEqual(output["q_push"],0)

    def test_requires_three_prior_player_games(self):
        short=copy.deepcopy(self.history)
        short["rows"]=[r for r in short["rows"]
                       if r["player_id"]!="p1" or r["game_id"] in
                       ("2025_test_00_A_B","2025_test_01_A_B")]
        result=sn.predict(**future_args(short))
        self.assertEqual(result["status"],"abstain")

    def test_malformed_incomplete_denominator_not_assumed_full_snap_share(self):
        data=fixture()
        p=data[0]["players"][0]
        p["workload"]=200
        rows=sn.normalize_bundles(data)["rows"]
        self.assertFalse(any(r["game_id"]==p["game_id"] and
                             r["player_id"]=="p1" for r in rows))

    def test_teammate_inactive_condition_requires_signed_pregame_status_receipts(self):
        with tempfile.TemporaryDirectory() as d:
            prior=[status(d,i,"active" if i<7 else "inactive") for i in range(15)]
            future=status(d,16,"inactive")
            args=future_args(self.history)
            args.update(teammate_id="mate",teammate_report=future,
                        historical_teammate_reports=prior,archive_root=d)
            inactive=sn.predict(**args)
            self.assertIsNotNone(inactive["projection_components"]["conditional_teammate_effect"])
            self.assertGreater(inactive["projection_components"]["conditional_teammate_effect"]["effect_on_snap_share"],0)
            future_active=status(d,16,"active")
            active=sn.predict(**{**args,"teammate_report":future_active})
            self.assertLess(active["projection_components"]["conditional_teammate_effect"]["effect_on_snap_share"],0)

    def test_missing_future_teammate_report_never_assigns_inactive_bonus(self):
        base=sn.predict(**future_args(self.history))
        no_report=sn.predict(**future_args(self.history),teammate_id="mate")
        self.assertEqual(
            base["projection_components"]["expected_tackles_assists"],
            no_report["projection_components"]["expected_tackles_assists"])
        self.assertIn("future_teammate_status_unverified",no_report["reliability_reasons"])

    def test_insufficient_historical_contrast_never_stacks_injury_bonus(self):
        with tempfile.TemporaryDirectory() as d:
            prior=[status(d,i,"active") for i in range(15)]
            future=status(d,16,"inactive")
            result=sn.predict(**future_args(self.history),teammate_id="mate",
                teammate_report=future,historical_teammate_reports=prior,
                archive_root=d)
            self.assertIsNone(result["projection_components"]["conditional_teammate_effect"])
            self.assertIn("insufficient_confirmed_teammate_contrast",result["reliability_reasons"])

    def test_unbacked_status_mutation_rejected_even_if_sha_matches_original(self):
        with tempfile.TemporaryDirectory() as d:
            prospective=status(d,16,"inactive")
            # Signed source file still claims inactive. Rewriting just the
            # in-memory status cannot turn it into a verified active player.
            prospective["status"]="active"
            with self.assertRaisesRegex(sn.TackleChallengerError,
                                        "archived_teammate_status_identity_mismatch"):
                sn.predict(**future_args(self.history),teammate_id="mate",
                           teammate_report=prospective,archive_root=d)

    def test_tampered_teammate_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            prospective=status(d,16,"inactive")
            (Path(d)/prospective["source_receipt"]["archive_path"]).write_text("modified")
            with self.assertRaisesRegex(sn.TackleChallengerError,"uncertified_teammate_status"):
                sn.predict(**future_args(self.history),teammate_id="mate",
                           teammate_report=prospective,archive_root=d)

    def test_poststart_teammate_report_fails(self):
        with tempfile.TemporaryDirectory() as d:
            prospective=status(d,16,"inactive")
            prospective["source_receipt"]["retrieved_at"]=(game_time(16)+timedelta(minutes=1)).isoformat()
            with self.assertRaisesRegex(sn.TackleChallengerError,"uncertified_teammate_status"):
                sn.predict(**future_args(self.history),teammate_id="mate",
                           teammate_report=prospective,archive_root=d)

    def test_teammate_status_must_match_actual_own_event(self):
        with tempfile.TemporaryDirectory() as d:
            prospective=status(d,16,"inactive",event_time=game_time(17))
            with self.assertRaisesRegex(sn.TackleChallengerError,"future_teammate_event_time_mismatch"):
                sn.predict(**future_args(self.history),teammate_id="mate",
                           teammate_report=prospective,archive_root=d)

    def test_historical_teammate_status_must_match_actual_own_game(self):
        with tempfile.TemporaryDirectory() as d:
            prior=[status(d,i,"active" if i<7 else "inactive") for i in range(15)]
            # Corrupt a report for a game inside the model's last-12 window.
            prior[5]["event_start"]=(game_time(5)+timedelta(days=1)).isoformat()
            prospective=status(d,16,"inactive")
            with self.assertRaisesRegex(sn.TackleChallengerError,"historical_teammate_event_time_mismatch"):
                sn.predict(**future_args(self.history),teammate_id="mate",
                  teammate_report=prospective,historical_teammate_reports=prior,archive_root=d)

    def test_sparse_walk_forward_returns_no_fabricated_confidence_interval(self):
        walk=sn.walk_forward(self.history,from_time=game_time(10).isoformat())
        result=sn.summarize_walk_forward(walk)
        self.assertGreater(result["score"]["n"],0)
        self.assertLess(result["n_dates"],20)
        self.assertIsNone(result["interval_95"])
        self.assertEqual(result["status"],"insufficient_independent_dates_for_promotion")
        self.assertFalse(result["production_eligible"])

    def test_same_cohort_baseline_and_challenger_and_date_bootstrap(self):
        # Deterministic synthetic example used to exercise *statistics*,
        # never to claim empirical NFL improvement.
        import math
        rows=[]
        for i in range(20):
            for player in range(6):
                y=8 if (i+player)%3 else 3
                rows.append({"date":(game_time(i).date().isoformat()),
                             "actual":y,"q_over":.62,"baseline":{"q_over":.58}})
        report={"schema":"nfl-tackle-walk-forward-research-v1",
                "line":5.5,"line_source":"fixed_5_5_synthetic_research_not_market",
                "rows":rows}
        a=sn.summarize_walk_forward(report,bootstraps=100)
        b=sn.summarize_walk_forward(report,bootstraps=100)
        self.assertEqual(a,b)
        self.assertEqual(a["score"]["n"],120)
        self.assertEqual(a["n_dates"],20)
        self.assertIsNotNone(a["interval_95"])
        self.assertEqual(a["status"],"research_only_date_cluster_interval_not_production_calibration")

    def test_walk_forward_uses_fixed_prior_volume_not_actual_holdout_plays(self):
        result=sn.walk_forward(self.history,from_time=game_time(10).isoformat())
        self.assertGreater(result["n"],0)
        self.assertEqual(result["line_source"],"fixed_5_5_synthetic_research_not_market")
        self.assertFalse(result["training_started"])
        for row in result["rows"]:
            self.assertEqual(row["forecast"]["projection_components"]["expected_team_defensive_plays"],65.)
            self.assertNotIn(row["game_id"],row["forecast"]["statistical_support"]["prior_player_game_ids"])


if __name__=="__main__":
    unittest.main()
