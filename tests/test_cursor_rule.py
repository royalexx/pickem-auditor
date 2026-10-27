"""Cursor rule file contract."""

import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "tests"))
from skill_docs import skill_md_frontmatter, skill_md_text


def _rule_path() -> Path:
    dotted = SKILL_DIR / ".cursor" / "rules" / "pickem-auditor.mdc"
    if dotted.is_file():
        return dotted
    return SKILL_DIR / "cursor" / "rules" / "pickem-auditor.mdc"


class CursorRuleTests(unittest.TestCase):
    def test_skill_md_has_yaml_frontmatter(self):
        text = skill_md_text()
        self.assertTrue(text.startswith("---\n"), "SKILL.md must start with YAML frontmatter (---)")
        fm = skill_md_frontmatter()
        self.assertEqual(fm.get("name"), "pickem-auditor")
        self.assertTrue(fm.get("description"))

    def test_rule_file_exists_and_is_short(self):
        path = _rule_path()
        self.assertTrue(path.is_file(), path)
        text = path.read_text(encoding="utf-8")
        self.assertLessEqual(len(text.splitlines()), 150)
        self.assertIn("alwaysApply: false", text)
        self.assertNotIn("globs:", text)
        self.assertIn(".cursor/skills/pickem-auditor/SKILL.md", text)
        self.assertTrue((SKILL_DIR / ".cursor/skills/pickem-auditor/SKILL.md").is_file())
        self.assertIn("Never use Underdog", text)
        self.assertIn("final_rank", text)
