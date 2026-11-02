"""Repository workflows must preserve immutable research gates and bounded API usage."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class VerificationWorkflowTests(unittest.TestCase):
    def test_afternoon_verifies_only_after_snapshot_and_queue(self):
        src=(ROOT/".github/workflows/pickem-daily.yml").read_text()
        self.assertLess(src.index("step('pregame_engines'"),src.index("step('research_triage'"))
        self.assertLess(src.index("step('research_triage'"),src.index("step('pick_verification'"))
        self.assertIn("review_template.json",src)
        self.assertIn("verified_board.json",src)
        self.assertIn("scripts/autonomous_investigator.py",src)
        self.assertIn("data/verification/",src)
        self.assertNotIn("research_checklist=True",src)

    def test_recheck_is_bounded_and_requires_live_source_queries(self):
        src=(ROOT/".github/workflows/pregame-verification.yml").read_text()
        self.assertIn("  workflow_dispatch:",src)
        self.assertNotIn("  schedule:",src)
        self.assertNotIn("cron:",src)
        self.assertIn("PICKEM_ODDS_QUOTA_GUARD: '1'",src)
        self.assertIn("--refresh-quotes",src)
        self.assertIn("scripts/autonomous_investigator.py",src)
        self.assertLess(src.index("scripts/autonomous_investigator.py"),
                        src.index("scripts/pick_verification.py"))
        self.assertIn("select(rows,queue,date,now,'recheck',30)",src)
        self.assertIn("bash scripts/shadow_store.sh save",src)
        self.assertIn("cancel-in-progress: false",src)
        self.assertIn("verified_board.json",src)

    def test_history_archive_and_original_forecasts_not_rewritten(self):
        src=(ROOT/"scripts/shadow_store.sh").read_text()
        self.assertIn("IMMUTABLE_VERIFICATION_DECISION_CONFLICT",src)
        self.assertIn("data/verification",src)
        self.assertIn("data/shadow-calibration",src)
        self.assertNotIn("git push origin HEAD:refs/heads/data/history-archive",src)

    def test_approved_decisions_require_positive_and_negative_evidence(self):
        src=(ROOT/"scripts/pick_verification.py").read_text()
        self.assertIn('("supporting", "opposing")',src)
        self.assertIn("UNRESOLVED_CONTRADICTORY_STATUS_EVIDENCE",src)
        self.assertIn("propline_not_called_no_validated_adversarial_review",src)
        self.assertIn("forecast_sha256",src)


if __name__=="__main__":
    unittest.main()
