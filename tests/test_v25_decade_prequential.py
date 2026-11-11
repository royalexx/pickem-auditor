"""Red-team decade cross-market NFL walk-forward, no posterior oracle access."""
import copy,math,sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from v25_decade_prequential import (
    OnlineCalibrator,asof_depth,sample_crps,model_offer,child_forecast,
    settle,MARKETS,BASE_MARKETS,EXTRA,SCHEMA,EXPERIMENT
)
from v25_decade_joint_opportunity import OpportunityModel
from v25_decade_qb_components import QBRushComponentModel
from test_v25_opportunity_distribution_repair import history
from test_v25_qb_rush_components import example_rows


def packet():
    h=history()
    pbp=example_rows()
    # The copied source already covers 2016 and 2025 as pre-event model years.
    return {"schema":SCHEMA,"experiment":EXPERIMENT,
       "season":2016,"week":1,"history":h,"pbp_prior":pbp,
       "games":[{"game_id":"2016_01_A_B","team":"A","opponent":"B","week":1}],
       "qb1":{"2016_01_A_B|A":{"player_id":"q","reason":None,
            "source_time_or_week":"2015_week18","confirmed_live_starter":False}},
       "calibration_preimage":OnlineCalibrator().receipt(),
       "source_capture_certified":False,"no_current_game_outcomes":True}


class DecadeScientificAcceptanceTests(unittest.TestCase):
    def test_market_scope_all_11_plus_qb2(self):
        self.assertEqual(len(BASE_MARKETS),11)
        self.assertEqual(len(EXTRA),2)
        self.assertEqual(len(MARKETS),13)
        self.assertEqual(set(BASE_MARKETS),{"pass attempts","completions","passing yards",
            "targets","receptions","receiving yards","carries","rushing yards",
            "tackles + assists","solo tackles","tackle assists"})

    def test_bayesian_calibration_only_changes_after_outcome_reveal(self):
        c=OnlineCalibrator()
        pre=c.apply("shared_opportunity","targets","WR",.9)
        self.assertAlmostEqual(pre,.9)
        c.train_after_week([("shared_opportunity","targets","WR",.9,0)]*200)
        post=c.apply("shared_opportunity","targets","WR",.9)
        self.assertLess(post,pre)
        self.assertAlmostEqual(c.apply("player_history","targets","WR",.9),.9)
        self.assertAlmostEqual(c.apply("shared_opportunity","carries","RB",.9),.9)

    def test_half_count_smooths_absolute_zero_one_confidence(self):
        zero=model_offer(np.zeros(128),.5)
        full=model_offer(np.full(128,4),.5)
        self.assertEqual(zero["q_over_raw"],.5/129)
        self.assertEqual(full["q_over_raw"],128.5/129)
        self.assertEqual(zero["zero_probability"],1.)

    def test_empirical_CRPS_known_exact(self):
        self.assertAlmostEqual(sample_crps([0,2],1),.5)
        self.assertAlmostEqual(sample_crps([3,3,3,3],3),0.)

    def test_historical_depth_never_selects_in_week_future_data(self):
        games=[{"game_id":"2016_02_A_B","week":2,"home_team":"A","away_team":"B"}]
        rows=[{"club_code":"A","gsis_id":"old","depth_team":"1",
                "depth_position":"QB","week":1},
              {"club_code":"A","gsis_id":"oracle","depth_team":"1",
                "depth_position":"QB","week":2}]
        report=asof_depth(2016,2,games,rows)
        self.assertEqual(report["2016_02_A_B","A"]["player_id"],"old")
        report=asof_depth(2016,1,[{**games[0],"week":1}],rows)
        self.assertIsNone(report["2016_02_A_B","A"]["player_id"])

    def test_2025_future_dated_depth_never_used(self):
        games=[{"game_id":"2025_01_A_B","week":1,"home_team":"A","away_team":"B",
                "gameday":"2025-09-07","gametime":"13:00"}]
        rows=[{"team":"A","gsis_id":"future","pos_abb":"QB",
              "pos_rank":1,"dt":"2025-09-09T12:00:00Z"},
              {"team":"A","gsis_id":"old","pos_abb":"QB",
              "pos_rank":1,"dt":"2025-09-05T12:00:00Z"}]
        report=asof_depth(2025,1,games,rows)
        self.assertEqual(report["2025_01_A_B","A"]["player_id"],"old")

    def test_future_week_player_history_rejected(self):
        p=packet()
        p["history"][-1]["season"]=2016
        with self.assertRaisesRegex(ValueError,"current_or_future_week_leak"):
            child_forecast(p,samples=128)

    def test_hidden_actual_result_input_fails_closed(self):
        p=packet()
        p["known_game_final_score"]=21
        with self.assertRaisesRegex(ValueError,"unregistered_child_input"):
            child_forecast(p,samples=128)

    def test_cross_market_joint_allocation_and_model_coverage(self):
        p=packet()
        o=child_forecast(p,samples=128,seed=2)
        self.assertTrue(o["forecasts_did_not_see_current_week_scores"])
        self.assertEqual(o["n_shared_team_volume_allocations"],1)
        eligible={r["market"] for r in o["offers"]}
        self.assertTrue({"pass attempts","completions","passing yards",
               "targets","receptions","receiving yards",
               "carries","rushing yards","tackles + assists",
               "solo tackles","tackle assists"}.issubset(eligible))
        self.assertTrue(all(r["role"]!="QB" or r["player_id"]=="q"
                          for r in o["offers"]))
        self.assertTrue(all("shared_opportunity" in r["forecast_models"] and
                        "player_history" in r["forecast_models"] for r in o["offers"]))

    def test_qb_rushing_component_uses_team_pass_draws(self):
        m=QBRushComponentModel(example_rows(),forecast_year=2016,forecast_week=1)
        low=m.draw("mobile",n=128,seed=5,dropback_samples=np.zeros(128,dtype=int))
        high=m.draw("mobile",n=128,seed=5,dropback_samples=np.full(128,70,dtype=int))
        self.assertEqual(sum(low["counts"]["scramble"]),0)
        self.assertGreater(sum(high["counts"]["scramble"]),0)
        self.assertTrue(high["shares_offensive_pass_workload"])

    def test_incomplete_score_not_under_hit_and_not_calibration_update(self):
        p=packet()
        o=child_forecast(p,samples=128,seed=2)
        # No observed outcomes -> explicitly no scoring, no calibration.
        settled,updates,cov=settle(o,[],OnlineCalibrator())
        self.assertEqual(len(updates),0)
        self.assertEqual(cov["no_original_player_observation_not_imputed"],len(o["offers"]))

    def test_brier_on_same_original_contract_and_model_gates(self):
        p=packet()
        o=child_forecast(p,samples=128,seed=2)
        rows=[{"event_id":"2016_01_A_B","team":"A",
            "players":{pid:{"role":"QB" if pid=="q" else "WR",
             "values":{market:0 for market in MARKETS}} for pid in
             {x["player_id"] for x in o["offers"]}}}]
        settled,updates,cov=settle(o,rows,OnlineCalibrator())
        self.assertGreater(len(updates),0)
        self.assertEqual(cov["scored_contracts"],len(o["offers"]))
        rec=next(x for x in settled if x.get("model_scores"))
        for s in rec["model_scores"].values():
            self.assertGreaterEqual(s["brier_raw"],0)
            self.assertLessEqual(s["brier_raw"],1)
            self.assertTrue(math.isfinite(s["crps"]))

if __name__=="__main__":unittest.main()
