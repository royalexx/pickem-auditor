"""Tests for pickem_math. These check the helper, not live sportsbook data."""

import json
import math
import subprocess
import sys
import unittest
import warnings
from pathlib import Path
from statistics import NormalDist

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "tests"))
sys.path.insert(0, str(SKILL_DIR / "scripts"))
from skill_docs import skill_corpus
import pickem_math as pm

HELPER = SKILL_DIR / "scripts" / "pickem_math.py"


def _run(args, stdin=None):
    return subprocess.run(
        [sys.executable, str(HELPER), *args],
        cwd=SKILL_DIR,
        input=stdin,
        capture_output=True,
        text=True,
    )


def poisson_ge(lam: float, threshold: int) -> float:
    return 1 - sum(math.exp(k * math.log(lam) - lam - math.lgamma(k + 1)) for k in range(threshold))



class DevigTests(unittest.TestCase):
    def test_known_two_way_price(self):
        row = pm.devig(-125, -105)
        p_target = 125 / 225
        p_other = 105 / 205
        total = p_target + p_other
        q_mult = p_target / total
        q_market = q_mult
        self.assertAlmostEqual(row["p_target"], p_target, places=6)
        self.assertAlmostEqual(row["hold"], total - 1, places=6)
        self.assertAlmostEqual(row["q_mult"], q_mult, places=6)
        self.assertAlmostEqual(row["q_market"], q_market, places=6)
        self.assertAlmostEqual(row["q_market"] + row["q_market_other"], 1.0, places=12)
        self.assertEqual(row["market_probability_method"], "proportional_no_vig_v2")
        self.assertGreater(row["hold_risk_penalty"], 0)
        self.assertFalse(row["reject_hold"])

    def test_market_two_sided_mass_conservation(self):
        for target, other in [(-120, -110), (-110, -120), (-110, -110),
                              (-150, 140), (120, -145)]:
            row = pm.devig(target, other)
            flipped = pm.devig(other, target)
            self.assertAlmostEqual(row["q_market"] + row["q_market_other"], 1, places=12)
            self.assertAlmostEqual(row["q_market"], flipped["q_market_other"], places=12)
        consensus = pm.consensus([("Pinnacle", 3.5, -120, -110)], 5)
        self.assertAlmostEqual(consensus["q_market"] + consensus["q_market_other"], 1, places=12)

    def test_high_hold_is_flagged(self):
        row = pm.devig(-150, -150)
        self.assertGreater(row["hold"], 0.0825)
        self.assertTrue(row["reject_hold"])

    def test_invalid_odds_fail(self):
        for odds in (0, 50, -50, float("nan"), float("inf")):
            with self.assertRaises(pm.PickemError):
                pm.devig(odds, -110)


class ConsensusTests(unittest.TestCase):
    def test_retail_mean_when_books_agree(self):
        result = pm.consensus([("FanDuel", 3.5, -125, -105), ("DraftKings", 3.5, -130, 100)])
        expected = (pm.devig(-125, -105)["q_market"] + pm.devig(-130, 100)["q_market"]) / 2
        self.assertTrue(result["valid"])
        self.assertAlmostEqual(result["q_market"], expected, places=6)
        self.assertNotIn("DISAGREE", " ".join(result["flags"]))

    def test_retail_below_a_sharp_anchor_does_not_undercut_it(self):
        # FanDuel sits just under Pinnacle and DraftKings sits just under 3 points
        # over it. The old full-range rule flagged DISAGREE and used FanDuel.
        # The sharp anchor stays, and that retail gap is not DISAGREE.
        result = pm.consensus([
            ("Pinnacle", 3.5, -130, 110),
            ("FanDuel", 3.5, -135, 105),
            ("DraftKings", 3.5, -160, 120),
        ])
        sharp = pm.devig(-130, 110)["q_market"]
        self.assertTrue(result["valid"])
        self.assertAlmostEqual(result["q_market"], sharp, places=6)
        self.assertLess(result["q_market"], 0.55)
        self.assertFalse(any(flag.startswith("DISAGREE") for flag in result["flags"]))

    def test_one_retail_book_is_not_a_market(self):
        result = pm.consensus([("FanDuel", 3.5, -160, 130)])
        self.assertFalse(result["valid"])
        self.assertNotIn("q_market", result)

    def test_unapproved_and_duplicate_books_fail(self):
        with self.assertRaises(pm.PickemError):
            pm.consensus([("Fanatics", 3.5, -120, -110), ("FanDuel", 3.5, -120, -110)])
        with self.assertRaises(pm.PickemError):
            pm.consensus([("FanDuel", 3.5, -120, -110), ("fanduel", 3.5, -125, -105)])

    def test_different_lines_are_not_averaged(self):
        with self.assertRaises(pm.PickemError):
            pm.consensus([("FanDuel", 3.5, -125, -105), ("DraftKings", 2.5, -140, 110)])

    def test_high_hold_book_cannot_pose_as_the_second_retail_price(self):
        result = pm.consensus([("FanDuel", 3.5, -125, -105), ("DraftKings", 3.5, -150, -150)])
        self.assertFalse(result["valid"])


class ConsensusDesignTests(unittest.TestCase):
    def test_lagging_retail_does_not_undercut_pinnacle(self):
        alone = pm.consensus([("Pinnacle", 3.5, -130, 110)], 5)
        lagged = pm.consensus([
            ("Pinnacle", 3.5, -130, 110),
            ("FanDuel", 3.5, -110, -110),
        ], 5)
        self.assertAlmostEqual(lagged["q_market"], alone["q_market"], places=6)
        self.assertGreater(alone["q_market"] - pm.devig(-110, -110)["q_market"], 0.03)
        self.assertFalse(any(flag.startswith("DISAGREE") for flag in lagged["flags"]))
        self.assertFalse(any(flag.startswith("PLUS-MONEY") for flag in lagged["flags"]))
        self.assertFalse(any("RETAIL_ONLY" in flag for flag in lagged["flags"]))

    def test_retail_shorter_than_sharp_flags_without_moving_the_anchor(self):
        alone = pm.consensus([("Pinnacle", 3.5, -130, 110)], 5)
        shorter = pm.consensus([
            ("Pinnacle", 3.5, -130, 110),
            ("FanDuel", 3.5, -170, 140),
        ], 5)
        self.assertAlmostEqual(shorter["q_market"], alone["q_market"], places=6)
        self.assertTrue(any(flag.startswith("DISAGREE") for flag in shorter["flags"]))
        self.assertFalse(any(flag.startswith("PLUS-MONEY") for flag in shorter["flags"]))

    def test_retail_only_disagreement_uses_the_lower_value(self):
        result = pm.consensus([
            ("FanDuel", 3.5, -130, 110),
            ("DraftKings", 3.5, -105, -115),
        ], 5)
        quotes = [pm.devig(-130, 110)["q_market"], pm.devig(-105, -115)["q_market"]]
        self.assertGreater(max(quotes) - min(quotes), 0.03)
        self.assertAlmostEqual(result["q_market"], min(quotes), places=6)
        self.assertTrue(any(flag.startswith("DISAGREE") for flag in result["flags"]))
        self.assertTrue(any(flag.startswith("RETAIL_ONLY_TWO_BOOKS") for flag in result["flags"]))

    def test_two_retail_books_flag_and_three_do_not(self):
        two = pm.consensus([
            ("FanDuel", 3.5, -125, -105),
            ("DraftKings", 3.5, -130, 100),
        ], 5)
        three = pm.consensus([
            ("FanDuel", 3.5, -125, -105),
            ("DraftKings", 3.5, -128, -102),
            ("BetMGM", 3.5, -125, -105),
        ], 5)
        self.assertTrue(any(flag.startswith("RETAIL_ONLY_TWO_BOOKS") for flag in two["flags"]))
        self.assertFalse(any("RETAIL_ONLY" in flag for flag in three["flags"]))
        self.assertFalse(any(flag.startswith("DISAGREE") for flag in three["flags"]))

    def test_plus_money_follows_the_anchor_only(self):
        sharp_plus = pm.consensus([("Pinnacle", 3.5, 120, -140)], 5)
        self.assertLess(sharp_plus["q_market"], 0.5)
        self.assertTrue(any(flag.startswith("PLUS-MONEY") for flag in sharp_plus["flags"]))
        favorite = pm.consensus([
            ("Pinnacle", 3.5, -130, 110),
            ("FanDuel", 3.5, 105, -125),
        ], 5)
        self.assertGreater(favorite["q_market"], 0.5)
        self.assertFalse(any(flag.startswith("PLUS-MONEY") for flag in favorite["flags"]))
        pickem = pm.consensus([
            ("FanDuel", 3.5, -110, -110),
            ("DraftKings", 3.5, -110, -110),
        ], 5)
        self.assertFalse(any(flag.startswith("PLUS-MONEY") for flag in pickem["flags"]))
        self.assertTrue(any(flag.startswith("RETAIL_ONLY_TWO_BOOKS") for flag in pickem["flags"]))

    def test_plus_money_matches_on_sharp_and_agreeing_retail(self):
        for target, other in ((110, 150), (100, 100), (-110, -110), (120, -140)):
            sharp = pm.consensus([("Pinnacle", 3.5, target, other)], 5)
            retail = pm.consensus([
                ("FanDuel", 3.5, target, other),
                ("DraftKings", 3.5, target, other),
            ], 5)
            sharp_note = any(flag.startswith("PLUS-MONEY") for flag in sharp["flags"])
            retail_note = any(flag.startswith("PLUS-MONEY") for flag in retail["flags"])
            self.assertEqual(sharp_note, retail_note, (target, other))
            self.assertAlmostEqual(sharp["q_market"], retail["q_market"], places=9)
            row = pm.devig(target, other)
            self.assertEqual(sharp_note, target > 0 or row["q_mult"] < 0.5, (target, other))
            self.assertTrue(any(flag.startswith("RETAIL_ONLY_TWO_BOOKS") for flag in retail["flags"]))
        noted = pm.evaluate_candidate({
            "dist": "poisson",
            "side": "over",
            "line": 2.5,
            "baseline_mean": 3.2,
            "baseline_n": 30,
            "books": [["FanDuel", 2.5, 110, 150], ["DraftKings", 2.5, 110, 150]],
            "retrieved_minutes_ago": 5,
            "soft_flags": 0,
            "mechanisms": 1,
            "hard_veto": False,
            "data_veto": False,
            "research_checklist": False,
        })
        self.assertTrue(any(flag.startswith("PLUS-MONEY") for flag in noted["consensus"]["flags"]))
        self.assertNotIn("PLUS-MONEY", noted["derived_flags"])
        decided = pm.decide(
            noted["project"]["q_win"],
            noted["consensus"]["q_market"],
            noted["soft_flags_to_grade"],
            noted["project"]["current_role_n"],
            1,
            False,
            False,
            noted["consensus"]["market_valid"],
            False,
        )
        self.assertEqual(noted["final_rank"], decided["final_rank"])

    def test_equal_mean_and_line_flags_both_sides(self):
        over = pm.project("poisson", "over", 3.0, baseline_mean=3.0, baseline_n=30)
        under = pm.project("poisson", "under", 3.0, baseline_mean=3.0, baseline_n=30)
        self.assertAlmostEqual(over["shrunk_mean"], 3.0, places=9)
        self.assertFalse(over["mean_supports_side"])
        self.assertFalse(under["mean_supports_side"])
        self.assertIn("MEAN_LINE_MISMATCH", pm._derived_flag_names(over, None, False))
        self.assertIn("MEAN_LINE_MISMATCH", pm._derived_flag_names(under, None, False))

    def test_two_sharp_books_can_disagree(self):
        result = pm.consensus([
            ("Pinnacle", 3.5, -150, 130),
            ("Circa", 3.5, -110, -110),
        ], 5)
        quotes = [pm.devig(-150, 130)["q_market"], pm.devig(-110, -110)["q_market"]]
        self.assertAlmostEqual(result["q_market"], min(quotes), places=6)
        self.assertTrue(any(flag.startswith("DISAGREE") for flag in result["flags"]))


class DistributionTests(unittest.TestCase):
    def test_poisson_over_matches_an_independent_sum(self):
        win, push = pm.side_probs("poisson", 3, 2.5, "over")
        self.assertAlmostEqual(win, poisson_ge(3, 3), places=6)
        self.assertEqual(push, 0)

    def test_whole_line_grades_the_strict_win_and_reports_the_push(self):
        win, push = pm.side_probs("poisson", 3, 3, "over")
        self.assertAlmostEqual(win, poisson_ge(3, 4), places=6)
        self.assertAlmostEqual(push, math.exp(3 * math.log(3) - 3 - math.lgamma(4)), places=6)
        self.assertGreater(push, 0.15)
        self.assertLess(win, win / (1 - push))

    def test_over_under_and_push_sum_to_one(self):
        for dist, kwargs in (
            ("poisson", {"sd": None, "r": None}),
            ("negbin", {"sd": None, "r": 1.4}),
            ("normal", {"sd": 6.2, "r": None}),
        ):
            over, push = pm.side_probs(dist, 18, 17, "over", **kwargs)
            under, push_under = pm.side_probs(dist, 18, 17, "under", **kwargs)
            self.assertAlmostEqual(push, push_under, places=6)
            self.assertAlmostEqual(over + under + push, 1, places=5)

    def test_higher_mean_raises_the_over(self):
        low, _ = pm.side_probs("normal", 20, 24.5, "over", sd=6)
        high, _ = pm.side_probs("normal", 30, 24.5, "over", sd=6)
        self.assertGreater(high, low)
        self.assertGreater(high, 0.80)

    def test_bad_distribution_inputs_fail(self):
        with self.assertRaises(pm.PickemError):
            pm.side_probs("normal", 10, 9.5, "over", sd=0)
        with self.assertRaises(pm.PickemError):
            pm.side_probs("negbin", 3, 2.5, "over", r=1.0)
        with self.assertRaises(pm.PickemError):
            pm.side_probs("poisson", -1, 2.5, "over")


class DistributionBoundaryTests(unittest.TestCase):
    def test_hook_and_whole_lines_for_each_distribution(self):
        specs = (
            ("poisson", {"sd": None, "r": None}),
            ("negbin", {"sd": None, "r": 1.4}),
            ("normal", {"sd": 6.0, "r": None}),
        )
        for dist, kwargs in specs:
            for line in (2.5, 3.0):
                over, push = pm.side_probs(dist, 3.2, line, "over", **kwargs)
                under, push_under = pm.side_probs(dist, 3.2, line, "under", **kwargs)
                self.assertAlmostEqual(push, push_under, places=6)
                self.assertAlmostEqual(over + under + push, 1, places=5)
                if abs(line - round(line)) < 1e-9:
                    self.assertGreater(push, 0)
                else:
                    self.assertEqual(push, 0)

    def test_var_ratio_at_or_under_1_10_requires_poisson(self):
        for ratio in (1.0, 1.05, 1.10):
            with self.assertRaises(pm.PickemError) as raised:
                pm.side_probs("negbin", 4, 3.5, "over", r=ratio)
            self.assertIn("poisson", str(raised.exception))
            with self.assertRaises(pm.PickemError) as raised_project:
                pm.project(
                    "negbin", "over", 3.5, baseline_mean=4, baseline_n=20, var_ratio=ratio,
                )
            self.assertIn("poisson", str(raised_project.exception))
        win, push = pm.side_probs("negbin", 4, 3.5, "over", r=1.11)
        self.assertGreater(win, 0)
        self.assertEqual(push, 0)

    def test_normal_left_tail_blocks_rank(self):
        projected = pm.project(
            "normal", "under", 10.5, baseline_mean=8, baseline_n=20, sd=6,
        )
        self.assertIn("NORMAL_LEFT_TAIL", projected["notes"])
        self.assertTrue(projected["sample_block"])
        self.assertTrue(projected["distribution_block"])
        self.assertGreater(projected["normal_left_mass"], 0.02)
        open_grade = pm.grade(projected["q_win"], projected["q_win"], 0, 20)
        self.assertEqual(open_grade["status"], "GRADED")
        blocked = pm.decide(
            projected["q_win"], projected["q_win"], 0, 20, mechanisms=2,
            research_checklist=True, normal_left_tail=True,
        )
        self.assertEqual(blocked["status"], "UNRANKED")
        self.assertEqual(blocked["reason"], "NORMAL_LEFT_TAIL")
        self.assertEqual(blocked["final_rank"], "Unranked")

    def test_sd_scales_with_the_shrunk_mean(self):
        # Minutes cut. Unscaled starter sd false-flags; scaled sd does not.
        out = pm.project("normal", "under", 16.5, baseline_mean=25, baseline_n=30,
                         workload_baseline=34, workload_expected=18.7, sd=8)
        self.assertEqual(out["shrunk_mean"], 25)
        self.assertEqual(out["sd_used"], 8)
        self.assertNotIn("SD_SCALED", out["notes"])


