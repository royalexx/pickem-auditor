"""Adversarial NFL Phase2 QB rushing event decomposition tests."""
import copy
import math
import unittest
import numpy as np
from scripts.v25_qb_rush_components import (
    KINDS,QBRushComponentModel,ComponentModelError,verify_component_row,
)


def example_rows():
    result=[]
    for i in range(112):
        mobile=i%4==0
        pid="mobile" if mobile else "pocket"
        scramble=5 if mobile else i%3==0
        designed=4 if mobile else 0
        kneel=0 if mobile else i%3==1
        other=0
        cc={"scramble":scramble,"designed":designed,"kneel":kneel,"other":other}
        yy={"scramble":scramble*7.0,"designed":designed*3.0,
            "kneel":-kneel*1.0,"other":0.0}
        result.append({"season":2023,"week":i%18+1,"game_id":f"2023_F{i:04d}",
            "team":"MOB" if mobile else "PKT","player_id":pid,
            "dropbacks":32 if mobile else 30,
            "counts":cc,"yards":yy,
            "reconciled_to_weekly_stats":True,
            "source_original_capture_verified":False,
            "official_attempts":sum(cc.values()),
            "official_rushing_yards":sum(yy.values())})
    return result


class ComponentDecompositionTests(unittest.TestCase):
    def setUp(self):
        self.rows=example_rows()
        self.model=QBRushComponentModel(self.rows,forecast_year=2024,forecast_week=1)

    def test_sampled_counts_yards_are_additive_and_disjoint(self):
        x=self.model.draw("mobile",n=1024,seed=12)
        attempts=np.asarray(x["qb_rushing_attempts"])
        yards=np.asarray(x["qb_rushing_yards"])
        self.assertTrue(np.array_equal(attempts,sum((np.asarray(x["counts"][k]) for k in KINDS))))
        self.assertTrue(np.array_equal(yards,sum((np.asarray(x["type_yards"][k]) for k in KINDS))))
        self.assertTrue(np.all(attempts>=0))
        self.assertTrue(np.all(np.isfinite(yards)))
        self.assertFalse(x["production_authorized"])

    def test_mobile_prior_projects_more_rush_attempts_than_pocket(self):
        mob=np.asarray(self.model.draw("mobile",n=2048,seed=12)["qb_rushing_attempts"])
        pocket=np.asarray(self.model.draw("pocket",n=2048,seed=12)["qb_rushing_attempts"])
        self.assertGreater(mob.mean(),pocket.mean()+1.0)

    def test_yards_zero_atom_exists_from_zero_attempt_mixture(self):
        pocket=self.model.draw("pocket",n=2048,seed=3)
        self.assertGreater(sum(v==0 for v in pocket["qb_rushing_yards"]),0)
        self.assertGreater(sum(v<0 for v in pocket["qb_rushing_yards"]),0)
        self.assertGreater(sum(v>0 for v in pocket["qb_rushing_yards"]),0)

    def test_deterministic_same_seed_and_independent_player_runs(self):
        first=self.model.draw("mobile",n=256,seed=19)
        second=self.model.draw("mobile",n=256,seed=19)
        self.assertEqual(first,second)
        other=self.model.draw("pocket",n=256,seed=19)
        self.assertNotEqual(first["qb_rushing_attempts"],other["qb_rushing_attempts"])

    def test_2024_week1_training_rejects_all_current_year(self):
        rows=copy.deepcopy(self.rows)
        rows[0]["season"]=2024
        rows[0]["week"]=1
        with self.assertRaisesRegex(ComponentModelError,"current_or_future_QB_PBP_leak"):
            QBRushComponentModel(rows,forecast_year=2024,forecast_week=1)

    def test_2025_week2_allows_previous_week_only(self):
        rows=copy.deepcopy(self.rows)
        rows[0]["season"]=2025;rows[0]["week"]=1
        QBRushComponentModel(rows,forecast_year=2025,forecast_week=2)
        with self.assertRaisesRegex(ComponentModelError,"current_or_future"):
            QBRushComponentModel(rows,forecast_year=2025,forecast_week=1)

    def test_unreconciled_prior_kept_out_of_fit_with_explicit_count(self):
        rows=copy.deepcopy(self.rows)
        rows[0]["reconciled_to_weekly_stats"]=False
        m=QBRushComponentModel(rows,forecast_year=2024,forecast_week=1)
        self.assertEqual(m.reference["discarded_unreconciled"],1)
        self.assertEqual(m.reference["source_training_rows"],111)

    def test_aborted_and_ambiguous_component_retained(self):
        row=copy.deepcopy(self.rows[0])
        row["counts"]["other"]=1
        row["yards"]["other"]=-3.0
        row["official_attempts"]+=1
        row["official_rushing_yards"]-=3
        cc,yy,d=verify_component_row(row)
        self.assertEqual(cc["other"],1)
        self.assertEqual(yy["other"],-3.0)
        self.assertEqual(sum(cc.values()),row["official_attempts"])

    def test_wrong_boxscore_counts_or_yards_fail(self):
        for key,change in (("official_attempts",+1),("official_rushing_yards",+3)):
            row=copy.deepcopy(self.rows[0]);row[key]+=change
            with self.assertRaisesRegex(ComponentModelError,"does_not_reconcile"):
                verify_component_row(row)

    def test_duplicate_prior_player_game_rejected(self):
        rows=copy.deepcopy(self.rows)
        with self.assertRaisesRegex(ComponentModelError,"duplicate_component_player_game"):
            QBRushComponentModel(rows+[copy.deepcopy(rows[0])],
                                 forecast_year=2024,forecast_week=1)

    def test_rookie_cold_start_is_explicit_not_assumed_known(self):
        x=self.model.draw("newly_named_QB1",n=256,seed=8)
        self.assertTrue(x["QB_cold_start_no_prior_games"])
        self.assertEqual(x["parameters"]["n_appearance_history"],0)
        self.assertFalse(x["production_authorized"])

    def test_failed_publication_receipt_cannot_be_marked_verified(self):
        rows=copy.deepcopy(self.rows)
        rows[0]["source_original_capture_verified"]=True
        with self.assertRaisesRegex(ComponentModelError,"source_retrospective"):
            QBRushComponentModel(rows,forecast_year=2024,forecast_week=1)

    def test_donor_yards_without_count_rejected(self):
        row=copy.deepcopy(self.rows[1])
        row["yards"]["other"]=3.0
        with self.assertRaisesRegex(ComponentModelError,"yards_without_count"):
            verify_component_row(row)

    def test_invalid_seed_sample_or_id_rejected(self):
        for n in (0,32,4097):
            with self.assertRaisesRegex(ComponentModelError,"bad_draw_count"):
                self.model.draw("mobile",n=n)
        with self.assertRaisesRegex(ComponentModelError,"invalid_qb_player_id"):
            self.model.draw("")


if __name__=="__main__":unittest.main()
