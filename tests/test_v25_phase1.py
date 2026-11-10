"""Adversarial Phase 1 contract, scoring and leakage regression tests."""
from dataclasses import replace
import math
import unittest

from v2.baselines import HistoricalExposure, poisson_rate_baseline, role_shrunk_rate
from v2.contracts import (ContractError, DiscreteDistribution, ForecastSnapshot,
                          MarketQuote, NormalDistribution, PoissonDistribution,
                          SourceReceipt, no_vig_over, parse_snapshot)
from v2.evaluation import (Settlement, evaluate, brier, crps_ensemble,
                           energy_score, variogram_score)

SHA = "a"*64
BASE = "2026-11-09T16:00:00Z"
FREEZE = "2026-11-09T16:30:00Z"
START = "2026-11-09T18:00:00Z"
AFTER = "2026-11-10T01:00:00Z"


def quote(**kwargs):
    data = dict(quote_id="q1", contract_id="c1", event_id="NFL-1", event_start_at=START,
                sport="NFL", league="NFL", season=2026, team_id="T1", opponent_id="T2",
                player_id="player1", stat_key="targets", period="full",
                line=4.5, book="example", product_type="pickem", quote_at=BASE,
                quote_receipt_sha256=SHA, settlement_policy="strict_gt_lt_equal_push", quote_kind="real")
    data.update(kwargs)
    return MarketQuote(**data)


def forecast(q=None, **kwargs):
    q = q or quote()
    data = dict(forecast_id="f1", run_id="r1", model_id="frozen_v1",
                model_version="frozen-original", quote_id=q.quote_id, contract_id=q.contract_id,
                event_id=q.event_id, sport=q.sport, league=q.league, season=q.season,
                team_id=q.team_id, opponent_id=q.opponent_id,
                quote_receipt_sha256=q.quote_receipt_sha256,
                player_id=q.player_id, stat_key=q.stat_key,
                period=q.period, line=q.line, forecast_at="2026-11-09T16:40:00Z",
                input_freeze_at=FREEZE, decision_cutoff_at="2026-11-09T16:35:00Z",
                model_training_cutoff_at="2026-11-08T23:59:00Z",
                model_artifact_sha256=SHA, code_commit="f"*40,
                sources=(SourceReceipt("stats-receipt", BASE, BASE, SHA, "https://example.org/stats", "stats/source.json"),),
                distribution=DiscreteDistribution(((0., .25), (6., .75))))
    data.update(kwargs)
    return ForecastSnapshot(**data)


def settlement(**kwargs):
    data = dict(event_id="NFL-1", player_id="player1", stat_key="targets",
                period="full", status="settled", actual=6, settled_at=AFTER)
    data.update(kwargs)
    return Settlement(**data)


class DistributionTests(unittest.TestCase):
    def test_push_and_signed_yardage(self):
        d = DiscreteDistribution(((-4., .2), (0., .5), (7., .3)))
        x = d.probabilities(0.)
        self.assertAlmostEqual(x.under, .2)
        self.assertAlmostEqual(x.push, .5)
        self.assertAlmostEqual(x.over, .3)
        self.assertAlmostEqual(x.conditional_over(), .6)
        self.assertAlmostEqual(sum((x.over, x.under, x.push)), 1)

    def test_fractional_line_cannot_push_discrete_integer(self):
        x = DiscreteDistribution(((4., .4), (5., .6))).probabilities(4.5)
        self.assertEqual(x.push, 0)
        self.assertAlmostEqual(x.over, .6)

    def test_poisson_complementarity_many_rates_and_lines(self):
        for rate in (0, 0.01, 1.5, 20., 55., 200., 300.):
            dist = PoissonDistribution(rate)
            for line in (-0.5, 0., 0.5, 1., 3.5, 20.5, 100., 300.5):
                with self.subTest(rate=rate, line=line):
                    p = dist.probabilities(line)
                    self.assertAlmostEqual(sum((p.over, p.under, p.push)), 1., places=10)
                    self.assertGreaterEqual(p.over, 0)

    def test_poisson_thresholds_and_zero_rate(self):
        x = PoissonDistribution(2).probabilities(2.)
        self.assertAlmostEqual(x.under, 3*math.exp(-2), places=10)
        self.assertAlmostEqual(x.push, 2*math.exp(-2), places=10)
        self.assertAlmostEqual(sum((x.over, x.under, x.push)), 1)
        zero = PoissonDistribution(0).probabilities(0)
        self.assertEqual((zero.over, zero.under, zero.push), (0, 0, 1))
        self.assertEqual(PoissonDistribution(0).probabilities(-.5).over, 1)

    def test_normal_allows_negative_line_and_no_push(self):
        x = NormalDistribution(-3, 2).probabilities(-3)
        self.assertAlmostEqual(x.over, .5)
        self.assertEqual(x.push, 0)

    def test_invalid_mass_and_nonfinite(self):
        with self.assertRaises(ContractError):
            DiscreteDistribution(((2., .5), (1., .5)))
        with self.assertRaises(ContractError):
            DiscreteDistribution(((1., .9),))
        with self.assertRaises(ContractError):
            NormalDistribution(0, float("nan"))

    def test_exact_scores_one_dimensional_example(self):
        self.assertAlmostEqual(crps_ensemble([0, 2], 1), .5)
        self.assertAlmostEqual(energy_score([(0,), (2,)], (1,)), .5)
        self.assertAlmostEqual(variogram_score([(0, 0), (2, 2)], (0, 1)), 1)
        self.assertAlmostEqual(energy_score([(0., 0.)], (0., 0.)), 0)
        with self.assertRaises(ContractError):
            variogram_score([(0., 1.)], (0., 1.), power=1.0)