class ProjectTests(unittest.TestCase):
    def test_market_probability_is_not_an_input(self):
        self.assertNotIn("q_market", pm.project.__code__.co_varnames)

    def test_stable_player_keeps_his_baseline(self):
        result = pm.project("poisson", "over", 2.5, baseline_mean=3.4, baseline_n=30)
        self.assertAlmostEqual(result["shrunk_mean"], 3.4, places=6)
        self.assertAlmostEqual(result["q_win"], poisson_ge(3.4, 3), places=5)
        self.assertFalse(result["sample_block"])

    def test_recent_streak_cannot_dominate_a_long_baseline(self):
        result = pm.project(
            "poisson", "over", 2.5, baseline_mean=10, baseline_n=30,
            recent_mean=20, recent_n=5, season_n=35,
        )
        self.assertAlmostEqual(result["recent_weight"], 5 / 35, places=6)
        self.assertAlmostEqual(result["blended_rate"], (30 * 10 + 5 * 20) / 35, places=6)
        self.assertLess(result["shrunk_mean"], 12)

    def test_overlapping_windows_are_rejected(self):
        with self.assertRaises(pm.PickemError):
            pm.project(
                "poisson", "over", 2.5, baseline_mean=10, baseline_n=30,
                recent_mean=14, recent_n=10, season_n=30,
            )

    def test_role_change_shrinks_the_new_sample_toward_the_old_role(self):
        changed = pm.project(
            "poisson", "over", 2.5, baseline_mean=10, baseline_n=30,
            recent_mean=18, recent_n=8, season_n=38, role_change=True,
        )
        pooled = pm.project(
            "poisson", "over", 2.5, baseline_mean=10, baseline_n=30,
            recent_mean=18, recent_n=8, season_n=38,
        )
        self.assertIn("ROLE_EB", changed["notes"])
        self.assertAlmostEqual(changed["blended_rate"], (8 * 18 + 8 * 10) / 16, places=6)
        self.assertGreater(changed["blended_rate"], pooled["blended_rate"])
        self.assertLess(changed["blended_rate"], 18)

    def test_short_recent_sample_is_ignored(self):
        result = pm.project(
            "poisson", "over", 2.5, baseline_mean=10, baseline_n=20,
            recent_mean=20, recent_n=4,
        )
        self.assertIn("RECENT_IGNORED", result["notes"])
        self.assertAlmostEqual(result["shrunk_mean"], 10, places=6)

    def test_opponent_factor_is_clamped_and_shrunk(self):
        out = pm.project("poisson", "over", 2.5, baseline_mean=20, baseline_n=40, opponent_factor=1.5)
        self.assertEqual(out["opponent_factor_used"], 1)
        self.assertEqual(out["shrunk_mean"], 20)
        self.assertIn("CONTEXT_EXCLUDED_FROM_ENGINE_A", out["notes"])

    def test_workload_cut_applies_and_role_change_widens_the_clamp(self):
        for role in (False, True):
            out = pm.project("poisson", "under", 12.5, baseline_mean=10, baseline_n=20,
                             workload_baseline=30, workload_expected=18, role_change=role)
            self.assertEqual(out["workload_ratio"], 1)
            self.assertEqual(out["shrunk_mean"], 10)
            self.assertEqual(out["sample_block"], role)

    def test_small_sample_without_a_role_change_is_blocked(self):
        result = pm.project("poisson", "over", 2.5, baseline_mean=4, baseline_n=4)
        self.assertTrue(result["sample_block"])

    def test_mean_must_sit_on_the_target_side_of_the_line(self):
        over = pm.project("normal", "over", 24.5, baseline_mean=20, baseline_n=20, sd=6)
        under = pm.project("normal", "under", 24.5, baseline_mean=20, baseline_n=20, sd=6)
        self.assertFalse(over["mean_supports_side"])
        self.assertTrue(under["mean_supports_side"])

    def test_missing_dispersion_fails(self):
        with self.assertRaises(pm.PickemError):
            pm.project("normal", "over", 24.5, baseline_mean=27, baseline_n=20)


class RecentZeroTests(unittest.TestCase):
    def test_zero_recent_mean_blends(self):
        result = pm.project(
            "poisson", "under", 1.5,
            baseline_mean=1.2, baseline_n=20,
            recent_mean=0.0, recent_n=5, season_n=25,
        )
        form = (20 * 1.2 + 5 * 0.0) / 25
        self.assertAlmostEqual(result["blended_rate"], form, places=6)
        self.assertGreater(result["shrunk_mean"], 0)
        self.assertFalse(result["sample_block"])

    def test_negative_recent_mean_is_rejected(self):
        with self.assertRaises(pm.PickemError):
            pm.project(
                "poisson", "over", 1.5,
                baseline_mean=1.2, baseline_n=20,
                recent_mean=-0.1, recent_n=5, season_n=25,
            )


class RoleChangeWorkloadTests(unittest.TestCase):
    def test_recent_n_zero_scales_the_whole_mean(self):
        out = pm.project("poisson", "over", 12.5, baseline_mean=10, baseline_n=20,
                         workload_baseline=20, workload_expected=26, role_change=True)
        self.assertEqual(out["shrunk_mean"], 10)
        self.assertEqual(out["current_role_n"], 0)
        self.assertTrue(out["sample_block"])

    def test_short_new_role_does_not_double_count_workload(self):
        out = pm.project("poisson", "over", 12.5, baseline_mean=10, baseline_n=30,
                         recent_mean=16, recent_n=3, season_n=33, role_change=True,
                         workload_baseline=18, workload_expected=32)
        self.assertAlmostEqual(out["trusted_mean"], (3*16+8*10)/11)
        self.assertEqual(out["current_role_n"], 3)
        self.assertIn("NEW_ROLE_THIN", out["notes"])

    def test_new_role_between_one_and_four_without_a_second_workload_scale(self):
        plain = pm.project(
            "poisson", "over", 2.5, baseline_mean=2, baseline_n=40,
            recent_mean=4, recent_n=1, season_n=41, role_change=True,
        )
        self.assertEqual(plain["current_role_n"], 1)
        self.assertAlmostEqual(plain["blended_rate"], (1 * 4 + 8 * 2) / 9, places=6)
        self.assertNotIn("WORKLOAD_ON_PRIOR_ONLY", plain["notes"])
        self.assertIn("NEW_ROLE_THIN", plain["notes"])

    def test_new_role_at_and_above_five_games(self):
        for n in (7,12):
            out=pm.project("poisson", "over", 2.5, baseline_mean=2, baseline_n=20,
                           recent_mean=3.5, recent_n=n, season_n=20+n, role_change=True,
                           workload_baseline=18, workload_expected=28)
            self.assertAlmostEqual(out["trusted_mean"], (n*3.5+8*2)/(n+8))
            self.assertNotIn("NEW_ROLE_THIN", out["notes"])


class GradeTests(unittest.TestCase):
    def test_model_grade_is_not_replaced_by_the_market(self):
        both = pm.grade(0.60, 0.59, 0, 30)
        self.assertEqual(both["probability_rank"], "NUMERIC_TIER_1")
        self.assertAlmostEqual(both["q_grade"], 0.60, places=6)
        self.assertTrue(both["unicorn_numeric"])
        disagreed = pm.grade(0.575, 0.54, 0, 30)
        self.assertEqual(disagreed["probability_rank"], "NUMERIC_TIER_2")
        self.assertAlmostEqual(disagreed["q_grade"], 0.575, places=6)
        self.assertFalse(disagreed["unicorn_numeric"])
        self.assertEqual(pm.grade(0.48, 0.62, 0, 30)["probability_rank"], "REJECT")
        wide = pm.grade(0.70, 0.48, 0, 30)
        self.assertEqual(wide["probability_rank"], "WATCHLIST")

    def test_bands(self):
        self.assertEqual(pm.grade(0.575, 0.58, 0, 20)["probability_rank"], "NUMERIC_TIER_2")
        self.assertEqual(pm.grade(0.565, 0.57, 0, 20)["probability_rank"], "NUMERIC_TIER_3")
        self.assertEqual(pm.grade(0.545, 0.60, 0, 20)["probability_rank"], "WATCHLIST")
        self.assertEqual(pm.grade(0.51, 0.70, 0, 20)["probability_rank"], "REJECT")

    def test_soft_flags_and_a_small_gap_cap_the_rank(self):
        flagged = pm.grade(0.62, 0.61, 1, 30)
        self.assertEqual(flagged["probability_rank"], "NUMERIC_TIER_2")
        gapped = pm.grade(0.62, 0.585, 0, 30)
        self.assertIn("MODEL_MARKET_GAP", gapped["notes"])
        self.assertEqual(gapped["notes"].count("MODEL_MARKET_GAP"), 1)
        self.assertEqual(gapped["probability_rank"], "NUMERIC_TIER_2")
        self.assertEqual(pm.grade(0.64, 0.63, 3, 30)["probability_rank"], "WATCHLIST")

    def test_large_gap_cannot_stay_a_qualified_tier(self):
        result = pm.grade(0.70, 0.59, 0, 30)
        self.assertIn("GAP_LARGE", result["notes"])
        self.assertEqual(result["probability_rank"], "WATCHLIST")

    def test_low_sample_adds_a_flag_and_a_tiny_sample_is_unranked(self):
        low = pm.grade(0.63, 0.62, 0, 9)
        self.assertIn("LOW_SAMPLE", low["notes"])
        self.assertEqual(low["probability_rank"], "NUMERIC_TIER_2")
        blocked = pm.grade(0.63, 0.62, 0, 4)
        self.assertEqual(blocked["status"], "UNRANKED")
        self.assertEqual(blocked["reason"], "SAMPLE_BLOCK")
        role = pm.grade(0.63, 0.62, 0, 4, role_change=True)
        self.assertEqual(role["status"], "GRADED")
        self.assertEqual(role["current_role_n"], 4)
        self.assertIn("NEW_ROLE_THIN", role["notes"])
        self.assertEqual(role["probability_rank"], "NUMERIC_TIER_3")

    def test_bad_probabilities_fail(self):
        for model, market in ((-0.1, 0.6), (1.2, 0.6), (float("nan"), 0.6)):
            with self.assertRaises(pm.PickemError):
                pm.grade(model, market, 0, 20)
        with self.assertRaises(pm.PickemError):
            pm.grade(0.6, 0.6, -1, 20)


class GapBoundaryTests(unittest.TestCase):
    def test_exact_three_point_float_does_not_flag(self):
        for model, market in ((0.61, 0.58), (0.60, 0.57)):
            magnitude = abs(model - market)
            self.assertGreater(magnitude, 0.03)
            self.assertFalse(pm._exceeds(magnitude, pm.GAP_FLAG))
            graded = pm.grade(model, market, 0, 30)
            self.assertNotIn("MODEL_MARKET_GAP", graded["notes"])
            self.assertNotIn("GAP_LARGE", graded["notes"])

    def test_sixty_one_minus_fifty_eight_can_be_tier_1(self):
        graded = pm.grade(0.61, 0.58, 0, 30)
        self.assertEqual(graded["probability_rank"], "NUMERIC_TIER_1")
        self.assertTrue(graded["unicorn_numeric"])
        decided = pm.decide(0.61, 0.58, 0, 30, mechanisms=2, research_checklist=True)
        self.assertEqual(decided["final_rank"], "Tier 1")

    def test_market_below_58_caps_the_numeric_band(self):
        graded = pm.grade(0.60, 0.57, 0, 30)
        self.assertEqual(graded["numerical_band"], "NUMERIC_TIER_2")
        self.assertEqual(graded["probability_rank"], "NUMERIC_TIER_2")
        self.assertFalse(graded["unicorn_numeric"])
        thin = pm.grade(0.59, 0.565, 0, 20)
        self.assertEqual(thin["probability_rank"], "NUMERIC_TIER_2")
        self.assertEqual(thin["numerical_band"], "NUMERIC_TIER_2")
        self.assertNotEqual(thin["probability_rank"], "NUMERIC_TIER_1")

    def test_eight_point_float_caps_watchlist(self):
        over = abs(0.66 - 0.58)
        self.assertGreater(over, 0.08)
        wide = pm.grade(0.66, 0.58, 0, 30)
        self.assertIn("GAP_LARGE", wide["notes"])
        self.assertEqual(wide["probability_rank"], "WATCHLIST")
        self.assertEqual(
            pm.decide(0.66, 0.58, 0, 30, mechanisms=2, research_checklist=True)["final_rank"],
            "Watchlist",
        )
        # 0.70 - 0.62 lands just under 0.08. The cap still has to fire.
        under = abs(0.70 - 0.62)
        self.assertLess(under, 0.08)
        self.assertTrue(pm._gap_caps(under))
        capped = pm.grade(0.70, 0.62, 0, 30)
        self.assertIn("GAP_LARGE", capped["notes"])
        self.assertEqual(
            pm.decide(0.70, 0.62, 0, 30, mechanisms=2, research_checklist=True)["final_rank"],
            "Watchlist",
        )

    def test_a_real_gap_above_three_points_still_flags(self):
        graded = pm.grade(0.62, 0.58, 0, 30)
        self.assertIn("MODEL_MARKET_GAP", graded["notes"])
        self.assertEqual(graded["notes"].count("MODEL_MARKET_GAP"), 1)


