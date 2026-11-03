"""Weekly fit produces reviewable proposals; it cannot write active certificates."""
from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import probability_blend as pb
import context_validation as cv


class CandidateRegistrationBoundary(unittest.TestCase):
    def test_blend_fit_only_writes_candidate(self):
        cfg = {"scope": "NHL|saves", "engine_version": pb.VERSION,
               "weight_a": .7, "underpowered": False,
               "validation": {"holdout_dates": 23, "improvement_ci_low": .005,
                              "blend_log_loss": .50, "a_log_loss": .55,
                              "holdout_end": "2026-10-31"}}
        with (tempfile.TemporaryDirectory() as td,
              patch.object(pb, "from_snapshots", return_value=[]),
              patch.object(pb, "fit", return_value=cfg)):
            result = pb.fit_scopes([{"sport": "NHL", "stat": "saves"}], td,
                                   as_of=date(2026,11,2))
            active = pb.config_path(td, "NHL|saves")
            self.assertFalse(active.exists())
            status = result["NHL|saves"]
            self.assertEqual(status["status"], "candidate_pending_registration")
            self.assertTrue(status["production_unchanged"])
            self.assertEqual(json.loads(Path(status["path"]).read_text()), cfg)

    def test_context_fit_only_writes_candidate(self):
        cfg = {"scope": "NHL|saves", "blend_fingerprint": "A_ONLY",
               "validation": {"holdout_dates": 24}}
        with (tempfile.TemporaryDirectory() as td,
              patch.object(cv, "fit", return_value=cfg),
              patch.object(cv, "eligible", return_value=True)):
            result = cv.fit_scopes([{"sport": "NHL", "stat": "saves"}], td,
                                   as_of=date(2026,11,2))
            self.assertFalse(cv.path(td,"NHL|saves").exists())
            self.assertEqual(result["NHL|saves"]["status"],
                             "candidate_pending_registration")
            self.assertEqual(json.loads(Path(result["NHL|saves"]["path"]).read_text()),cfg)


if __name__ == "__main__":
    unittest.main()
