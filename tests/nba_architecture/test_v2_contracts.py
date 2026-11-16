"""P0R v2.0.0 contract/fixture tests. No historical predictive scoring."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from golden_v2 import (golden_cases, pregame, distribution, original_offer,
                       j_scenarios, game_state, opportunity, source, players,
                       H, P_FREEZE, P_EVENT)
from v2.nba_architecture.v2_contracts import (
    VERSION, ContractError, seal, receipt, verify, freeze_once,
    validate_pregame, validate_distribution, validate_scenarios,
    validate_offer, validate_offer_view, validate_evaluation,
    marginal_from_joint, threshold_triplet, offer_view, seed_for,
)


def edited(obj, fn):
    o = copy.deepcopy(obj)
    o.pop("content_hash")
    fn(o)
    return seal(o)


def reissue(r, **change):
    x = copy.deepcopy(r)
    x.pop("receipt_sha256")
    x.update(change)
    return receipt(x)


def evaluation(d, offer=None, *, status="settled", actual=2, revision=1,
               previous=None, participation="PLAYED", line=None):
    return seal({
        "schema": VERSION, "kind": "evaluation",
        "distribution_sha256": d["content_hash"],
        "offer_view_sha256": offer["content_hash"] if offer else None,
        "status": status, "actual": actual, "revision": revision,
        "supersedes_evaluation_sha256": previous,
        "official_source_sha256": H if status in ("settled","push") else None,
        "participation": participation, "void_basis":
            "source:original_terms" if status == "void" else None,
        "contract_line": line,
        "game_id": d["game_id"], "event_start_at": d["event_start_at"],
        "evaluated_at": "2026-11-17T03:00:00Z",
    })


class V2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.goldens = golden_cases()

    def failcode(self, code, fn, *a):
        with self.assertRaises(ContractError) as c:
            fn(*a)
        self.assertEqual(c.exception.code, code)

    def test_four_primitive_stats_offer_free(self):
        x = self.goldens["historical_offer_free"]
        self.assertEqual(set(x["four_stats"]),
                         {"points","rebounds","assists","threes"})
        for stat, law in x["four_stats"].items():
            self.assertEqual(law["stat"], stat)
            self.assertTrue(validate_distribution(law, x["pregame"]))
            self.assertIsNone(law["scenario_bundle_sha256"])

    def test_adversarial_hidden_actual_feature(self):
        p = pregame()
        self.failcode("UNEXPECTED_FIELDS", validate_pregame,
            edited(p, lambda x: x["features"][0].update(actual_minutes=30)))

    def test_adversarial_source_receipt_join(self):
        p = pregame()
        self.failcode("FEATURE_REVISION_UNBOUND", validate_pregame,
            edited(p, lambda x: x["features"][0].update(
                source_receipt_sha256="f"*64)))

    def test_prospective_late_publication_claim(self):
        p = pregame("original_prospective")
        def m(x):
            x["sources"][0] = reissue(x["sources"][0],
                provider_published_at=P_EVENT,
                publication_evidence="source_header_claim")
            x["features"][0]["source_receipt_sha256"] = x["sources"][0]["receipt_sha256"]
        self.failcode("PUBLICATION_CLAIM_AFTER_FREEZE",
                      validate_pregame, edited(p, m))

    def test_j_marginal_crosschecked_against_scenarios(self):
        x = self.goldens["joint_same_draw"]
        self.assertTrue(validate_distribution(x["points"], x["pregame"],
                                              x["scenarios"]))

    def test_j_marginal_cannot_swap_weights(self):
        x = self.goldens["joint_same_draw"]
        d = edited(x["points"], lambda y: y["pmf"][0].update(mass=.6))
        self.failcode("PMF_NOT_NORMALIZED", validate_distribution, d,
                      x["pregame"], x["scenarios"])

    def test_source_revision_backdating_rejected(self):
        p = pregame()
        def m(x):
            prior = x["sources"][0]
            x["sources"].append(reissue(prior, source_revision=2,
                supersedes_receipt_sha256=prior["receipt_sha256"],
                collector_observed_at="2025-01-01T00:00:00Z"))
        self.failcode("BACKDATED_SOURCE_CORRECTION", validate_pregame, edited(p,m))

    def test_optional_g_cannot_use_future_fit(self):
        p = pregame()
        d = distribution(p, mode="S_O")
        d = edited(d, lambda x: x["lineage"].update(G={
            "model_id": "research:G:v2", "version":"v2.fixture",
            "artifact_sha256": H, "code_sha256": H,
            "training_cutoff_at": P_EVENT}))
        self.failcode("FUTURE_OPTIONAL_GAME_STATE", validate_distribution, d, p)

    def test_offer_observation_must_match_receipt(self):
        p = pregame("original_prospective", with_offer=True)
        q = original_offer(p)
        self.failcode("QUOTE_OBSERVATION_NOT_RECEIPT", validate_offer,
            edited(q, lambda x: x.update(observed_at=P_FREEZE)), p)

    def test_quote_cannot_be_timestamped_after_observation(self):
        p = pregame("original_prospective", with_offer=True)
        q = original_offer(p)
        self.failcode("QUOTE_TIMESTAMP_AFTER_OBSERVATION", validate_offer,
            edited(q, lambda x: x.update(quoted_at="2026-11-16T22:50:00Z")), p)

    def test_weighted_mc_effective_sample_size(self):
        x = self.goldens["joint_same_draw"]
        n = x["points"]["numerical"]
        self.assertAlmostEqual(n["effective_sample_size"], 1/.52, places=8)
        self.assertGreater(n["zero_event_95_upper_bound"], .5)
        self.assertEqual(n["uncertainty_basis"], "heuristic_weighted_ess")

    def test_bad_weighted_mc_zero_bound(self):
        x = self.goldens["joint_same_draw"]
        d = edited(x["points"], lambda y: y["numerical"].update(
            zero_event_95_upper_bound=0.0))
        self.failcode("MC_ZERO_TAIL_UNCERTAINTY", validate_distribution,
                      d, x["pregame"])

    def test_historical_offer_free_golden(self):
        x = self.goldens["historical_offer_free"]
        self.assertTrue(validate_pregame(x["pregame"]))
        self.assertTrue(validate_distribution(x["distribution"], x["pregame"]))
        self.assertEqual(x["pregame"]["original_offer_count"], 0)

    def test_prospective_original_offer_golden(self):
        x = self.goldens["prospective_original_offer"]
        self.assertTrue(validate_pregame(x["pregame"]))
        self.assertTrue(validate_distribution(x["distribution"], x["pregame"]))
        self.assertTrue(validate_offer(x["offer"], x["pregame"]))
        self.assertTrue(validate_offer_view(x["offer_view"], x["distribution"],
                                            x["offer"], x["pregame"]))

    def test_g_o_j_independent_envelopes_are_coherent(self):
        x = self.goldens["joint_same_draw"]
        from v2.nba_architecture.families_v2 import (
            validate_game_state, validate_opportunity, validate_integration)
        self.assertTrue(validate_game_state(x["game_state"], x["pregame"]))
        self.assertTrue(validate_opportunity(x["opportunity"], x["pregame"],
                                              x["game_state"]))
        self.assertTrue(validate_integration(x["scenarios"], x["pregame"],
                                             x["game_state"], x["opportunity"]))

    def test_g_state_bad_weights(self):
        from v2.nba_architecture.families_v2 import validate_game_state
        x = self.goldens["joint_same_draw"]
        g = edited(x["game_state"], lambda q: q["scenarios"][0].update(weight=.3))
        self.failcode("G_WEIGHT_SUM", validate_game_state, g, x["pregame"])

    def test_o_unknown_participation_must_not_be_one(self):
        from v2.nba_architecture.families_v2 import validate_opportunity
        x = self.goldens["joint_same_draw"]
        o = edited(x["opportunity"], lambda q: q["players"][0].update(
              participation_probability=1.0))
        self.failcode("O_UNKNOWN_PARTICIPATION", validate_opportunity, o,
                      x["pregame"], x["game_state"])

    def test_o_missing_player(self):
        from v2.nba_architecture.families_v2 import validate_opportunity
        x = self.goldens["joint_same_draw"]
        o = edited(x["opportunity"], lambda q: q["players"].pop())
        self.failcode("O_ROSTER_COVERAGE", validate_opportunity, o,
                      x["pregame"], x["game_state"])

    def test_j_cannot_change_g_hash(self):
        from v2.nba_architecture.families_v2 import validate_integration
        x = self.goldens["joint_same_draw"]
        j = edited(x["scenarios"], lambda q: q.update(game_state_sha256="f"*64))
        self.failcode("J_G_O_HASH_JOIN", validate_integration, j,
                      x["pregame"], x["game_state"], x["opportunity"])

    def test_j_cannot_reseed_o_draw(self):
        from v2.nba_architecture.families_v2 import validate_integration
        x = self.goldens["joint_same_draw"]
        o = edited(x["opportunity"], lambda q: q["scenarios"][0]["players"][0].update(
             participation="DNP",minutes=0.))
        # Conserved minutes fail before the attempt to pass a tampered J.
        self.failcode("O_TEAM_MINUTE_CONSERVATION", validate_integration,
                      x["scenarios"], x["pregame"], x["game_state"], o)

    def test_joint_same_draw_golden(self):
        x = self.goldens["joint_same_draw"]
        self.assertTrue(validate_scenarios(x["scenarios"], x["pregame"]))
        self.assertTrue(validate_distribution(x["points"], x["pregame"]))
        self.assertTrue(validate_distribution(x["pra"], x["pregame"]))
        self.assertEqual(x["pra"]["pmf"], x["points"]["pmf"])

    def test_j_threes_from_same_scenario(self):
        x = self.goldens["joint_same_draw"]
        p = x["pregame"]
        d = marginal_from_joint(x["scenarios"], p, p["players"][0]["player_id"],
                                "threes", "2026-11-16T23:03:00Z", 42)
        self.assertEqual(d["pmf"], [{"value": 0, "mass": .4},
                                    {"value": 1, "mass": .6}])

    def test_source_retrieved_years_after_historical_event(self):
        p = self.goldens["historical_offer_free"]["pregame"]
        self.assertGreater(p["sources"][0]["retrieved_at"], p["event_start_at"])
        self.assertTrue(validate_pregame(p))

    def test_historical_publication_unknown_not_invented(self):
        s = self.goldens["historical_offer_free"]["pregame"]["sources"][0]
        self.assertIsNone(s["provider_published_at"])
        self.assertEqual(s["publication_evidence"], "unknown")

    def test_historical_no_original_line(self):
        p = self.goldens["historical_offer_free"]["pregame"]
        self.failcode("HISTORICAL_OFFER_NOT_ORIGINAL", validate_offer,
                      self.goldens["prospective_original_offer"]["offer"], p)

    def test_historical_no_target_game_data(self):
        p = pregame()
        p = edited(p, lambda q: q["features"][0].update({"target_game_outcome": True}))
        self.failcode("TARGET_GAME_FEATURE_LEAK", validate_pregame, p)

    def test_historical_feature_current_game_not_allowed(self):
        p = pregame()
        p = edited(p, lambda q: q["features"][0].update(
            {"prior_game_date": q["decision_local_date"]}))
        self.failcode("HISTORICAL_FEATURE_LEAK", validate_pregame, p)

    def test_historical_source_after_date_proxy(self):
        p = pregame()
        def mutate(x):
            x["sources"][0] = reissue(x["sources"][0],
                                      historical_game_date="2022-10-19")
        self.failcode("HISTORICAL_PRIOR_DATE_REQUIRED",
                      validate_pregame, edited(p, mutate))

    def test_historical_archive_rebranded_original(self):
        p = pregame()
        self.failcode("PROSPECTIVE_SOURCE_REQUIRED", validate_pregame,
            edited(p, lambda q: q.update({
                "source_profile": "original_prospective",
                "certification": "ORIGINAL_SOURCE_SHADOW"
            })))

    def test_prospective_retrieval_after_freeze(self):
        p = pregame("original_prospective")
        self.failcode("POSTFREEZE_SOURCE", validate_pregame,
            edited(p, lambda x: x["sources"].__setitem__(0,
                reissue(x["sources"][0], retrieved_at=P_EVENT))))

    def test_prospective_ingest_after_freeze(self):
        p = pregame("original_prospective")
        self.failcode("POSTFREEZE_SOURCE", validate_pregame,
            edited(p, lambda x: x["sources"].__setitem__(0,
                reissue(x["sources"][0], ingested_at=P_EVENT))))

    def test_prospective_observation_after_freeze(self):
        p = pregame("original_prospective")
        self.failcode("POSTFREEZE_SOURCE", validate_pregame,
            edited(p, lambda x: x["sources"].__setitem__(0,
                reissue(x["sources"][0], collector_observed_at=P_EVENT))))

    def test_original_source_cannot_be_retrospective(self):
        p = pregame("original_prospective")
        self.failcode("PROSPECTIVE_SOURCE_REQUIRED", validate_pregame,
            edited(p, lambda x: x["sources"].__setitem__(0,
                reissue(x["sources"][0], origin="retrospective_retrieval"))))

    def test_timestamp_order_model_after_freeze(self):
        p = pregame("original_prospective")
        self.failcode("PREGAME_CLOCK_ORDER", validate_pregame,
                      edited(p, lambda q: q.update(training_cutoff_at=P_EVENT)))

    def test_timestamp_order_forecast_after_event(self):
        p = pregame("original_prospective")
        self.failcode("PREGAME_CLOCK_ORDER", validate_pregame,
                      edited(p, lambda q: q.update(forecast_at=P_EVENT)))

    def test_timestamp_non_utc(self):
        p = pregame("original_prospective")
        self.failcode("UTC_TIMESTAMP_REQUIRED", validate_pregame,
                      edited(p, lambda q: q.update(
                          event_start_at="2026-11-16T19:00:00-05:00")))

    def test_publication_unknown_with_nonnull_claim_fails(self):
        p = pregame("original_prospective")
        def m(x):
            x["sources"][0] = reissue(x["sources"][0],
                provider_published_at="2026-11-16T22:00:00Z")
        self.failcode("PUBLICATION_EVIDENCE_REQUIRED", validate_pregame,
                      edited(p, m))

    def test_verified_publication_after_retrieval_fails(self):
        p = pregame("original_prospective")
        def m(x):
            x["sources"][0] = reissue(x["sources"][0],
                provider_published_at="2026-11-16T22:59:00Z",
                publication_evidence="verified")
        self.failcode("PUBLICATION_AFTER_RETRIEVAL", validate_pregame,
                      edited(p, m))

    def test_source_hash_tampering_fails(self):
        p = pregame("original_prospective")
        tampered = copy.deepcopy(p)
        tampered["sources"][0]["raw_sha256"] = "f" * 64
        self.failcode("CONTENT_HASH_MISMATCH", validate_pregame, tampered)

    def test_source_receipt_bad_hash_fails(self):
        p = pregame()
        p = edited(p, lambda q: q["sources"][0].update(raw_sha256="f"*64))
        self.failcode("RECEIPT_HASH_MISMATCH", validate_pregame, p)

    def test_source_revision_supersession_chain(self):
        p = pregame()
        def m(x):
            prior = x["sources"][0]
            x["sources"].append(reissue(prior, source_revision=2,
                  supersedes_receipt_sha256=prior["receipt_sha256"]))
        self.assertTrue(validate_pregame(edited(p, m)))

    def test_source_revision_wrong_parent(self):
        p = pregame()
        def m(x):
            prior = x["sources"][0]
            x["sources"].append(reissue(prior, source_revision=2,
                  supersedes_receipt_sha256="f"*64))
        self.failcode("SOURCE_REVISION_CHAIN", validate_pregame, edited(p, m))

    def test_source_revision_conflict(self):
        p = pregame()
        self.failcode("DUPLICATE_SOURCE_REVISION", validate_pregame,
            edited(p, lambda x: x["sources"].append(dict(x["sources"][0]))))

    def test_missing_eligibility_allowed(self):
        p = pregame("original_prospective")
        self.assertIsNone(p["players"][0]["legal_eligibility"])
        self.assertTrue(validate_pregame(p))

    def test_disallowed_eligibility_assumption_historical(self):
        p = pregame()
        self.failcode("HISTORICAL_ELIGIBILITY_LEAK", validate_pregame,
            edited(p, lambda x: x["players"][0].update(legal_eligibility=True)))

    def test_roster_wrong_team(self):
        p = pregame()
        self.failcode("PLAYER_TEAM_MISMATCH", validate_pregame,
            edited(p, lambda x: x["players"][0].update(team_id="espn:team:999")))

    def test_duplicate_player(self):
        p = pregame()
        self.failcode("DUPLICATE_PLAYER", validate_pregame,
            edited(p, lambda x: x["players"].append(dict(x["players"][0]))))

    def test_s_only_full_distribution(self):
        p = pregame()
        self.assertTrue(validate_distribution(distribution(p), p))

    def test_s_o_full_distribution(self):
        p = pregame()
        self.assertTrue(validate_distribution(distribution(p, mode="S_O"), p))

    def test_s_o_j_full_distribution(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        d = marginal_from_joint(j, p, p["players"][0]["player_id"], "points",
                                "2026-11-16T23:03:00Z", 100)
        self.assertTrue(validate_distribution(d, p))
        self.assertEqual(d["scenario_bundle_sha256"], j["content_hash"])

    def test_s_o_requires_opportunity_lineage(self):
        p = pregame()
        d = distribution(p, mode="S_O")
        self.failcode("MODEL_COMPONENT_REQUIRED", validate_distribution,
            edited(d, lambda x: x["lineage"].update(O=None)), p)

    def test_pipeline_mode_cannot_forge_j(self):
        p = pregame()
        d = distribution(p)
        self.failcode("MODEL_COMPONENT_REQUIRED", validate_distribution,
            edited(d, lambda x: x.update(pipeline_mode="S_O_J")), p)

    def test_s_model_trained_future(self):
        p = pregame()
        d = distribution(p)
        self.failcode("FUTURE_MODEL_FIT", validate_distribution,
            edited(d, lambda x: x["lineage"]["S"].update(training_cutoff_at=P_EVENT)), p)

    def test_discrete_pmf_normalized(self):
        p = pregame()
        d = distribution(p)
        self.failcode("PMF_NOT_NORMALIZED", validate_distribution,
            edited(d, lambda x: x["pmf"][1].update(mass=.7)), p)

    def test_duplicate_mass_point(self):
        p = pregame()
        d = distribution(p)
        self.failcode("PMF_SUPPORT", validate_distribution,
            edited(d, lambda x: x["pmf"][1].update(value=0)), p)

    def test_negative_mass(self):
        p = pregame()
        d = distribution(p)
        self.failcode("NUMBER_BELOW_MINIMUM", validate_distribution,
            edited(d, lambda x: x["pmf"][1].update(mass=-.75)), p)

    def test_unsupported_stat(self):
        p = pregame()
        d = distribution(p)
        self.failcode("STAT_PERIOD", validate_distribution,
            edited(d, lambda x: x.update(stat="fake_points")), p)

    def test_unknown_player_distribution(self):
        p = pregame()
        d = distribution(p)
        self.failcode("STAT_PLAYER_TEAM_MISMATCH", validate_distribution,
            edited(d, lambda x: x.update(player_id="espn:player:unknown")), p)

    def test_distribution_freeze_after_tipoff(self):
        p = pregame()
        d = distribution(p)
        self.failcode("FORECAST_FREEZE_TIME", validate_distribution,
            edited(d, lambda x: x.update(frozen_at=p["event_start_at"])), p)

    def test_finite_mc_uncertainty_required(self):
        p = pregame()
        d = distribution(p)
        self.failcode("MC_COUNT_REQUIRED", validate_distribution,
            edited(d, lambda x: x["numerical"].update(method="empirical_mc")), p)

    def test_analytic_cannot_claim_mc_uncertainty(self):
        p = pregame()
        d = distribution(p)
        self.failcode("ANALYTIC_MC_CONFLICT", validate_distribution,
            edited(d, lambda x: x["numerical"].update(scenario_count=128)), p)

    def test_truncated_distribution_bound(self):
        p = pregame()
        d = distribution(p)
        self.failcode("TRUNCATED_LAW_UNCERTIFIED", validate_distribution,
            edited(d, lambda x: x["numerical"].update(tail_mass_upper_bound=.01)), p)

    def test_historical_limitations_persist(self):
        p = pregame()
        d = distribution(p)
        self.failcode("HISTORICAL_LIMITATION_LOST", validate_distribution,
            edited(d, lambda x: x.update(historical_asof_limitations=None)), p)

    def test_prospective_missing_quote_is_valid(self):
        p = pregame("original_prospective")
        d = distribution(p)
        self.assertTrue(validate_distribution(d, p))
        self.assertEqual(p["original_offer_count"], 0)

    def test_original_offer_stale_quote_timestamp(self):
        p = pregame("original_prospective", with_offer=True)
        q = original_offer(p)
        self.failcode("POSTFREEZE_OFFER", validate_offer,
            edited(q, lambda x: x.update(quoted_at=P_EVENT)), p)

    def test_original_offer_source_hash_mismatch(self):
        p = pregame("original_prospective", with_offer=True)
        q = original_offer(p)
        self.failcode("OFFER_BYTES_MISMATCH", validate_offer,
            edited(q, lambda x: x.update(raw_quote_sha256="f"*64)), p)

    def test_offer_wrong_player_team(self):
        p = pregame("original_prospective", with_offer=True)
        q = original_offer(p)
        self.failcode("OFFER_PLAYER_JOIN", validate_offer,
            edited(q, lambda x: x.update(player_id="espn:player:999")), p)

    def test_offer_view_exact_probability_triplet(self):
        x = self.goldens["prospective_original_offer"]
        self.assertEqual(x["offer_view"]["probabilities"],
                         {"over": .75, "under": .25, "push": 0})

    def test_integer_push_exact(self):
        pmf = [{"value": 0, "mass": .1}, {"value": 2, "mass": .7},
               {"value": 3, "mass": .2}]
        self.assertEqual(threshold_triplet(pmf, 2),
                         {"over": .2, "under": .1, "push": .7})

    def test_corrupt_offer_view_triplet(self):
        x = self.goldens["prospective_original_offer"]
        v = edited(x["offer_view"], lambda y: y["probabilities"].update(over=.5))
        self.failcode("TRIPLET_MISMATCH", validate_offer_view, v,
                      x["distribution"], x["offer"], x["pregame"])

    def test_offer_view_cannot_infer_void(self):
        x = self.goldens["prospective_original_offer"]
        v = edited(x["offer_view"], lambda y: y.update(
                 product_void_semantics="automatic_DNP_push"))
        self.failcode("DNP_VOID_INFERRED", validate_offer_view, v,
                      x["distribution"], x["offer"], x["pregame"])

    def test_scenarios_distinguish_dnp_zero(self):
        x = self.goldens["joint_same_draw"]
        a, b = x["scenarios"]["scenarios"]
        self.assertEqual(a["players"][5]["participation"], "DNP")
        self.assertEqual(b["players"][5]["participation"], "PLAYED_ZERO_MINUTES")
        self.assertTrue(validate_scenarios(x["scenarios"], x["pregame"]))

    def test_j_scenario_player_missing(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        self.failcode("INCOMPLETE_J_ROSTER", validate_scenarios,
             edited(j, lambda x: x["scenarios"][0]["players"].pop()), p)

    def test_j_scenario_team_wrong(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        self.failcode("TEAM_MINUTES_CONSERVATION", validate_scenarios,
             edited(j, lambda x: x["scenarios"][0]["players"][0].update(
                 team_id="espn:team:2")), p)

    def test_j_minutes_not_conserved(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        self.failcode("TEAM_MINUTES_CONSERVATION", validate_scenarios,
             edited(j, lambda x: x["scenarios"][0]["players"][0].update(minutes=40.)), p)

    def test_j_dnp_nonzero_stats(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        self.failcode("ZERO_MINUTE_STATS", validate_scenarios,
             edited(j, lambda x: x["scenarios"][0]["players"][5]["stats"].update(
                steals=1)), p)

    def test_j_zero_minutes_played_stats(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        self.failcode("ZERO_MINUTE_STATS", validate_scenarios,
             edited(j, lambda x: x["scenarios"][1]["players"][5]["stats"].update(
                blocks=1)), p)

    def test_j_overtime_conservation(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        def m(x):
            x["scenarios"][0]["overtime_periods"] = 1
            x["game_state_witness"]["synthetic:draw:0"]["overtime_periods"] = 1
        self.failcode("TEAM_MINUTES_CONSERVATION", validate_scenarios, edited(j, m), p)

    def test_j_opportunity_witness_drift(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        def m(x):
            x["opportunity_witness"]["synthetic:draw:0"][0]["minutes"] = 40.
        self.failcode("OPPORTUNITY_DRAW_CHANGED", validate_scenarios, edited(j, m), p)

    def test_j_game_state_mismatch(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        def m(x):
            x["game_state_witness"]["synthetic:draw:0"]["overtime_periods"] = 1
        self.failcode("INDEPENDENT_GAME_STATE_DRAW", validate_scenarios, edited(j, m), p)

    def test_j_scenario_duplicate_ids(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        def m(x):
            x["scenarios"][1]["scenario_id"] = "synthetic:draw:0"
        self.failcode("DUPLICATE_SCENARIO", validate_scenarios, edited(j, m), p)

    def test_j_scenario_bad_weights(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        def m(x):
            x["scenarios"][0]["weight"] = .3
        self.failcode("SCENARIO_WEIGHTS", validate_scenarios, edited(j, m), p)

    def test_j_scoring_points_identity(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        def m(x):
            x["scenarios"][0]["players"][0]["stats"]["two_pm"] = 0
        self.failcode("FG_ACCOUNTING", validate_scenarios, edited(j, m), p)

    def test_j_three_attempts_constraint(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        def m(x):
            x["scenarios"][1]["players"][0]["stats"]["three_pa"] = 0
        self.failcode("SHOT_CONVERSIONS", validate_scenarios, edited(j, m), p)

    def test_j_rebound_identity(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        def m(x):
            x["scenarios"][0]["players"][0]["stats"]["rebounds"] = 1
        self.failcode("REBOUND_ACCOUNTING", validate_scenarios, edited(j, m), p)

    def test_j_combo_identity(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        def m(x):
            x["scenarios"][0]["players"][0]["stats"]["pra"] = 5
        self.failcode("COMBO_ACCOUNTING_pra", validate_scenarios, edited(j, m), p)

    def test_j_wrong_source_snapshot(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        self.failcode("SCENARIO_SOURCE_JOIN", validate_scenarios,
             edited(j, lambda x: x.update(source_snapshot_sha256="f"*64)), p)

    def test_j_marginal_lineage_is_stable(self):
        p = pregame("original_prospective")
        j = j_scenarios(p)
        a = marginal_from_joint(j, p, p["players"][0]["player_id"], "pr",
                                "2026-11-16T23:03:00Z", 42)
        b = marginal_from_joint(j, p, p["players"][0]["player_id"], "pr",
                                "2026-11-16T23:03:00Z", 42)
        self.assertEqual(a["content_hash"], b["content_hash"])

    def test_frozen_bytes_idempotent(self):
        x = self.goldens["historical_offer_free"]["distribution"]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "forecast.json"
            freeze_once(path, x)
            freeze_once(path, x)
            self.assertEqual(path.read_bytes()[-1:], b"\n")
            self.assertEqual(verify(x), x["content_hash"])

    def test_frozen_conflicting_bytes_rejected(self):
        x = self.goldens["historical_offer_free"]["distribution"]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "forecast.json"
            freeze_once(path, x)
            corrupted = edited(x, lambda y: y.update(rng_seed=43))
            self.failcode("IMMUTABLE_CONFLICT", freeze_once, path, corrupted)

    def test_deterministic_seed(self):
        a = seed_for(123, "espn:game:x", "scenario:1", "S-v2")
        self.assertEqual(a, seed_for(123, "espn:game:x", "scenario:1", "S-v2"))
        self.assertNotEqual(a, seed_for(123, "espn:game:x", "scenario:2", "S-v2"))

    def test_ambiguous_scenario_seed(self):
        self.failcode("AMBIGUOUS_SEED", seed_for, 1, "game|id", "s", "S")

    def test_evaluation_too_early(self):
        x = self.goldens["prospective_original_offer"]
        e = evaluation(x["distribution"], x["offer_view"])
        self.failcode("EVALUATED_BEFORE_EVENT", validate_evaluation,
             edited(e, lambda y: y.update(evaluated_at=P_FREEZE)),
             x["distribution"], x["offer_view"])

    def test_settlement_corrected_append_only(self):
        x = self.goldens["prospective_original_offer"]
        first = evaluation(x["distribution"], x["offer_view"])
        corrected = evaluation(x["distribution"], x["offer_view"],
             revision=2, previous=first["content_hash"], actual=3)
        self.assertTrue(validate_evaluation(first, x["distribution"], x["offer_view"]))
        self.assertTrue(validate_evaluation(corrected, x["distribution"], x["offer_view"]))
        self.assertNotEqual(first["content_hash"], corrected["content_hash"])

    def test_settlement_correction_missing_parent(self):
        x = self.goldens["historical_offer_free"]
        e = evaluation(x["distribution"], revision=2)
        self.failcode("CORRECTION_PREDECESSOR_MISSING",
                      validate_evaluation, e, x["distribution"])

    def test_settlement_push_label_mismatch(self):
        x = self.goldens["prospective_original_offer"]
        e = evaluation(x["distribution"], x["offer_view"], status="push", line=1.5)
        self.failcode("FALSE_PUSH", validate_evaluation, e,
                      x["distribution"], x["offer_view"])

    def test_settlement_void_kept_distinct(self):
        x = self.goldens["historical_offer_free"]
        e = evaluation(x["distribution"], status="void", actual=None,
                       participation="DNP")
        self.assertTrue(validate_evaluation(e, x["distribution"]))

    def test_settlement_dnp_outcome_not_imputed(self):
        x = self.goldens["historical_offer_free"]
        e = evaluation(x["distribution"], status="pending", actual=None,
                       participation="unknown")
        self.assertTrue(validate_evaluation(e, x["distribution"]))

    def test_golden_files_match_generated_if_present(self):
        """Golden JSON fixtures become committed outputs after candidate freeze."""
        root = Path(__file__).parent / "golden_v2"
        if not root.exists():
            self.skipTest("GOLDEN_JSON_NOT_YET_PUBLISHED")
        for name, generated in self.goldens.items():
            b = (root / (name + ".json")).read_bytes()
            self.assertEqual(b, json.dumps(generated, sort_keys=True,
                ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()+b"\n")


if __name__ == "__main__":
    unittest.main()
