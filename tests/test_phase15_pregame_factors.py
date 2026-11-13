"""Phase 1.5 V25-P1.5-07 pregame factor capture — adversarial tests A–K."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from v2.official_nba_nhl_capture import SettlementCaptureError
from v2.phase15_pregame_factors import (
    SCHEMA_PRODUCER_OUTPUT,
    STATUS_AVAILABLE,
    STATUS_INVALID,
    STATUS_UNMEASURED,
    build_capture_manifest,
    factor_specs,
    integrate_shadow_factor_capture,
    make_shadow_receipt,
    manifest_canonical_hash,
    validate_factor_row,
    write_capture_manifest,
)

CLOCK = "2026-11-11T18:00:00Z"
EVENT = "2026-11-12T00:00:00Z"
RUN_ID = "test-run-7f3a"
FORECAST_ID = "forecast-test-001"


def write_producer_archive(
    root: Path,
    relative: str,
    *,
    sport: str,
    stat: str,
    factors: dict[str, float],
    identity: dict,
) -> str:
    predictions = [
        {
            "factor_name": fname,
            "units": next(u for n, _c, u in factor_specs(sport, stat) if n == fname),
            "predicted_value": value,
        }
        for fname, value in factors.items()
    ]
    doc = {
        "schema": SCHEMA_PRODUCER_OUTPUT,
        "model_version": identity["model_version"],
        "run_id": identity.get("run_id", RUN_ID),
        "forecast_id": identity.get("forecast_id", FORECAST_ID),
        "sport": sport,
        "event_id": identity["event_id"],
        "player_id": identity["player_id"],
        "stat": stat,
        "input_freeze_at": identity["input_freeze_at"],
        "forecast_at": identity["forecast_at"],
        "model_training_cutoff_at": identity.get("model_training_cutoff_at"),
        "factor_predictions": predictions,
    }
    path = root / relative
    path.write_text(json.dumps(doc, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def producer_data(root, sport="NHL", *, omit=None):
    identity = {
        "sport": sport,
        "stat": "shots on goal" if sport == "NHL" else "pra",
        "event_id": "pregame-event",
        "player_id": "123",
        "model_version": "shadow-study-001",
        "input_freeze_at": "2026-11-11T17:30:00Z",
        "forecast_at": "2026-11-11T17:30:00Z",
        "model_training_cutoff_at": "2026-11-10T00:00:00Z",
        "run_id": RUN_ID,
        "forecast_id": FORECAST_ID,
    }
    ret = {
        **{k: identity[k] for k in ("sport",) if k in identity},
        "stat": identity["stat"],
        "event_id": identity["event_id"],
        "player_id": identity["player_id"],
        "model_version": identity["model_version"],
        "forecast_id": identity["forecast_id"],
        "producer_run_id": identity["run_id"],
        "period": "full",
        "event_start": EVENT,
        "forecast_at": identity["forecast_at"],
        "input_freeze_at": identity["input_freeze_at"],
        "model_training_cutoff_at": identity["model_training_cutoff_at"],
        "source_receipts": [],
    }
    if sport == "NHL":
        factors = {
            "team_unblocked_attempts": 60,
            "probability_active": 0.95,
            "individual_share_if_active": 0.08,
            "on_target_probability": 0.60,
        }
        ret["factorization"] = "nhl_SOG_unblocked_team_attempt_product_v1"
        ret["implied_mean"] = 60 * 0.95 * 0.08 * 0.60
    else:
        factors = {
            "projected_minutes": 29,
            "projected_team_possessions": 101,
            "player_usage_or_opportunity_rate": 0.21,
            "conditional_stat_rate_per_minute": 0.67,
        }
        ret["factorization"] = "nba_diagnostic_nonmultiplicative_v1"
        ret["implied_mean"] = None
    if omit:
        factors.pop(omit)
    ret["factors"] = factors
    digest = write_producer_archive(root, "one.json", sport=sport, stat=ret["stat"], factors=factors, identity=identity)
    ret["source_receipts"] = [
        {
            "archive_path": "one.json",
            "sha256": digest,
            "retrieved_at": "2026-11-11T17:00:00Z",
            "factor_names": list(factors.keys()),
        }
    ]
    return ret


def frozen_bundle(root, sport="NHL", *, full=True):
    prod = producer_data(root, sport) if full else {
        "sport": sport,
        "stat": "shots on goal" if sport == "NHL" else "pra",
        "event_id": "pregame-event",
        "player_id": "123",
        "event_start": EVENT,
        "forecast_at": "2026-11-11T17:30:00Z",
        "input_freeze_at": "2026-11-11T17:30:00Z",
    }
    if full:
        return {
            "schema": "v25_phase15_frozen_capture_bundle_v1",
            "experiment_id": "EXP-TEST",
            "run_id": RUN_ID,
            "contracts": [
                {
                    **{k: prod[k] for k in ("sport", "stat", "event_id", "player_id", "event_start")},
                    "game_date": "2026-11-11",
                    "forecast_at": prod["forecast_at"],
                    "input_freeze_at": prod["input_freeze_at"],
                    "model_training_cutoff_at": prod.get("model_training_cutoff_at"),
                    "model_version": prod.get("model_version"),
                    "producer_run_id": prod.get("producer_run_id"),
                    "original_forecast_contract_id": prod.get("forecast_id"),
                    "producer_factors": {
                        "factors": prod.get("factors"),
                        "source_receipts": prod.get("source_receipts"),
                    },
                }
            ],
        }
    return {
        "schema": "v25_phase15_frozen_capture_bundle_v1",
        "experiment_id": "EXP-TEST",
        "run_id": RUN_ID,
        "contracts": [
            {
                "sport": sport,
                "stat": "shots on goal" if sport == "NHL" else "pra",
                "event_id": "pregame-event",
                "player_id": "123",
                "game_date": "2026-11-11",
                "event_start": EVENT,
                "forecast_at": "2026-11-11T17:30:00Z",
                "input_freeze_at": "2026-11-11T17:30:00Z",
            }
        ],
    }


class FactorReceiptTests(unittest.TestCase):
    def test_A_valid_pregame_source_available_factor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ret = producer_data(root)
            manifest = build_capture_manifest(
                frozen_bundle(root),
                source_root=root,
                observed_clock=CLOCK,
            )
            rows = manifest["contracts"][0]["factor_rows"]
            self.assertEqual(len(rows), 4)
            self.assertTrue(all(r["status"] == STATUS_AVAILABLE for r in rows))

    def test_B_missing_authentic_prediction_unmeasured(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = build_capture_manifest(
                frozen_bundle(root, full=False),
                source_root=root,
                observed_clock=CLOCK,
            )
            rows = manifest["contracts"][0]["factor_rows"]
            self.assertEqual(len(rows), 4)
            self.assertTrue(all(r["status"] == STATUS_UNMEASURED for r in rows))
            self.assertFalse(manifest["four_factor_attribution_possible"])

    def test_C_source_retrieved_after_freeze_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = frozen_bundle(root)
            bundle["contracts"][0]["producer_factors"]["source_receipts"][0]["retrieved_at"] = (
                "2026-11-11T18:01:00Z"
            )
            manifest = build_capture_manifest(bundle, source_root=root, observed_clock=CLOCK)
            statuses = {r["factor_name"]: r["status"] for r in manifest["contracts"][0]["factor_rows"]}
            self.assertEqual(statuses["team_unblocked_attempts"], STATUS_INVALID)

    def test_D_forecast_at_or_after_event_start_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = frozen_bundle(root)
            bundle["contracts"][0]["forecast_at"] = EVENT
            manifest = build_capture_manifest(bundle, source_root=root, observed_clock=CLOCK)
            self.assertTrue(
                all(r["status"] == STATUS_INVALID for r in manifest["contracts"][0]["factor_rows"])
            )

    def test_E_mismatched_event_player_id_invalid(self):
        event = datetime(2026, 11, 12, 0, 0, tzinfo=timezone.utc)
        clock = datetime(2026, 11, 11, 18, 0, tzinfo=timezone.utc)
        row = {
            "factor_name": "team_unblocked_attempts",
            "status": STATUS_AVAILABLE,
            "predicted_value": 10,
            "event_id": "other-event",
            "player_id": "123",
            "input_freeze_at": "2026-11-11T17:00:00Z",
            "forecast_at": "2026-11-11T17:00:00Z",
            "source_identifier": "s",
            "source_content_sha256": "a" * 64,
            "source_retrieved_at": "2026-11-11T16:00:00Z",
        }
        with self.assertRaisesRegex(SettlementCaptureError, "factor_row_event_mismatch"):
            validate_factor_row(
                row,
                sport="NHL",
                stat="shots on goal",
                event_id="pregame-event",
                player_id="123",
                event_start=event,
                possession_clock=clock,
            )

    def test_F_tampered_archived_bytes_integrity_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ret = producer_data(root)
            (root / "one.json").write_text('{"tampered":true}', encoding="utf-8")
            with self.assertRaisesRegex(SettlementCaptureError, "hash_mismatch"):
                make_shadow_receipt(ret, source_root=root, observed_clock=CLOCK)

    def test_G_duplicate_capture_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "captures"
            m1 = build_capture_manifest(frozen_bundle(root), source_root=root, observed_clock=CLOCK)
            write_capture_manifest(m1, out)
            bundle2 = frozen_bundle(root)
            bundle2["run_id"] = RUN_ID
            bundle2["contracts"][0]["player_id"] = "999"
            m2 = build_capture_manifest(bundle2, source_root=root, observed_clock="2026-11-11T19:00:00Z")
            with self.assertRaisesRegex(SettlementCaptureError, "duplicate_capture_key"):
                write_capture_manifest(m2, out)

    def test_H_rerun_same_frozen_input_identical_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = frozen_bundle(root)
            m1 = build_capture_manifest(bundle, source_root=root, observed_clock=CLOCK)
            m2 = build_capture_manifest(bundle, source_root=root, observed_clock=CLOCK)
            self.assertEqual(m1["manifest_sha256"], m2["manifest_sha256"])
            self.assertEqual(manifest_canonical_hash(m1), m2["manifest_sha256"])

    def test_K_postgame_actual_cannot_populate_pregame_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ret = producer_data(root)
            ret["factors"]["actual_team_volume"] = 50
            with self.assertRaisesRegex(SettlementCaptureError, "postgame_factor_forbidden"):
                make_shadow_receipt(ret, source_root=root, observed_clock=CLOCK)

    def test_valid_future_NHL_shadow_is_sha_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ret = producer_data(root)
            a = make_shadow_receipt(ret, source_root=root, observed_clock=CLOCK)
            self.assertEqual(a["validation_receipt"]["source_count"], 1)
            self.assertFalse(a["production_promotion_allowed"])
            self.assertIn("receipt_sha256", a)

    def test_NBA_combo_requires_nonmultiplicative_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ret = producer_data(root, "NBA")
            self.assertEqual(
                make_shadow_receipt(ret, source_root=root, observed_clock=CLOCK)["stat"], "pra"
            )
            ret["factorization"] = "nba_false_four_factor_product"
            with self.assertRaisesRegex(SettlementCaptureError, "nba_invalid"):
                make_shadow_receipt(ret, source_root=root, observed_clock=CLOCK)

    def test_stale_or_game_started_cannot_be_preforecast(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ret = producer_data(root)
            ret["event_start"] = "2026-11-11T17:00:00Z"
            with self.assertRaisesRegex(SettlementCaptureError, "not_genuinely_pregame"):
                make_shadow_receipt(ret, source_root=root, observed_clock=CLOCK)

    def test_future_source_receipt_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ret = producer_data(root)
            ret["source_receipts"][0]["retrieved_at"] = "2026-11-11T18:01:00Z"
            with self.assertRaisesRegex(SettlementCaptureError, "factor_future_source"):
                make_shadow_receipt(ret, source_root=root, observed_clock=CLOCK)

    def test_nhl_mean_product_inconsistent_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ret = producer_data(root)
            ret["implied_mean"] = 100
            with self.assertRaisesRegex(SettlementCaptureError, "product_not_coherent"):
                make_shadow_receipt(ret, source_root=root, observed_clock=CLOCK)

    def test_unavailable_factors_cannot_be_synthesized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ret = producer_data(root)
            ret["factors"].pop("individual_share_if_active")
            with self.assertRaisesRegex(SettlementCaptureError, "fields_missing"):
                make_shadow_receipt(ret, source_root=root, observed_clock=CLOCK)

    def test_negative_control_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = build_capture_manifest(
                frozen_bundle(root, full=False),
                source_root=root,
                observed_clock=CLOCK,
                include_negative_control=True,
            )
            nc = manifest["negative_control_receipt"]
            self.assertEqual(nc["expected_status"], STATUS_INVALID)

    def test_non_producer_archive_cannot_authenticate_factors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "one.json").write_text('{"captured_before_forecast": true}\n', encoding="utf-8")
            digest = hashlib.sha256((root / "one.json").read_bytes()).hexdigest()
            factors = {
                "team_unblocked_attempts": 60,
                "probability_active": 0.95,
                "individual_share_if_active": 0.08,
                "on_target_probability": 0.60,
            }
            bundle = {
                "schema": "v25_phase15_frozen_capture_bundle_v1",
                "experiment_id": "EXP-TEST",
                "run_id": RUN_ID,
                "contracts": [
                    {
                        "sport": "NHL",
                        "stat": "shots on goal",
                        "event_id": "pregame-event",
                        "player_id": "123",
                        "game_date": "2026-11-11",
                        "event_start": EVENT,
                        "forecast_at": "2026-11-11T17:30:00Z",
                        "input_freeze_at": "2026-11-11T17:30:00Z",
                        "model_training_cutoff_at": "2026-11-10T00:00:00Z",
                        "model_version": "shadow-study-001",
                        "producer_run_id": RUN_ID,
                        "original_forecast_contract_id": FORECAST_ID,
                        "producer_factors": {
                            "factors": factors,
                            "source_receipts": [
                                {
                                    "archive_path": "one.json",
                                    "sha256": digest,
                                    "retrieved_at": "2026-11-11T17:00:00Z",
                                    "factor_names": list(factors.keys()),
                                }
                            ],
                        },
                    }
                ],
            }
            manifest = build_capture_manifest(bundle, source_root=root, observed_clock=CLOCK)
            rows = manifest["contracts"][0]["factor_rows"]
            self.assertEqual(len(rows), 4)
            self.assertTrue(all(r["status"] == STATUS_INVALID for r in rows))
            self.assertFalse(any(r["status"] == STATUS_AVAILABLE for r in rows))

    def test_valid_producer_archive_binds_all_four_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = build_capture_manifest(frozen_bundle(root), source_root=root, observed_clock=CLOCK)
            rows = manifest["contracts"][0]["factor_rows"]
            self.assertTrue(all(r["status"] == STATUS_AVAILABLE for r in rows))
            self.assertTrue(all("source_to_value_binding" in r for r in rows))

    def test_one_factor_claim_alteration_invalidates_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = frozen_bundle(root)
            bundle["contracts"][0]["producer_factors"]["factors"]["on_target_probability"] = 0.61
            manifest = build_capture_manifest(bundle, source_root=root, observed_clock=CLOCK)
            row = next(
                r for r in manifest["contracts"][0]["factor_rows"]
                if r["factor_name"] == "on_target_probability"
            )
            self.assertEqual(row["status"], STATUS_INVALID)
            self.assertIn("binding_mismatch", row.get("invalid_reason", ""))

    def test_archive_player_id_mismatch_invalidates_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prod = producer_data(root)
            doc = json.loads((root / "one.json").read_text(encoding="utf-8"))
            doc["player_id"] = "wrong-player"
            (root / "one.json").write_text(json.dumps(doc, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            digest = hashlib.sha256((root / "one.json").read_bytes()).hexdigest()
            prod["source_receipts"][0]["sha256"] = digest
            bundle = frozen_bundle(root)
            bundle["contracts"][0]["producer_factors"] = {
                "factors": prod["factors"],
                "source_receipts": prod["source_receipts"],
            }
            manifest = build_capture_manifest(bundle, source_root=root, observed_clock=CLOCK)
            self.assertTrue(
                all(r["status"] == STATUS_INVALID for r in manifest["contracts"][0]["factor_rows"])
            )

    def test_numeric_factors_without_bound_source_not_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prod = producer_data(root)
            bundle = frozen_bundle(root)
            bundle["contracts"][0]["producer_factors"] = {
                "factors": prod["factors"],
                "source_receipts": [],
            }
            manifest = build_capture_manifest(bundle, source_root=root, observed_clock=CLOCK)
            rows = manifest["contracts"][0]["factor_rows"]
            self.assertTrue(all(r["status"] == STATUS_INVALID for r in rows))
            self.assertFalse(any(r["status"] == STATUS_AVAILABLE for r in rows))

    def test_placeholder_source_digest_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = frozen_bundle(root)
            bundle["contracts"][0]["producer_factors"]["source_receipts"][0]["sha256"] = (
                "0" * 64
            )
            manifest = build_capture_manifest(bundle, source_root=root, observed_clock=CLOCK)
            self.assertTrue(
                all(r["status"] == STATUS_INVALID for r in manifest["contracts"][0]["factor_rows"])
            )

    def test_partial_bundle_single_verified_factor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prod = producer_data(root)
            bundle = frozen_bundle(root)
            pf = bundle["contracts"][0]["producer_factors"]
            pf["factors"] = {"team_unblocked_attempts": prod["factors"]["team_unblocked_attempts"]}
            pf["source_receipts"] = [
                {
                    **prod["source_receipts"][0],
                    "factor_names": ["team_unblocked_attempts"],
                }
            ]
            manifest = build_capture_manifest(bundle, source_root=root, observed_clock=CLOCK)
            rows = {r["factor_name"]: r["status"] for r in manifest["contracts"][0]["factor_rows"]}
            self.assertEqual(rows["team_unblocked_attempts"], STATUS_AVAILABLE)
            self.assertEqual(rows["probability_active"], STATUS_UNMEASURED)

    def test_manifest_sha256_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = build_capture_manifest(frozen_bundle(root), source_root=root, observed_clock=CLOCK)
            manifest["manifest_sha256"] = "f" * 64
            with self.assertRaisesRegex(SettlementCaptureError, "manifest_sha256_mismatch"):
                write_capture_manifest(manifest, root / "out")

    def test_idempotent_write_verifies_existing_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "cap"
            manifest = build_capture_manifest(frozen_bundle(root), source_root=root, observed_clock=CLOCK)
            first = write_capture_manifest(manifest, out)
            second = write_capture_manifest(manifest, out)
            self.assertTrue(first["written"])
            self.assertFalse(second["written"])
            self.assertEqual(second["reason"], "identical_capture_exists")

    def test_existing_manifest_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "cap"
            manifest = build_capture_manifest(frozen_bundle(root), source_root=root, observed_clock=CLOCK)
            write_capture_manifest(manifest, out)
            files = list(out.glob("phase15_factor_capture_*.json"))
            doc = json.loads(files[0].read_text(encoding="utf-8"))
            doc["run_id"] = doc["run_id"] + "-tampered"
            files[0].write_text(json.dumps(doc, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(SettlementCaptureError, "existing_manifest_tampered"):
                write_capture_manifest(manifest, out)

    def test_nba_overtime_minutes_within_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ret = producer_data(root, "NBA")
            ret["factors"]["projected_minutes"] = 52
            identity = {
                "event_id": ret["event_id"],
                "player_id": ret["player_id"],
                "model_version": ret["model_version"],
                "input_freeze_at": ret["input_freeze_at"],
                "forecast_at": ret["forecast_at"],
                "model_training_cutoff_at": ret["model_training_cutoff_at"],
                "run_id": ret["producer_run_id"],
                "forecast_id": ret["forecast_id"],
            }
            digest = write_producer_archive(
                root, "one.json", sport="NBA", stat="pra", factors=ret["factors"], identity=identity
            )
            ret["source_receipts"][0]["sha256"] = digest
            manifest = build_capture_manifest(
                {
                    "schema": "v25_phase15_frozen_capture_bundle_v1",
                    "experiment_id": "EXP-TEST",
                    "run_id": RUN_ID,
                    "contracts": [
                        {
                            "sport": "NBA",
                            "stat": "pra",
                            "event_id": "pregame-event",
                            "player_id": "123",
                            "game_date": "2026-11-11",
                            "event_start": EVENT,
                            "forecast_at": ret["forecast_at"],
                            "input_freeze_at": ret["input_freeze_at"],
                            "model_training_cutoff_at": ret["model_training_cutoff_at"],
                            "model_version": ret["model_version"],
                            "producer_run_id": ret["producer_run_id"],
                            "original_forecast_contract_id": ret["forecast_id"],
                            "producer_factors": {
                                "factors": ret["factors"],
                                "source_receipts": ret["source_receipts"],
                            },
                        }
                    ],
                },
                source_root=root,
                observed_clock=CLOCK,
            )
            minutes_row = next(
                r for r in manifest["contracts"][0]["factor_rows"]
                if r["factor_name"] == "projected_minutes"
            )
            self.assertEqual(minutes_row["status"], STATUS_AVAILABLE)

    def test_nba_negative_minutes_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ret = producer_data(root, "NBA")
            ret["factors"]["projected_minutes"] = -1
            identity = {
                "event_id": ret["event_id"],
                "player_id": ret["player_id"],
                "model_version": ret["model_version"],
                "input_freeze_at": ret["input_freeze_at"],
                "forecast_at": ret["forecast_at"],
                "model_training_cutoff_at": ret["model_training_cutoff_at"],
                "run_id": ret["producer_run_id"],
                "forecast_id": ret["forecast_id"],
            }
            digest = write_producer_archive(
                root, "one.json", sport="NBA", stat="pra", factors=ret["factors"], identity=identity
            )
            bundle = frozen_bundle(root, "NBA")
            pf = bundle["contracts"][0]["producer_factors"]
            pf["factors"]["projected_minutes"] = -1
            pf["source_receipts"][0]["sha256"] = digest
            manifest = build_capture_manifest(bundle, source_root=root, observed_clock=CLOCK)
            row = next(
                r for r in manifest["contracts"][0]["factor_rows"]
                if r["factor_name"] == "projected_minutes"
            )
            self.assertEqual(row["status"], STATUS_INVALID)


class JobsIntegrationTests(unittest.TestCase):
    def test_I_integrate_does_not_mutate_evaluated_contracts(self):
        evaluated = [
            {
                "status": "forecast",
                "sport": "NHL",
                "stat": "shots on goal",
                "id": "x",
                "meta": {
                    "event_id": "e1",
                    "player_id": "p1",
                    "event_start": EVENT,
                    "forecast_at": "2026-11-11T17:00:00Z",
                    "input_freeze_at": "2026-11-11T17:00:00Z",
                },
            }
        ]
        before = json.dumps(evaluated, sort_keys=True)
        with tempfile.TemporaryDirectory() as tmp:
            integrate_shadow_factor_capture(
                evaluated,
                run_id="r1",
                output_root=Path(tmp),
                observed_clock=datetime(2026, 11, 11, 18, tzinfo=timezone.utc),
            )
        self.assertEqual(json.dumps(evaluated, sort_keys=True), before)

    def test_J_default_disabled_env_gate(self):
        jobs_path = Path(__file__).resolve().parents[1] / "scripts" / "jobs.py"
        source = jobs_path.read_text(encoding="utf-8")
        self.assertIn("PICKEM_PHASE15_FACTOR_CAPTURE", source)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PICKEM_PHASE15_FACTOR_CAPTURE", None)
            self.assertNotEqual(os.environ.get("PICKEM_PHASE15_FACTOR_CAPTURE"), "1")


if __name__ == "__main__":
    unittest.main()