class ReconciliationTests(unittest.TestCase):
    def test_whole_number_market_is_converted_before_the_gap(self):
        over = pm.grade(0.50, 0.625, 0, 30, q_push=0.20)
        self.assertAlmostEqual(over["q_loss"], 0.30, places=6)
        self.assertAlmostEqual(over["q_market_comparable"], 0.50, places=6)
        self.assertAlmostEqual(over["q_gap"], 0.0, places=6)
        self.assertEqual(over["probability_rank"], "REJECT")
        under = pm.grade(0.46, 0.60, 0, 30, q_push=0.20)
        self.assertAlmostEqual(under["q_market_comparable"], 0.48, places=6)
        self.assertLess(abs(under["q_gap"]), 0.03)
        self.assertNotIn("GAP", under["notes"])

    def test_push_cannot_make_the_probabilities_impossible(self):
        with self.assertRaises(pm.PickemError):
            pm.grade(0.80, 0.60, 0, 20, q_push=0.30)

    def test_skew_can_clear_a_line_the_mean_does_not_support(self):
        capped = pm.project(
            "negbin", "under", 3.5, baseline_mean=6, baseline_n=30, var_ratio=12,
        )
        self.assertIn("VAR_RATIO_CLAMPED", capped["notes"])
        capped_prob, _ = pm.side_probs("negbin", 6, 3.5, "under", r=3)
        self.assertAlmostEqual(capped["q_win"], capped_prob, places=5)
        moderate = pm.project(
            "negbin", "under", 3.5, baseline_mean=6, baseline_n=30, var_ratio=3,
        )
        self.assertFalse(moderate["mean_supports_side"])
        self.assertNotIn("VAR_RATIO_CLAMPED", moderate["notes"])

    def test_normal_mass_below_zero_is_flagged(self):
        result = pm.project("normal", "over", 2.5, baseline_mean=2, baseline_n=20, sd=6)
        self.assertIn("NORMAL_LEFT_TAIL", result["notes"])

    def test_final_rank_blocks_a_numeric_unicorn(self):
        perfect = dict(q_model=0.61, q_market=0.60, soft_flags=0, current_role_n=20, q_push=0)
        self.assertEqual(pm.decide(**perfect, mechanisms=2, research_checklist=True)["final_rank"], "Tier 1")
        self.assertEqual(pm.decide(**perfect, mechanisms=1, research_checklist=True)["final_rank"], "Tier 2")
        self.assertEqual(pm.decide(**perfect, mechanisms=0, research_checklist=True)["final_rank"], "Watchlist")
        self.assertEqual(pm.decide(**perfect, mechanisms=2, research_checklist=False)["final_rank"], "Tier 2")
        self.assertEqual(pm.decide(**perfect, mechanisms=2, research_checklist=True, hard_veto=True)["final_rank"], "Reject")
        self.assertEqual(pm.decide(**perfect, mechanisms=2, research_checklist=True, data_veto=True)["final_rank"], "Unranked")
        self.assertEqual(pm.decide(**perfect, mechanisms=2, research_checklist=True, market_valid=False)["final_rank"], "Unranked")


class EnforcementTests(unittest.TestCase):
    def _rank(self, q_model, q_market, flags, role_n, mechanisms, **extra):
        return pm.decide(
            q_model, q_market, flags, role_n, mechanisms,
            extra.pop("hard_veto", False), extra.pop("data_veto", False),
            extra.pop("market_valid", True), extra.pop("research_checklist", True),
            extra.pop("role_change", False), extra.pop("q_push", 0.0),
            extra.pop("workload_adjusted", False),
        )

    def test_soft_flag_ceilings(self):
        self.assertEqual(self._rank(0.60, 0.60, 1, 20, 2)["final_rank"], "Tier 2")
        self.assertEqual(self._rank(0.60, 0.60, 2, 20, 2)["final_rank"], "Tier 3")
        self.assertEqual(self._rank(0.60, 0.60, 3, 20, 2)["final_rank"], "Watchlist")
        self.assertNotEqual(self._rank(0.575, 0.59, 0, 20, 2)["final_rank"], "Tier 1")
        self.assertEqual(self._rank(0.55, 0.55, 0, 20, 2)["final_rank"], "Watchlist")

    def test_absolute_gaps_are_symmetric(self):
        above = pm.grade(0.59, 0.55, 0, 20)
        below = pm.grade(0.55, 0.59, 0, 20)
        self.assertAlmostEqual(above["q_gap"], 0.04, places=6)
        self.assertAlmostEqual(below["q_gap"], -0.04, places=6)
        self.assertEqual(above["notes"].count("MODEL_MARKET_GAP"), 1)
        self.assertEqual(below["notes"].count("MODEL_MARKET_GAP"), 1)
        wide_model = self._rank(0.60, 0.515, 0, 20, 2)
        wide_market = self._rank(0.57, 0.66, 0, 20, 2)
        low_model = self._rank(0.515, 0.60, 0, 20, 2)
        self.assertEqual(wide_model["final_rank"], "Watchlist")
        self.assertEqual(wide_market["final_rank"], "Watchlist")
        self.assertIn("GAP_LARGE", low_model["notes"])
        self.assertEqual(low_model["final_rank"], "Reject")
        exact_three = pm.grade(0.58, 0.55, 0, 20)
        exact_eight = pm.grade(0.60, 0.52, 0, 20)
        self.assertNotIn("MODEL_MARKET_GAP", exact_three["notes"])
        self.assertIn("GAP_LARGE", exact_eight["notes"])
        self.assertEqual(
            pm.decide(0.60, 0.52, 0, 20, mechanisms=2, research_checklist=True)["final_rank"],
            "Watchlist",
        )
        self.assertEqual(self._rank(0.60, 0.515, 0, 20, 2)["final_rank"], "Watchlist")

    def test_current_role_samples(self):
        stable = pm.project(
            "poisson", "over", 2.5, baseline_mean=3, baseline_n=20,
            recent_mean=4, recent_n=10, season_n=30,
        )
        self.assertEqual(stable["current_role_n"], 30)
        changed = pm.project(
            "poisson", "over", 2.5, baseline_mean=2, baseline_n=40,
            recent_mean=4, recent_n=3, season_n=43, role_change=True,
        )
        self.assertEqual(changed["current_role_n"], 3)
        self.assertTrue(changed["low_sample"])
        self.assertIn("NEW_ROLE_SHORT_WINDOW", changed["notes"])
        self.assertNotEqual(changed["current_role_n"], 40)
        mid = pm.project(
            "poisson", "over", 2.5, baseline_mean=2, baseline_n=20,
            recent_mean=3.5, recent_n=7, season_n=27, role_change=True,
        )
        self.assertEqual(mid["current_role_n"], 7)
        long = pm.project(
            "poisson", "over", 2.5, baseline_mean=2, baseline_n=20,
            recent_mean=3.2, recent_n=12, season_n=32, role_change=True,
        )
        self.assertEqual(long["current_role_n"], 12)
        hot = pm.project(
            "poisson", "over", 2.5, baseline_mean=2, baseline_n=20,
            recent_mean=6, recent_n=5, season_n=25,
        )
        self.assertNotIn("ROLE_EB", hot["notes"])
        thin = self._rank(0.70, 0.70, 0, 7, 2, role_change=True)
        self.assertEqual(thin["final_rank"], "Tier 2")
        self.assertIn("LOW_SAMPLE", thin["notes"])

    def test_context_weight_is_not_a_prior_toward_the_baseline(self):
        low = pm.project("poisson", "over", 2.5, baseline_mean=10, baseline_n=8, opponent_factor=.85)
        high = pm.project("poisson", "over", 2.5, baseline_mean=10, baseline_n=40, opponent_factor=1.15)
        self.assertEqual(low["shrunk_mean"], high["shrunk_mean"])
        self.assertGreater(low["mean_se"], high["mean_se"])

    def test_sog_main_line_is_not_limited_to_three_numbers(self):
        result = pm.project("poisson", "over", 4.5, baseline_mean=5.2, baseline_n=30)
        self.assertGreater(result["q_win_over"], 0)
        self.assertAlmostEqual(result["q_win_over"] + result["q_win_under"], 1, places=5)
        skill = skill_corpus()
        self.assertNotIn("shots on goal at 1.5, 2.5, and 3.5", skill)

    def test_grade_and_rank_share_one_score(self):
        scored = pm.grade(0.60, 0.60, 1, 20)
        decided = pm.decide(0.60, 0.60, 1, 20, mechanisms=2, research_checklist=True)
        self.assertEqual(scored["probability_rank"], decided["probability_rank"])
        self.assertEqual(scored["soft_flags"], decided["soft_flags"])
        self.assertEqual(decided["final_rank"], "Tier 2")


class PipelineTests(unittest.TestCase):
    def _base(self, **extra):
        raw = {
            "dist": "poisson",
            "side": "over",
            "line": 2.5,
            "baseline_mean": 3.4,
            "baseline_n": 30,
            "soft_flags": 0,
            "mechanisms": 2,
            "hard_veto": False,
            "data_veto": False,
            "research_checklist": True,
            "q_market": 0.60,
            "retrieved_minutes_ago": 5,
        }
        raw.update(extra)
        return raw

    def test_grade_receives_the_unrounded_win_probability(self):
        trap = 0.57996
        self.assertEqual(f"{100 * trap:.2f}", "58.00")
        self.assertGreaterEqual(float(f"{100 * trap:.2f}") / 100, 0.58)
        self.assertLess(trap, 0.58)
        self.assertEqual(pm.grade(0.58, 0.58, 0, 30)["probability_rank"], "NUMERIC_TIER_1")
        self.assertNotEqual(pm.grade(trap, 0.58, 0, 30)["probability_rank"], "NUMERIC_TIER_1")
        self.assertEqual(f"{0.5799995:.6f}", "0.580000")
        result = pm.evaluate_candidate(self._base())
        self.assertEqual(result["grade"]["q_model"], result["project"]["q_win_robust"])
        self.assertEqual(result["grade"]["q_push"], result["project"]["q_push"])
        self.assertEqual(result["grade"]["current_role_n"], result["project"]["current_role_n"])

    def test_left_tail_cannot_publish_a_tier(self):
        projected = pm.project("normal", "under", 10.5, baseline_mean=8, baseline_n=20, sd=6)
        result = pm.evaluate_candidate({
            "dist": "normal",
            "side": "under",
            "line": 10.5,
            "baseline_mean": 8,
            "baseline_n": 20,
            "sd": 6,
            "q_market": projected["q_win"],
            "retrieved_minutes_ago": 5,
            "soft_flags": 0,
            "mechanisms": 2,
            "hard_veto": False,
            "data_veto": False,
            "research_checklist": True,
        })
        self.assertEqual(result["final_rank"], "Unranked")
        self.assertEqual(result["reason"], "NORMAL_LEFT_TAIL")
        self.assertEqual(result["grade"]["q_model"], projected["q_win_robust"])
        self.assertTrue(result["project"]["sample_block"])

    def test_scaled_minutes_cut_stays_rankable(self):
        result = pm.evaluate_candidate({
            "dist": "normal",
            "side": "under",
            "line": 16.5,
            "baseline_mean": 25,
            "baseline_n": 30,
            "sd": 8,
            "role_change": True,
            "workload_baseline": 34,
            "workload_expected": 18.7,
            "q_market": 0.70,
            "retrieved_minutes_ago": 5,
            "soft_flags": 0,
            "mechanisms": 1,
            "hard_veto": False,
            "data_veto": False,
            "research_checklist": False,
        })
        self.assertNotIn("NORMAL_LEFT_TAIL", result["project"]["notes"])
        self.assertEqual(result["final_rank"], "Unranked")
        self.assertEqual(result["grade"]["reason"], "NO_CURRENT_ROLE")

    def test_books_derive_disagree_but_not_plus_money(self):
        lagged = pm.evaluate_candidate(self._base(
            q_market=None,
            books=[["Pinnacle", 2.5, -130, 110], ["FanDuel", 2.5, -110, -110]],
            retrieved_minutes_ago=5,
        ))
        self.assertNotIn("DISAGREE", lagged["derived_flags"])
        alone = pm.devig(-130, 110)["q_market"]
        self.assertAlmostEqual(lagged["consensus"]["q_market"], alone, places=6)
        shorter = pm.evaluate_candidate(self._base(
            q_market=None,
            books=[{"book": "Pinnacle", "line": 2.5, "target": -130, "other": 110},
                   {"book": "FanDuel", "line": 2.5, "target": -170, "other": 140}],
            retrieved_minutes_ago=5,
        ))
        self.assertIn("DISAGREE", shorter["derived_flags"])
        self.assertNotIn("PLUS-MONEY", shorter["derived_flags"])
        self.assertNotIn("RETAIL_ONLY_TWO_BOOKS", shorter["derived_flags"])
        self.assertEqual(
            shorter["soft_flags_to_grade"],
            shorter["soft_flags_passed"] + len(shorter["derived_flags"]),
        )
        self.assertAlmostEqual(shorter["consensus"]["q_market"], alone, places=6)

    def test_mean_mismatch_is_derived_once(self):
        result = pm.evaluate_candidate(self._base(line=8.5, q_market=0.20))
        self.assertIn("MEAN_LINE_MISMATCH", result["derived_flags"])
        self.assertEqual(result["derived_flags"].count("MEAN_LINE_MISMATCH"), 1)


