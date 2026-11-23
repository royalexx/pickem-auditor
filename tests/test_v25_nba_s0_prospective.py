"""Synthetic adversarial tests only; never a certified original capture."""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib
import unittest

from v2.p0_integrity.contracts import record, sha256
from research.v25_remediation import nba_s0_prospective as s0
from research.nba_p3_frozen.engine import create_research_model


class PredeclaredMethodTests(unittest.TestCase):
    def setUp(self):
        self.code="a"*40
        self.at="2026-11-22T17:00:00Z"
        self.spec=s0._method_spec(self.code,self.at)

    def test_s0_is_predeclared_prediction_only_not_fitted_or_joint(self):
        payload,model=s0._expected_model(self.spec)
        self.assertEqual(payload["family"],"S0")
        self.assertEqual(payload["training_cutoff_at"],self.at)
        self.assertEqual(self.spec["training"],"PREDICTION_ONLY_NO_PRIOR_FIT")
        self.assertIsNone(self.spec["participation_probability"] if
                          self.spec["participation_probability"] is None else None)
        self.assertEqual(self.spec["participation_probability"],"UNKNOWN_NOT_ESTIMATED")
        self.assertEqual(payload["update_policy"],"PREDICTION_ONLY")
        self.assertEqual(payload["priors_per_minute"],{})
        self.assertEqual(payload["opportunity"],{})
        self.assertEqual(model["model_code_sha"],self.code)
        self.assertEqual(payload["training_reference_sha256"],sha256(self.spec))
        self.assertEqual(model["training_scope"],
                         "PREDICTION_ONLY_NO_FITTING_METHOD_REFERENCE")

    def test_real_p3_model_api_accepts_method_without_external_training_claim(self):
        payload,expected=s0._expected_model(self.spec)
        with TemporaryDirectory() as root:
            got=create_research_model(payload,source_root=root,
                model_code_sha=self.code,created_at=self.at,persist=False)
            self.assertEqual(got["record"]["artifact_sha256"],expected["artifact_sha256"])
            self.assertEqual(got["record"]["artifact_path"],expected["artifact_path"])
            self.assertNotEqual(got["record"]["training_scope"],expected["training_scope"])
            self.assertFalse(got["persisted"])
            self.assertEqual(hashlib.sha256(
                (Path(root)/expected["artifact_path"]).read_bytes()).hexdigest(),
                expected["artifact_sha256"])

    def test_model_protocol_wrong_commit_and_naive_date_rejected(self):
        with self.assertRaisesRegex(s0.IntegrationBlocked,"UNPINNED"):
            s0._method_spec("a"*39,self.at)
        with self.assertRaises(ValueError):
            s0._method_spec(self.code,"2026-11-22T17:00:00")

    def test_prepare_never_counts_as_actual_training(self):
        self.assertFalse(self.spec["training"]=="INCREMENTAL_UPDATE")
        self.assertFalse(self.spec["training"]=="FULL_REFIT")


