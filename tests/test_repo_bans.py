"""Repo-wide vendor and tool-name bans (model-agnostic research)."""

import re
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]

SKIP_DIR_NAMES = {
    "tests",
    "__pycache__",
    ".git",
    "fixtures",
}

# Paths relative to skill root where banned tokens may appear when documenting the ban.
ALLOWED_REL_PATHS = {
    "references/research_packet.md",
    "references/workflow_stages.md",
    "references/veto_rules.md",
    "references/funnel_checks.md",
    "cursor/rules/pickem-auditor.mdc",
    ".cursor/rules/pickem-auditor.mdc",
    "SKILL.md",
    # Frozen V2.5 governing and audit artifacts cite external tool/repo names by URL
    # or historical review label; they are not executable vendor dependencies.
    "docs/Pickem_Auditor_V2_5_Master_Implementation_Plan_v1_1_2026-11-10.md",
    "docs/V25_FULL_NOV11_FORENSIC_AUDIT_AND_PHASE2_GATE.md",
}

DOMAIN_PATTERNS = (
    re.compile(r"underdog\.com", re.I),
    re.compile(r"underdogfantasy", re.I),
)

STRING_PATTERNS = (
    re.compile(r"web_search"),
    re.compile(r"anthropic", re.I),
    re.compile(r"\bclaude\b", re.I),
)


def _iter_source_files():
    for path in SKILL_DIR.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(SKILL_DIR).as_posix()
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if rel in ALLOWED_REL_PATHS:
            continue
        if path.suffix in {".pyc", ".jsonl"}:
            continue
        if path.name.endswith(".json") and "fixtures" in rel:
            continue
        yield rel, path


class RepoBanTests(unittest.TestCase):
    def test_no_banned_vendor_tokens_outside_allowed_docs(self):
        hits = []
        for rel, path in _iter_source_files():
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for pattern in DOMAIN_PATTERNS + STRING_PATTERNS:
                if pattern.search(text):
                    hits.append(f"{rel}: {pattern.pattern}")
        self.assertEqual(hits, [])
