"""V25-C07 discrete settlement contract repair (discretized Normal wrapper)."""
from __future__ import annotations

import math
import random
import unittest

from v2.contracts import (ContractError, DiscretizedNormalDistribution,
                            ForecastSnapshot, MarketQuote, NormalDistribution,
                            SourceReceipt, parse_distribution)
from v2.evaluation import categorical_brier, categorical_log_loss


SHA = "a" * 64
BASE = "2026-11-09T16:00:00Z"
FREEZE = "2026-11-09T16:30:00Z"
START = "2026-11-09T18:00:00Z"


def receiving_yards_quote(line: float) -> MarketQuote:
    return MarketQuote(
        quote_id="q-yards", contract_id="c-yards", event_id="NFL-1",
        event_start_at=START, sport="NFL", league="NFL", season=2026,
        team_id="T1", opponent_id="T2", player_id="player1",
        stat_key="receiving yards", period="full", line=line, book="example",
        product_type="pickem", quote_at=BASE, quote_receipt_sha256=SHA,
        settlement_policy="strict_gt_lt_equal_push", quote_kind="real",
    )


def targets_quote(line: float = 4.5) -> MarketQuote:
    return MarketQuote(
        quote_id="q1", contract_id="c1", event_id="NFL-1", event_start_at=START,
        sport="NFL", league="NFL", season=2026, team_id="T1", opponent_id="T2",
        player_id="player1", stat_key="targets", period="full", line=line,
        book="example", product_type="pickem", quote_at=BASE,
        quote_receipt_sha256=SHA, settlement_policy="strict_gt_lt_equal_push",
        quote_kind="real",
    )


def forecast_for(q: MarketQuote, distribution) -> ForecastSnapshot:
    return ForecastSnapshot(
        forecast_id="f1", run_id="r1", model_id="v25-discrete-contract",
        model_version="c07-prototype", quote_id=q.quote_id,
        contract_id=q.contract_id, event_id=q.event_id, sport=q.sport,
        league=q.league, season=q.season, team_id=q.team_id,
        opponent_id=q.opponent_id, quote_receipt_sha256=q.quote_receipt_sha256,
        player_id=q.player_id, stat_key=q.stat_key, period=q.period,
        line=q.line, forecast_at="2026-11-09T16:40:00Z",
        input_freeze_at=FREEZE, decision_cutoff_at="2026-11-09T16:35:00Z",
        model_training_cutoff_at="2026-11-08T23:59:00Z",
        model_artifact_sha256=SHA, code_commit="f" * 40,
        sources=(SourceReceipt(
            "stats-receipt", BASE, BASE, SHA, "https://example.org/stats",
            "stats/source.json",
        ),),
        distribution=distribution,
    )


class ProblemReproduction(unittest.TestCase):
    def test_continuous_normal_never_pushes_on_integer_line(self):
        d = NormalDistribution(55, 20)
        p = d.probabilities(55.0)
        self.assertEqual(p.push, 0.0)
        self.assertAlmostEqual(p.over + p.under, 1.0)


class DiscretizedNormalCore(unittest.TestCase):
    def setUp(self) -> None:
        self.d = DiscretizedNormalDistribution(55, 20, "signed_integer")

    def test_push_positive_at_integer_line(self):
        p = self.d.probabilities(55.0)
        self.assertGreater(p.push, 0.0)

    def test_no_push_at_half_integer_line(self):
        p = self.d.probabilities(55.5)
        self.assertEqual(p.push, 0.0)

    def test_cdf_coherence_between_integer_and_half_step(self):
        at_int = self.d.probabilities(55.0)
        at_half = self.d.probabilities(55.5)
        self.assertAlmostEqual(at_int.under + at_int.push, at_half.under, places=10)

    def test_exact_complementarity(self):
        for line in (0.0, 0.5, 55.0, 55.5, 200.0, 200.5, -12.0, -11.5):
            p = self.d.probabilities(line)
            self.assertAlmostEqual(p.over + p.under + p.push, 1.0, places=10)

    def test_signed_support_allows_negative_pmf(self):
        self.assertGreater(self.d.pmf(-5), 0.0)
        self.assertEqual(
            DiscretizedNormalDistribution(3, 1, "nonnegative_integer").pmf(-1),
            0.0,
        )


