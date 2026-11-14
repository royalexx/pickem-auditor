"""C10 adversarial anti-peeking, cutoff, metadata, and power checks.

The primary result remains permanently non-promotional under both simulated
C10 candidate methods; no realized paired score is accessed by this module.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from math import isfinite
import hashlib
import json
import unittest

from v2.c10_sog_inference_gate import (
    SCHEMA, EXPERIMENT, GOAL_DATES, ONE_SIDED_ALPHA, MIN_USEFUL_BRIER,
    PENDING_CANDIDATES, C10GateError,
    blind_metadata_health, decision_for_existing_study,
    iid_gaussian_planning, power_feasibility_table,
    write_research_health_report,
)


def valid_health_manifest():
    return {
        "schema": "v25_nhl_sog_daily_prospective_paired_validation_v1",
        "experiment_id": EXPERIMENT,
        "generated_at_utc": "2026-11-14T19:33:37.236588Z",
        "local_date": "2026-11-14",
        "preregistered_research_minimum_dates": 40,
        "production_modified": False,
        "t1_t2_promotion_allowed": False,
        "never_backdate_pregame_forecasts": True,
        "not_a_model_retraining_workflow": True,
        "source_capture_time_not_provider_publisher_signed": True,
        "evaluation_only_on_independent_official_FINAL": True,
        "eligible_date_count": 1,
        "settled_scored_count": 7,
        "genuine_original_success_attempts_found": 11,
        "frozen_source_qualified": 7,
        "synthetic_test_cases_scored": 0,
        "scientific_validation_gate": "NOT_ESTABLISHED",
    }


class NeverReadOutcomes(dict):
    banned = {
        "date_equal_GP_minus_poisson", "paired_GP_minus_poisson",
        "paired_daily_mean_metrics", "model_metrics",
        "scored_outcomes", "models", "player_predictions",
    }

    def __getitem__(self, name):
        if name in self.banned:
            raise AssertionError("UNAPPROVED_INTERIM_STATISTICAL_PEEK:" + name)
        return super().__getitem__(name)

    def get(self, name, default=None):
        if name in self.banned:
            raise AssertionError("UNAPPROVED_INTERIM_STATISTICAL_PEEK:" + name)
        return super().get(name, default)

    def __contains__(self, name):
        if name in self.banned:
            raise AssertionError("UNAPPROVED_INTERIM_STATISTICAL_PEEK:" + name)
        return super().__contains__(name)


class C10InferenceGateTests(unittest.TestCase):
    def test_fixed_protocol_and_competing_methods_not_cherry_picked(self):
        self.assertEqual(GOAL_DATES, 40)
        self.assertEqual(ONE_SIDED_ALPHA, 0.025)
        self.assertEqual(MIN_USEFUL_BRIER, .002)
        self.assertEqual(len(PENDING_CANDIDATES), 2)
        self.assertNotEqual(PENDING_CANDIDATES[0], PENDING_CANDIDATES[1])

    def test_outcome_read_forbidden_even_with_poisoned_result_fields(self):
        original = valid_health_manifest()
        for field in NeverReadOutcomes.banned:
            original[field] = object()
        x = blind_metadata_health(NeverReadOutcomes(original), "f" * 64)
        self.assertEqual(x["eligible_slate_dates_reported"], 1)
        self.assertEqual(x["matched_offered_contracts_reported"], 7)
        self.assertFalse(x["realized_proper_scores_accessed"])

    def test_too_few_dates_status_no_early_test(self):
        metadata = blind_metadata_health(valid_health_manifest(), "f" * 64)
        x = decision_for_existing_study(metadata, as_of=date(2026, 11, 14))
        self.assertEqual(x["status"], "RESEARCH_COLLECTING_CONFIRMATORY_BLOCKED")
        self.assertEqual(x["missing_eligible_dates"], 39)
        self.assertIsNone(x["p_value"])
        self.assertIsNone(x["confidence_interval"])
        self.assertFalse(x["lag3_or_lag5_confirmatory_method_approved"])
        self.assertFalse(x["approved_for_promotional_probability_or_tier"])

    def test_even_40_dates_never_authorizes_previously_unapproved_method(self):
        x = decision_for_existing_study(
            {"eligible_slate_dates_reported": 40},
            as_of=date(2027, 1, 30))
        self.assertEqual(x["status"], "FORTY_DATES_MET_NO_APPROVED_INFERENCE")
        self.assertFalse(x["independent_statistical_signoff"])
        self.assertFalse(x["40_dates_statistically_adequate_power_proven"])
        self.assertTrue(x["future_experiment_requires_new_versioned_preoutcome_protocol"])
        self.assertIsNone(x["p_value"])

    def test_after_deadline_no_flexible_extension(self):
        x = decision_for_existing_study(
            {"eligible_slate_dates_reported": 39},
            as_of=date(2027, 2, 1))
        self.assertEqual(x["status"], "ADMINISTRATIVELY_INCOMPLETE_40_DATES")
        self.assertEqual(x["missing_eligible_dates"], 1)

    def test_invalid_denominators_and_source_provenance_fail_closed(self):
        for mutation in (
            {"production_modified": True},
            {"t1_t2_promotion_allowed": True},
            {"source_capture_time_not_provider_publisher_signed": False},
            {"evaluation_only_on_independent_official_FINAL": False},
            {"synthetic_test_cases_scored": 1},
            {"preregistered_research_minimum_dates": 39},
            {"eligible_date_count": 41},
            {"eligible_date_count": 2, "settled_scored_count": 1},
            {"settled_scored_count": 12},
            {"frozen_source_qualified": 12},
            {"scientific_validation_gate": "APPROVED"},
            {"generated_at_utc": "2026-11-14T10:00:00"},
        ):
            with self.subTest(mutation=mutation):
                m = {**valid_health_manifest(), **mutation}
                with self.assertRaises(C10GateError):
                    blind_metadata_health(m, "a" * 64)

    def test_no_fabricated_sha_and_nonint_date_count(self):
        m = valid_health_manifest()
        with self.assertRaisesRegex(C10GateError, "SHA_MISSING"):
            blind_metadata_health(m, "not-digest")
        for val in (True, 1.0, -1, "1"):
            m = valid_health_manifest()
            m["eligible_date_count"] = val
            with self.subTest(value=val), self.assertRaises(C10GateError):
                blind_metadata_health(m, "b"*64)

    def test_ideal_gaussian_power_fails_horizon_across_assumption_grid(self):
        grid = power_feasibility_table()
        self.assertEqual(len(grid), 12)
        self.assertEqual(len({(x["assumed_sd"], x["assumed_ar1_rho"])
                              for x in grid}), 12)
        self.assertTrue(all(0 <= x["optimistic_known_variance_z_power"] < .8
                            for x in grid))
        self.assertTrue(all(x["optimistic_dates_for_target_power"] > 40
                            for x in grid))
        ideal = iid_gaussian_planning(sd=.01, rho=0)
        self.assertTrue(.20 < ideal["optimistic_known_variance_z_power"] < .30)
        self.assertTrue(190 <= ideal["optimistic_dates_for_target_power"] <= 210)
        large_sd = iid_gaussian_planning(sd=.04, rho=.6)
        self.assertLess(large_sd["optimistic_known_variance_z_power"],
                        ideal["optimistic_known_variance_z_power"])
        self.assertGreater(large_sd["optimistic_dates_for_target_power"], 10000)
        self.assertEqual(ideal["type"],
                         "GAUSSIAN_KNOWN_VARIANCE_PLANNING_ONLY_NOT_INFERENCE")

    def test_no_invalid_analytic_input_or_fake_asof(self):
        for kwargs in ({"sd": 0.0}, {"sd": -.01}, {"sd": .01, "rho": 1},
                       {"sd": .01, "rho": -.2}, {"sd": float("nan")},
                       {"sd": .01, "effect": 0}, {"sd": .01, "n": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(C10GateError):
                iid_gaussian_planning(**kwargs)
        with self.assertRaises(C10GateError):
            decision_for_existing_study({}, as_of="2026-11-14")

    def test_readonly_derived_file_never_changes_existing_record(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            source = root / "external-original.json"
            original = valid_health_manifest()
            original["scored_outcomes"] = [{"private_brier": 999.999}]
            original["paired_GP_minus_poisson"] = {"SECRET": 42}
            raw = json.dumps(original).encode()
            source.write_bytes(raw)
            output = root / "new-analysis/receipt.json"
            first, digest = write_research_health_report(
                source, output, as_of=date(2026, 11, 14))
            self.assertEqual(raw, source.read_bytes())
            self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), digest)
            self.assertEqual(first["eligible_date_count"], 1)
            self.assertNotIn("SECRET", output.read_text())
            self.assertNotIn("private_brier", output.read_text())
            second, second_hash = write_research_health_report(
                source, output, as_of=date(2026, 11, 14))
            self.assertEqual(second, first)
            self.assertEqual(second_hash, digest)
            original["eligible_date_count"] = 2
            original["settled_scored_count"] = 7
            source.write_text(json.dumps(original))
            with self.assertRaises(C10GateError):
                write_research_health_report(
                    source, output, as_of=date(2026, 11, 14))


if __name__ == "__main__":
    unittest.main()
