"""Adversarial NBA/NHL P0 temporal, identity, distribution and durability tests.

Synthetic records cannot be mislabelled as genuine live captures.
"""
import copy
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

from v2.p0_integrity.contracts import (AdmissionError, record, sha256,
    admit_forecast,admit_settlement,admit_training_update,validate_record,
    reject_duplicate_records,verify_source_bytes)
from v2.p0_integrity import storage
from v2.p0_integrity.compat import (legacy_forecast_reference,
    legacy_source_receipt,nba_pregame_feature_adapter)

CODE="a"*40
ART="b"*64
TRAIN="c"*64
START="2026-11-21T19:00:00Z"
FREEZE="2026-11-21T17:10:00Z"
FORECAST="2026-11-21T17:11:00Z"
AVAIL="2026-11-21T17:00:00Z"
CAPTURE="2026-11-21T17:01:00Z"
CUTOFF="2026-11-21T16:00:00Z"

class CommonContractsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/"original").mkdir()
        (self.root/"original"/"stats.json").write_bytes(b'{"historical":true}')
        self.src=self.source("source-1","original/stats.json",AVAIL,CAPTURE)
        self.features={"past_games":[{"p":22}],"injury_state":"UNKNOWN"}
        self.feature=record("PregameFeatureSnapshot",
            feature_snapshot_id="feature-1",sport="NBA",event_id="event-99",
            team_id="BOS",opponent_id="LAL",player_id="NBA:7",
            stat_key="points",period="full_game",input_freeze_at=FREEZE,
            source_receipt_ids=["source-1"],feature_sha256=sha256(self.features),
            reconstruction_class="original",features=self.features)
        (self.root/"models").mkdir()
        (self.root/"models"/"model.bin").write_bytes(b"frozen model example")
        self.actual_artifact_sha=hashlib.sha256((self.root/"models"/"model.bin").read_bytes()).hexdigest()
        self.model=record("ModelArtifact",model_artifact_id="model-1",
            model_id="nba:S1+O0",model_version="1",model_code_sha=CODE,
            artifact_sha256=self.actual_artifact_sha,artifact_path="models/model.bin",training_data_sha256=TRAIN,
            training_cutoff_at=CUTOFF,created_at="2026-11-21T16:30:00Z",
            training_scope="pre-event",feature_schema_id="P0/1")
        self.distribution={"kind":"discrete","masses":[[0,0.4],[1,0.6]]}
        self.fc=record("ForecastSnapshot",forecast_id="forecast-1",
            run_id="research-run",sport="NBA",league="NBA",season=2026,
            event_id="event-99",team_id="BOS",opponent_id="LAL",
            player_id="NBA:7",stat_key="points",period="full_game",
            event_start_at=START,forecast_at=FORECAST,input_freeze_at=FREEZE,
            model_training_cutoff_at=CUTOFF,feature_snapshot_id="feature-1",
            model_artifact_id="model-1",model_id="nba:S1+O0",
            model_version="1",source_receipt_ids=["source-1"],
            input_sha256=sha256(self.feature),output_sha256=sha256(self.distribution),
            model_code_sha=CODE,artifact_sha256=self.actual_artifact_sha,seed=20261121,
            distribution=self.distribution,uncertainty={"epistemic":0.1,"aleatoric":0.2},
            abstention_reasons=[],admission_class="A",eligible=True,
            quote_id=None,line=None,side=None,market_probability=None)
        self.quote=None

    def source(self,id,path,available,captured):
        return record("SourceReceipt",receipt_id=id,source_id="official:"+id,
            source_kind="historical_stat",source_available_at=available,
            collected_at=captured,
            source_sha256=hashlib.sha256((self.root/path).read_bytes()).hexdigest(),
            archive_path=path,provenance_class="original_publication")

    def b_fixture(self):
        (self.root/"original"/"offer.json").write_bytes(b'{"real_quote":"over 0.5"}')
        quoted=self.source("quote-1","original/offer.json",
            "2026-11-21T17:04:00Z","2026-11-21T17:05:00Z")
        self.quote=record("MarketQuote",quote_id="quote-one",
            contract_id="original-book-contract",event_id="event-99",sport="NBA",
            team_id="BOS",opponent_id="LAL",player_id="NBA:7",
            stat_key="points",period="full_game",quote_timestamp="2026-11-21T17:04:00Z",
            event_start_at=START,book="ExampleBook",product_type="sportsbook_two_sided",
            quote_kind="real",line=0.5,side="over",source_receipt_id="quote-1",
            source_sha256=quoted["source_sha256"],terms={"over_decimal_odds":None,
            "under_decimal_odds":None,"payout":"unknown"},accepted=True,reject_reason=None)
        fc=dict(self.fc,admission_class="B",quote_id="quote-one",line=0.5,
                side="over",source_receipt_ids=["source-1","quote-1"])
        return fc,[self.src,quoted],self.quote

    def assertBlocked(self,func,code):
        with self.assertRaisesRegex(AdmissionError,code):
            func()

    def admit(self,fc=None,feat=None,model=None,sources=None,quote=None):
        return admit_forecast(fc or self.fc,feat or self.feature,model or self.model,
                sources if sources is not None else [self.src],quote,
                source_root=self.root)

    def test_A_no_market_original_distribution_passes(self):
        got=self.admit()
        self.assertEqual(got["admission_class"],"A")
        self.assertFalse(got["production_allowed"])

    def test_B_authentic_quote_no_odds_still_valid_distribution_research(self):
        fc,sources,q=self.b_fixture()
        self.assertEqual(self.admit(fc,sources=sources,quote=q)["admission_class"],"B")
        self.assertIsNone(fc["market_probability"])

    def test_reconstructed_history_not_original(self):
        f=dict(self.feature,reconstruction_class="reconstructed")
        forecast=dict(self.fc,input_sha256=sha256(f))
        self.assertBlocked(lambda:self.admit(fc=forecast,feat=f),"RECONSTRUCTED_MASQUERADES_AS_ORIGINAL")

    def test_reconstructed_C_is_separate(self):
        f=dict(self.feature,reconstruction_class="reconstructed")
        c=dict(self.fc,admission_class="C",input_sha256=sha256(f))
        self.assertEqual(self.admit(c,f)["admission_class"],"C")

    def test_source_future_publication_rejected(self):
        s=dict(self.src,source_available_at="2026-11-21T17:15:00Z",
               collected_at="2026-11-21T17:16:00Z")
        self.assertBlocked(lambda:self.admit(sources=[s]),"FUTURE_SOURCE_LEAKAGE")

    def test_source_collected_after_freeze_rejected(self):
        s=dict(self.src,collected_at="2026-11-21T17:12:00Z")
        self.assertBlocked(lambda:self.admit(sources=[s]),"FUTURE_SOURCE_LEAKAGE")

    def test_content_tamper_rejected(self):
        (self.root/"original"/"stats.json").write_bytes(b"changed")
        self.assertBlocked(self.admit,"SOURCE_CONTENT_CHANGED")

    def test_source_symlink_escape_rejected(self):
        (self.root/"original"/"stats.json").unlink()
        (self.root/"original"/"stats.json").symlink_to("/etc/hosts")
        self.assertBlocked(self.admit,"UNSAFE_SOURCE_SYMLINK")

    def test_without_original_source_archive_no_certification(self):
        self.assertBlocked(lambda:admit_forecast(self.fc,self.feature,self.model,[self.src]),
            "ORIGINAL_SOURCE_BYTES_NOT_REVERIFIED")

    def test_wrong_player_identity_rejected(self):
        f=dict(self.feature,player_id="NBA:9")
        self.assertBlocked(lambda:self.admit(feat=f),"FEATURE_IDENTITY_MISMATCH")

    def test_wrong_event_identity_rejected(self):
        f=dict(self.feature,event_id="other-event")
        self.assertBlocked(lambda:self.admit(feat=f),"FEATURE_IDENTITY_MISMATCH")

    def test_opponent_alias_collision_rejected(self):
        f=dict(self.fc,opponent_id="BOS")
        self.assertBlocked(lambda:validate_record("ForecastSnapshot",f),"SPORT_OR_TEAM")

    def test_model_training_after_freeze_rejected(self):
        f=dict(self.fc,model_training_cutoff_at="2026-11-21T17:20:00Z")
        self.assertBlocked(lambda:validate_record("ForecastSnapshot",f),"FORECAST_TEMPORAL_ORDER")

    def test_model_mismatch_rejected(self):
        m=dict(self.model,artifact_sha256="d"*64)
        self.assertBlocked(lambda:self.admit(model=m),"MODEL_ARTIFACT_IDENTITY_MISMATCH")

    def test_model_created_after_forecast_rejected(self):
        m=dict(self.model,created_at="2026-11-21T17:12:00Z")
        self.assertBlocked(lambda:self.admit(model=m),"MODEL_CREATED_AFTER_FORECAST")

    def test_naive_clock_rejected(self):
        f=dict(self.fc,forecast_at="2026-11-21T17:11:00")
        self.assertBlocked(lambda:validate_record("ForecastSnapshot",f),"TIMESTAMP_MUST_BE_UTC_AWARE")

    def test_timezone_offset_not_utc_rejected(self):
        f=dict(self.fc,forecast_at="2026-11-21T12:11:00-05:00")
        self.assertBlocked(lambda:validate_record("ForecastSnapshot",f),"TIMESTAMP_MUST_BE_UTC_AWARE")

    def test_post_event_forecast_rejected(self):
        f=dict(self.fc,forecast_at="2026-11-21T19:00:00Z")
        self.assertBlocked(lambda:validate_record("ForecastSnapshot",f),"FORECAST_TEMPORAL_ORDER")

    def test_naked_market_probability_rejected(self):
        f=dict(self.fc,market_probability=0.55)
        self.assertBlocked(lambda:validate_record("ForecastSnapshot",f),"A_MUST_BE_MARKET_FREE")

    def test_B_late_quote_rejected(self):
        fc,sources,q=self.b_fixture()
        q=dict(q,quote_timestamp="2026-11-21T17:12:00Z")
        self.assertBlocked(lambda:self.admit(fc,sources=sources,quote=q),"QUOTE_LINE_SIDE_OR_TIME_MISMATCH")

    def test_B_side_changed_rejected(self):
        fc,sources,q=self.b_fixture()
        q=dict(q,side="under")
        self.assertBlocked(lambda:self.admit(fc,sources=sources,quote=q),"QUOTE_LINE_SIDE_OR_TIME_MISMATCH")

    def test_B_wrong_stat_rejected(self):
        fc,sources,q=self.b_fixture()
        q=dict(q,stat_key="rebounds")
        self.assertBlocked(lambda:self.admit(fc,sources=sources,quote=q),"QUOTE_FORECAST_IDENTITY_MISMATCH")

    def test_B_unverified_quote_source_rejected(self):
        fc,sources,q=self.b_fixture()
        q=dict(q,source_sha256="d"*64)
        self.assertBlocked(lambda:self.admit(fc,sources=sources,quote=q),"QUOTE_SOURCE_RECEIPT_MISMATCH")

    def test_B_synthetic_quote_rejected(self):
        fc,sources,q=self.b_fixture()
        q=dict(q,quote_kind="synthetic")
        self.assertBlocked(lambda:self.admit(fc,sources=sources,quote=q),"B_AUTHENTIC_QUOTE_REQUIRED")

    def test_distribution_negative_mass_rejected(self):
        f=dict(self.fc,distribution={"kind":"discrete","masses":[[0,1.1],[1,-0.1]]})
        f["output_sha256"]=sha256(f["distribution"])
        self.assertBlocked(lambda:validate_record("ForecastSnapshot",f),"DISTRIBUTION_MASS_OR_SUPPORT_INVALID")

    def test_distribution_non_normalized_rejected(self):
        f=dict(self.fc,distribution={"kind":"discrete","masses":[[0,0.4],[1,0.4]]})
        f["output_sha256"]=sha256(f["distribution"])
        self.assertBlocked(lambda:validate_record("ForecastSnapshot",f),"DISTRIBUTION_NOT_NORMALIZED")

    def test_distribution_output_tamper_rejected(self):
        f=dict(self.fc,output_sha256="f"*64)
        self.assertBlocked(lambda:validate_record("ForecastSnapshot",f),"OUTPUT_HASH_MISMATCH")

    def test_distribution_simulation_hash_required(self):
        f=dict(self.fc,distribution={"kind":"scenario_ref","count":100,
            "scenario_sha256":"bad","support":"nonnegative_integer"})
        f["output_sha256"]=sha256(f["distribution"])
        self.assertBlocked(lambda:validate_record("ForecastSnapshot",f),"SCENARIO_SHA_INVALID")

    def test_same_game_outcome_feature_forbidden(self):
        f=dict(self.feature,features={"actual_minutes":31})
        f["feature_sha256"]=sha256(f["features"])
        self.assertBlocked(lambda:validate_record("PregameFeatureSnapshot",f),
            "TARGET_GAME_OUTCOME_AS_PREGAME_FEATURE")

    def test_duplicate_forecast_id_rejected(self):
        self.assertBlocked(lambda:reject_duplicate_records([self.fc,self.fc]),"DUPLICATE_RECORD_ID")

    def test_duplicate_forecast_natural_key_rejected(self):
        f=dict(self.fc,forecast_id="other")
        self.assertBlocked(lambda:reject_duplicate_records([self.fc,f]),"DUPLICATE_FORECAST_NATURAL_KEY")

    def test_DNP_not_zero(self):
        o=self.outcome()
        o=dict(o,participation="DNP",actual_value=0)
        self.assertBlocked(lambda:validate_record("OutcomeRecord",o),"DNP_IS_NOT_ZERO")

    def outcome(self):
        return record("OutcomeRecord",outcome_id="out-1",sport="NBA",
            event_id="event-99",team_id="BOS",player_id="NBA:7",
            stat_key="points",period="full_game",
            official_result_available_at="2026-11-21T22:00:00Z",
            official_source_receipt_id="official-1",
            official_source_sha256="e"*64,
            actual_value=1,participation="PLAYED",result_version=1,status="FINAL")

    def settlement(self):
        return record("SettlementRecord",settlement_id="settle-1",
            forecast_id="forecast-1",outcome_id="out-1",quote_id=None,
            contract_id=None,settled_at="2026-11-21T22:30:00Z",
            disposition="SCORED",settlement_policy="full_game",
            settlement_version=1,supersedes_id=None,
            source_receipt_ids=["official-1"],computation_sha256="9"*64)

    def test_valid_A_postgame_score(self):
        a=admit_settlement(self.settlement(),self.fc,self.outcome())
        self.assertEqual(a["status"],"SETTLEMENT_ADMITTED_RESEARCH_ONLY")

    def test_official_outcome_after_settlement_rejected(self):
        o=dict(self.outcome(),official_result_available_at="2026-11-21T23:00:00Z")
        self.assertBlocked(lambda:admit_settlement(self.settlement(),self.fc,o),
            "OUTCOME_NOT_AVAILABLE_FOR_SETTLEMENT")

    def test_wrong_settlement_player_rejected(self):
        o=dict(self.outcome(),player_id="NBA:999")
        self.assertBlocked(lambda:admit_settlement(self.settlement(),self.fc,o),
            "OUTCOME_IDENTITY_MISMATCH")

    def test_training_uses_only_settled_past(self):
        update=record("TrainingUpdateReceipt",training_state_id="tr-1",
            sport="NBA",model_id="nba:S1+O0",prior_artifact_sha256=ART,
            new_artifact_sha256="d"*64,observation_cutoff_at="2026-11-22T00:00:00Z",
            updated_at="2026-11-22T00:30:00Z",
            settlement_ids=["settle-1"],source_receipt_ids=["official-1"],
            model_code_sha=CODE,state_sha256="1"*64,update_mode="shadow_incremental")
        self.assertEqual(admit_training_update(update,[self.settlement()])["status"],
                         "RESEARCH_TRAINING_RECEIPT_ADMITTED")
        early=dict(update,observation_cutoff_at="2026-11-21T21:00:00Z")
        self.assertBlocked(lambda:admit_training_update(early,[self.settlement()]),
            "TRAINING_USES_UNRELEASED_SETTLEMENT")


    def test_model_actual_artifact_bytes_tampered(self):
        (self.root/"models"/"model.bin").write_bytes(b"frozen model changed")
        self.assertBlocked(self.admit,"MODEL_ARTIFACT_BYTES_CHANGED")

    def test_model_artifact_symlink_attack(self):
        (self.root/"models"/"model.bin").unlink()
        (self.root/"models"/"model.bin").symlink_to("/etc/hosts")
        self.assertBlocked(self.admit,"UNSAFE_MODEL_ARTIFACT_PATH")

    def test_missing_event_id_rejected(self):
        f=dict(self.fc,event_id=None)
        self.assertBlocked(lambda:validate_record("ForecastSnapshot",f),"INVALID_ID:event_id")

    def test_missing_player_id_rejected(self):
        f=dict(self.fc,player_id=None)
        self.assertBlocked(lambda:validate_record("ForecastSnapshot",f),"INVALID_ID:player_id")

    def test_missing_model_artifact_path_rejected(self):
        m=dict(self.model,artifact_path=None)
        self.assertBlocked(lambda:validate_record("ModelArtifact",m),"UNSAFE_ARCHIVE_PATH")

    def test_legacy_forecast_never_promoted(self):
        ref=legacy_forecast_reference({"forecast_id":"old","event_id":"old-event",
                                       "model":"legacy-60-40"})
        self.assertFalse(ref["may_promote_to_original"])

    def test_legacy_receipt_conservatively_uses_possession_clock(self):
        raw={"source_id":"old-official","first_available_at":AVAIL,
             "retrieved_at":CAPTURE,"content_sha256":self.src["source_sha256"],
             "archive_path":"original/stats.json","source_kind":"provider_publication"}
        adapted=legacy_source_receipt(raw)
        self.assertEqual(adapted["source_available_at"],CAPTURE)
        self.assertEqual(adapted["provenance_class"],"collector_possession")

    def test_nba_subset_needs_explicit_reconstruction_class(self):
        self.assertBlocked(lambda:nba_pregame_feature_adapter({},reconstruction_class="assumed"),
            "MISSING_EXPLICIT_NBA_RECONSTRUCTION_CLASS")

