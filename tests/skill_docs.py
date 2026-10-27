"""Load pickem-auditor reference docs (replaces monolithic SKILL.md for contract tests)."""

from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
REFERENCES = SKILL_DIR / "references"

_CORPUS_FILES = (
    "workflow_stages.md",
    "slate_fetch.md",
    "math_helper.md",
    "funnel_checks.md",
    "veto_rules.md",
)


def skill_corpus() -> str:
    workflow = (REFERENCES / "workflow_stages.md").read_text(encoding="utf-8")
    funnel = (REFERENCES / "funnel_checks.md").read_text(encoding="utf-8")
    marker = "## C3. Environment"
    idx = workflow.index(marker)
    workflow = workflow[:idx] + funnel + "\n" + workflow[idx:]
    parts = [workflow]
    for name in _CORPUS_FILES:
        if name in ("workflow_stages.md", "funnel_checks.md"):
            continue
        parts.append((REFERENCES / name).read_text(encoding="utf-8"))
    return "\n".join(parts)


def skill_md_text() -> str:
    return (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


def skill_md_frontmatter() -> dict[str, str]:
    text = skill_md_text()
    if not text.startswith("---"):
        raise ValueError("SKILL.md must start with YAML frontmatter (---)")
    end = text.find("\n---", 3)
    if end < 0:
        raise ValueError("SKILL.md frontmatter must close with ---")
    block = text[3:end].strip()
    out: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        out[key.strip()] = val.strip()
    return out
