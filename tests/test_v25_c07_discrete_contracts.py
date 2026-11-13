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


def pmf_mass_sum(dist: DiscretizedNormalDistribution, *, max_k: int = 500) -> float:
    total = 0.0
    if dist.support == "signed_integer":
        for k in range(-max_k, max_k + 1):
            total += dist.pmf(k)
        return total
    for k in range(0, max_k + 1):
        total += dist.pmf(k)
    tail = dist.prob_greater_than(float(max_k))
    return total + tail


class ProblemReproduction(unittest.TestCase):
    def test_continuous_normal_never_pushes_on_integer_line(self):
        d = NormalDistribution(55, 20)
        p = d.probabilities(55.0)
        self.assertEqual(p.push, 0.0)
        self.assertAlmostEqual(p.over + p.under, 1.0)


class NonnegativeClamp(unittest.TestCase):
    def test_under_zero_line_is_zero(self):
        d = DiscretizedNormalDistribution(0, 2, "nonnegative_integer")
        self.assertAlmostEqual(d.probabilities(0.0).under, 0.0, places=12)

    def test_pmf_mass_sums_to_one(self):
        d = DiscretizedNormalDistribution(12, 4, "nonnegative_integer")
        self.assertAlmostEqual(pmf_mass_sum(d), 1.0, places=9)

    def test_negative_mean_assigns_mass_to_zero(self):
        d = DiscretizedNormalDistribution(-5, 2, "nonnegative_integer")
        self.assertGreater(d.pmf(0), 0.95)
        self.assertGreater(d.pmf(1), 0.0)

    def test_no_probability_below_zero(self):
        d = DiscretizedNormalDistribution(-5, 2, "nonnegative_integer")
        for k in range(-20, 0):
            self.assertEqual(d.pmf(k), 0.0)
        self.assertAlmostEqual(d.prob_less_than(0.0), 0.0, places=12)

    def test_fractional_line_cutpoint(self):
        d = DiscretizedNormalDistribution(4, 2, "nonnegative_integer")
        self.assertAlmostEqual(
            d.probabilities(0.25).under,
            d.probabilities(0.5).under,
            places=12,
        )


class SignedLattice(unittest.TestCase):
    def test_fractional_negative_line_uses_lattice(self):
        d = DiscretizedNormalDistribution(0, 3, "signed_integer")
        self.assertAlmostEqual(d.prob_less_than(-0.25), d._cdf(-0.5), places=12)

    def test_integer_push_matches_pmf(self):
        d = DiscretizedNormalDistribution(55, 20, "signed_integer")
        p = d.probabilities(55.0)
        self.assertAlmostEqual(p.push, d.pmf(55), places=12)


class SettlementLaws(unittest.TestCase):
    def setUp(self) -> None:
        self.d = DiscretizedNormalDistribution(55, 20, "signed_integer")

    def test_push_positive_at_integer_line(self):
        self.assertGreater(self.d.probabilities(55.0).push, 0.0)

    def test_no_push_at_half_integer_line(self):
        self.assertEqual(self.d.probabilities(55.5).push, 0.0)

    def test_cdf_coherence_between_integer_and_half_step(self):
        at_int = self.d.probabilities(55.0)
        at_half = self.d.probabilities(55.5)
        self.assertAlmostEqual(at_int.under + at_int.push, at_half.under, places=10)

    def test_complementarity(self):
        lines = (0.0, 0.25, 0.5, 55.0, 55.5, 99.7, -12.0, -11.5, -0.25)
        for dist in (
            self.d,
            DiscretizedNormalDistribution(0, 2, "nonnegative_integer"),
        ):
            for line in lines:
                p = dist.probabilities(line)
                self.assertAlmostEqual(p.over + p.under + p.push, 1.0, places=10)

    def test_discrete_cdf_monotone(self):
        d = DiscretizedNormalDistribution(20, 6, "signed_integer")
        prev = 0.0
        for y in range(-30, 80):
            cur = d.prob_le(y)
            self.assertGreaterEqual(cur, prev - 1e-15)
            prev = cur


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

    def test_nonnegative_targets_validate(self):
        q = targets_quote(40.0)
        d = DiscretizedNormalDistribution(40, 10, "nonnegative_integer")
        forecast_for(q, d).validate_against(q)

    def test_signed_receiving_yards_validate(self):
        q = receiving_yards_quote(-3.0)
        d = DiscretizedNormalDistribution(-2, 15, "signed_integer")
        forecast_for(q, d).validate_against(q)


class Serialization(unittest.TestCase):
    def test_round_trip_preserves_probabilities(self):
        d = DiscretizedNormalDistribution(55, 20, "signed_integer")
        restored = parse_distribution(d.to_record())
        for line in (-0.25, 54.5, 55.0, 55.5, 120.0, 120.25):
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
        for _ in range(120):
            mean = rng.uniform(-80, 120)
            sd = rng.uniform(0.05, 40)
            support = rng.choice(("signed_integer", "nonnegative_integer"))
            line = rng.uniform(-20, 90)
            dist = DiscretizedNormalDistribution(mean, sd, support)
            p = dist.probabilities(line)
            self.assertAlmostEqual(p.over + p.under + p.push, 1.0, places=9)


if __name__ == "__main__":
    unittest.main()
