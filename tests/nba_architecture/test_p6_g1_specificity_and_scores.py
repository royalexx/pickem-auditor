"""P6 QA-only exact-error adversarial controls and independent score semantics.

Applies to the unapproved v2.0.0 G0 repair candidate. Does not alter models,
implement a C optimizer, or assert historical predictive performance.
"""
import copy
import hashlib
import math
import unittest

from golden_v2 import pregame, j_scenarios, marginal_from_joint, distribution, receipt
from v2.nba_architecture.v2_contracts import (
    VERSION, ContractError, canonical, seal, validate_pregame, validate_scenarios,
    validate_distribution, validate_evaluation, threshold_triplet, seed_for,
)


def mutate_and_seal(src, fn):
    out = copy.deepcopy(src)
    out.pop("content_hash")
    fn(out)
    return seal(out)


class ExactBoundaryRejections(unittest.TestCase):
    """Assert the *specific* failure rather than any incidental schema error."""

    def reject_code(self, code, callback, *args):
        with self.assertRaises(ContractError) as caught:
            callback(*args)
        self.assertEqual(caught.exception.code, code)

    def test_future_game_result_flag_rejected(self):
        p = pregame("original_prospective")
        altered = mutate_and_seal(
            p, lambda x: x["features"][0].update(target_game_outcome=True))
        self.reject_code("TARGET_GAME_FEATURE_LEAK", validate_pregame, altered)

    def test_actual_minutes_alias_not_accepted_as_pregame_feature(self):
        p = pregame("original_prospective")
        altered = mutate_and_seal(
            p, lambda x: x["features"][0].update(name="actual_minutes"))
        self.reject_code("FEATURE_NAME_LEAKAGE", validate_pregame, altered)

    def test_late_source_feature_timestamp(self):
        p = pregame("original_prospective")
        altered = mutate_and_seal(
            p, lambda x: x["features"][0].update(available_at=x["event_start_at"]))
        self.reject_code("FUTURE_FEATURE", validate_pregame, altered)

    def test_missing_source_receipt_list(self):
        p = pregame("original_prospective")
        altered = mutate_and_seal(p, lambda x: x.update(sources=[]))
        self.reject_code("SOURCE_RECEIPTS_REQUIRED", validate_pregame, altered)

    def test_corrupt_raw_source_receipt_sha_chain(self):
        p = pregame("original_prospective")
        altered = mutate_and_seal(
            p, lambda x: x["sources"][0].update(raw_sha256="f" * 64))
        self.reject_code("RECEIPT_HASH_MISMATCH", validate_pregame, altered)

    def test_orphan_source_revision_exactly_rejected(self):
        p = pregame("original_prospective")
        def modify(x):
            original = x["sources"][0]
            body = {k: v for k, v in original.items() if k != "receipt_sha256"}
            body.update(source_revision=2, supersedes_receipt_sha256="d" * 64)
            x["sources"][0] = receipt(body)
            x["features"][0]["source_receipt_sha256"] = x["sources"][0]["receipt_sha256"]
        altered = mutate_and_seal(p, modify)
        self.reject_code("MISSING_SOURCE_PREDECESSOR", validate_pregame, altered)

    def test_same_player_on_both_teams(self):
        p = pregame()
        altered = mutate_and_seal(
            p, lambda x: x["players"][7].update(
                player_id=x["players"][0]["player_id"]))
        self.reject_code("DUPLICATE_PLAYER", validate_pregame, altered)

    def test_evidence_bound_out_player_never_played(self):
        p = pregame("original_prospective")
        def mark_out(x):
            player = x["players"][0]
            player["availability"] = "out"
            player["availability_evidence"] = {
                "source_receipt_sha256": x["sources"][0]["receipt_sha256"],
                "player_id": player["player_id"], "game_id": x["game_id"],
                "field": "availability", "value": "out",
            }
        frozen = mutate_and_seal(p, mark_out)
        self.assertTrue(validate_pregame(frozen),
                        "Verify our adversarial pregame is valid before testing J")
        j = j_scenarios(frozen)
        self.reject_code("EXCLUDED_PARTICIPATION",
                         validate_scenarios, j, frozen)

    def test_joint_distribution_requires_real_scenario_context(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        d = marginal_from_joint(j, p, p["players"][0]["player_id"],
                                "points", "2026-11-16T23:03:00Z", 42)
        self.assertTrue(validate_distribution(d, p, j))
        self.reject_code("J_SCENARIO_CONTEXT_REQUIRED",
                         validate_distribution, d, p)

    def test_joint_pmf_reweighting_rejected_from_actual_draws(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        d = marginal_from_joint(j, p, p["players"][0]["player_id"],
                                "points", "2026-11-16T23:03:00Z", 42)
        forged = mutate_and_seal(
            d, lambda x: [x["pmf"][0].update(mass=0.6),
                          x["pmf"][1].update(mass=0.4)])
        self.reject_code("J_MARGINAL_NOT_FROM_DRAWS",
                         validate_distribution, forged, p, j)

    def test_duplicate_scenario_id_rejected_before_witness(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        malformed = mutate_and_seal(
            j, lambda x: x["scenarios"][1].update(
                scenario_id=x["scenarios"][0]["scenario_id"]))
        self.reject_code("DUPLICATE_SCENARIO",
                         validate_scenarios, malformed, p)

    def test_dnp_with_settled_positive_count_exact_rejection(self):
        p = pregame("original_prospective")
        d = distribution(p)
        evaluation = seal({
            "schema": VERSION, "kind": "evaluation",
            "distribution_sha256": d["content_hash"], "offer_view_sha256": None,
            "status": "settled", "actual": 12, "revision": 1,
            "supersedes_evaluation_sha256": None,
            "official_source_sha256": "a" * 64,
            "participation": "DNP", "void_basis": None, "contract_line": None,
            "game_id": d["game_id"], "event_start_at": d["event_start_at"],
            "evaluated_at": "2026-11-17T03:00:00Z",
        })
        self.reject_code("DNP_CANNOT_HAVE_SETTLED_COUNT",
                         validate_evaluation, evaluation, d)

    def test_cross_seed_and_scenario_identity_reproducibility(self):
        x = seed_for(42, "espn:game:synthetic", "draw:1", "j:1")
        self.assertEqual(x, seed_for(42, "espn:game:synthetic", "draw:1", "j:1"))
        self.assertNotEqual(x, seed_for(42, "espn:game:synthetic", "draw:2", "j:1"))
        self.assertNotEqual(x, seed_for(43, "espn:game:synthetic", "draw:1", "j:1"))

    def test_independently_hashed_snapshot_bytes(self):
        p = pregame()
        body = {k: v for k, v in p.items() if k != "content_hash"}
        self.assertEqual(p["content_hash"], hashlib.sha256(canonical(body)).hexdigest())


class IndependentProperScoreSemantics(unittest.TestCase):
    """C owners must distinguish point-forecast MAE/RMSE from sampled squared loss."""

    def test_poisson_1_zero_point_rmse_differs_from_expected_draw_loss(self):
        mu, variance, actual = 1., 1., 0.
        point_mae = abs(mu-actual)
        single_point_rmse = math.sqrt((mu-actual)**2)
        expected_predictive_draw_rmse = math.sqrt(variance+(mu-actual)**2)
        self.assertEqual(point_mae, 1.)
        self.assertEqual(single_point_rmse, 1.)
        self.assertAlmostEqual(expected_predictive_draw_rmse, math.sqrt(2))
        self.assertNotEqual(single_point_rmse, expected_predictive_draw_rmse)

    def test_nb_2_half_zero_point_rmse_differs_from_draw_loss(self):
        r, success_p, actual = 2., .5, 0.
        mu = r*(1-success_p)/success_p
        variance = r*(1-success_p)/(success_p**2)
        self.assertEqual(mu, 2.)
        self.assertEqual(variance, 4.)
        self.assertEqual(abs(mu-actual), 2.)
        self.assertEqual(math.sqrt((mu-actual)**2), 2.)
        self.assertAlmostEqual(math.sqrt(variance+(mu-actual)**2), math.sqrt(8))
        self.assertAlmostEqual(-math.log(success_p**r), math.log(4))

    def test_multi_game_point_rmse_aggregates_observation_errors(self):
        predicted_means = [1., 3., 4.]
        outcomes = [0, 4, 1]
        residuals = [p-y for p, y in zip(predicted_means, outcomes)]
        self.assertAlmostEqual(sum(map(abs, residuals))/3, 5/3)
        self.assertAlmostEqual(math.sqrt(sum(x*x for x in residuals)/3),
                               math.sqrt(11/3))
        self.assertAlmostEqual(sum(residuals)/3, 1.)

    def test_ten_thousand_simulations_are_not_ten_thousand_games(self):
        samples = [{"game": g, "date": f"2026-11-{16+g}", "path": i}
                   for g in range(2) for i in range(5000)]
        self.assertEqual(len(samples), 10000)
        self.assertEqual(len({(r["game"], r["date"]) for r in samples}), 2)
        # A future actual C optimizer must resample at the game/date level.

    def test_no_stage_as_independent_voter(self):
        stages = {"S", "O", "J"}
        legal_complete_pipeline_ids = {"S_ONLY", "S_O", "S_O_J"}
        self.assertTrue(stages.isdisjoint(legal_complete_pipeline_ids))
        self.assertEqual(len(legal_complete_pipeline_ids), 3)
        # This is a schema/reference control, NOT validation of a C optimizer.


if __name__ == "__main__":
    unittest.main()
