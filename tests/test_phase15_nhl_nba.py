"""Adversarial, source-bound NHL/NBA Phase 1.5 diagnostic invariants."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT/"tests"))

from test_v25_nhl_nba_phase1 import fixture
from v2.contracts import ContractError
from v2.nhl_nba_phase1 import run_phase1
from v2.phase15_nhl_nba import diagnose, digest


def make_source(*, settled=False):
    temp=tempfile.TemporaryDirectory()
    root=Path(temp.name)
    packet,attempts=fixture(root)
    kwargs={}
    if settled:
        folder=root/"official"
        folder.mkdir()
        original=b'{"provider":"nhl","game":"event-1","shots_on_goal":5}'
        (folder/"game.json").write_bytes(original)
        kwargs["settlement_archive_root"]=folder
        kwargs["settlement_rows"]=[{
            "sport":"NHL","event_id":"event-1","player_id":"8470001",
            "stat":"shots on goal","period":"full","status":"settled",
            "actual":5,"settled_at":"2026-11-09T21:00:00Z",
            "retrieved_at":"2026-11-09T21:01:00Z",
            "source_url":"https://api-web.nhle.com/v1/gamecenter",
            "source_sha256":hashlib.sha256(original).hexdigest(),
            "source_archive_path":"game.json",
        }]
    receipt=run_phase1(packet,attempts,archive_root=root/"replay",
            bundle_sha256="a"*64,code_commit="a"*40,**kwargs)
    return temp,receipt


def seal(source):
    source["report_sha256"]=digest(
        {k:v for k,v in source.items() if k!="report_sha256"})
    return source


class Phase15NhlNbaRegression(unittest.TestCase):
    def test_accepted_pending_real_baselines_not_an_accuracy_claim(self):
        temp,source=make_source()
        with temp:
            r=diagnose(source)
            self.assertEqual(r["actual_scored_contracts"],0)
            self.assertIsNone(r["cohorts"]["ALL"]["forecasts"][
                "naive_recent_exposure_rate"]["empirical_scores"]["brier"])
            self.assertIsNone(r["cohorts"]["ALL"]["comparisons"][
                "naive_recent_exposure_rate"]["model_vs_market_brier_difference"])
            self.assertEqual(r["gates"]["B_directional_accuracy"]["status"],
                             "BLOCKED_NO_GENUINE_POSTGAME_SETTLEMENT")
            self.assertFalse(r["tier1_tier2_publication_allowed"])
            self.assertEqual(r["investment_decision"],
                "DEFER_PHASE2_AND_HEAVY_COMPUTE_CONTINUE_CAPTURE_AND_SIMPLE_SHADOW")

    def test_identical_source_is_byte_deterministic(self):
        temp,source=make_source()
        with temp:
            self.assertEqual(digest(diagnose(source)),digest(diagnose(source)))

    def test_invalid_source_hash_never_silently_repaired(self):
        temp,source=make_source()
        with temp:
            source["contracts"][0]["models"]["naive_recent_exposure_rate"][
                "p_over_nonpush"]=.99
            with self.assertRaisesRegex(ContractError,"tampered_phase1_receipt_digest"):
                diagnose(source)

    def test_resealing_invalid_probability_fails(self):
        temp,source=make_source()
        with temp:
            source["contracts"][0]["models"]["naive_recent_exposure_rate"][
                "p_over_nonpush"]=1.1
            seal(source)
            with self.assertRaisesRegex(ContractError,"invalid_probability"):
                diagnose(source)

    def test_resealing_threeway_inconsistent_probs_fails(self):
        temp,source=make_source()
        with temp:
            source["contracts"][0]["models"]["naive_recent_exposure_rate"][
                "q_push"]=.5
            seal(source)
            with self.assertRaisesRegex(ContractError,"distribution_probabilities_not_normalized"):
                diagnose(source)

    def test_mismatched_rejected_attempts_fails(self):
        temp,source=make_source()
        with temp:
            source["prepared_attempt_statuses"]["forecast"]=1
            seal(source)
            with self.assertRaisesRegex(ContractError,"attempted_universe_denominator"):
                diagnose(source)

    def test_forged_original_final_publication_flags_fail(self):
        temp,source=make_source()
        with temp:
            source["contracts"][0]["models"]["naive_recent_exposure_rate"][
                "originally_published_forecast"]=True
            seal(source)
            with self.assertRaisesRegex(ContractError,"counterfactual_mislabeled_original"):
                diagnose(source)

    def test_missing_model_column_is_not_backfilled(self):
        temp,source=make_source()
        with temp:
            source["contracts"][0]["models"].pop("NUTS")
            seal(source)
            with self.assertRaisesRegex(ContractError,"phase15_model_columns_missing"):
                diagnose(source)

    def test_duplicate_exact_contract_is_detected(self):
        temp,source=make_source()
        with temp:
            source["contracts"].append(deepcopy(source["contracts"][0]))
            source["retained_paired_contracts"]=2
            source["original_forecast_rows"]=4
            source["prepared_attempt_count"]=4
            source["prepared_attempt_statuses"]={"forecast":4,"unavailable":0}
            seal(source)
            with self.assertRaisesRegex(ContractError,"duplicate_phase15_exact_contract"):
                diagnose(source)

    def test_nonpregame_original_freeze_rejected_even_if_resealed(self):
        temp,source=make_source()
        with temp:
            source["contracts"][0]["input_freeze_at"]="2026-11-09T23:00:00Z"
            seal(source)
            with self.assertRaisesRegex(ContractError,"nonpregame_phase15_freeze"):
                diagnose(source)

    def test_official_settled_scoring_matches_phase1_on_exact_contract(self):
        temp,source=make_source(settled=True)
        with temp:
            r=diagnose(source)
            self.assertEqual(r["actual_scored_contracts"],1)
            self.assertEqual(r["cohorts"]["NHL"]["forecasts"][
                "real_no_vig_market"]["empirical_scores"]["n"],1)
            diff=r["cohorts"]["ALL"]["comparisons"][
                "naive_recent_exposure_rate"]
            self.assertEqual(diff["matched_scored_contracts"],1)
            self.assertIsNotNone(diff["model_vs_market_brier_difference"])
            self.assertFalse(r["tier1_tier2_publication_allowed"])

    def test_resealing_inconsistent_observed_outcome_fails(self):
        temp,source=make_source(settled=True)
        with temp:
            source["contracts"][0]["outcome"]["actual"]=0
            seal(source)
            with self.assertRaisesRegex(ContractError,"settlement_semantics_or_time_mismatch"):
                diagnose(source)

    def test_resealing_changed_score_requires_phase1_matching(self):
        temp,source=make_source(settled=True)
        with temp:
            source["models"]["real_no_vig_market"]["brier"]=.999
            seal(source)
            with self.assertRaisesRegex(ContractError,"phase1_vs_phase15_score_disagreement"):
                diagnose(source)

    def test_promotion_mutation_fails_even_if_resealed(self):
        temp,source=make_source()
        with temp:
            source["tier1_tier2_publication_allowed"]=True
            seal(source)
            with self.assertRaisesRegex(ContractError,"phase1_promotion_flag_must_be_false"):
                diagnose(source)


if __name__=="__main__":
    unittest.main()