class ProvenanceTests(unittest.TestCase):
    def test_snapshot_valid_and_reproducible_hash(self):
        q = quote()
        f = forecast(q)
        f.validate_against(q)
        self.assertEqual(f.snapshot_sha256, parse_snapshot(f.to_record()).snapshot_sha256)
        self.assertEqual(len(f.snapshot_sha256), 64)

    def test_future_training_rejected(self):
        with self.assertRaisesRegex(ContractError, "forecast_temporal_order"):
            forecast(model_training_cutoff_at=AFTER).validate_against(quote())

    def test_future_source_rejected(self):
        with self.assertRaisesRegex(ContractError, "future_source_retrieval"):
            forecast(sources=(SourceReceipt("late", BASE, AFTER, SHA, "https://example.org/stats", "stats/late.json"),)).validate_against(quote())

    def test_timestamp_naive_and_future_quote_rejected(self):
        with self.assertRaisesRegex(ContractError, "naive_timestamp"):
            forecast(input_freeze_at="2026-11-09T16:30:00").validate_against(quote())
        with self.assertRaisesRegex(ContractError, "quote_after_input_freeze"):
            forecast().validate_against(quote(quote_at="2026-11-09T16:38:00Z"))

    def test_immutable_internal_collections_and_commit_sha(self):
        with self.assertRaisesRegex(ContractError, "distribution_masses_must_be_immutable_pairs"):
            DiscreteDistribution([[1., 1.]])
        with self.assertRaisesRegex(ContractError, "sources_must_be_immutable_tuple"):
            forecast(sources=[]).validate_against(quote())
        with self.assertRaisesRegex(ContractError, "invalid_code_commit_sha"):
            forecast(code_commit="not-a-real-commit").validate_against(quote())

    def test_postgame_forecast_rejected(self):
        with self.assertRaisesRegex(ContractError, "forecast_temporal_order"):
            forecast(forecast_at=AFTER).validate_against(quote())

    def test_mismatched_market_identity_rejected(self):
        with self.assertRaisesRegex(ContractError, "forecast_quote_mismatch"):
            forecast(line=3.5).validate_against(quote())

    def test_market_probability_no_invented_odds(self):
        self.assertIsNone(no_vig_over(quote()))
        self.assertIsNone(no_vig_over(quote(quote_kind="synthetic", over_decimal_odds=1.8, under_decimal_odds=2)))
        self.assertIsNone(no_vig_over(quote(over_decimal_odds=2, under_decimal_odds=2)))
        self.assertAlmostEqual(no_vig_over(quote(product_type="sportsbook_two_sided", over_decimal_odds=2, under_decimal_odds=2)), .5)