class StorageTests(unittest.TestCase):
    def test_actual_cross_run_proof_in_deepnote(self):
        if not Path("/work/research/p0_integration_integrity/probe_20261121").exists():
            self.skipTest("Real Deepnote project proof not present in local test environment")
        result=storage.attest_project_storage("/work")
        self.assertEqual(result["status"],"STORAGE_ATTESTED_FOR_PROJECT_PATH")

    def test_tmp_rejected(self):
        self.assertBlocked(lambda:storage.attest_project_storage("/tmp"),
                           "UNAPPROVED_LOGICAL_ROOT")
    def assertBlocked(self,fn,code):
        with self.assertRaisesRegex(AdmissionError,code):fn()

    def test_wrong_project_rejected(self):
        self.assertBlocked(lambda:storage.attest_project_storage("/work",
                           project_id="wrong"),"WRONG_DEEPNOTE_PROJECT_ID")

    def test_unsafe_parent_rejected(self):
        self.assertBlocked(lambda:storage.attest_project_storage("/work/../tmp"),
                           "UNAPPROVED_LOGICAL_PATH")

    def test_malicious_symlink_rejected(self):
        if not Path("/work").exists():self.skipTest("Deepnote only")
        name=Path("/work/research/p0_integration_integrity/test_symlink_forbidden")
        try:
            name.symlink_to("/tmp",target_is_directory=True)
            self.assertBlocked(lambda:storage.attest_project_storage(name),
                               "UNSAFE_NESTED_SYMLINK")
        finally:
            name.unlink(missing_ok=True)

if __name__=="__main__":
    unittest.main()
