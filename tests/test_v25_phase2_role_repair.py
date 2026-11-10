"""Phase 2 repair: strictly as-of role opportunity and calibration smoke.

Synthetic fixtures only. No 2024 performance-claims or production promotion.
"""
from __future__ import annotations

from copy import deepcopy
import unittest

from scripts.v25_phase2_target_only_forecast import forecast as old_forecast
from scripts.v25_phase2_role_repair_forecast import forecast_repaired
from scripts.v25_phase2_online_probability_calibration import calibrate_asof

from test_v25_phase2_target_only import fixture


class RepairedTargetModelTests(unittest.TestCase):
    def test_conservation_and_week_one_original_model_identical(self):
        p=fixture()
        baseline=old_forecast(p,samples=128,seed=4)
        new=forecast_repaired(p,samples=128,seed=4)
        self.assertEqual(new["train_2024_max_week"],0)
        self.assertFalse(new["promotion_authorized"])
        x=new["forecasts"][0]["models"]
        self.assertEqual(x["updated"],baseline["forecasts"][0]["models"]["updated"])
        self.assertEqual(x["no_refit"],baseline["forecasts"][0]["models"]["no_refit"])
        for model in ("role_repaired","role_no_hurdle"):
            self.assertTrue(x[model]["all_targets_conserved"])
            self.assertFalse(x[model]["uses_actual_2024_current_or_future_stats"])
            self.assertEqual(set(x[model]["player_roles"]),set(x[model]["player_targets"]))
            for j in range(128):
                self.assertEqual(
                  x[model]["pass_attempts"][j],
                  x[model]["unassigned_attempts"][j]+sum(
                    v[j] for v in x[model]["player_targets"].values()))
                self.assertEqual(x[model]["pass_attempts"][j],
                                 x["updated"]["pass_attempts"][j])

    def test_complete_2024_current_game_poison_cannot_enter(self):
        p=fixture(3)
        p["history"].append({"event_id":"illegal_future","season":2024,
                "week":3,"team":"A","pass_attempts":48,"players":{}})
        with self.assertRaisesRegex(ValueError,"current_or_future_week_observation"):
            forecast_repaired(p,samples=128)

    def test_source_roster_selection_is_past_games_only(self):
        p=fixture()
        original=forecast_repaired(p,samples=128,seed=123)
        other=deepcopy(p)
        other["schedule"][0]["future_targets"]=50
        with self.assertRaisesRegex(ValueError,"schedule_contains_outcome"):
            forecast_repaired(other,samples=128)
        repeat=forecast_repaired(p,samples=128,seed=123)
        self.assertEqual(original["forecast_digest"],repeat["forecast_digest"])
        self.assertEqual(original["forecasts"],repeat["forecasts"])

    def test_role_hurdle_is_isolated_ablation(self):
        x=forecast_repaired(fixture(),samples=128,seed=5)["forecasts"][0]["models"]
        self.assertFalse(x["role_no_hurdle"]["uses_zero_target_participation_hurdle"])
        self.assertTrue(x["role_repaired"]["uses_zero_target_participation_hurdle"])


class CalibratorNoFutureLabelTests(unittest.TestCase):
    def training(self,week=2,n=120):
        return [{
          "week":week-1,"event_id":"historical_g_"+str(i),
          "team":"T","player_id":"p_"+str(i),"role":("WR","RB","TE")[i%3],
          "raw_over":.10+(i%12)*.06,
          "actual_over":i%2,
        } for i in range(n)]

    def offers(self):
        return [{"event_id":"current","team":"T",
                 "player_id":"new","role":"WR","raw_over":.12}]

    def test_identity_on_week_one(self):
        result=calibrate_asof([],self.offers(),week=1,mode="role_platt")
        self.assertEqual(result["trained_on_latest_week"],0)
        self.assertEqual(result["status"],"identity_no_history")
        self.assertAlmostEqual(result["probabilities"][0]["calibrated_over"],.12)

    def test_previous_week_only_fit_and_probability_bounds(self):
        trained=self.training()
        for mode in ("global_platt","role_platt","raw"):
            x=calibrate_asof(trained,self.offers(),week=2,mode=mode)
            self.assertEqual(x["trained_on_latest_week"],1)
            prob=x["probabilities"][0]["calibrated_over"]
            self.assertTrue(0<prob<1)
            self.assertAlmostEqual(prob+x["probabilities"][0]["calibrated_under"],1.)
            self.assertFalse(x["future_labels_read"])
        x=calibrate_asof(trained,self.offers(),week=2,mode="role_platt")
        self.assertNotAlmostEqual(
            x["probabilities"][0]["calibrated_over"],.12)

    def test_current_future_labels_rejected_even_same_role(self):
        for badweek in (2,3,18):
            history=self.training()
            history[0]["week"]=badweek
            with self.assertRaisesRegex(ValueError,"current_or_future_label"):
                calibrate_asof(history,self.offers(),week=2)

    def test_current_game_offer_cannot_have_actual(self):
        bad=self.offers()
        bad[0]["actual_over"]=0
        with self.assertRaisesRegex(ValueError,"current_offer_has_actual"):
            calibrate_asof([],bad,week=1)

    def test_no_duplicate_prior_game_and_player_rows(self):
        history=self.training()
        history.append(deepcopy(history[0]))
        with self.assertRaisesRegex(ValueError,"duplicate_historical_offer"):
            calibrate_asof(history,self.offers(),week=2)

    def test_zero_history_calibration_is_not_retrofit(self):
        q=self.offers()
        for k in range(2,6):
            x=calibrate_asof(self.training(week=k,n=10),q,week=k,mode="role_platt")
            self.assertEqual(x["status"],"identity_insufficient_80_prior_rows")


if __name__=="__main__":
    unittest.main()