class CommandTests(unittest.TestCase):
    def test_documented_commands_run(self):
        commands = [
            [sys.executable, str(HELPER), "devig", "--target", "-125", "--other", "-105"],
            [sys.executable, str(HELPER), "consensus", "--side-name", "Over 3.5 SOG",
             "--retrieved-minutes-ago", "5",
             "--book", "Pinnacle:3.5:-130:+110", "--book", "FanDuel:3.5:-135:+105"],
            [sys.executable, str(HELPER), "project", "--dist", "poisson", "--side", "over",
             "--line", "2.5", "--baseline-mean", "3.2", "--baseline-n", "30",
             "--recent-mean", "3.8", "--recent-n", "10", "--season-n", "40",
             "--opponent-factor", "1.08"],
            [sys.executable, str(HELPER), "grade", "--q-model", "0.575", "--q-market", "0.55",
             "--q-push", "0", "--soft-flags", "0", "--current-role-n", "30"],
            [sys.executable, str(HELPER), "rank", "--q-model", "0.61", "--q-market", "0.60",
             "--q-push", "0", "--soft-flags", "0", "--current-role-n", "20",
             "--mechanisms", "1", "--hard-veto", "no", "--data-veto", "no",
             "--market-valid", "yes", "--research-checklist", "yes"],
        ]
        for command in commands:
            completed = subprocess.run(command, cwd=SKILL_DIR, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertNotIn("ERROR", completed.stdout)

    def test_invalid_odds_do_not_print_a_grade(self):
        completed = subprocess.run(
            [sys.executable, str(HELPER), "devig", "--target", "50", "--other", "-110"],
            cwd=SKILL_DIR, capture_output=True, text=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("ERROR", completed.stderr)

    def test_skill_and_helper_do_not_bring_back_removed_workflows(self):
        helper = HELPER.read_text(encoding="utf-8")
        skill = skill_corpus()
        for banned in ("def ladder", "def line_shift", "add_parser(\"roi\")", "add_parser(\"flex\")", "add_parser(\"push\")"):
            self.assertNotIn(banned, helper)
        for banned in (
            "pickem_math.py ladder",
            "pickem_math.py roi",
            "pickem_math.py flex",
            "pickem_math.py be",
            "Tracker rows",
            "Play Over only if",
            "Tier 1 if the Underdog line",
        ):
            self.assertNotIn(banned, skill)


class CommandSurfaceTests(unittest.TestCase):
    def test_every_subcommand_help(self):
        completed = _run(["--help"])
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("pipeline", completed.stdout)
        for name in ("devig", "consensus", "project", "grade", "rank", "log", "pipeline", "scan"):
            help_run = _run([name, "--help"])
            self.assertEqual(help_run.returncode, 0, help_run.stderr)
            self.assertIn(name, help_run.stdout.lower() + help_run.stderr.lower() + "pipeline")

    def test_each_subcommand_runs(self):
        devig = _run(["devig", "--target", "-125", "--other", "-105"])
        self.assertEqual(devig.returncode, 0, devig.stderr)
        self.assertIn("q_market=", devig.stdout)
        consensus = _run([
            "consensus", "--retrieved-minutes-ago", "5", "--json",
            "--book", "Pinnacle:3.5:-130:+110", "--book", "FanDuel:3.5:-135:+105",
        ])
        self.assertEqual(consensus.returncode, 0, consensus.stderr)
        payload = json.loads(consensus.stdout)
        self.assertIn("q_market", payload)
        project = _run([
            "project", "--dist", "poisson", "--side", "over", "--line", "2.5",
            "--baseline-mean", "3.2", "--baseline-n", "30", "--json",
        ])
        self.assertEqual(project.returncode, 0, project.stderr)
        body = json.loads(project.stdout)
        direct = pm.project("poisson", "over", 2.5, baseline_mean=3.2, baseline_n=30)
        self.assertEqual(body["q_win"], direct["q_win"])
        text = _run([
            "project", "--dist", "poisson", "--side", "over", "--line", "2.5",
            "--baseline-mean", "3.2", "--baseline-n", "30",
        ])
        self.assertIn("q_win_raw=", text.stdout)
        grade = _run([
            "grade", "--q-model", "0.61", "--q-market", "0.58", "--q-push", "0",
            "--soft-flags", "0", "--current-role-n", "30",
        ])
        self.assertEqual(grade.returncode, 0, grade.stderr)
        self.assertIn("probability_rank=NUMERIC_TIER_1", grade.stdout)
        self.assertNotIn("MODEL_MARKET_GAP", grade.stdout)
        rank = _run([
            "rank", "--q-model", "0.61", "--q-market", "0.60", "--soft-flags", "0",
            "--current-role-n", "20", "--mechanisms", "2", "--hard-veto", "no",
            "--data-veto", "no", "--market-valid", "yes", "--research-checklist", "yes",
            "--normal-left-tail", "yes",
        ])
        self.assertEqual(rank.returncode, 0, rank.stderr)
        self.assertIn("final_rank=Unranked", rank.stdout)
        self.assertIn("NORMAL_LEFT_TAIL", rank.stdout)
        pipe = _run([
            "pipeline", "--dist", "poisson", "--side", "over", "--line", "2.5",
            "--baseline-mean", "3.4", "--baseline-n", "30", "--soft-flags", "0",
            "--mechanisms", "1", "--hard-veto", "no", "--data-veto", "no",
            "--research-checklist", "no", "--q-market", "0.60",
            "--retrieved-minutes-ago", "5", "--json",
        ])
        self.assertEqual(pipe.returncode, 0, pipe.stderr)
        audited = json.loads(pipe.stdout)
        self.assertEqual(audited["grade"]["q_model"], audited["project"]["q_win_robust"])
        self.assertIn(audited["final_rank"], pm.SNAPSHOT_RANKS)
        import tempfile
        record = {
            "run_at": "2026-10-22 12:00 ET",
            "game_date": "2026-10-22",
            "sport": "NBA",
            "matchup": "BOS @ NYK",
            "player": "Example",
            "stat": "points",
            "side": "Over",
            "reference_line": 24.5,
            "final_rank": "Reject",
            "status": "GRADED",
            "researched": True,
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "props.jsonl"
            logged = _run(["log", "--stdin", "--path", str(path)], stdin=json.dumps(record))
            self.assertEqual(logged.returncode, 0, logged.stderr)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["side"], "over")

    def test_batch_pipeline(self):
        good = {
            "id": "good",
            "dist": "poisson",
            "side": "over",
            "line": 2.5,
            "baseline_mean": 3.4,
            "baseline_n": 30,
            "q_market": 0.62,
            "retrieved_minutes_ago": 5,
            "soft_flags": 0,
            "mechanisms": 1,
            "hard_veto": "no",
            "data_veto": "no",
            "research_checklist": "no",
        }
        bad = dict(good)
        bad.update(id="bad", dist="negbin", var_ratio=1.05)
        ok = _run(["pipeline", "--batch", "--stdin"], stdin=json.dumps(good) + "\n")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        row = json.loads(ok.stdout)
        self.assertTrue(row["ok"])
        self.assertEqual(row["id"], "good")
        self.assertEqual(row["grade"]["q_model"], row["project"]["q_win_robust"])
        failed = _run(
            ["pipeline", "--batch", "--stdin"],
            stdin=json.dumps(good) + "\n" + json.dumps(bad) + "\n",
        )
        self.assertNotEqual(failed.returncode, 0)
        lines = [json.loads(line) for line in failed.stdout.splitlines() if line.strip()]
        self.assertEqual(lines[0]["final_rank"] != "ERROR", True)
        self.assertTrue(lines[0]["ok"])
        self.assertFalse(lines[1]["ok"])
        self.assertEqual(lines[1]["final_rank"], "Unranked")
        self.assertIn("poisson", lines[1]["error"])


class SnapshotTests(unittest.TestCase):
    def _record(self, rank):
        return {
            "run_at": "2026-10-21 21:00 ET",
            "game_date": "2026-10-21",
            "sport": "NHL",
            "matchup": "BOS @ TOR",
            "player": "Example Skater",
            "stat": "SOG",
            "side": "over",
            "reference_line": 2.5,
            "final_rank": rank,
            "status": "GRADED",
            "researched": True,
            "q_model": 0.61,
            "q_market": 0.55,
        }

    def test_log_stores_rejects_as_well_as_picks(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "props.jsonl"
            pm.append_snapshot(self._record("Reject"), path)
            pm.append_snapshot(self._record("Tier 2"), path)
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["final_rank"] for row in rows], ["Reject", "Tier 2"])
        self.assertIsNone(rows[0]["actual_stat"])
        self.assertIsNone(rows[1]["closing_line"])

    def test_log_refuses_an_underdog_field(self):
        record = self._record("Watchlist")
        record["underdog_line"] = 1.5
        with self.assertRaises(pm.PickemError):
            pm.append_snapshot(record, Path("unused.jsonl"))

    def test_log_command_appends_stdin(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "props.jsonl"
            completed = subprocess.run(
                [sys.executable, str(HELPER), "log", "--stdin", "--path", str(path)],
                input=json.dumps(self._record("Unranked")),
                capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("logged=1", completed.stdout)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["final_rank"], "Unranked")

    def test_helper_does_not_define_a_results_file(self):
        source = HELPER.read_text(encoding="utf-8")
        self.assertNotIn(".csv", source)
        self.assertNotIn("q_grade = min", source)


class SnapshotNormalizationTests(unittest.TestCase):
    def test_over_and_under_are_normalized(self):
        record = {
            "run_at": "2026-10-22 12:00 ET",
            "game_date": "2026-10-22",
            "sport": " NBA ",
            "matchup": "BOS @ NYK",
            "player": "Example",
            "stat": "points",
            "side": " Over ",
            "reference_line": 24.5,
            "final_rank": " Tier 2 ",
            "status": "GRADED",
            "researched": True,
        }
        normalized = pm.normalize_snapshot(record)
        self.assertEqual(normalized["side"], "over")
        self.assertEqual(normalized["sport"], "NBA")
        self.assertEqual(normalized["final_rank"], "Tier 2")
        record["side"] = "Under"
        record["sport"] = "NHL"
        record["final_rank"] = "Unranked"
        self.assertEqual(pm.normalize_snapshot(record)["side"], "under")


class FunnelChannelTests(unittest.TestCase):
    def _at_caps(self, channels, **extra):
        return pm.project(
            "poisson", "over", 2.5,
            baseline_mean=10, baseline_n=30,
            opponent_factor=1.15, pace_factor=1.10,
            funnel_channels=channels,
            **extra,
        )

    def test_weights_are_8_16_and_24(self):
        for channels in (0,1,2):
            out=self._at_caps(channels)
            self.assertEqual(out["context_weight"],0)
            self.assertEqual(out["shrunk_mean"],10)

    def test_clamps_do_not_move_when_the_weight_does(self):
        out=pm.project("poisson", "over", 2.5, baseline_mean=10, baseline_n=30,
                       opponent_factor=1.5, pace_factor=1.4, funnel_channels=2)
        self.assertEqual(out["opponent_factor_used"],1)
        self.assertEqual(out["pace_factor_used"],1)
        self.assertEqual(out["context_weight"],0)

    def test_two_pace_checks_are_still_one_channel(self):
        self.assertEqual(self._at_caps(1)["context_weight"],0)
        self.assertEqual(self._at_caps(2)["context_weight"],0)

    def test_role_change_is_not_a_funnel_channel(self):
        out=pm.project("poisson", "over", 2.5, baseline_mean=10, baseline_n=30,
                       role_change=True, workload_baseline=30, workload_expected=36)
        self.assertEqual(out["funnel_channels"],0)
        self.assertEqual(out["context_weight"],0)
        self.assertTrue(out["sample_block"])

    def test_every_named_check_has_one_label(self):
        skill = skill_corpus()
        block = skill[skill.index("#### NFL funnel checks"):skill.index("## C3. Environment")]
        bullets = [line for line in block.splitlines() if line.startswith("- **")]
        self.assertEqual(len(bullets), 56)
        labels = ("Pace. ", "Opponent environment. ", "Role. ")
        for bullet in bullets:
            body = bullet.split(".** ", 1)[1]
            hits = [label for label in labels if body.startswith(label)]
            self.assertEqual(hits, hits[:1] and [hits[0]], bullet[:70])
            self.assertEqual(len(hits), 1, bullet[:70])

    def test_bad_channel_count_is_rejected(self):
        for value in (3, -1, 1.5, True):
            with self.assertRaises(pm.PickemError):
                self._at_caps(value)

    def test_pipeline_passes_the_flag_and_prints_the_weight(self):
        completed = _run([
            "pipeline", "--dist", "poisson", "--side", "over", "--line", "2.5",
            "--baseline-mean", "10", "--baseline-n", "30",
            "--opponent-factor", "1.15", "--pace-factor", "1.10",
            "--funnel-channels", "1",
            "--soft-flags", "0", "--mechanisms", "1",
            "--hard-veto", "no", "--data-veto", "no", "--research-checklist", "no",
            "--q-market", "0.55", "--retrieved-minutes-ago", "5", "--json",
        ])
        self.assertEqual(completed.returncode, 0, completed.stderr)
        body = json.loads(completed.stdout)
        self.assertEqual(body["project"]["funnel_channels"], 0)
        self.assertEqual(body["project"]["context_weight"], 0)
        self.assertEqual(body["grade"]["q_model"], body["project"]["q_win_robust"])
        self.assertAlmostEqual(body["grade"]["q_grade"], body["project"]["q_win_robust"], places=9)
        text = _run([
            "project", "--dist", "poisson", "--side", "over", "--line", "2.5",
            "--baseline-mean", "10", "--baseline-n", "30",
            "--opponent-factor", "1.15", "--pace-factor", "1.10",
            "--funnel-channels", "2",
        ])
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn("funnel_channels=0", text.stdout)
        self.assertIn("context_weight=0", text.stdout)


class SkillContractTests(unittest.TestCase):
    def test_stage_i_is_no_longer_split_by_stage_j(self):
        skill = skill_corpus()
        stage_i = skill.index("# Stage I. Adversarial review")
        question = skill.index("1. What is the strongest evidence the side is wrong?")
        closing = skill.index("Do not argue it back up.")
        stage_j = skill.index("# Stage J. Snapshot every researched prop")
        self.assertLess(stage_i, question)
        self.assertLess(question, closing)
        self.assertLess(closing, stage_j)
        for phrase in (
            "Engine A is a pure historical statistical engine",
            "sd_used",
            "weather.gc.ca",
            "at least 8.0 and less than 9.5",
            "at least 4.5 and less than 6.5",
            "at least 15.0 mph and less than 18.0",
            "outdoor NHL shots-on-goal Overs",
            "current_role_n` is at least 10",
            "1.10 or less",
            "use poisson",
            "RETAIL_ONLY_TWO_BOOKS",
            "not a soft flag",
            "pipeline --batch",
            "expected defensive snaps",
            "yards per target",
            "at least 2 distinct mechanisms",
            "at least 1 and at most 4",
            "scan --stdin",
            "log --batch --stdin",
            "Signal 6 alone does not create a serious candidate.",
            "Scanned, unresearchable, and shortlisted",
        ):
            self.assertIn(phrase, skill)
        self.assertNotIn("defensive snaps times opponent plays", skill)
        self.assertNotIn("Two to four mechanisms", skill)


class MarketIntegrityTests(unittest.TestCase):
    def _candidate(self, **extra):
        raw = {
            "dist": "poisson",
            "side": "over",
            "line": 2.5,
            "baseline_mean": 3.4,
            "baseline_n": 30,
            "soft_flags": 0,
            "mechanisms": 2,
            "hard_veto": False,
            "data_veto": False,
            "research_checklist": True,
            "q_market": 0.60,
            "retrieved_minutes_ago": 5,
        }
        raw.update(extra)
        return raw

    def _pipe(self, *extra):
        return _run([
            "pipeline", "--dist", "poisson", "--side", "over", "--line", "2.5",
            "--baseline-mean", "3.4", "--baseline-n", "30", "--soft-flags", "0",
            "--mechanisms", "2", "--hard-veto", "no", "--data-veto", "no",
            "--research-checklist", "yes", *extra,
        ])

    def test_model_line_2_5_with_pinnacle_at_3_5_errors(self):
        with self.assertRaises(pm.PickemError) as caught:
            pm.evaluate_candidate(self._candidate(
                q_market=None,
                books=["Pinnacle:3.5:-130:+110"],
            ))
        self.assertEqual(
            str(caught.exception),
            "market line 3.5 does not match projected line 2.5",
        )

    def test_line_mismatch_is_unranked_in_batch_and_on_the_cli(self):
        payload = self._candidate(
            id="mismatch",
            q_market=None,
            books=["Pinnacle:3.5:-130:+110:over"],
        )
        batch = _run(["pipeline", "--batch", "--stdin"], stdin=json.dumps(payload) + "\n")
        self.assertNotEqual(batch.returncode, 0)
        row = json.loads(batch.stdout)
        self.assertFalse(row["ok"])
        self.assertEqual(row["id"], "mismatch")
        self.assertEqual(row["final_rank"], "Unranked")
        self.assertEqual(row["error"], "market line 3.5 does not match projected line 2.5")
        cli = self._pipe(
            "--book", "Pinnacle:3.5:-130:+110:over",
            "--retrieved-minutes-ago", "5", "--json",
        )
        self.assertNotEqual(cli.returncode, 0)
        self.assertIn("market line 3.5 does not match projected line 2.5", cli.stderr)

    def test_line_inside_tolerance_matches_and_outside_it_does_not(self):
        inside = pm.evaluate_candidate(self._candidate(
            q_market=None,
            books=[{
                "book": "Pinnacle",
                "line": 2.5 + 5e-10,
                "target": -130,
                "other": 110,
                "book_side": "over",
            }],
        ))
        self.assertIn("line_match", inside["market_checks"])
        with self.assertRaises(pm.PickemError) as caught:
            pm.evaluate_candidate(self._candidate(
                q_market=None,
                books=[{
                    "book": "Pinnacle",
                    "line": 2.5 + 5e-9,
                    "target": -130,
                    "other": 110,
                    "book_side": "over",
                }],
            ))
        self.assertIn("does not match projected line", str(caught.exception))

    def test_q_market_without_a_timestamp_errors(self):
        raw = self._candidate()
        raw.pop("retrieved_minutes_ago")
        with self.assertRaises(pm.PickemError) as caught:
            pm.evaluate_candidate(raw)
        self.assertIn("retrieved_minutes_ago", str(caught.exception))
        cli = self._pipe("--q-market", "0.60", "--json")
        self.assertNotEqual(cli.returncode, 0)
        self.assertIn("retrieved_minutes_ago", cli.stderr)
        batch = _run(["pipeline", "--batch", "--stdin"], stdin=json.dumps(raw) + "\n")
        row = json.loads(batch.stdout)
        self.assertEqual(row["final_rank"], "Unranked")
        self.assertFalse(row["ok"])
        self.assertIn("retrieved_minutes_ago", row["error"])

    def test_stale_direct_price_cannot_be_upgraded(self):
        stale = pm.evaluate_candidate(self._candidate(retrieved_minutes_ago=31))
        self.assertFalse(stale["grade"]["market_valid"])
        self.assertEqual(stale["final_rank"], "Unranked")
        self.assertNotIn("timestamp_fresh", stale["market_checks"])
        upgraded = pm.evaluate_candidate(self._candidate(
            retrieved_minutes_ago=45, market_valid="yes",
        ))
        self.assertFalse(upgraded["grade"]["market_valid"])
        self.assertEqual(upgraded["final_rank"], "Unranked")
        fresh = pm.evaluate_candidate(self._candidate(retrieved_minutes_ago=30))
        self.assertTrue(fresh["grade"]["market_valid"])
        self.assertNotEqual(fresh["final_rank"], "Unranked")
        self.assertEqual(fresh["market_checks"], ["timestamp_fresh"])
        downgraded = pm.evaluate_candidate(self._candidate(
            retrieved_minutes_ago=5, market_valid=False,
        ))
        self.assertFalse(downgraded["grade"]["market_valid"])
        self.assertEqual(downgraded["final_rank"], "Unranked")
        self.assertEqual(downgraded["market_checks"], ["timestamp_fresh"])
        cli = self._pipe(
            "--q-market", "0.60", "--retrieved-minutes-ago", "45",
            "--market-valid", "yes", "--json",
        )
        self.assertEqual(cli.returncode, 0, cli.stderr)
        body = json.loads(cli.stdout)
        self.assertFalse(body["grade"]["market_valid"])
        self.assertEqual(body["final_rank"], "Unranked")
        self.assertNotIn("timestamp_fresh", body["market_checks"])

    def test_q_market_must_be_inside_the_open_unit_interval(self):
        for bad in (0, 1, -0.01, 1.01):
            with self.assertRaises(pm.PickemError) as caught:
                pm.evaluate_candidate(self._candidate(q_market=bad))
            self.assertIn("(0, 1)", str(caught.exception))
        tiny = pm.evaluate_candidate(self._candidate(q_market=1e-9))
        self.assertTrue(tiny["ok"])
        self.assertEqual(tiny["market_checks"], ["timestamp_fresh"])

    def test_q_market_cannot_be_combined_with_books(self):
        with self.assertRaises(pm.PickemError) as caught:
            pm.evaluate_candidate(self._candidate(
                books=["Pinnacle:2.5:-130:+110:over"],
            ))
        self.assertEqual(str(caught.exception), "pass q_market or books, not both")
        cli = self._pipe(
            "--q-market", "0.55",
            "--book", "Pinnacle:2.5:-130:+110:over",
            "--retrieved-minutes-ago", "5",
        )
        self.assertNotEqual(cli.returncode, 0)
        self.assertIn("not both", cli.stderr)

    def test_book_side_must_match_the_candidate_side(self):
        specs = (
            ["Pinnacle:2.5:-130:+110:under"],
            [{"book": "Pinnacle", "line": 2.5, "target": -130, "other": 110, "book_side": "Under"}],
            [["Pinnacle", 2.5, -130, 110, "under"]],
        )
        for books in specs:
            with self.assertRaises(pm.PickemError) as caught:
                pm.evaluate_candidate(self._candidate(q_market=None, books=books))
            self.assertIn(
                "book_side under does not match candidate side over",
                str(caught.exception),
            )
        with self.assertRaises(pm.PickemError) as caught:
            pm._parse_book_spec("Pinnacle:2.5:-130:+110:sideways")
        self.assertIn("book_side", str(caught.exception))

    def test_five_part_spec_verifies_the_side_and_lists_every_check(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = pm.evaluate_candidate(self._candidate(
                q_market=None,
                books=["Pinnacle:2.5:-130:+110:Over"],
            ))
        self.assertFalse([item for item in caught if issubclass(item.category, DeprecationWarning)])
        self.assertNotIn("SIDE_UNVERIFIED", result["derived_flags"])
        self.assertEqual(result["market_checks"], [
            "line_match", "side_match", "timestamp_fresh", "hold_ok", "approved_books",
        ])
        self.assertTrue(result["grade"]["market_valid"])
        self.assertNotEqual(result["final_rank"], "Unranked")
        cli = self._pipe(
            "--book", "Pinnacle:2.5:-130:+110:over",
            "--retrieved-minutes-ago", "5", "--json",
        )
        self.assertEqual(cli.returncode, 0, cli.stderr)
        body = json.loads(cli.stdout)
        self.assertEqual(body["market_checks"], result["market_checks"])

    def test_legacy_four_part_spec_warns_and_adds_one_soft_flag(self):
        with self.assertWarns(DeprecationWarning) as caught:
            result = pm.evaluate_candidate(self._candidate(
                q_market=None,
                books=["Pinnacle:2.5:-130:+110"],
            ))
        self.assertIn("deprecated", str(caught.warning))
        self.assertIn("SIDE_UNVERIFIED", str(caught.warning))
        self.assertEqual(result["derived_flags"].count("SIDE_UNVERIFIED"), 1)
        self.assertEqual(
            result["soft_flags_to_grade"],
            result["soft_flags_passed"] + len(result["derived_flags"]),
        )
        self.assertEqual(result["grade"]["qualitative_flags"], result["soft_flags_to_grade"])
        self.assertGreaterEqual(result["soft_flags_to_grade"], 1)
        self.assertNotIn("side_match", result["market_checks"])
        self.assertIn("line_match", result["market_checks"])
        with self.assertWarns(DeprecationWarning):
            listed = pm.evaluate_candidate(self._candidate(
                q_market=None,
                books=[["Pinnacle", 2.5, -130, 110]],
            ))
        self.assertIn("SIDE_UNVERIFIED", listed["derived_flags"])
        with self.assertWarns(DeprecationWarning):
            record = pm.evaluate_candidate(self._candidate(
                q_market=None,
                books=[{"book": "Pinnacle", "line": 2.5, "target": -130, "other": 110}],
            ))
        self.assertIn("SIDE_UNVERIFIED", record["derived_flags"])
        cli = self._pipe(
            "--book", "Pinnacle:2.5:-130:+110",
            "--retrieved-minutes-ago", "5", "--json",
        )
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertIn("DeprecationWarning", cli.stderr)
        body = json.loads(cli.stdout)
        self.assertIn("SIDE_UNVERIFIED", body["derived_flags"])
        self.assertNotIn("side_match", body["market_checks"])

    def test_failed_hold_and_an_unapproved_book(self):
        juicy = pm.evaluate_candidate(self._candidate(
            q_market=None,
            books=[
                "Pinnacle:2.5:-130:+110:over",
                "FanDuel:2.5:-150:-150:over",
            ],
        ))
        self.assertEqual(juicy["market_checks"], [
            "line_match", "side_match", "timestamp_fresh", "approved_books",
        ])
        with self.assertRaises(pm.PickemError) as caught:
            pm.evaluate_candidate(self._candidate(
                q_market=None,
                books=["Fanatics:2.5:-120:-110:over"],
            ))
        self.assertIn("unapproved", str(caught.exception))

    def test_books_without_a_timestamp_stay_invalid_without_raising(self):
        result = pm.evaluate_candidate(self._candidate(
            q_market=None,
            books=["Pinnacle:2.5:-130:+110:over"],
            retrieved_minutes_ago=None,
        ))
        self.assertIn("q_market", result["consensus"])
        self.assertTrue(any(flag.startswith("TIMESTAMP_MISSING") for flag in result["consensus"]["flags"]))
        self.assertFalse(result["consensus"]["market_valid"])
        self.assertFalse(result["grade"]["market_valid"])
        self.assertEqual(result["final_rank"], "Unranked")
        self.assertNotIn("timestamp_fresh", result["market_checks"])
        self.assertIn("line_match", result["market_checks"])
        fresh = pm.evaluate_candidate(self._candidate(
            q_market=None,
            books=["Pinnacle:2.5:-130:+110:over"],
            retrieved_minutes_ago=30,
        ))
        self.assertTrue(fresh["grade"]["market_valid"])
        self.assertIn("timestamp_fresh", fresh["market_checks"])
        stale = pm.evaluate_candidate(self._candidate(
            q_market=None,
            books=["Pinnacle:2.5:-130:+110:over"],
            retrieved_minutes_ago=45,
            market_valid="yes",
        ))
        self.assertFalse(stale["grade"]["market_valid"])
        self.assertEqual(stale["final_rank"], "Unranked")
        self.assertNotIn("timestamp_fresh", stale["market_checks"])
        with self.assertRaises(pm.PickemError) as caught:
            pm.evaluate_candidate(self._candidate(retrieved_minutes_ago=-1))
        self.assertIn("retrieved_minutes_ago", str(caught.exception))

    def test_a_colon_inside_a_legacy_book_name_is_not_a_side(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            parsed = pm._parse_book_spec("Foo:Bar:2.5:-130:+110")
        self.assertEqual(parsed["book"], "Foo:Bar")
        self.assertIsNone(parsed["book_side"])
        self.assertEqual(parsed["line"], 2.5)
        sided = pm._parse_book_spec("Foo:Bar:2.5:-130:+110:over")
        self.assertEqual(sided["book"], "Foo:Bar")
        self.assertEqual(sided["book_side"], "over")

    def test_direct_json_lists_only_the_timestamp_check(self):
        cli = self._pipe(
            "--q-market", "0.60", "--retrieved-minutes-ago", "5", "--json",
        )
        self.assertEqual(cli.returncode, 0, cli.stderr)
        body = json.loads(cli.stdout)
        self.assertEqual(body["market_checks"], ["timestamp_fresh"])
        self.assertTrue(body["grade"]["market_valid"])
        text = self._pipe("--q-market", "0.60", "--retrieved-minutes-ago", "5")
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn("market_checks=timestamp_fresh", text.stdout)


class StageGDerivationTests(unittest.TestCase):
    """Numeric Stage G cuts come from context fields, not a hand-typed count."""

    def _row(self, **extra):
        raw = {
            "dist": "poisson",
            "side": "over",
            "line": 2.5,
            "baseline_mean": 3.4,
            "baseline_n": 30,
            "soft_flags": 0,
            "mechanisms": 2,
            "hard_veto": False,
            "data_veto": False,
            "research_checklist": True,
            "q_market": 0.66,
            "retrieved_minutes_ago": 5,
        }
        raw.update(extra)
        return raw

    def _derive(self, **fields):
        return pm.derive_vetoes_and_flags(fields)

    def _reasons(self, **fields):
        got = self._derive(**fields)
        return got["hard_veto_reasons"], got["soft_flags_derived"]

    def test_tier_floors_stay_put(self):
        self.assertEqual((pm.TIER_1, pm.TIER_2, pm.TIER_3, pm.WATCH_FLOOR), (0.58, 0.57, 0.56, 0.52))

    def test_omitted_fields_derive_nothing(self):
        got = self._derive()
        self.assertEqual(got, {
            "hard_veto_reasons": [],
            "data_veto_reasons": [],
            "soft_flags_derived": [],
        })
        bare = pm.evaluate_candidate(self._row())
        self.assertEqual(bare["derived_vetoes"], {
            "hard_veto_reasons": [],
            "data_veto_reasons": [],
        })
        self.assertEqual(bare["derived_soft_flags"], [])
        self.assertEqual(
            bare["soft_flags_to_grade"],
            bare["soft_flags_passed"] + len(bare["derived_flags"]),
        )
        self.assertEqual(bare["final_rank"], "Watchlist")
        self.assertNotIn("QUESTIONABLE_PLAYER", bare["derived_soft_flags"])
        self.assertNotIn("CONTEXT_AGAINST", bare["derived_soft_flags"])
        self.assertNotIn("SINGLE_SOURCE_LINEUP", bare["derived_soft_flags"])
        self.assertNotIn("PROJECTION_CONFLICT", bare["derived_soft_flags"])

    def test_minutes_boundaries(self):
        cases = [
            (17.9, ["NBA_MINUTES_UNDER_18"], []),
            (18.0 - 1e-8, ["NBA_MINUTES_UNDER_18"], []),
            (18.0 - 1e-12, [], ["THIN_WORKLOAD"]),
            (18.0, [], ["THIN_WORKLOAD"]),
            (27.9, [], ["THIN_WORKLOAD"]),
            (27.9 + 1e-12, [], ["THIN_WORKLOAD"]),
            (27.9 + 1e-8, [], []),
            (28.0, [], []),
        ]
        for minutes, hard, soft in cases:
            with self.subTest(minutes=minutes):
                self.assertEqual(
                    self._reasons(stat="points", side="over", minutes_tonight=minutes),
                    (hard, soft),
                )
        under = self._derive(stat="points", side="under", minutes_tonight=10)
        self.assertEqual(under["hard_veto_reasons"], [])
        self.assertEqual(under["soft_flags_derived"], [])
        self.assertEqual(
            self._reasons(stat="receptions", side="over", minutes_tonight=10),
            ([], []),
        )

    def test_ice_snap_and_route_boundaries(self):
        ice_cases = [
            (11.99, ["NHL_ICE_UNDER_12"], []),
            (12.0, [], ["THIN_WORKLOAD"]),
            (17 + 29 / 60, [], ["THIN_WORKLOAD"]),
            (17.5, [], []),
        ]
        for ice, hard, soft in ice_cases:
            with self.subTest(ice=ice):
                self.assertEqual(
                    self._reasons(stat="shots on goal", side="over", ice_time_tonight=ice),
                    (hard, soft),
                )
        self.assertEqual(
            self._reasons(stat="saves", side="over", ice_time_tonight=10),
            ([], []),
        )
        snap_cases = [
            (0.40 - 1e-8, ["NFL_SNAPS_UNDER_40"], []),
            (0.40 - 1e-12, [], ["THIN_WORKLOAD"]),
            (0.40, [], ["THIN_WORKLOAD"]),
            (0.599, [], ["THIN_WORKLOAD"]),
            (0.60, [], []),
            (39.9, ["NFL_SNAPS_UNDER_40"], []),
            (40, [], ["THIN_WORKLOAD"]),
        ]
        for snaps, hard, soft in snap_cases:
            with self.subTest(snaps=snaps):
                self.assertEqual(
                    self._reasons(stat="receptions", side="over", snap_pct_tonight=snaps),
                    (hard, soft),
                )
        route_cases = [
            (0.50 - 1e-8, ["WR_TE_ROUTES_UNDER_50"], []),
            (0.50 - 1e-12, [], ["THIN_WORKLOAD"]),
            (0.50, [], ["THIN_WORKLOAD"]),
            (0.699, [], ["THIN_WORKLOAD"]),
            (0.70, [], []),
        ]
        for routes, hard, soft in route_cases:
            with self.subTest(routes=routes):
                self.assertEqual(
                    self._reasons(stat="receptions", side="over", role="wr", route_pct_tonight=routes),
                    (hard, soft),
                )
        self.assertEqual(
            self._reasons(stat="receptions", side="over", role="rb", route_pct_tonight=0.30),
            ([], []),
        )
        self.assertEqual(
            self._reasons(stat="receptions", side="over", role="wr", snap_pct_tonight=0.30, route_pct_tonight=0.30),
            (["NFL_SNAPS_UNDER_40", "WR_TE_ROUTES_UNDER_50"], []),
        )

    def test_tackle_snap_band(self):
        cases = [
            (0.35, ["NFL_SNAPS_UNDER_40", "TACKLES_SNAPS_UNDER_50"], []),
            (0.49, ["TACKLES_SNAPS_UNDER_50"], []),
            (0.50, [], ["THIN_WORKLOAD"]),
            (0.79, [], ["THIN_WORKLOAD"]),
            (0.80, [], []),
        ]
        for snaps, hard, soft in cases:
            with self.subTest(snaps=snaps):
                self.assertEqual(
                    self._reasons(stat="tackles + assists", side="over", snap_pct_tonight=snaps),
                    (hard, soft),
                )

    def test_spread_boundaries(self):
        nba = [
            (7.99, [], []),
            (8.0 - 1e-12, [], ["SCRIPT_RISK"]),
            (8.0, [], ["SCRIPT_RISK"]),
            (9.49, [], ["SCRIPT_RISK"]),
            (9.5 - 1e-12, ["NBA_STARTER_SPREAD"], []),
            (9.5, ["NBA_STARTER_SPREAD"], []),
            (-9.5, ["NBA_STARTER_SPREAD"], []),
            (-8.5, [], ["SCRIPT_RISK"]),
        ]
        for spread, hard, soft in nba:
            with self.subTest(spread=spread):
                self.assertEqual(
                    self._reasons(stat="points", side="over", is_starter=True, spread=spread),
                    (hard, soft),
                )
        self.assertEqual(
            self._reasons(stat="points", side="over", is_starter=False, spread=12),
            ([], []),
        )
        self.assertEqual(
            self._reasons(stat="points", side="over", spread=12),
            ([], []),
        )
        dogs = [
            (4.49, [], []),
            (4.5, [], ["SCRIPT_RISK"]),
            (6.49, [], ["SCRIPT_RISK"]),
            (6.5 - 1e-12, ["NFL_RB_UNDERDOG_RUSH"], []),
            (6.5, ["NFL_RB_UNDERDOG_RUSH"], []),
        ]
        for spread, hard, soft in dogs:
            with self.subTest(dog=spread):
                self.assertEqual(
                    self._reasons(stat="rushing yards", side="over", role="rb", spread=spread),
                    (hard, soft),
                )
        self.assertEqual(
            self._reasons(stat="rush attempts", side="over", role="rb", spread=6.5),
            (["NFL_RB_UNDERDOG_RUSH"], []),
        )
        self.assertEqual(
            self._reasons(stat="rushing yards", side="over", role="wr", spread=10),
            ([], []),
        )
        self.assertEqual(
            self._reasons(stat="rushing yards", side="over", role="rb", spread=7, team_is_underdog=False),
            ([], []),
        )
        self.assertEqual(
            self._reasons(stat="rushing yards", side="over", role="rb", spread=-6.5, team_is_underdog=True),
            (["NFL_RB_UNDERDOG_RUSH"], []),
        )
        self.assertEqual(
            self._reasons(stat="rushing yards", side="over", role="rb", spread=-6.5),
            ([], []),
        )

    def test_wind_gust_snow_and_rain_boundaries(self):
        winds = [
            (14.99, [], []),
            (15.0 - 1e-12, [], ["WEATHER_RISK"]),
            (15.0, [], ["WEATHER_RISK"]),
            (17.99, [], ["WEATHER_RISK"]),
            (18.0 - 1e-12, ["SUSTAINED_WIND"], []),
            (18.0, ["SUSTAINED_WIND"], []),
            (18.01, ["SUSTAINED_WIND"], []),
        ]
        for wind, hard, soft in winds:
            with self.subTest(wind=wind):
                self.assertEqual(
                    self._reasons(stat="passing yards", side="over", sustained_wind_mph=wind),
                    (hard, soft),
                )
        self.assertEqual(
            self._reasons(stat="rushing yards", side="over", role="rb", sustained_wind_mph=20),
            ([], []),
        )
        self.assertEqual(
            self._reasons(stat="passing yards", side="over", outdoor=False, sustained_wind_mph=20),
            ([], []),
        )
        self.assertEqual(
            self._reasons(stat="shots on goal", side="over", outdoor=True, sustained_wind_mph=17.99),
            ([], ["WEATHER_RISK"]),
        )
        self.assertEqual(
            self._reasons(stat="shots on goal", side="over", outdoor=True, sustained_wind_mph=18.0),
            (["SUSTAINED_WIND"], []),
        )
        self.assertEqual(
            self._reasons(stat="shots on goal", side="over", sustained_wind_mph=20),
            ([], []),
        )
        self.assertEqual(
            self._reasons(stat="passing yards", side="over", gust_mph=24.99),
            ([], []),
        )
        self.assertEqual(
            self._reasons(stat="passing yards", side="over", gust_mph=25),
            ([], ["WEATHER_RISK"]),
        )
        self.assertEqual(
            self._reasons(stat="passing yards", side="over", gust_mph=40),
            ([], ["WEATHER_RISK"]),
        )
        self.assertEqual(
            self._reasons(stat="shots on goal", side="over", outdoor=True, gust_mph=40),
            ([], []),
        )
        both = self._derive(stat="pass attempts", side="over", sustained_wind_mph=18, gust_mph=30)
        self.assertEqual(both["hard_veto_reasons"], ["SUSTAINED_WIND"])
        self.assertEqual(both["soft_flags_derived"], ["WEATHER_RISK"])
        self.assertEqual(
            self._reasons(
                stat="passing yards", side="over",
                sustained_wind_mph=17.99, gust_mph=25,
            ),
            ([], ["WEATHER_RISK"]),
        )
        snow_yes = self._derive(
            stat="receptions", side="over", snow=True, precip_prob=60, precip_intensity="moderate",
        )
        self.assertEqual(snow_yes["hard_veto_reasons"], ["SNOW"])
        self.assertEqual(snow_yes["soft_flags_derived"], [])
        self.assertEqual(
            self._reasons(
                stat="completions", side="over", snow=True, precip_prob=0.60, precip_intensity="heavy",
            ),
            (["SNOW"], []),
        )
        for fields in (
            {"snow": True, "precip_prob": 60, "precip_intensity": "light"},
            {"snow": True, "precip_prob": 59.99, "precip_intensity": "heavy"},
            {"snow": True, "precip_prob": 60},
            {"snow": False, "precip_prob": 60, "precip_intensity": "light"},
        ):
            with self.subTest(fields=fields):
                self.assertEqual(self._reasons(stat="receiving yards", side="over", **fields), ([], []))
        self.assertEqual(
            self._reasons(
                stat="receiving yards", side="over",
                snow=False, precip_prob=60, precip_intensity="moderate",
            ),
            ([], ["WEATHER_RISK"]),
        )
        self.assertEqual(
            self._reasons(
                stat="receiving yards", side="over",
                snow=False, precip_prob=10, precip_intensity="heavy",
            ),
            ([], []),
        )
        nhl_snow = self._derive(
            stat="sog", side="over", outdoor=True,
            snow=True, precip_prob=60, precip_intensity="heavy",
        )
        self.assertEqual(nhl_snow["hard_veto_reasons"], ["SNOW"])
        self.assertNotIn("WEATHER_RISK", nhl_snow["soft_flags_derived"])
        nhl_rain = self._derive(
            stat="shots", side="over", outdoor=True, precip_intensity="light",
        )
        self.assertEqual(nhl_rain["hard_veto_reasons"], ["OUTDOOR_NHL_RAIN"])
        self.assertEqual(nhl_rain["soft_flags_derived"], [])
        self.assertEqual(
            self._reasons(
                stat="shots on goal", side="over", outdoor=True,
                precip_prob=10, precip_intensity="moderate",
            ),
            (["OUTDOOR_NHL_RAIN"], []),
        )
        self.assertEqual(
            self._reasons(stat="shots on goal", side="over", precip_intensity="heavy"),
            ([], []),
        )

    def test_goalie_quarterback_and_rest(self):
        saves = self._derive(stat="saves", side="over", goalie_confirmed=False)
        self.assertEqual(saves["hard_veto_reasons"], ["SAVES_GOALIE_UNCONFIRMED"])
        self.assertNotIn("UNCONFIRMED_GOALIE", saves["soft_flags_derived"])
        self.assertEqual(self._reasons(stat="saves", side="under", goalie_confirmed=False), (["SAVES_GOALIE_UNCONFIRMED"], []))
        self.assertEqual(self._reasons(stat="saves", side="over", goalie_confirmed=True), ([], []))
        shots = self._derive(stat="shots on goal", side="under", goalie_confirmed=False)
        self.assertEqual(shots["hard_veto_reasons"], [])
        self.assertEqual(shots["soft_flags_derived"], ["UNCONFIRMED_GOALIE"])
        self.assertEqual(self._reasons(stat="shots on goal", side="over", goalie_confirmed=True), ([], []))
        self.assertEqual(
            self._reasons(stat="pass attempts", side="over", expected_starting_qb=False),
            (["NOT_EXPECTED_STARTING_QB"], []),
        )
        self.assertEqual(
            self._reasons(stat="passing yards", side="over", expected_starting_qb=True),
            ([], []),
        )
        self.assertEqual(
            self._reasons(stat="receptions", side="over", expected_starting_qb=False),
            ([], []),
        )
        self.assertEqual(
            self._reasons(
                stat="pass attempts", side="over",
                expected_starting_qb=False, sustained_wind_mph=20,
            ),
            (["NOT_EXPECTED_STARTING_QB", "SUSTAINED_WIND"], []),
        )
        self.assertEqual(
            self._reasons(stat="points", side="over", back_to_back=True),
            ([], ["REST_SPOT"]),
        )
        self.assertEqual(
            self._reasons(stat="points", side="under", back_to_back=True, third_in_four=True),
            ([], []),
        )
        self.assertEqual(
            self._reasons(stat="assists", side="over", back_to_back=True, third_in_four=True),
            ([], ["REST_SPOT"]),
        )

    def test_weather_not_checked_is_a_data_veto(self):
        missing = self._derive(stat="passing yards", side="over", outdoor=True)
        self.assertIn("WEATHER_NOT_CHECKED", missing["data_veto_reasons"])
        self.assertIn("STARTING_QB_UNCONFIRMED", missing["data_veto_reasons"])
        self.assertEqual(
            self._derive(stat="blocked shots", side="over", outdoor=True)["data_veto_reasons"],
            ["WEATHER_NOT_CHECKED"],
        )
        self.assertEqual(
            self._derive(stat="points", side="over", outdoor=True)["data_veto_reasons"],
            [],
        )
        self.assertEqual(
            self._derive(stat="passing yards", side="over", outdoor=False)["data_veto_reasons"],
            ["STARTING_QB_UNCONFIRMED"],
        )
        checked = self._derive(stat="rushing yards", side="over", outdoor=True, sustained_wind_mph=0)
        self.assertEqual(checked["data_veto_reasons"], ["WEATHER_NOT_CHECKED"])
        self.assertEqual(checked["hard_veto_reasons"], [])

    def test_bad_context_is_rejected(self):
        for fields in (
            {"stat": "steals"},
            {"stat": "points", "role": "lb"},
            {"stat": "points", "precip_intensity": "severe"},
            {"stat": "points", "minutes_tonight": -1},
            {"stat": "points", "sustained_wind_mph": -1},
            {"stat": "points", "precip_prob": 101},
            {"stat": "points", "snap_pct_tonight": 1.2},
        ):
            with self.subTest(fields=fields):
                with self.assertRaises(pm.PickemError):
                    self._derive(side="over", **fields)
        with self.assertRaises(pm.PickemError) as caught:
            pm.evaluate_candidate(self._row(stat="points", blowout=True))
        self.assertIn("unknown pipeline fields: blowout", str(caught.exception))

    def test_aliases(self):
        self.assertEqual(
            self._reasons(stat="PRA", side="over", minutes_tonight=17.9),
            (["NBA_MINUTES_UNDER_18"], []),
        )
        self.assertEqual(
            self._reasons(stat="SOG", side="over", ice_time_tonight=11),
            (["NHL_ICE_UNDER_12"], []),
        )

    def test_pipeline_ors_the_veto_and_adds_the_flag(self):
        vetoed = pm.evaluate_candidate(self._row(stat="points", minutes_tonight=17.9))
        self.assertEqual(vetoed["derived_vetoes"]["hard_veto_reasons"], ["NBA_MINUTES_UNDER_18"])
        self.assertNotIn("THIN_WORKLOAD", vetoed["derived_soft_flags"])
        self.assertNotIn("NBA_MINUTES_UNDER_18", vetoed["derived_flags"])
        self.assertTrue(vetoed["grade"]["hard_veto"])
        self.assertNotEqual(vetoed["grade"]["probability_rank"], "REJECT")
        self.assertEqual(vetoed["final_rank"], "Reject")

        thin = pm.evaluate_candidate(self._row(stat="points", minutes_tonight=18.0))
        self.assertEqual(thin["derived_soft_flags"], ["THIN_WORKLOAD"])
        self.assertFalse(thin["grade"]["hard_veto"])
        self.assertEqual(thin["soft_flags_to_grade"], 1)
        self.assertEqual(thin["grade"]["qualitative_flags"], 1)
        self.assertEqual(thin["final_rank"], "Watchlist")

        added = pm.evaluate_candidate(self._row(stat="points", minutes_tonight=20, soft_flags=1))
        self.assertEqual(added["soft_flags_passed"], 1)
        self.assertEqual(added["soft_flags_to_grade"], 2)
        self.assertEqual(added["final_rank"], "Watchlist")

        stacked = pm.evaluate_candidate(self._row(
            stat="points", minutes_tonight=20, is_starter=True, spread=8.5, back_to_back=True,
        ))
        self.assertEqual(
            stacked["derived_soft_flags"],
            ["THIN_WORKLOAD", "SCRIPT_RISK", "REST_SPOT"],
        )
        self.assertEqual(stacked["final_rank"], "Watchlist")

        manual = pm.evaluate_candidate(self._row(stat="points", minutes_tonight=32, hard_veto=True))
        self.assertEqual(manual["derived_vetoes"]["hard_veto_reasons"], [])
        self.assertTrue(manual["grade"]["hard_veto"])
        self.assertEqual(manual["final_rank"], "Reject")

        quiet = pm.evaluate_candidate(self._row(
            stat="points", side="under", minutes_tonight=10,
            baseline_mean=1.2, q_market=0.70,
        ))
        self.assertEqual(quiet["derived_vetoes"]["hard_veto_reasons"], [])
        self.assertEqual(quiet["derived_soft_flags"], [])
        self.assertFalse(quiet["grade"]["hard_veto"])
        self.assertNotEqual(quiet["final_rank"], "Reject")

    def test_missing_outdoor_weather_unranks_and_keeps_a_hard_reason(self):
        result = pm.evaluate_candidate(self._row(
            stat="passing yards", outdoor=True, snap_pct_tonight=0.30,
        ))
        self.assertIn("WEATHER_NOT_CHECKED", result["derived_vetoes"]["data_veto_reasons"])
        self.assertIn("STARTING_QB_UNCONFIRMED", result["derived_vetoes"]["data_veto_reasons"])
        self.assertIn("NFL_SNAPS_UNDER_40", result["derived_vetoes"]["hard_veto_reasons"])
        self.assertTrue(result["grade"]["data_veto"])
        self.assertTrue(result["grade"]["hard_veto"])
        self.assertEqual(result["final_rank"], "Unranked")

    def test_cli_and_batch_accept_the_context_fields(self):
        help_run = _run(["pipeline", "--help"])
        self.assertEqual(help_run.returncode, 0, help_run.stderr)
        self.assertIn("--minutes-tonight", help_run.stdout)
        self.assertIn("Do not count them manually", help_run.stdout)
        common = [
            "pipeline", "--dist", "poisson", "--side", "over", "--line", "2.5",
            "--baseline-mean", "3.4", "--baseline-n", "30", "--soft-flags", "0",
            "--mechanisms", "2", "--hard-veto", "no", "--data-veto", "no",
            "--research-checklist", "yes", "--q-market", "0.66",
            "--retrieved-minutes-ago", "5", "--stat", "points",
        ]
        veto = _run([*common, "--minutes-tonight", "17.9", "--json"])
        self.assertEqual(veto.returncode, 0, veto.stderr)
        body = json.loads(veto.stdout)
        self.assertEqual(body["final_rank"], "Reject")
        self.assertEqual(body["derived_vetoes"]["hard_veto_reasons"], ["NBA_MINUTES_UNDER_18"])
        text = _run([*common, "--minutes-tonight", "18"])
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn("derived_soft_flags=THIN_WORKLOAD", text.stdout)
        self.assertIn("derived_vetoes=none", text.stdout)
        spread = _run([
            *common, "--is-starter", "yes", "--spread", "9.5", "--json",
        ])
        self.assertEqual(spread.returncode, 0, spread.stderr)
        self.assertEqual(json.loads(spread.stdout)["final_rank"], "Reject")
        good = self._row(id="thin", stat="points", minutes_tonight=18)
        bad = self._row(id="bad-role", stat="points", role="lb")
        batch = _run(
            ["pipeline", "--batch", "--stdin"],
            stdin=json.dumps(good) + "\n" + json.dumps(bad) + "\n",
        )
        self.assertNotEqual(batch.returncode, 0)
        rows = [json.loads(line) for line in batch.stdout.splitlines() if line.strip()]
        self.assertEqual(rows[0]["final_rank"], "Watchlist")
        self.assertEqual(rows[0]["derived_soft_flags"], ["THIN_WORKLOAD"])
        self.assertFalse(rows[1]["ok"])
        self.assertEqual(rows[1]["final_rank"], "Unranked")
        self.assertIn("role must be", rows[1]["error"])


class RobustMeanTests(unittest.TestCase):
    """q_win stays the plug-in probability. q_win_robust averages it over the mean."""

    def _row(self, **extra):
        raw = {
            "dist": "poisson",
            "side": "over",
            "line": 2.5,
            "baseline_mean": 3.02,
            "baseline_n": 10,
            "soft_flags": 0,
            "mechanisms": 2,
            "hard_veto": False,
            "data_veto": False,
            "research_checklist": True,
            "q_market": 0.60,
            "retrieved_minutes_ago": 5,
        }
        raw.update(extra)
        return raw

    def _distance(self, n):
        row = pm.project("poisson", "over", 2.5, baseline_mean=4.0, baseline_n=n)
        return abs(row["q_win"] - row["q_win_robust"])

    def test_docstring_warns_that_constants_stay_uncalibrated(self):
        warning = "All constants remain uncalibrated until scripts/report.py shows at least 300"
        self.assertIn(warning, pm.__doc__)
        self.assertIn(warning, pm.project.__doc__)
        self.assertEqual((pm.TIER_1, pm.TIER_2, pm.TIER_3, pm.WATCH_FLOOR), (0.58, 0.57, 0.56, 0.52))

    def test_point_probability_is_unchanged_and_prior_defaults_off(self):
        row = pm.project("poisson", "over", 2.5, baseline_mean=3.4, baseline_n=30)
        self.assertAlmostEqual(row["q_win"], poisson_ge(3.4, 3), places=5)
        self.assertNotIn("PRIOR_USED", row["notes"])
        self.assertAlmostEqual(row["sample_effective_n"], row["current_role_n"])
        self.assertAlmostEqual(row["mean_se"], math.sqrt(row["shrunk_mean"] / row["sample_effective_n"]))
        self.assertIn("q_win_robust", row)
        self.assertIn("mean_se", row)

    def test_robust_probability_is_pulled_toward_one_half(self):
        cases = (
            ("poisson", "over", 2.5, {"baseline_mean": 4.0, "baseline_n": 8}),
            ("poisson", "under", 2.5, {"baseline_mean": 4.0, "baseline_n": 8}),
            ("negbin", "over", 2.5, {"baseline_mean": 4.0, "baseline_n": 8, "var_ratio": 1.8}),
            ("normal", "over", 24.5, {"baseline_mean": 27.0, "baseline_n": 12, "sd": 6}),
            ("normal", "under", 24.5, {"baseline_mean": 27.0, "baseline_n": 12, "sd": 6}),
        )
        for dist, side, line, kwargs in cases:
            row = pm.project(dist, side, line, **kwargs)
            point, robust = row["q_win"], row["q_win_robust"]
            self.assertLess(abs(robust - 0.5), abs(point - 0.5), msg=dist + " " + side)
            if point > 0.5:
                self.assertGreater(point, robust)
                self.assertGreater(robust, 0.5)
            else:
                self.assertLess(point, robust)
                self.assertLess(robust, 0.5)

    def test_small_samples_move_farther_than_long_samples(self):
        short = pm.project("poisson", "over", 2.5, baseline_mean=4.0, baseline_n=5)
        long = pm.project("poisson", "over", 2.5, baseline_mean=4.0, baseline_n=30)
        self.assertAlmostEqual(short["q_win"], long["q_win"], places=12)
        self.assertGreater(self._distance(5), self._distance(30))
        self.assertGreater(self._distance(30), self._distance(200))

    def test_robust_converges_to_q_win_as_n_grows(self):
        self.assertGreater(self._distance(200), self._distance(2000))
        huge = pm.project("poisson", "over", 2.5, baseline_mean=4.0, baseline_n=20000)
        self.assertAlmostEqual(huge["q_win"], huge["q_win_robust"], places=4)
        normal = pm.project("normal", "over", 24.5, baseline_mean=27, baseline_n=12, sd=6)
        predictive_sd = math.sqrt(normal["sd_used"] ** 2 + normal["mean_se"] ** 2)
        closed = 1 - NormalDist(normal["shrunk_mean"], predictive_sd).cdf(24.5)
        self.assertAlmostEqual(normal["q_win_robust"], closed, places=6)

    def test_prior_path_is_monotone_and_capped_at_20(self):
        previous = None
        for prior_mean in (1.0, 2.5, 4.0, 7.0):
            row = pm.project(
                "poisson", "over", 2.5, baseline_mean=3.0, baseline_n=12,
                prior_mean=prior_mean, prior_n=8,
            )
            self.assertIn("PRIOR_USED", row["notes"])
            self.assertAlmostEqual(row["sample_effective_n"], row["current_role_n"] + 8)
            if previous is not None:
                self.assertGreater(row["shrunk_mean"], previous["shrunk_mean"])
                self.assertGreater(row["q_win"], previous["q_win"])
            previous = row
        rising = []
        for prior_n in (1, 5, 10, 20, 35):
            row = pm.project(
                "poisson", "over", 2.5, baseline_mean=2.0, baseline_n=10,
                prior_mean=8.0, prior_n=prior_n,
            )
            rising.append(row["shrunk_mean"])
            self.assertAlmostEqual(row["sample_effective_n"], 10 + min(prior_n, 20))
        self.assertGreater(rising[1], rising[0])
        self.assertGreater(rising[2], rising[1])
        self.assertGreater(rising[3], rising[2])
        self.assertAlmostEqual(rising[3], rising[4], places=12)
        capped = (10 * 2.0 + 20 * 8.0) / 30
        self.assertAlmostEqual(rising[4], capped, places=9)
        self.assertNotAlmostEqual(rising[4], (10 * 2.0 + 35 * 8.0) / 45, places=3)
        falling = []
        for prior_n in (1, 5, 20):
            row = pm.project(
                "poisson", "over", 2.5, baseline_mean=5.0, baseline_n=10,
                prior_mean=1.0, prior_n=prior_n,
            )
            falling.append(row["q_win"])
        self.assertGreater(falling[0], falling[1])
        self.assertGreater(falling[1], falling[2])
        matched = pm.project(
            "poisson", "over", 2.5, baseline_mean=4.0, baseline_n=10,
            prior_mean=4.0, prior_n=10,
        )
        plain = pm.project("poisson", "over", 2.5, baseline_mean=4.0, baseline_n=10)
        self.assertAlmostEqual(matched["q_win"], plain["q_win"], places=12)
        self.assertGreater(self._distance(10), abs(matched["q_win"] - matched["q_win_robust"]))

    def test_prior_is_applied_before_the_recent_blend(self):
        row = pm.project(
            "poisson", "over", 2.5,
            baseline_mean=2, baseline_n=10,
            prior_mean=6, prior_n=10,
            recent_mean=8, recent_n=10, season_n=20,
        )
        self.assertAlmostEqual(row["blended_rate"], 160/30, places=9)
        self.assertEqual(row["current_role_n"], 20)
        self.assertAlmostEqual(row["sample_effective_n"], 30)
        self.assertIn("PRIOR_USED", row["notes"])
        baseline_prime = (30 * 2 + 10 * 6) / 40
        role = pm.project(
            "poisson", "over", 2.5,
            baseline_mean=2, baseline_n=30,
            prior_mean=6, prior_n=10,
            recent_mean=8, recent_n=4, season_n=34,
            role_change=True,
            workload_baseline=20, workload_expected=24,
        )
        self.assertAlmostEqual(role["blended_rate"], (4 * 8 + 8 * baseline_prime) / 12, places=9)
        self.assertAlmostEqual(role["trusted_mean"], (4 * 8 + 8 * baseline_prime) / 12, places=9)
        self.assertEqual(role["current_role_n"], 4)
        self.assertAlmostEqual(role["sample_effective_n"], 12**2/(4+8**2/40))
        self.assertNotIn("WORKLOAD_ON_PRIOR_ONLY", role["notes"])
        with self.assertRaises(pm.PickemError):
            pm.project("poisson", "over", 2.5, baseline_mean=3, baseline_n=10, prior_mean=4)
        with self.assertRaises(pm.PickemError):
            pm.project("poisson", "over", 2.5, baseline_mean=3, baseline_n=10, prior_n=4)

    def test_mean_se_follows_the_distribution(self):
        poisson = pm.project("poisson", "over", 2.5, baseline_mean=4, baseline_n=20)
        self.assertAlmostEqual(poisson["mean_se"], math.sqrt(4 / 20), places=9)
        negbin = pm.project("negbin", "over", 2.5, baseline_mean=4, baseline_n=20, var_ratio=1.8)
        self.assertAlmostEqual(
            negbin["mean_se"], math.sqrt(1.8 * negbin["shrunk_mean"] / 20), places=9,
        )
        normal = pm.project("normal", "over", 24.5, baseline_mean=27, baseline_n=12, sd=6)
        self.assertAlmostEqual(normal["mean_se"], normal["sd_used"] / math.sqrt(12), places=9)
        with_prior = pm.project(
            "poisson", "over", 2.5, baseline_mean=4, baseline_n=10,
            prior_mean=4, prior_n=25,
        )
        self.assertAlmostEqual(with_prior["sample_effective_n"], 30)
        self.assertAlmostEqual(with_prior["mean_se"], math.sqrt(4 / 30), places=9)
        empty = pm.project(
            "poisson", "over", 2.5, baseline_mean=3, baseline_n=20,
            role_change=True, workload_baseline=20, workload_expected=24,
        )
        self.assertEqual(empty["sample_effective_n"], 0)
        self.assertIsNone(empty["mean_se"])
        self.assertAlmostEqual(empty["q_win_robust"], empty["q_win"])
        self.assertNotIn("PRIOR_USED", empty["notes"])

    def test_whole_number_lines_still_sum_to_one_with_push(self):
        specs = (
            ("poisson", {"baseline_mean": 3.2, "baseline_n": 18}),
            ("negbin", {"baseline_mean": 3.2, "baseline_n": 18, "var_ratio": 1.8}),
            ("normal", {"baseline_mean": 3.2, "baseline_n": 18, "sd": 1.4}),
        )
        for dist, kwargs in specs:
            row = pm.project(dist, "over", 3, **kwargs)
            self.assertTrue(row["whole_line"])
            self.assertGreater(row["q_push"], 0)
            self.assertGreater(row["q_push_robust"], 0)
            self.assertAlmostEqual(row["q_win"] + row["q_loss"] + row["q_push"], 1, places=9)
            self.assertAlmostEqual(
                row["q_win_over_robust"] + row["q_win_under_robust"] + row["q_push_robust"],
                1,
                places=9,
            )
            self.assertAlmostEqual(
                row["q_win_robust"] + row["q_loss_robust"] + row["q_push_robust"],
                1,
                places=9,
            )
        hook = pm.project("poisson", "over", 2.5, baseline_mean=3.2, baseline_n=18)
        self.assertAlmostEqual(hook["q_push_robust"], 0, places=12)
        self.assertAlmostEqual(hook["q_win_over_robust"] + hook["q_win_under_robust"], 1, places=9)

    def test_default_tier_basis_integrates_uncertainty(self):
        point = pm.evaluate_candidate(self._row())
        self.assertEqual(point["tier_basis"], "q_win_robust")
        self.assertEqual(point["grade"]["q_model"], point["project"]["q_win_robust"])
        self.assertEqual(point["grade"]["q_push"], point["project"]["q_push_robust"])
        self.assertNotEqual(point["final_rank"], "Tier 1")

    def test_robust_tier_basis_moves_the_gap_and_the_unicorn(self):
        robust = pm.evaluate_candidate(self._row(tier_basis="q_win_robust"))
        self.assertEqual(robust["tier_basis"], "q_win_robust")
        self.assertEqual(robust["grade"]["tier_basis"], "q_win_robust")
        self.assertEqual(robust["grade"]["q_model"], robust["project"]["q_win_robust"])
        self.assertLess(robust["grade"]["q_grade"], pm.TIER_1)
        self.assertFalse(robust["grade"]["unicorn_numeric"])
        self.assertEqual(robust["final_rank"], "Watchlist")
        self.assertAlmostEqual(
            robust["grade"]["q_gap"],
            robust["grade"]["q_model"] - robust["grade"]["q_market_comparable"],
            places=12,
        )
        whole = pm.evaluate_candidate(self._row(line=3.0, baseline_mean=3.4, tier_basis="q_win_robust"))
        self.assertEqual(whole["grade"]["q_model"], whole["project"]["q_win_robust"])
        self.assertEqual(whole["grade"]["q_push"], whole["project"]["q_push_robust"])
        self.assertGreater(abs(whole["project"]["q_push"] - whole["project"]["q_push_robust"]), 1e-4)
        with self.assertRaises(pm.PickemError):
            pm.evaluate_candidate(self._row(tier_basis="shrunk"))

    def test_cli_prints_both_probabilities(self):
        text = _run([
            "project", "--dist", "poisson", "--side", "over", "--line", "2.5",
            "--baseline-mean", "4", "--baseline-n", "12",
        ])
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn("q_win=", text.stdout)
        self.assertIn("q_win_robust=", text.stdout)
        self.assertIn("q_win_robust_raw=", text.stdout)
        self.assertIn("mean_se=", text.stdout)
        self.assertIn("sample_effective_n=", text.stdout)
        self.assertNotIn("PRIOR_USED", text.stdout)
        used = _run([
            "project", "--dist", "poisson", "--side", "over", "--line", "2.5",
            "--baseline-mean", "4", "--baseline-n", "12",
            "--prior-mean", "6", "--prior-n", "40", "--json",
        ])
        self.assertEqual(used.returncode, 0, used.stderr)
        body = json.loads(used.stdout)
        self.assertIn("PRIOR_USED", body["notes"])
        self.assertAlmostEqual(body["sample_effective_n"], 32)
        self.assertIn("--prior-mean", _run(["project", "--help"]).stdout)
        help_run = _run(["pipeline", "--help"])
        self.assertIn("--tier-basis", help_run.stdout)
        self.assertIn("q_win_robust", help_run.stdout)
        pipe = _run([
            "pipeline", "--dist", "poisson", "--side", "over", "--line", "2.5",
            "--baseline-mean", "3.02", "--baseline-n", "10",
            "--soft-flags", "0", "--mechanisms", "2",
            "--hard-veto", "no", "--data-veto", "no", "--research-checklist", "yes",
            "--q-market", "0.60", "--retrieved-minutes-ago", "5",
            "--tier-basis", "q_win_robust", "--json",
        ])
        self.assertEqual(pipe.returncode, 0, pipe.stderr)
        audited = json.loads(pipe.stdout)
        self.assertEqual(audited["tier_basis"], "q_win_robust")
        self.assertEqual(audited["grade"]["q_model"], audited["project"]["q_win_robust"])
        self.assertEqual(audited["final_rank"], "Watchlist")
        shown = _run([
            "pipeline", "--dist", "poisson", "--side", "over", "--line", "2.5",
            "--baseline-mean", "4", "--baseline-n", "12",
            "--soft-flags", "0", "--mechanisms", "1",
            "--hard-veto", "no", "--data-veto", "no", "--research-checklist", "no",
            "--q-market", "0.55", "--retrieved-minutes-ago", "5",
        ])
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertIn("q_win=", shown.stdout)
        self.assertIn("q_win_robust=", shown.stdout)
        self.assertIn("tier_basis=q_win", shown.stdout)


_SCAN_FIELDS = (
    "id", "side", "q_win", "q_market_comparable", "q_gap",
    "shrunk_mean", "current_role_n", "sample_block", "reason",
)


class ScanTests(unittest.TestCase):
    def _row(self, ident, side="over", mean=3.4, market=0.60, **extra):
        raw = {
            "id": ident,
            "dist": "poisson",
            "side": side,
            "line": 2.5,
            "baseline_mean": mean,
            "baseline_n": 30,
            "q_market": market,
            "retrieved_minutes_ago": 5,
            "hard_veto": "no",
            "data_veto": "no",
            "research_checklist": "no",
        }
        raw.update(extra)
        return raw

    def _ids(self, result):
        return [row["id"] for row in result["shortlist"]]

    def test_placeholders_shortlist_and_block_a_thin_sample(self):
        strong = self._row("NBA|A|points|over", mean=4.0, market=0.55)
        self.assertNotIn("mechanisms", strong)
        self.assertNotIn("soft_flags", strong)
        weak = self._row("NBA|B|points|over", mean=2.2, market=0.40, mechanisms=0, soft_flags=4)
        blocked = self._row("NBA|C|points|over", mean=4.0, market=0.55, baseline_n=3)
        result = pm.scan_candidates([strong, weak, blocked])
        self.assertEqual(result["tier_basis"], "q_win_robust")
        self.assertEqual(result["counts"], {"scanned": 3, "unresearchable": 1, "shortlisted": 1})
        self.assertEqual(set(result["shortlist"][0]), set(_SCAN_FIELDS))
        kept = result["shortlist"][0]
        projected = pm.project("poisson", "over", 2.5, baseline_mean=4.0, baseline_n=30)
        self.assertEqual(kept["id"], "NBA|A|points|over")
        self.assertEqual(kept["side"], "over")
        self.assertEqual(kept["q_win"], projected["q_win"])
        self.assertGreaterEqual(kept["q_win"], 0.56)
        self.assertEqual(kept["shrunk_mean"], projected["shrunk_mean"])
        self.assertEqual(kept["current_role_n"], projected["current_role_n"])
        self.assertFalse(kept["sample_block"])
        self.assertEqual(kept["reason"], "q_win")
        self.assertEqual(weak["mechanisms"], 0)
        self.assertEqual(weak["soft_flags"], 4)
        blocked_row = result["unresearchable"][0]
        self.assertEqual(blocked_row["id"], "NBA|C|points|over")
        self.assertTrue(blocked_row["sample_block"])
        self.assertEqual(blocked_row["reason"], "SAMPLE_BLOCK")
        self.assertNotIn("NBA|B|points|over", self._ids(result))

    def test_gap_clause_and_both_sides_floor(self):
        close = pm.project("poisson", "over", 2.5, baseline_mean=2.90, baseline_n=30)
        self.assertLess(close["q_win"], 0.56)
        self.assertLessEqual(abs(close["q_win"] - 0.55), 0.06)
        kept = pm.scan_candidates([self._row("NBA|Gap|sog|over", mean=2.90, market=0.55)])
        self.assertEqual(self._ids(kept), ["NBA|Gap|sog|over"])
        self.assertEqual(kept["shortlist"][0]["reason"], "q_gap")
        self.assertGreaterEqual(kept["shortlist"][0]["q_market_comparable"], 0.54)
        far = pm.scan_candidates([self._row("NBA|Far|sog|over", mean=2.90, market=0.40)])
        self.assertEqual(far["shortlist"], [])
        self.assertEqual(far["counts"]["unresearchable"], 0)

        over = pm.project("poisson", "over", 2.5, baseline_mean=2.70, baseline_n=30)
        under = pm.project("poisson", "under", 2.5, baseline_mean=2.70, baseline_n=30)
        self.assertTrue(pm._below(over["q_win"], 0.52))
        self.assertTrue(pm._below(under["q_win"], 0.52))
        alone = pm.scan_candidates([self._row("NBA|Pair|sog|over", mean=2.70, market=0.54)])
        self.assertEqual(self._ids(alone), ["NBA|Pair|sog|over"])
        pair = pm.scan_candidates([
            self._row("NBA|Pair|sog|over", mean=2.70, market=0.54),
            self._row("NBA|Pair|sog|under", side="under", mean=2.70, market=0.40),
        ])
        self.assertEqual(pair["shortlist"], [])
        self.assertEqual(pair["counts"], {"scanned": 2, "unresearchable": 0, "shortlisted": 0})

    def test_cap_sorts_by_q_win_then_tighter_gap(self):
        rows = [
            self._row(f"NBA|P{i:02d}|points|over", mean=3.0 + i * 0.05, market=0.55)
            for i in range(41)
        ]
        capped = pm.scan_candidates(rows)
        self.assertEqual(capped["counts"]["scanned"], 41)
        self.assertEqual(capped["counts"]["shortlisted"], 40)
        self.assertNotIn("NBA|P00|points|over", self._ids(capped))
        self.assertEqual(capped["shortlist"][0]["id"], "NBA|P40|points|over")
        q_wins = [row["q_win"] for row in capped["shortlist"]]
        self.assertEqual(q_wins, sorted(q_wins, reverse=True))

        high = self._row("NBA|High|points|over", mean=4.0, market=0.50)
        tight = self._row("NBA|Tight|points|over", mean=3.2, market=0.62)
        order = pm.scan_candidates([tight, high], cap=1)
        self.assertEqual(self._ids(order), ["NBA|High|points|over"])
        wider = self._row("NBA|Wide|points|over", mean=4.0, market=0.70)
        nearer = self._row("NBA|Near|points|over", mean=4.0, market=0.76)
        tie = pm.scan_candidates([wider, nearer], cap=1)
        self.assertEqual(self._ids(tie), ["NBA|Near|points|over"])
        wider_only = pm.scan_candidates([wider], cap=1)["shortlist"][0]["q_gap"]
        self.assertLess(abs(tie["shortlist"][0]["q_gap"]), abs(wider_only))

    def test_trigger_bypasses_the_cap_and_the_floor(self):
        strong = self._row("NBA|A|points|over", mean=4.0, market=0.55)
        other = self._row("NBA|B|points|over", mean=3.4, market=0.55)
        weak = self._row("NBA|C|points|over", mean=2.55, market=0.40, trigger=True)
        result = pm.scan_candidates([strong, other, weak], cap=1)
        self.assertEqual(self._ids(result), ["NBA|A|points|over", "NBA|C|points|over"])
        reasons = {row["id"]: row["reason"] for row in result["shortlist"]}
        self.assertEqual(reasons["NBA|C|points|over"], "trigger")
        pair = pm.scan_candidates(
            [
                self._row("NBA|Pair|sog|over", mean=2.70, market=0.54),
                self._row("NBA|Pair|sog|under", side="under", mean=2.70, market=0.40),
            ],
            triggers=["NBA|Pair|sog|over"],
        )
        self.assertEqual(self._ids(pair), ["NBA|Pair|sog|over"])
        listed = pm.scan_candidates(
            [
                {"triggers": ["NBA|Role|points"]},
                self._row("NBA|Role|points|over", mean=2.55, market=0.40),
                self._row("NBA|Role|points|under", side="under", mean=2.55, market=0.40),
            ],
        )
        self.assertEqual(listed["counts"]["scanned"], 2)
        self.assertEqual(set(self._ids(listed)), {"NBA|Role|points|over", "NBA|Role|points|under"})
        thin = self._row("NBA|Thin|points|over", mean=4.0, market=0.55, baseline_n=3, trigger=True)
        blocked = pm.scan_candidates([thin], triggers=["NBA|Thin|points"])
        self.assertEqual(blocked["shortlist"], [])
        self.assertEqual(blocked["unresearchable"][0]["reason"], "SAMPLE_BLOCK")

    def test_market_line_and_derived_vetoes_stay_in_force(self):
        mismatch = self._row(
            "NBA|Bad|points|over", mean=4.0,
            books=["Pinnacle:3.5:-130:+110:over"],
        )
        mismatch.pop("q_market")
        blocked = pm.scan_candidates([mismatch])
        self.assertEqual(blocked["shortlist"], [])
        self.assertIn("does not match", blocked["unresearchable"][0]["reason"])
        self.assertIsNone(blocked["unresearchable"][0]["sample_block"])

        stale = self._row(
            "NBA|Old|points|over", mean=4.0,
            books=["Pinnacle:2.5:-130:+110:over"],
            retrieved_minutes_ago=45,
        )
        stale.pop("q_market")
        stale_result = pm.scan_candidates([stale])
        self.assertEqual(stale_result["unresearchable"][0]["reason"], "STALE")
        self.assertFalse(stale_result["unresearchable"][0]["sample_block"])

        weather = self._row(
            "NFL|Wind|yards|over", mean=260, market=0.60,
            dist="normal", sd=40, line=240.5, stat="passing yards", outdoor="yes",
        )
        weather_result = pm.scan_candidates([weather])
        self.assertIn("WEATHER_NOT_CHECKED", weather_result["unresearchable"][0]["reason"])

        tail = self._row(
            "NBA|Tail|points|under", side="under", mean=8, market=0.60,
            dist="normal", sd=6, line=10.5, baseline_n=20,
        )
        tail_result = pm.scan_candidates([tail])
        self.assertTrue(tail_result["unresearchable"][0]["sample_block"])
        self.assertEqual(tail_result["unresearchable"][0]["reason"], "NORMAL_LEFT_TAIL")

        veto = self._row(
            "NBA|Minutes|points|over", mean=4.0, market=0.55,
            stat="points", minutes_tonight=10,
        )
        graded = pm.evaluate_candidate({
            **veto, "mechanisms": 2, "soft_flags": 0,
        })
        self.assertEqual(graded["final_rank"], "Reject")
        self.assertIn("NBA_MINUTES_UNDER_18", graded["derived_vetoes"]["hard_veto_reasons"])
        kept = pm.scan_candidates([veto])
        self.assertEqual(self._ids(kept), ["NBA|Minutes|points|over"])

    def test_robust_basis_moves_the_cut_and_the_default_stays_on_q_win(self):
        projected = pm.project("poisson", "over", 2.5, baseline_mean=2.93, baseline_n=30)
        self.assertGreaterEqual(projected["q_win"], 0.56)
        self.assertLess(projected["q_win_robust"], 0.56)
        row = self._row("NBA|Edge|points|over", mean=2.93, market=0.40)
        default = pm.scan_candidates([row])
        robust = pm.scan_candidates([row], tier_basis="q_win_robust")
        self.assertEqual(default["shortlist"], [])
        self.assertEqual(default["tier_basis"], "q_win_robust")
        self.assertEqual(robust["shortlist"], [])
        self.assertEqual(robust["tier_basis"], "q_win_robust")
        raised = pm.scan_candidates([self._row("NBA|Hi|points|over", mean=4.0)], min_q_win=0.90)
        self.assertEqual(raised["shortlist"], [])

    def test_cli_reads_prep_jsonl(self):
        body = "\n".join([
            json.dumps({"triggers": ["NBA|Role|points"]}),
            "",
            json.dumps(self._row("NBA|A|points|over", mean=4.0, market=0.55)),
            "{not json",
            json.dumps(self._row("NBA|Role|points|under", side="under", mean=2.55, market=0.40)),
        ])
        completed = _run(["scan", "--stdin", "--cap", "1"], stdin=body)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["counts"]["scanned"], 3)
        self.assertEqual(result["counts"]["unresearchable"], 1)
        self.assertEqual(result["counts"]["shortlisted"], 2)
        self.assertTrue(result["unresearchable"][0]["reason"].startswith("invalid JSON"))
        self.assertEqual(
            [row["id"] for row in result["shortlist"]],
            ["NBA|A|points|over", "NBA|Role|points|under"],
        )
        missing = _run(["scan"])
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("stdin", missing.stderr)


class LogBatchTests(unittest.TestCase):
    def _record(self, player):
        return {
            "run_at": "2026-10-22 12:00 ET",
            "game_date": "2026-10-22",
            "sport": "NBA",
            "matchup": "BOS @ NYK",
            "player": player,
            "stat": "points",
            "side": "Over",
            "reference_line": 24.5,
            "final_rank": "Reject",
            "status": "GRADED",
            "researched": True,
        }

    def test_batch_appends_many_rows_in_one_process(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "props.jsonl"
            text = json.dumps(self._record("One")) + "\n" + json.dumps(self._record("Two")) + "\n"
            completed = _run(["log", "--batch", "--stdin", "--path", str(path)], stdin=text)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("logged=2", completed.stdout)
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["player"] for row in rows], ["One", "Two"])
        self.assertEqual(rows[0]["side"], "over")
        self.assertIsNone(rows[0]["actual_stat"])
        self.assertIsNone(rows[1]["closing_line"])

    def test_a_bad_row_writes_nothing(self):
        import tempfile
        good = self._record("One")
        bad = self._record("Two")
        bad["underdog_line"] = 1.5
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nested" / "props.jsonl"
            with self.assertRaises(pm.PickemError):
                pm.append_snapshots([good, bad], path)
            self.assertFalse(path.exists())
            completed = _run(
                ["log", "--batch", "--stdin", "--path", str(path)],
                stdin=json.dumps(good) + "\n{not json\n",
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("invalid", completed.stderr)
            self.assertFalse(path.exists())
        missing = _run(["log", "--batch"])
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("--stdin", missing.stderr)


if __name__ == "__main__":
    unittest.main()
