"""One original quote/player/event/line per morning score; adversarial coverage."""
from __future__ import annotations
import copy
import unittest
from scripts.morning_contract_metrics import score_contract_rows,canonical_source_digest

FORECAST="2026-11-11T17:05:00Z"
EVENT="2026-11-11T23:30:00Z"


def rows(*,over=0.75,under=0.25,result="over"):
    basic={
      "game_date":"2026-11-11","run_id":"frozen-run-A","sport":"NHL",
      "event_id":"official-or-original-pre-event-id",
      "player_id":"8480069","player":"Original Player",
      "team":"COL","opponent":"TOR","stat":"shots on goal",
      "period":"full","event_start":EVENT,"forecast_at":FORECAST,
      "line":2.5,"actual_stat":3 if result=="over" else 2,
      "original_source_run_id":"frozen-run-A",
    }
    a={**basic,"side":"over","outcome":"win" if result=="over" else "loss",
       "engine_a":over,"market_raw_novig":0.54,
       "online_bayesian_a":0.62,"online_bayesian_b":0.57}
    b={**basic,"side":"under","outcome":"loss" if result=="over" else "win",
       "engine_a":under,"market_raw_novig":0.46,
       "online_bayesian_a":0.45,"online_bayesian_b":0.47}
    return [a,b]


class ContractAuditTests(unittest.TestCase):
    def test_one_pair_is_one_contract_and_direction_is_real_not_fifty_fifty(self):
        result=score_contract_rows(rows())
        self.assertEqual(result["raw_original_side_rows"],2)
        self.assertEqual(result["settled_valid_paired_contracts"],1)
        self.assertEqual(result["accepted_contracts_by_sport"],{"NHL":1})
        metric=result["metrics"]["NHL"]["shots on goal"]["engine_a"]
        self.assertEqual(metric["n_contracts"],1)
        self.assertEqual(metric["observed_over_frequency"],1)
        self.assertEqual(metric["mean_p_over"],.75)
        self.assertEqual(metric["selected_hit_rate"],1)
        self.assertAlmostEqual(metric["brier"],.0625)
        self.assertEqual(result["contract_ledger"][0]["models_scored"],[
            "engine_a","market_raw_novig"])
        self.assertFalse(result["model_promotion_allowed"])

    def test_incoherent_online_research_cannot_be_accidentally_scored(self):
        result=score_contract_rows(rows())
        cov=result["model_coverage_and_invalidity"]["NHL"]["shots on goal"]
        self.assertEqual(cov["online_bayesian_a"]["noncomplementary_probabilities"],1)
        self.assertEqual(cov["online_bayesian_b"]["noncomplementary_probabilities"],1)
        self.assertNotIn("online_bayesian_a",result["metrics"]["NHL"]["shots on goal"])
        self.assertNotIn("online_bayesian_b",result["metrics"]["NHL"]["shots on goal"])
        self.assertEqual(len(result["contract_ledger"]),1)

    def test_do_not_renormalize_two_bad_probs_to_look_good(self):
        bad=rows()
        bad[0]["engine_a"]=.6
        bad[1]["engine_a"]=.5
        result=score_contract_rows(bad)
        self.assertNotIn("engine_a",result["metrics"]["NHL"]["shots on goal"])
        self.assertEqual(result["contract_ledger"][0]["model_exclusions"]["engine_a"],
                         "noncomplementary_probabilities")

    def test_duplicate_side_rejected_not_double_scored(self):
        items=rows()
        with self.assertRaisesRegex(ValueError,"duplicate_original_side"):
            score_contract_rows(items+[copy.deepcopy(items[0])])

    def test_source_identity_missing_is_fail_closed(self):
        for field in ("player_id","event_id","run_id"):
            items=rows()
            for row in items:row.pop(field)
            result=score_contract_rows(items)
            self.assertEqual(result["settled_valid_paired_contracts"],0)
            self.assertEqual(result["invalid_or_unsettled_contract_reasons"][
                "incomplete_original_contract_identity"],2)

    def test_post_event_or_unzoned_forecasts_are_not_scored(self):
        for time in (EVENT,"2026-11-11T23:30:00","2026-11-12T23:30:00Z"):
            items=rows()
            for r in items:r["forecast_at"]=time
            result=score_contract_rows(items)
            self.assertEqual(result["settled_valid_paired_contracts"],0)

    def test_same_player_different_run_and_line_never_collide(self):
        items=rows()
        later=rows(over=.65,under=.35)
        for row in later:
            row["run_id"]="frozen-run-B"
            row["original_source_run_id"]="frozen-run-B"
        report=score_contract_rows(items+later)
        self.assertEqual(report["settled_valid_paired_contracts"],2)
        self.assertEqual(report["metrics"]["NHL"]["shots on goal"]["engine_a"]["n_contracts"],2)

    def test_contradictory_actual_or_result_refused(self):
        items=rows()
        items[1]["actual_stat"]=1
        self.assertEqual(score_contract_rows(items)["invalid_or_unsettled_contract_reasons"][
            "contradictory_original_pair"],1)
        items=rows()
        items[1]["outcome"]="win"
        self.assertEqual(score_contract_rows(items)["invalid_or_unsettled_contract_reasons"][
            "incoherent_settled_opposite_sides"],1)

    def test_absent_side_and_push_never_count_as_under(self):
        items=rows()
        result=score_contract_rows(items[:1])
        self.assertEqual(result["invalid_or_unsettled_contract_reasons"][
            "unpaired_original_contract"],1)
        items=rows()
        items[0]["outcome"]="push"
        items[1]["outcome"]="push"
        self.assertEqual(score_contract_rows(items)["settled_valid_paired_contracts"],0)

    def test_model_coverage_and_matched_market_brier_are_exact(self):
        items=rows(over=.75,under=.25)
        result=score_contract_rows(items)
        comparison=result["paired_model_vs_market"]["NHL"]["shots on goal"]["engine_a"]
        self.assertAlmostEqual(comparison["mean_brier_delta_vs_market"],
                               (.75-1)**2-(.54-1)**2)
        self.assertEqual(comparison["n_date_clusters"],1)
        m=result["metrics"]["NHL"]["shots on goal"]["engine_a"]
        self.assertFalse(m["full_calendar_date_cluster_power_available"])

    def test_source_digest_stable_and_sensitive(self):
        x=rows()[0]
        self.assertEqual(canonical_source_digest(x),canonical_source_digest(copy.deepcopy(x)))
        alt=copy.deepcopy(x);alt["line"]=3.5
        self.assertNotEqual(canonical_source_digest(x),canonical_source_digest(alt))


if __name__=="__main__":unittest.main()
