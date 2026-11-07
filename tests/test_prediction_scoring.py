"""Conditional scoring regressions; no model forecasts or records are changed."""
import ast
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prediction_scoring import conditional_mixture_win, conditional_win, market_conditional_win


class ConditionalMixtureTests(unittest.TestCase):
    def test_market_policy_score_retains_conditional_scale_and_zero(self):
        self.assertEqual(market_conditional_win({'q_market':.6,'q_market_comparable':.48,'q_push':.2}),.6)
        self.assertAlmostEqual(market_conditional_win({'q_market_comparable':.48,'q_push':.2}),.6)
        self.assertEqual(market_conditional_win({'q_market':0,'market':{'q_market':.6}}),0)
        self.assertEqual(market_conditional_win({'q_market_comparable':0,'q_push':.2,'market':{'q_market_comparable':.48}}),0)

    def test_missing_integer_market_push_mass_is_not_assumed(self):
        with self.assertRaisesRegex(ValueError,'market_conditional_scale_unavailable'):
            market_conditional_win({'reference_line':20,'q_market_comparable':.48})
        self.assertEqual(market_conditional_win({'reference_line':20.5,'q_market_comparable':.6}),.6)

    def test_single_probability_uses_same_nonpush_target(self):
        self.assertAlmostEqual(conditional_win(.4, .2), .5)
        self.assertEqual(conditional_win(.6, 0), .6)
        for q,push in [(0,1),(.9,.2),(None,0),(True,0),(.4,float('nan'))]:
            with self.subTest(q=q,push=push), self.assertRaises(ValueError):
                conditional_win(q,push)

    def test_equal_components_condition_on_nonpush(self):
        self.assertAlmostEqual(conditional_mixture_win(.4, .2, .4, .2), .5)

    def test_unequal_push_mass_uses_bayes_mixture_weights(self):
        # A: (win=.4,push=.5,loss=.1), B: (.6,0,.4).
        # Joint mixture masses: win=.46, push=.35, loss=.19.
        value = conditional_mixture_win(.4, .5, .6, 0)
        self.assertAlmostEqual(value, .46 / .65)
        self.assertNotAlmostEqual(value, .7 * (.4 / .5) + .3 * .6)

    def test_half_point_zero_push_probability_is_unchanged(self):
        self.assertAlmostEqual(conditional_mixture_win(.7, 0, .3, 0), .58)

    def test_all_push_component_has_zero_nonpush_posterior_weight(self):
        self.assertAlmostEqual(conditional_mixture_win(0, 1, .6, 0), .6)
        with self.assertRaisesRegex(ValueError, "undefined_all_push"):
            conditional_mixture_win(0, 1, 0, 1)

    def test_invalid_masses_and_weights_are_rejected(self):
        for q, push in [(None, 0), (True, 0), (.9, .2), (-.1, 0),
                        (.2, float("nan")), (float("inf"), 0)]:
            with self.subTest(q=q, push=push), self.assertRaises(ValueError):
                conditional_mixture_win(q, push, .5, 0)
        for weight in [-.1, 1.1, True, None, float("nan")]:
            with self.subTest(weight=weight), self.assertRaises(ValueError):
                conditional_mixture_win(.4, .2, .6, 0, weight_a=weight)

    def test_notebook_consensus_assignment_uses_conditional_transform(self):
        # Execute only the actual scorer's small assignment block; never run
        # notebook setup, API calls, settlement, or persistent write cells.
        notebook = json.loads((ROOT / "notebooks/deepnote_daily_cloud_inference.ipynb").read_text())
        source = next("".join(c.get("source", [])) for c in notebook["cells"]
                      if "# Morning: audit ONLY immutable pregame probabilities" in "".join(c.get("source", [])))
        tree = ast.parse(source)
        blocks = [n for n in ast.walk(tree) if isinstance(n, ast.Try) and
                  any(isinstance(child, ast.Assign) and
                      any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                          and t.slice.value == "diagnostic_70_30" for t in child.targets)
                      for child in n.body)]
        self.assertEqual(len(blocks), 1)
        env = {"conditional_mixture_win": conditional_mixture_win,
               "model": {"engine_a": .4, "engine_b": .4},
               "a": {"q_push_robust": .2}, "b": {"q_push": .2}}
        exec(compile(ast.Module(body=blocks, type_ignores=[]), "notebook_scorer_assignment", "exec"), env)
        self.assertAlmostEqual(env["model"]["diagnostic_70_30"], .5)


if __name__ == "__main__":
    unittest.main()
