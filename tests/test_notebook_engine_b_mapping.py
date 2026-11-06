"""Regression guard: notebook reports the Engine B production probability correctly."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class NotebookEngineBMappingTests(unittest.TestCase):
    def test_deepnote_four_model_export_reads_scouting_q_win(self):
        notebook=json.loads((ROOT/"notebooks/deepnote_daily_cloud_inference.ipynb").read_text(encoding="utf-8"))
        text="\n".join("".join(c.get("source",[])) for c in notebook.get("cells",[]) if c.get("cell_type")=="code")
        self.assertIn('B.get("q_win")',text)
        self.assertNotIn('B.get("q_win_b")',text)
        self.assertIn('all(p is not None for p in estimates)',text)
        self.assertIn('production_engines_reliable',text)

    def test_morning_audit_uses_canonical_first_frozen_batch(self):
        notebook=json.loads((ROOT/"notebooks/deepnote_daily_cloud_inference.ipynb").read_text(encoding="utf-8"))
        text="\n".join("".join(c.get("source",[])) for c in notebook.get("cells",[]) if c.get("cell_type")=="code")
        self.assertIn('canonical_originals=pool.canonical_afternoon_docs(originals)',text)
        self.assertIn('later_archives_excluded=len(originals)-len(canonical_originals)',text)
        self.assertIn('b.get("q_win")',text)
        self.assertNotIn('b.get("q_win_b")',text)

if __name__=="__main__":
    unittest.main()
