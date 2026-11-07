"""Regression guard: notebook reports the Engine B production probability correctly."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class NotebookEngineBMappingTests(unittest.TestCase):
    def test_deepnote_four_model_export_reads_scouting_q_win(self):
        notebook=json.loads((ROOT/"notebooks/deepnote_daily_cloud_inference.ipynb").read_text(encoding="utf-8"))
        text="\n".join("".join(c.get("source",[])) for c in notebook.get("cells",[]) if c.get("cell_type")=="code")
        self.assertIn('scripts/slate_model_report.py',text)
        self.assertIn('"Engine_A","Engine_B","Consensus"',text)
        # The export now delegates to one tested shared mapping instead of
        # embedding a second implementation in the notebook.
        import sys
        sys.path.insert(0,str(ROOT/'scripts'))
        from slate_model_report import masses
        self.assertAlmostEqual(masses({'q_win':.6,'q_push':.2,'q_win_b':None})['probability'],.75)

    def test_original_comparison_chart_and_new_evidence_top10_coexist(self):
        notebook=json.loads((ROOT/"notebooks/deepnote_daily_cloud_inference.ipynb").read_text(encoding="utf-8"))
        cells=["".join(c.get("source",[])) for c in notebook.get("cells",[])
               if c.get("cell_type")=="code"]
        display_cell=next(c for c in cells if 'stage("slate_model_comparison"' in c)
        # Original top ten remains available, ordered as before by consensus
        # availability, market gap, then probability, without replacement.
        self.assertIn('["production_consensus_available","Consensus_gap_pp","Consensus"]',display_cell)
        self.assertIn('display(selection[columns].round(4))',display_cell)
        self.assertIn('production consensus candidates',display_cell)
        # Second independent table has the new priority score and explanations.
        self.assertIn('slate_top10_evidence.json',display_cell)
        self.assertIn('["Priority_score"]+columns',display_cell)
        self.assertIn('for evidence in ranked["explanations"]',display_cell)
        self.assertLess(display_cell.index('display(selection[columns].round(4))'),
                        display_cell.index('top=json.loads((OUT/"slate_top10_evidence.json")'))

    def test_morning_audit_uses_canonical_first_frozen_batch(self):
        notebook=json.loads((ROOT/"notebooks/deepnote_daily_cloud_inference.ipynb").read_text(encoding="utf-8"))
        text="\n".join("".join(c.get("source",[])) for c in notebook.get("cells",[]) if c.get("cell_type")=="code")
        self.assertIn('canonical_originals=pool.canonical_afternoon_docs(originals)',text)
        self.assertIn('later_archives_excluded=len(originals)-len(canonical_originals)',text)
        self.assertIn('b.get("q_win")',text)
        self.assertNotIn('b.get("q_win_b")',text)

if __name__=="__main__":
    unittest.main()
