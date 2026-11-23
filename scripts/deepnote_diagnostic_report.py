"""Compact, evidence-preserving Deepnote validation reports for Codex.

Use from the final validation block of an opt-in research notebook. This module
does not change Deepnote MCP server responses or notebook execution policies.
All full evidence is written before any compact summary is emitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "pickem.deepnote_diagnostic.v1"
TERMINAL_STATUSES = {"success", "warning", "error", "internal_error", "stopped", "blocked"}
_RUN_ID = re.compile(r"^[a-zA-Z0-9_.-]{1,128}$")


def _scalar_map(value: Any, name: str, *, nonnegative_int: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    if len(value) > 128:
        raise ValueError(f"{name} has too many fields; keep bulk data in full evidence")
    result: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key:
            raise ValueError(f"{name} keys must be non-empty strings")
        if nonnegative_int:
            if isinstance(item, bool) or not isinstance(item, int) or item < 0:
                raise ValueError(f"{name}.{key} must be a nonnegative integer")
        elif item is not None and (
            isinstance(item, (dict, list, tuple))
            or not isinstance(item, (str, int, float, bool))
            or (isinstance(item, float) and not math.isfinite(item))
        ):
            raise ValueError(f"{name}.{key} must be a finite JSON scalar")
        result[key] = item
    return result


def _short(value: Any, limit: int) -> str:
    text = value if isinstance(value, str) else json.dumps(
        value, ensure_ascii=False, sort_keys=True, default=str
    )
    if len(text) <= limit:
        return text
    return text[:limit] + f" [TRUNCATED {len(text) - limit} chars; see full evidence]"


def publish_report(
    report: Mapping[str, Any],
    output_dir: str | Path,
    *,
    max_issues: int = 3,
    max_samples: int = 2,
    emit_stdout: bool = True,
) -> dict[str, Any]:
    """Persist complete immutable evidence, then emit a bounded agent summary.

    Required report keys: run_id, notebook_id, status, tests (passed/failed/skipped).
    Optional: sport, market, model, git_sha, counts, metrics, provenance, issues,
    samples and any additional full-evidence fields. Never include credentials.
    """
    if not isinstance(report, Mapping):
        raise ValueError("report must be an object")
    if max_issues < 0 or max_samples < 0:
        raise ValueError("max_issues/max_samples must be nonnegative")
    payload = dict(report)
    run_id, notebook_id, status = (
        payload.get("run_id"), payload.get("notebook_id"), payload.get("status")
    )
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise ValueError("run_id must be a safe, nonempty identifier")
    if not isinstance(notebook_id, str) or not notebook_id.strip():
        raise ValueError("notebook_id is required")
    if status not in TERMINAL_STATUSES:
        raise ValueError("status must be a terminal execution status")

    tests = _scalar_map(payload.get("tests"), "tests", nonnegative_int=True)
    if not {"passed", "failed", "skipped"} <= tests.keys():
        raise ValueError("tests must include passed, failed and skipped")
    counts = _scalar_map(payload.get("counts", {}), "counts", nonnegative_int=True)
    metrics = _scalar_map(payload.get("metrics", {}), "metrics")
    provenance = _scalar_map(payload.get("provenance", {}), "provenance")
    issues = payload.get("issues", [])
    samples = payload.get("samples", [])
    if not isinstance(issues, list) or not all(isinstance(x, dict) for x in issues):
        raise ValueError("issues must be a list of objects")
    if not isinstance(samples, list):
        raise ValueError("samples must be a list")
    if status == "success" and tests["failed"] > 0:
        raise ValueError("cannot report success with failed tests")

    payload["schema_version"] = SCHEMA_VERSION
    full_bytes = (json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ) + "\n").encode("utf-8")
    digest = hashlib.sha256(full_bytes).hexdigest()
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    full_path = root / f"{run_id}-{digest[:16]}.full.json"
    summary_path = root / f"{run_id}.summary.json"
    if summary_path.exists():
        previous = json.loads(summary_path.read_text(encoding="utf-8"))
        if previous.get("full_evidence_sha256") != digest:
            raise RuntimeError("run_id reused with different evidence; use a new run identifier")
    try:
        with full_path.open("xb") as fh:
            fh.write(full_bytes)
    except FileExistsError:
        if full_path.read_bytes() != full_bytes:
            raise RuntimeError("immutable evidence collision: existing bytes differ") from None

    errors = []
    for issue in issues[:max_issues]:
        errors.append({
            "code": _short(issue.get("code", "UNSPECIFIED"), 120),
            "message": _short(issue.get("message", ""), 600),
            **({"traceback_tail": _short(issue["traceback"][-1600:], 1800)}
               if status != "success" and isinstance(issue.get("traceback"), str)
               else {}),
        })
    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "notebook_id": notebook_id,
        "status": status,
        "sport": payload.get("sport"),
        "market": payload.get("market"),
        "model": payload.get("model"),
        "git_sha": payload.get("git_sha"),
        "tests": tests,
        "counts": counts,
        "metrics": metrics,
        "provenance": provenance,
        "issue_count": len(issues),
        "issues": errors,
        "omitted_issue_count": len(issues) - len(errors),
        "sample_count": len(samples),
        "sample_examples": ([_short(x, 500) for x in samples[:max_samples]]
                            if status != "success" else []),
        "omitted_sample_count": (len(samples) - min(max_samples, len(samples))
                                  if status != "success" else len(samples)),
        "diagnostic_gap": status != "success" and not issues,
        "full_evidence_path": str(full_path),
        "full_evidence_sha256": digest,
        "summary_path": str(summary_path),
    }
    summary_bytes = (json.dumps(
        summary, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ) + "\n").encode("utf-8")
    try:
        with summary_path.open("xb") as fh:
            fh.write(summary_bytes)
    except FileExistsError:
        if summary_path.read_bytes() != summary_bytes:
            raise RuntimeError("immutable summary collision: existing bytes differ") from None
    if emit_stdout:
        print(json.dumps(summary, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Full report JSON path")
    parser.add_argument("--output-dir", required=True, help="Durable evidence directory")
    parser.add_argument("--max-issues", type=int, default=3)
    parser.add_argument("--max-samples", type=int, default=2)
    args = parser.parse_args()
    report = json.loads(Path(args.input).read_text(encoding="utf-8"))
    publish_report(
        report, args.output_dir, max_issues=args.max_issues, max_samples=args.max_samples
    )


if __name__ == "__main__":
    main()