class OriginalHandoffContractTests(unittest.TestCase):
    def setUp(self):
        self.at="2026-11-22T19:20:00Z"
        self.start="2026-11-22T20:30:00Z"
        self.src=record("SourceReceipt",
           receipt_id="nba-source-1",
           source_id="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=100",
           source_kind="retrospective_retrieval",
           source_available_at=self.at,collected_at=self.at,
           source_sha256="a"*64,
           archive_path="research/nba_p1_original/dev_v1/source_bytes/test.raw",
           provenance_class="collector_possession")
        self.feature=record("PregameFeatureSnapshot",
            feature_snapshot_id="nba-feature-1",sport="NBA",
            event_id="espn:game:200",team_id="espn:team:1",
            opponent_id="espn:team:2",player_id="espn:player:99",
            stat_key="points",period="full",input_freeze_at=self.at,
            source_receipt_ids=[self.src["receipt_id"]],
            feature_sha256=sha256({"candidate_kind":"SOURCE_LISTED_SUBSET",
                "interface_version":"PA-NBA-P1/1",
                "reconstruction_note":"AUTHENTIC_SAME_DAY_POSSESSION",
                "participation_probability":None,
                "legal_eligibility":"UNVERIFIED"}),
            reconstruction_class="original",
            features={"candidate_kind":"SOURCE_LISTED_SUBSET",
                "interface_version":"PA-NBA-P1/1",
                "reconstruction_note":"AUTHENTIC_SAME_DAY_POSSESSION",
                "participation_probability":None,
                "legal_eligibility":"UNVERIFIED"})
        self.bundle={
          "summary":{"reconstruction_class":"original",
              "research_profile":"source_listed_subset",
              "input_freeze_at":self.at,"event_start_at":self.start,
              "sources":[{"p0_sha256":"f"*64}]},
          "features":[self.feature]
        }

    def verify(self,src):
        with patch.object(s0,"verify_dev_p0_record",return_value=src),\
             patch.object(s0,"verify_source_bytes",return_value=True):
            return s0._verify_raw_handoff(self.bundle)

    def test_collector_possession_of_prior_completed_games_is_admissible(self):
        got=self.verify(self.src)
        self.assertEqual(set(got),{"nba-source-1"})

    def test_fixture_or_unqualified_historical_source_rejected(self):
        for bad in (
          dict(self.src,source_kind="fixture"),
          dict(self.src,provenance_class="original_publication"),
          dict(self.src,source_id="https://unverified.example.org/data"),
          dict(self.src,collected_at="2026-11-22T21:00:00Z"),
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(s0.IntegrationBlocked):
                    self.verify(bad)

    def test_player_participation_is_never_imputed_as_certain(self):
        bad=dict(self.feature)
        bad["features"]={**bad["features"],"participation_probability":1.0}
        self.bundle["features"]=[bad]
        with self.assertRaisesRegex(s0.IntegrationBlocked,
                                    "P1_PARTICIPATION_OR_SOURCE_PROFILE_CHANGED"):
            self.verify(self.src)

    def test_prestart_cutoff_and_original_label_required(self):
        self.bundle["summary"]["event_start_at"]="2026-11-22T18:00:00Z"
        with self.assertRaisesRegex(s0.IntegrationBlocked,"PREGAME_SOURCE_REQUIRED"):
            self.verify(self.src)
        self.bundle["summary"]["event_start_at"]=self.start
        self.bundle["summary"]["reconstruction_class"]="reconstructed"
        with self.assertRaisesRegex(s0.IntegrationBlocked,
                                    "P1_ORIGINAL_SOURCE_LISTED_PROFILE_REQUIRED"):
            self.verify(self.src)


class NoRetroactiveForecastTests(unittest.TestCase):
    def test_event_started_blocks_before_any_canonical_write(self):
        with patch.object(s0,"attest_project_storage",return_value=True),\
             patch.object(s0,"load_handoff",return_value={
                 "summary":{"event_start_at":"2026-11-22T19:00:00Z",
                            "input_freeze_at":"2026-11-22T18:00:00Z"},
                 "features":[]}),\
             patch.object(s0,"_verify_raw_handoff",return_value={}),\
             patch.object(s0,"load_predeclared_model",return_value={"artifact_sha256":"a"*64}),\
             patch.object(s0,"append_immutable") as storage:
            with self.assertRaisesRegex(s0.IntegrationBlocked,
                                        "EVENT_STARTED_NO_RETROACTIVE_FREEZE"):
                s0.freeze_handoff(
                    handoff_relpath=("research/nba_p1_original/dev_v1/handoffs/"
                                     +"f"*64+".json"),
                    code_commit="a"*40,run_id="TEST",
                    clock=lambda:datetime(2026,11,22,20,tzinfo=timezone.utc))
            storage.assert_not_called()


if __name__=="__main__":
    unittest.main()