class SupportAndValidation(unittest.TestCase):
    def test_nonnegative_count_forecast_rejects_signed_support(self):
        q = targets_quote(10.0)
        d = DiscretizedNormalDistribution(5, 2, "signed_integer")
        with self.assertRaisesRegex(ContractError, "nonnegative_support_required"):
            forecast_for(q, d).validate_against(q)

    def test_signed_yards_reject_nonnegative_support(self):
        q = receiving_yards_quote(40.0)
        d = DiscretizedNormalDistribution(40, 15, "nonnegative_integer")
        with self.assertRaisesRegex(ContractError, "signed_support_required"):
            forecast_for(q, d).validate_against(q)

    def test_nonnegative_pmf_never_assigns_negative_counts(self):
        d = DiscretizedNormalDistribution(-5, 2, "nonnegative_integer")
        for k in range(-10, 0):
            self.assertEqual(d.pmf(k), 0.0)

    def test_nonnegative_passes_with_low_negative_tail(self):
        q = targets_quote(40.0)
        d = DiscretizedNormalDistribution(40, 10, "nonnegative_integer")
        forecast_for(q, d).validate_against(q)


class Serialization(unittest.TestCase):
    def test_round_trip_preserves_probabilities(self):
        d = DiscretizedNormalDistribution(55, 20, "signed_integer")
        restored = parse_distribution(d.to_record())
        for line in (54.5, 55.0, 55.5, 120.0):
            self.assertEqual(d.probabilities(line), restored.probabilities(line))

    def test_legacy_continuous_normal_unchanged(self):
        record = {"kind": "normal", "mean": -3, "sd": 2}
        d = parse_distribution(record)
        self.assertIsInstance(d, NormalDistribution)
        self.assertEqual(d.probabilities(-3).push, 0.0)


class EvaluationCompatibility(unittest.TestCase):
    def test_categorical_scores_accept_discretized_probabilities(self):
        d = DiscretizedNormalDistribution(55, 20, "signed_integer")
        p = d.probabilities(55.0)
        probs = (p.over, p.under, p.push)
        expected_brier = p.over ** 2 + p.under ** 2 + (p.push - 1) ** 2
        self.assertAlmostEqual(categorical_brier(probs, "push"), expected_brier, places=10)
        self.assertAlmostEqual(categorical_log_loss(probs, "push"), -math.log(p.push), places=10)


class NumericalStress(unittest.TestCase):
    def test_extreme_parameters(self):
        cases = (
            (DiscretizedNormalDistribution(1e6, 500, "signed_integer"), 1e6 + 0.5),
            (DiscretizedNormalDistribution(0, 0.01, "signed_integer"), 0.0),
            (DiscretizedNormalDistribution(-40, 8, "signed_integer"), -40.0),
            (DiscretizedNormalDistribution(12, 4, "nonnegative_integer"), 500.5),
        )
        for dist, line in cases:
            with self.subTest(mean=dist.mean, sd=dist.sd, line=line):
                p = dist.probabilities(line)
                self.assertGreaterEqual(p.over, 0.0)
                self.assertGreaterEqual(p.under, 0.0)
                self.assertGreaterEqual(p.push, 0.0)
                self.assertAlmostEqual(p.over + p.under + p.push, 1.0, places=9)

    def test_random_fuzz_complementarity(self):
        rng = random.Random(20261112)
        for _ in range(80):
            mean = rng.uniform(-80, 120)
            sd = rng.uniform(0.05, 40)
            support = rng.choice(("signed_integer", "nonnegative_integer"))
            line = rng.choice([x + 0.0 for x in range(-5, 100)] + [x + 0.5 for x in range(-5, 100)])
            dist = DiscretizedNormalDistribution(mean, sd, support)
            p = dist.probabilities(line)
            self.assertAlmostEqual(p.over + p.under + p.push, 1.0, places=9)


if __name__ == "__main__":
    unittest.main()
