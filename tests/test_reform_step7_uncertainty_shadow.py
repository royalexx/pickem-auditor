"""Step 7 read-only rank shadow: zero hindsight, deterministic negative controls."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT/"tests"))
import reform_step7_uncertainty_shadow as shadow
import reform_phase5_selection_audit as original
from test_reform_phase5_selection_audit import files,board_from


def setup(root):
    a,b=files(root)
    pool,_,_=original.rebuild_pool(a,b)
    doc=board_from(pool[0])
    p=Path(root)/"board.json"
    p.write_text(json.dumps(doc))
    return a,b,p


class Step7UncertaintyShadowTests(unittest.TestCase):
    def test_zero_strength_preserves_original_score(self):
        item={"score":72.25,"edge_pp":12.,"floor":.65}
        self.assertAlmostEqual(shadow.shadow_score(item,penalty_pp=10,strength=0),72.25)

    def test_penalty_reduces_edge_component_without_creating_negative_edge(self):
        item={"score":72.25,"edge_pp":12.,"floor":.65}
        a=shadow.shadow_score(item,penalty_pp=0,strength=1)
        b=shadow.shadow_score(item,penalty_pp=8,strength=1)
        c=shadow.shadow_score(item,penalty_pp=100,strength=1)
        self.assertGreater(a,b)
        self.assertGreater(b,c)
        self.assertAlmostEqual(c,72.25-12)
        self.assertAlmostEqual(a,72.25)

    def test_disagreement_is_not_mislabeled_as_calibrated_se(self):
        item={"row":{"Engine_A":.71,"Engine_B":.51,"Bayesian_A":.80,
                     "Bayesian_B":None,"models":{"Engine_B":{}}}}
        p=shadow.candidate_profile(item)
        self.assertAlmostEqual(p["spread"],.29)
        self.assertIsNone(p["relative_se"])
        self.assertIn("not_probability_standard_error",p["uncertainty_kind"])

    def test_invalid_engine_b_relative_se_rejected_not_imputed(self):
        item={"row":{"Engine_A":.71,"Engine_B":.51,"Bayesian_A":None,
                     "Bayesian_B":None,"models":{"Engine_B":{"relative_se":-.2}}}}
        with self.assertRaisesRegex(original.SelectionAuditError,"invalid_engine_b_relative_se"):
            shadow.candidate_profile(item)

    def test_immutable_exact_original_board_verified_before_research(self):
        with tempfile.TemporaryDirectory() as d:
            a,b,board=setup(d)
            result=shadow.audit(a,b,board)
            self.assertTrue(result["original_30_top10_reproduced"])
            self.assertEqual(result["original_eligible_candidates"],1)
            self.assertEqual(result["uncertainty_available"]["missing_relative_se"],1)
            self.assertFalse(result["production_modified"])
            self.assertFalse(result["rank_formula_deployed"])
            self.assertFalse(result["training_started"])
            self.assertEqual(result["variants"]["0.0"]["per_sport"]["NFL"]["original_overlap_top10"],1)
            self.assertEqual(result["negative_control_top10_overlap"]["NFL"],1)

    def test_shuffled_penalties_are_reproducible(self):
        with tempfile.TemporaryDirectory() as d:
            a,b,board=setup(d)
            self.assertEqual(shadow.audit(a,b,board),shadow.audit(a,b,board))

    def test_rewritten_rank_board_is_rejected_before_shadow_comparison(self):
        with tempfile.TemporaryDirectory() as d:
            a,b,board=setup(d)
            doc=json.loads(board.read_text())
            doc["top_10_by_sport"]["NFL"][0]["research_priority_score"]+=7.
            board.write_text(json.dumps(doc))
            with self.assertRaisesRegex(original.SelectionAuditError,
                                        "not_reproducible"):
                shadow.audit(a,b,board)

    def test_no_uncertainty_penalty_cannot_promote_probability(self):
        item={"score":88.0,"edge_pp":24.0,"floor":.79}
        score=shadow.shadow_score(item,penalty_pp=5,strength=1)
        self.assertLess(score,item["score"])
        self.assertEqual(item["score"],88.0)
        self.assertEqual(item["edge_pp"],24.0)


if __name__=="__main__":
    unittest.main()
