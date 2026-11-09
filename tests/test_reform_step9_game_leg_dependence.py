"""Step 9 adversarial tests for hypothetical same-game leg dependence."""
from datetime import date,timedelta
import copy
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import reform_step9_game_leg_dependence as dep


def record(*,day="2026-11-08",game="G1",team="BUF",person="p1",
           stat="receptions",line=3.5,side="over",p=.7,
           hit=1,model="Consensus",sport="NFL",reliable=True):
    winning=side if hit else ("under" if side=="over" else "over")
    q_over=p if side=="over" else 1-p
    leg={"side":side,"p":p,"hit":hit,"winner":winning,
         "over":q_over,"under":1-q_over,"side_sum":1.}
    return {"sport":sport,"date":day,"game_id":game,
            "stat":stat,"outcome":winning,
            "models":{model:leg},
            "original_reliable":reliable,
            "contract":(sport,day+"T18:00:00Z",team,
                        "MIA" if team=="BUF" else "BUF",
                        person,person,stat,str(line))}


class LegDependenceTests(unittest.TestCase):
    def test_independent_two_leg_product_and_observed_joint(self):
        rows=[record(person="a",p=.7),record(person="b",p=.8)]
        by,excluded=dep.eligible_legs(rows,model="Consensus")
        self.assertEqual(excluded,{})
        pair=dep.combine_legs(by,length=2)
        self.assertEqual(len(pair),1)
        self.assertAlmostEqual(pair[0]["independence_probability"],.56)
        self.assertEqual(pair[0]["joint_hit"],1)
        self.assertAlmostEqual(pair[0]["excess_joint_hit_vs_independent"],.44)
        self.assertAlmostEqual(pair[0]["residual_product"],.06)
        self.assertEqual(pair[0]["pair_type"],"teammates")

    def test_mixed_side_opponent_pair_and_negative_result(self):
        rows=[record(person="a",side="over",hit=1),
              record(person="b",team="MIA",side="under",p=.8,hit=0)]
        by,_=dep.eligible_legs(rows,model="Consensus")
        pair=dep.combine_legs(by,length=2)[0]
        self.assertEqual(pair["pair_type"],"opponents")
        self.assertEqual(pair["direction_type"],"mixed_directions")
        self.assertEqual(pair["joint_hit"],0)
        self.assertAlmostEqual(pair["excess_joint_hit_vs_independent"],-.56)
        self.assertAlmostEqual(pair["residual_product"],-.24)

    def test_same_player_cross_stat_is_separate_dependent_category(self):
        rows=[record(person="a",stat="receptions",line=3.5),
              record(person="a",stat="targets",line=5.5)]
        by,_=dep.eligible_legs(rows,model="Consensus")
        pair=dep.combine_legs(by,length=2)[0]
        self.assertEqual(pair["pair_type"],"same_player_different_stats")

    def test_multiple_lines_same_player_and_stat_all_abstain(self):
        rows=[record(person="a",line=3.5),record(person="a",line=4.5),
              record(person="b",stat="receptions")]
        by,excluded=dep.eligible_legs(rows,model="Consensus")
        self.assertEqual(excluded["ambiguous_player_stat_multiple_lines"],2)
        self.assertEqual(sum(len(g) for g in by.values()),1)
        self.assertEqual(dep.combine_legs(by,length=2),[])

    def test_posthoc_duplicate_contract_is_fatal(self):
        row=record()
        with self.assertRaisesRegex(dep.LegDependenceError,"duplicate_original_settled_contract"):
            dep.eligible_legs([row,copy.deepcopy(row)],model="Consensus")

    def test_different_games_never_get_grouped_together(self):
        rows=[record(person="a",game="G1"),
              record(person="b",game="G2")]
        by,_=dep.eligible_legs(rows,model="Consensus")
        self.assertEqual(dep.combine_legs(by,length=2),[])

    def test_nonunit_original_probability_is_excluded(self):
        row=record()
        row["models"]["Consensus"]["under"]=.27
        by,rejected=dep.eligible_legs([row],model="Consensus")
        self.assertEqual(rejected,{"noncomplementary_model_probability":1})
        self.assertEqual(sum(len(g) for g in by.values()),0)

    def test_unreliable_history_gate_and_confidence_threshold(self):
        rows=[record(person="a",p=.55,reliable=True),
              record(person="b",p=.63,reliable=False),
              record(person="c",p=.71,reliable=True)]
        b,reject=dep.eligible_legs(rows,model="Consensus",
                                    historically_reliable_only=True,
                                    minimum_probability=.60)
        self.assertEqual(sum(len(g) for g in b.values()),1)
        self.assertEqual(reject["historically_unqualified"],1)
        self.assertEqual(reject["under_confidence_floor_or_inconsistent_selected_side"],1)

    def test_outcome_side_disagreement_raises_instead_of_relabeling(self):
        row=record(hit=1)
        row["models"]["Consensus"]["hit"]=0
        with self.assertRaisesRegex(dep.LegDependenceError,"mismatched_official_outcome"):
            dep.eligible_legs([row],model="Consensus")

    def test_one_game_many_pair_combinations_still_no_interval(self):
        rows=[record(person=f"p{i}",p=.55+i*.001,hit=(i%2))
              for i in range(18)]
        b,_=dep.eligible_legs(rows,model="Consensus")
        pairs=dep.combine_legs(b,length=2)
        self.assertEqual(len(pairs),153)
        summary=dep._summary(pairs)
        self.assertEqual(summary["independent_games"],1)
        self.assertEqual(summary["independent_dates"],1)
        self.assertIsNone(summary["interval_95"])
        self.assertEqual(summary["status"],"descriptive_low_independent_date_coverage")

    def test_date_block_interval_requires_independent_dates(self):
        start=date(2026,1,1)
        rows=[]
        for i in range(22):
            day=(start+timedelta(days=i)).isoformat()
            rows.extend(record(day=day,game=f"G{i}",person=f"p{n}",
                               p=.62,hit=int((i+n)%3>0)) for n in range(8))
        b,_=dep.eligible_legs(rows,model="Consensus")
        pairs=dep.combine_legs(b,length=2)
        one=dep._summary(pairs,bootstraps=120)
        two=dep._summary(pairs,bootstraps=120)
        self.assertEqual(one,two)
        self.assertEqual(one["independent_games"],22)
        self.assertEqual(one["independent_dates"],22)
        self.assertEqual(one["status"],"descriptive_date_block_interval_not_production_covariance")
        self.assertEqual(len(one["interval_95"]),2)

    def test_three_leg_joint_observed_vs_product_not_fitted(self):
        rows=[record(person="a",p=.7),record(person="b",p=.8),
              record(person="c",p=.6)]
        by,_=dep.eligible_legs(rows,model="Consensus")
        triple=dep.combine_legs(by,length=3)
        self.assertEqual(len(triple),1)
        self.assertAlmostEqual(triple[0]["independence_probability"],.336)
        self.assertEqual(triple[0]["joint_hit"],1)
        self.assertIsNone(triple[0]["residual_product"])

    def test_report_policies_never_deploy_or_pool_old_policy(self):
        same=[record(person="a"),record(person="b")]
        old=[record(person="c",model="Engine_A",day="2026-11-06"),
             record(person="d",model="Engine_A",day="2026-11-06")]
        def stable_read(_):
            return {}, "hash"
        with patch.object(dep,"load_nfl_slate",return_value=(same,{})), \
             patch.object(dep,"load_historical",return_value=(old,{})), \
             patch.object(dep,"read_json",side_effect=stable_read):
            report=dep.audit(frozen="x",settlement="x",pinned="x",
                             historical="x",archive_root="x")
        self.assertFalse(report["production_changed"])
        self.assertFalse(report["entry_probability_model_deployed"])
        self.assertFalse(report["training_started"])
        self.assertTrue(report["independence_is_not_validated"])
        self.assertEqual(report["cohorts"]["current_2026_11_08_original_60_40"]["cohorts"]["0.50"]["combinations"]["2"]["all"]["hypothetical_combinations"],1)


if __name__=="__main__":
    unittest.main()