class EvaluationTests(unittest.TestCase):
    def test_hard_zero_probability_is_scored_with_disclosed_floor(self):
        q = quote()
        f = forecast(q, distribution=DiscreteDistribution(((0., 1.),)))
        r = evaluate([q], [f], [settlement(actual=6)])
        self.assertEqual(r["models"]["frozen_v1"]["log_loss_clipped_rows"], 1)
        self.assertGreater(r["models"]["frozen_v1"]["log_loss"], 20)

    def test_one_contract_one_score(self):
        q = quote()
        r = evaluate([q], [forecast(q)], [settlement()])
        self.assertEqual(r["scorable_contracts"], 1)
        self.assertEqual(r["models"]["frozen_v1"]["scored"], 1)
        self.assertAlmostEqual(r["models"]["frozen_v1"]["brier"], .0625)
        self.assertFalse(r["promotion_authorized"])

    def test_missing_and_rejected_preserve_denominators(self):
        q1 = quote()
        q2 = quote(quote_id="q2", contract_id="c2", player_id="other")
        q3 = quote(quote_id="q3", contract_id="c3", accepted=False, reject_reason="QUOTE_STALE")
        r = evaluate([q1, q2, q3], [forecast(q1)], [settlement()])
        self.assertEqual(r["quotes_total"], 3)
        self.assertEqual(r["statuses"]["missing_settlement"], 1)
        self.assertEqual(r["statuses"]["rejected"], 1)
        self.assertEqual(r["rejection_reasons"]["QUOTE_STALE"], 1)
        self.assertEqual(r["scorable_contracts"], 1)

    def test_push_and_void_not_losses(self):
        q = quote(line=6.)
        f = forecast(q)
        r = evaluate([q], [f], [settlement(actual=6)])
        self.assertEqual(r["statuses"]["push"], 1)
        self.assertEqual(r["scorable_contracts"], 0)
        r = evaluate([q], [f], [settlement(status="void", actual=None, settled_at=None)])
        self.assertEqual(r["statuses"]["void"], 1)

    def test_duplicate_model_and_forecast_ids_rejected(self):
        q = quote()
        with self.assertRaises(ContractError):
            evaluate([q], [forecast(q), forecast(q)], [settlement()])

    def test_paired_same_contract_and_cluster_gate(self):
        q = quote()
        f0 = forecast(q)
        f1 = forecast(q, forecast_id="f2", model_id="v25", distribution=DiscreteDistribution(((0., .1), (6., .9))))
        r = evaluate([q], [f0, f1], [settlement()])
        self.assertEqual(r["paired"]["v25"]["matched_contracts"], 1)
        self.assertLess(r["paired"]["v25"]["brier_difference"], 0)
        self.assertEqual(r["paired"]["v25"]["brier_cluster_interval"]["status"], "insufficient_clusters")

    def test_outcome_available_before_game_is_invalid(self):
        with self.assertRaisesRegex(ContractError, "outcome_available_before_game"):
            evaluate([quote()], [forecast()], [settlement(settled_at=BASE)])

    def test_binary_scores_condition_on_nonpush(self):
        # Negative values are legal for signed yardage, never for targets.
        q = quote(stat_key="receiving yards", line=0.)
        f = forecast(q, line=0., distribution=DiscreteDistribution(((-1., .2), (0., .5), (1., .3))))
        s = settlement(stat_key="receiving yards", actual=1)
        r = evaluate([q], [f], [s])
        self.assertAlmostEqual(r["models"]["frozen_v1"]["brier"], .16)

    def test_synthetic_count_not_market_claim(self):
        q = quote(quote_kind="synthetic")
        r = evaluate([q], [forecast(q)], [settlement()])
        self.assertEqual(r["statuses"]["accepted_synthetic"], 1)
        self.assertEqual(r["models"]["frozen_v1"]["synthetic_diagnostic_scored"], 1)


class BaselineTests(unittest.TestCase):
    def rows(self):
        return [HistoricalExposure("p1", "targets", "WR1", "e1", "2026-11-01T18:00:00Z", "2026-11-02T00:00:00Z", 10, 2),
                HistoricalExposure("p1", "targets", "WR1", "e2", "2026-11-08T18:00:00Z", "2026-11-09T00:00:00Z", 10, 4),
                HistoricalExposure("p1", "targets", "WR1", "future", START, AFTER, 10, 100),
                HistoricalExposure("p2", "targets", "WR1", "e3", "2026-11-08T18:00:00Z", "2026-11-09T00:00:00Z", 10, 6)]

    def test_historical_outcome_future_excluded(self):
        dist = poisson_rate_baseline(self.rows(), player_id="p1", stat_key="targets",
                                     freeze_at=FREEZE, projected_exposure=10)
        self.assertAlmostEqual(dist.rate, 3)

    def test_prior_uses_role_peers_only(self):
        dist = role_shrunk_rate(self.rows(), player_id="p1", stat_key="targets", role="WR1",
                                freeze_at=FREEZE, projected_exposure=10, prior_exposure=20)
        self.assertAlmostEqual(dist.rate, 4.5)

    def test_no_training_labels(self):
        with self.assertRaisesRegex(ContractError, "no_pregame_history"):
            poisson_rate_baseline([], player_id="p", stat_key="targets", freeze_at=FREEZE)


if __name__ == "__main__":
    unittest.main()
