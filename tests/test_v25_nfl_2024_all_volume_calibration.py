"""Phase 2 2024 all-volume calibration tests, chronological and adversarial."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.v25_nfl_2024_all_volume_rolling_calibration import (
    MARKETS,PROB_KEYS, fit_from_past, ptransform, role_for, run, selection, score_for,
)

ROLE={
 "pass attempts":"QB","completions":"QB","passing yards":"QB",
 "targets":"WR","receptions":"TE","receiving yards":"WR",
 "carries":"RB","rushing yards":"RB",
 "tackles + assists":"LB","solo tackles":"DB","tackle assists":"DT",
}

def fixture(root:Path,wrong_cutoff=False,missing_outcome=False):
    folder=root/"2024_walkforward_expanding_online_v2"/"FROZEN"
    folder.mkdir(parents=True)
    o=root/"2024_walkforward_expanding_online_v2__PRIVATE_2024_ORACLE"
    o.mkdir(parents=True)
    oracle={"weeks":{}}
    for w in range(1,19):
        preds=[]
        truth=[]
        for i,m in enumerate(MARKETS):
            p={
                "market":m,"game_id":f"2024_{w:02}_A_B",
                "team":"A","player_id":f"p_{i}",
                "position":ROLE[m],"research_line":float(i)+.5,
                "forecast_week":w,"week":w,
                "training_last_revealed_week":w-1,
                "bookmaker_quote_verified":False,
                "roster_2024_verified":False,
                "p_over":.15 if i%2 else .85,
                "p_under":.85 if i%2 else .15,
                "p_push":0.,
                "p_over_hurdle":.20 if i%2 else .80,
                "p_over_no_refit":.30 if i%2 else .70,
            }
            preds.append(p)
            if not(missing_outcome and m=="targets"):
                truth.append({"stat":m,"game_id":p["game_id"],
                    "team":"A","player_id":p["player_id"],
                    "value":float(i+1)})
        packet={"week":w,"latest_revealed_week":w if wrong_cutoff and w==6 else w-1,
            "training_label_week_limit":w-1,
            "future_2024_week_data_accessed_by_forecaster":False,
            "predictions":preds}
        (folder/f"week_{w:02}.json").write_text(json.dumps(packet))
        oracle["weeks"][str(w)]={"players":truth,"team_games":[]}
    (o/"oracle_2024.json").write_text(json.dumps(oracle))

class TestElevenMarketSequentialCalibration(unittest.TestCase):
 def test_registry_matches_production_volume_policy(self):
    from scripts.nfl_volume_market_policy import NFL_VOLUME_MARKETS
    self.assertEqual(set(MARKETS),set(NFL_VOLUME_MARKETS))
 def test_position_coarsening_is_a_finite_role_not_player_name(self):
    for position,expected in (("QB","QB"),("WR","WR"),("DT","DL"),
                              ("DE","DL"),("OLB","LB"),("CB","DB"),
                              ("SS","DB")):
        self.assertEqual(role_for(position),expected)
 def test_model_sees_no_current_label_on_week_one_and_calibration_identity(self):
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        fixture(root)
        result=run(root)
        self.assertEqual(result["scored_weeks"],18)
        self.assertEqual(result["n_volume_markets"],11)
        self.assertTrue(result["no_same_or_future_week_outcomes_used"])
        self.assertFalse(result["production_promotion_authorized"])
        for market in MARKETS:
            self.assertEqual(result["summary_by_market"][market]["models"]["archive_raw"]["raw"]["n"],18)
            first=result["week_by_week"][0]["markets"][market]["market_models"]["archive_raw"]
            self.assertEqual(first["raw"]["brier"],first["global"]["brier"])
            self.assertEqual(first["raw"]["brier"],first["role"]["brier"])
            self.assertEqual(first["global"]["train_n"],0)
            self.assertEqual(result["week_by_week"][5]["markets"][market]["market_models"]["archive_raw"]["global"]["train_n"],5)
 def test_temporal_future_week_leak_is_fatal(self):
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        fixture(root,wrong_cutoff=True)
        with self.assertRaisesRegex(AssertionError,"original_future_week_knowledge"):
            run(root)
 def test_missing_true_outcome_is_abstention_not_assumed_zero(self):
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        fixture(root,missing_outcome=True)
        report=run(root)
        self.assertEqual(report["summary_by_market"]["targets"]["models"]["archive_raw"]["raw"]["n"],0)
        self.assertEqual(report["summary_by_market"]["targets"]["counts"]["unsettled_no_observation"],18)
        self.assertEqual(report["summary_by_market"]["receptions"]["models"]["archive_raw"]["raw"]["n"],18)
 def test_strict_prior_calibration_corrects_overconfidence(self):
    hist=[{"p":.15 if i%3==0 else .9,
           "y":1 if i%3==0 else 0,"role":"WR" if i%2 else "TE",
           "week":1+(i%8)} for i in range(200)]
    f=fit_from_past(hist)
    self.assertTrue(f["active"])
    self.assertEqual(f["trained_n"],200)
    self.assertNotAlmostEqual(.9,ptransform(.9,"WR",f,"global"))
    self.assertTrue(0<ptransform(.15,"TE",f,"role")<1)
 def test_symmetric_proper_scoring_and_side_accuracy(self):
    self.assertAlmostEqual(score_for(.8,1)["brier"],.04)
    self.assertAlmostEqual(score_for(.2,0)["brier"],.04)
    rows=[{"prob":.85,"truth_over":1},{"prob":.1,"truth_over":0},
          {"prob":.5,"truth_over":1}]
    x=selection(rows,.8)
    self.assertEqual(x["n"],2)
    self.assertEqual(x["under"],1)
    self.assertEqual(x["over"],1)
    self.assertEqual(x["hit"],1.)

if __name__=="__main__":
    unittest.main()
