"""Regression coverage for bounded disagreement and source-grounded top-ten narratives."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import slate_candidate_ranking as ranks
from usage_baseline import key


DAY = "2026-11-07"


def pair(player="Scoot Henderson", *, side="under", line=3.5, stat="assists",
         a=.7145, b=.7946, ba=.924, bb=.929, cons=.739, market=.540,
         player_id="scoot"):
    row = {"game_date": DAY, "run_id": "frozen", "run_type": "shadow",
           "forecast_at": "2026-11-07T21:08:00Z",
           "event_start": "2026-11-08T03:00:00Z",
           "sport": "NBA", "player": player, "player_id": player_id,
           "team": "POR", "opponent": "SAS", "side": side,
           "stat": stat, "reference_line": line, "reason": "STATUS_NOT_VERIFIED",
           "engine_a": {"reliable": True}, "engine_b": {"reliable": True},
           "market": {"market_valid": True}}
    comparison = {k: row[k] for k in ("game_date", "run_id", "forecast_at",
                                      "sport", "player", "player_id", "team", "opponent", "side", "stat")}
    comparison.update(line=line, Engine_A=a, Engine_B=b, Bayesian_A=ba,
                      Bayesian_B=bb, Consensus=cons, Market=market,
                      NUTS=None, NUTS_status="unavailable",
                      production_consensus_available=True,
                      models={"Market": {"status": "forecast",
                                         "books": ["FanDuel", "DraftKings"]}})
    return row, comparison


def write_usage(root, row, *, retrieved="2026-11-07T20:50:00Z",
                observations=None, integrity=True):
    path = Path(root) / "usage" / (key(row["sport"], row["player_id"],
                                        row["stat"], row["game_date"])+".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    if observations is None:
        observations = [{"id": f"game-{n}", "date": (datetime(2026, 11, 1, tzinfo=timezone.utc)
                         - timedelta(days=10-n)).date().isoformat(),
                         "value": 1 if n < 10 else 2,
                         "workload": 20.0 if n < 5 else 25.0}
                        for n in range(10)]
    record = {"version": "usage-history-v2",
              "sport": row["sport"], "team": row["team"],
              "player_id": row["player_id"], "stat": row["stat"],
              "game_date": row["game_date"], "source_url": "https://example.org/game-logs",
              "retrieved_at": retrieved, "observations": observations,
              "prior_observations": []}
    encoded = json.dumps(record, sort_keys=True, allow_nan=False)
    record["content_sha256"] = hashlib.sha256(encoded.encode()).hexdigest()
    if not integrity:
        record["observations"][0]["value"] = 999
    path.write_text(json.dumps(record))
    return path


class PrioritizedSlateTests(unittest.TestCase):
    def test_scoot_not_buried_for_bayesian_disagreement(self):
        scoot, scomp = pair()
        eason, ecomp = pair("Tari Eason", stat="threes", line=1.5,
                            player_id="eason", a=.778, b=.769, ba=.744,
                            bb=.739, cons=.775, market=.589)
        with tempfile.TemporaryDirectory() as d:
            write_usage(d, scoot)
            board = ranks.build([scoot, eason], [scomp, ecomp], DAY, data_root=d)
            self.assertEqual(board["top_counts"]["NBA"], 2)
            picked = next(x for x in board["top_10_by_sport"]["NBA"]
                          if x["player"] == "Scoot Henderson")
            self.assertEqual(picked["game_date"], DAY)
            self.assertEqual(picked["run_id"], "frozen")
            self.assertEqual(picked["history"]["last_5"]["wins"], 5)
            self.assertEqual(picked["history"]["last_5"]["games"], 5)
            self.assertAlmostEqual(picked["model_spread_pp"], 21.45, places=2)
            self.assertIn("material_model_disagreement_review_role_and_sample", picked["warnings"])
            self.assertEqual(len(picked["explanations"]), 6)
            self.assertIn("Exact under 3.5 hit history", " ".join(picked["explanations"]))
            self.assertEqual(picked["history"]["opportunity"]["change_pct"], 25.0)
            self.assertFalse(picked["publication_eligible"])
            self.assertIsNone(picked["tier"])
            self.assertEqual(board["ranking_kind"], "research_only")
            self.assertEqual(board["top_counts"]["NHL"], 0)
            self.assertEqual(board["top_counts"]["NFL"], 0)

    def test_missing_and_dishonest_history_never_claims_hit_rate(self):
        original, comparison = pair()
        with tempfile.TemporaryDirectory() as d:
            no_history = ranks.build([original], [comparison], DAY, data_root=d)
            item = no_history["top_10_by_sport"]["NBA"][0]
            self.assertEqual(item["history"]["status"], "unavailable")
            self.assertIn("No integrity-checked same-line game history", item["explanations"][2])
            path = write_usage(d, original, integrity=False)
            forged = ranks.build([original], [comparison], DAY, data_root=d)
            self.assertEqual(forged["top_10_by_sport"]["NBA"][0]["history"]["status"], "unavailable")
            write_usage(d, original, retrieved="2026-11-07T22:01:00Z")
            future = ranks.build([original], [comparison], DAY, data_root=d)
            self.assertEqual(future["top_10_by_sport"]["NBA"][0]["history"]["status"], "unavailable")

    def test_integrity_checks_exclude_same_day_and_future_outcomes(self):
        row, comp = pair()
        with tempfile.TemporaryDirectory() as d:
            p = write_usage(d, row, observations=[
                {"id": "today", "date": DAY, "value": 0, "workload": 0}])
            self.assertEqual(ranks.historical_evidence(row, d)["status"], "unavailable")

    def test_two_books_and_reliable_production_are_gates(self):
        row, comp = pair()
        with tempfile.TemporaryDirectory() as d:
            changed = copy.deepcopy(comp)
            changed["models"]["Market"]["books"] = ["FanDuel"]
            self.assertEqual(ranks.build([row], [changed], DAY, data_root=d)["candidate_pool_count"], 0)
            changed = copy.deepcopy(row)
            changed["engine_b"]["reliable"] = False
            self.assertEqual(ranks.build([changed], [comp], DAY, data_root=d)["candidate_pool_count"], 0)
            changed = copy.deepcopy(comp)
            changed["line"] = 4.5
            self.assertEqual(ranks.build([row], [changed], DAY, data_root=d)["candidate_pool_count"], 0)

    def test_rank_is_not_mistaken_for_betting_probability_or_double_counted(self):
        row, comp = pair()
        with tempfile.TemporaryDirectory() as d:
            board = ranks.build([row], [comp], DAY, data_root=d)
            candidate = board["top_10_by_sport"]["NBA"][0]
            self.assertNotAlmostEqual(candidate["research_priority_score"]/100,
                                      candidate["production_consensus"], places=2)
            self.assertTrue(board["ranking_not_a_probability"])
            self.assertEqual(candidate["history"]["status"], "unavailable")
            self.assertAlmostEqual(sum(candidate["score_components"].values()),
                                   candidate["research_priority_score"], places=2)
            docs = ranks.render_markdown(board)
            self.assertIn("NOT a hit probability", docs)
            self.assertIn("game_specific_active_status_not_verified", docs)

    def test_max_ten_each_sport_with_all_explanations_and_history_pending(self):
        pairs = [pair(f"Other Player {i}", player_id=f"id-{i}",
                      cons=.70+(i/1000), a=.75, b=.72, ba=.70, bb=.73, market=.50)
                 for i in range(16)]
        for i, (row, comp) in enumerate(pairs):
            row["team"] = comp["team"] = f"T{i%6}"
            row["opponent"] = comp["opponent"] = f"O{i%6}"
        with tempfile.TemporaryDirectory() as d:
            result = ranks.build([p[0] for p in pairs], [p[1] for p in pairs],
                                 DAY, data_root=d)
            self.assertEqual(result["candidate_pool_count"], 16)
            self.assertEqual(result["full_universe_review_count"],16)
            self.assertEqual(len(result["full_universe_reviews"]),16)
            ranks.write(result,d)
            full=json.loads((Path(d)/"slate_full_universe_research.json").read_text())
            self.assertEqual(full["contracts_reviewed"],16)
            self.assertEqual(len(full["reviews"]),16)
            self.assertTrue(full["top10_is_only_a_display_limit"])
            self.assertEqual(len(result["top_10_by_sport"]["NBA"]), 10)
            for item in result["top_10_by_sport"]["NBA"]:
                self.assertGreaterEqual(len(item["explanations"]), 4)
                self.assertEqual(item["verification_status"], "pending")
                self.assertIn("warnings", item)

    def test_order_and_count_are_integrity_checked(self):
        row, comp = pair()
        with self.assertRaisesRegex(ValueError, "comparison_count_mismatch"):
            ranks.build([row], [], DAY, data_root=".")
        altered = {**comp, "game_date": "2026-11-08"}
        with self.assertRaisesRegex(ValueError, "cross_date"):
            ranks.build([row], [altered], DAY, data_root=".")


if __name__ == "__main__":
    unittest.main()
