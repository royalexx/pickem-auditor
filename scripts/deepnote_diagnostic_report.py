"""Publish and recover opt-in, evidence-preserving Deepnote execution reports."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "pickem.deepnote_diagnostic.v2"
MAX_SUMMARY_BYTES = 12 * 1024
TERMINAL_STATUSES = {"success", "warning", "error", "internal_error", "stopped", "blocked"}
GATE_STATUSES = {"passed", "failed", "blocked", "warning", "skipped", "not_applicable"}
COUNT_FIELDS = ("total", "eligible", "rejected", "missing", "unmatched", "abstained")
PROVENANCE_FIELDS = ("input_sha256", "output_sha256", "input_uri", "output_uri")
TEST_FIELDS = ("passed", "failed", "skipped")
IDENTITY_FIELDS = ("notebook_id", "sport", "market", "model", "model_version", "git_sha")
_RUN_ID = re.compile(r"[a-zA-Z0-9_.-]{1,128}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_GIT_SHA = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")


class EvidenceError(RuntimeError):
    """A durable receipt could not be published or verified."""


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("ascii")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_id(value: Any) -> str:
    if not isinstance(value, str) or not _RUN_ID.fullmatch(value) or value in {".", ".."}:
        raise ValueError("run_id must be a safe, nonempty identifier")
    return value


def _json_object(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _text(value: Any, limit: int = 128) -> bool:
    return isinstance(value, str) and 0 < len(value) <= limit and bool(value.strip())


def _uri(value: Any) -> bool:
    return _text(value, 1024) and value.isascii() and value.isprintable()


def _number(value: Any) -> bool:
    return type(value) in (int, float) and (isinstance(value, int) or math.isfinite(value))


def _normalize(value: Any, nonfinite: list, path: tuple = ()) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        nonfinite.append(list(path))
        return {math.inf: "Infinity", -math.inf: "-Infinity"}.get(value, "NaN")
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("JSON object keys must be strings")
        return {key: _normalize(value[key], nonfinite, (*path, key)) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_normalize(item, nonfinite, (*path, index)) for index, item in enumerate(value)]
    return value


def _file_ref(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _sync_directory(path: Path) -> None:
    # Python's Windows file API cannot open directories for fsync.
    if os.name == "nt":
        return
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _publish_staged(temp: Path, target: Path, digest: str, size: int) -> None:
    try:
        os.link(temp, target)
    except FileExistsError:
        if target.is_symlink() or _file_ref(target) != (digest, size):
            raise EvidenceError(f"immutable collision or corruption: {target.name}") from None
    _sync_directory(target.parent)


def _publish_bytes(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
        temp = Path(output.name)
        try:
            with output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            _publish_staged(temp, path, _digest(data), len(data))
        finally:
            temp.unlink(missing_ok=True)


def _archive_artifact(root: Path, source: Path) -> dict:
    if not source.is_file():
        raise FileNotFoundError("artifact source is missing or is not a regular file")
    digest = hashlib.sha256()
    size = 0
    with tempfile.NamedTemporaryFile(dir=root, delete=False) as output:
        temp = Path(output.name)
        try:
            with source.open("rb") as stream, output:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                    size += len(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            sha256 = digest.hexdigest()
            name = f"artifact-{sha256}"
            _publish_staged(temp, root / name, sha256, size)
        finally:
            temp.unlink(missing_ok=True)
    return {"path": name, "sha256": sha256, "bytes": size}


def _comparison_valid(item: dict) -> bool:
    values = (item.get("ci_low"), item.get("delta"), item.get("ci_high"))
    return (_text(item.get("baseline_id")) and all(map(_number, values))
            and values[0] <= values[1] <= values[2]
            and _number(item.get("harm_threshold", 0)))


def _probability_valid(row: Any) -> bool:
    row = _json_object(row)
    values = [row.get(side) for side in ("over", "under", "push")]
    return (all(_number(value) and 0 <= value <= 1 for value in values)
            and abs(math.fsum(values) - 1) <= 1e-12)


def _audit(report: dict, nonfinite: list, missing_artifacts: list, artifacts: dict) -> list[dict]:
    issues = []

    def add(code, severity, message, **details):
        issues.append({"code": code, "stage": "report_validation", "severity": severity,
                       "message": message, **details})

    identity = [key for key in IDENTITY_FIELDS if not _text(report.get(key))]
    if report.get("sport") not in ("NBA", "NHL", "NFL") and "sport" not in identity:
        identity.append("sport")
    if "git_sha" not in identity and not _GIT_SHA.fullmatch(report["git_sha"]):
        identity.append("git_sha")
    if report.get("deepnote_run_id") is not None and not _text(report["deepnote_run_id"]):
        identity.append("deepnote_run_id")
    if identity:
        add("INCOMPLETE_IDENTITY", "blocked", ", ".join(identity))

    for field, keys in (("tests", TEST_FIELDS), ("counts", COUNT_FIELDS)):
        values = _json_object(report.get(field))
        invalid = [key for key in keys if type(values.get(key)) is not int or values[key] < 0]
        if invalid:
            add(f"INCOMPLETE_{field.upper()}", "blocked", ", ".join(invalid))
        elif field == "tests" and values["failed"]:
            add("FAILED_TESTS", "error", f"{values['failed']} reported test failures")
        elif field == "counts" and any(values[key] > values["total"] for key in keys[1:]):
            add("INVALID_DENOMINATOR", "error", "An observation count exceeds the population total")

    provenance = _json_object(report.get("provenance"))
    invalid = [key for key in PROVENANCE_FIELDS if not _uri(provenance.get(key))
               or (key.endswith("_sha256") and not _SHA256.fullmatch(provenance[key]))]
    if invalid:
        add("INCOMPLETE_PROVENANCE", "blocked", ", ".join(invalid))

    archived_paths = {descriptor["path"] for descriptor in artifacts.values()}
    for direction in ("input", "output"):
        uri = provenance.get(f"{direction}_uri")
        sha256 = provenance.get(f"{direction}_sha256")
        if isinstance(uri, str) and uri.startswith("artifact-") and (
            uri != f"artifact-{sha256}" or uri not in archived_paths
        ):
            add("UNVERIFIED_PROVENANCE_ARTIFACT", "blocked", direction)

    status = report.get("status")
    if status not in tuple(TERMINAL_STATUSES):
        add("INVALID_EXECUTION_STATUS", "blocked", "Expected a terminal execution status")
    elif status != "success":
        severity = "warning" if status == "warning" else "blocked" if status == "blocked" else "error"
        add("EXECUTION_STATUS", severity, status)

    for name in ("metrics", "gates", "comparisons", "parameters", "distribution_diagnostics",
                 "constraint_diagnostics"):
        if name in report and not isinstance(report[name], dict):
            add("INVALID_REPORT_SECTION", "blocked", name)
    for name in ("issues", "samples", "probabilities"):
        if name in report and not isinstance(report[name], list):
            add("INVALID_REPORT_SECTION", "blocked", name)

    supplied = report.get("issues", [])
    if isinstance(supplied, list) and any(
        not isinstance(item, dict) or not _text(item.get("code")) or
        item.get("severity", "error") not in ("error", "warning", "blocked", "info")
        for item in supplied
    ):
        add("INVALID_ISSUE_RECORD", "blocked", "An issue is missing a code or has an invalid severity")

    gates = _json_object(report.get("gates"))
    if not gates:
        add("MISSING_GATES", "blocked", "No validation gates were reported")
    for name, gate in gates.items():
        if gate not in tuple(GATE_STATUSES):
            add("INVALID_GATE_STATUS", "blocked", name, test=name)
        elif gate in ("failed", "blocked", "warning", "skipped"):
            severity = {"failed": "error", "blocked": "blocked", "warning": "warning",
                        "skipped": "blocked"}[gate]
            add("VALIDATION_GATE", severity, gate, test=name)

    for name, comparison in _json_object(report.get("comparisons")).items():
        if not _comparison_valid(_json_object(comparison)):
            add("INVALID_BASELINE_COMPARISON", "blocked", name, test=name)
        elif comparison["ci_low"] > comparison.get("harm_threshold", 0):
            add("STATISTICAL_REGRESSION", "error", name, test=name)

    probabilities = report.get("probabilities")
    if isinstance(probabilities, list):
        invalid = [index for index, row in enumerate(probabilities) if not _probability_valid(row)]
        if invalid:
            add("INVALID_PROBABILITY", "error", f"{len(invalid)} invalid probability records",
                affected_indices=invalid)

    if nonfinite:
        add("NONFINITE_VALUE", "error", f"{len(nonfinite)} non-finite values")
    if missing_artifacts:
        add("ARTIFACT_UNAVAILABLE", "blocked", f"{len(missing_artifacts)} artifacts unavailable")
    return issues


def _excerpt(value: Any, limit: int, *, tail: bool = False) -> str:
    value = value if isinstance(value, str) else _json_bytes(value).decode().rstrip("\n")
    if len(value) <= limit:
        return value
    marker = "[truncated; see full evidence]"
    return marker + value[-limit:] if tail else value[:limit] + marker


def _issue_preview(issue: dict) -> dict:
    limits = {"code": 100, "severity": 20, "message": 300, "stage": 96, "test": 96}
    preview = {key: _excerpt(issue[key], limit) for key, limit in limits.items() if key in issue}
    if isinstance(issue.get("traceback"), str):
        preview["traceback_tail"] = _excerpt(issue["traceback"], 900, tail=True)
    return preview


def _status(issues: list[dict]) -> str:
    severities = [issue.get("severity", "error") for issue in issues]
    for severity, status in (("error", "failed"), ("blocked", "blocked"), ("warning", "warning")):
        if severity in severities:
            return status
    return "passed"


def _extend_bounded(summary: dict, target: list | dict, key: int | str, value: Any) -> None:
    if isinstance(target, list):
        target.append(value)
    else:
        target[key] = value
    if len(_json_bytes(summary)) > MAX_SUMMARY_BYTES - 256:
        if isinstance(target, list):
            target.pop()
        else:
            del target[key]


def _summary(envelope: dict, full_sha: str, size: int) -> dict:
    report = envelope["report"]
    run_id = report["run_id"]
    supplied = report.get("issues", [])
    if not isinstance(supplied, list):
        supplied = []
    supplied = [item for item in supplied if isinstance(item, dict)]
    generated = envelope["generated_issues"]
    issues = sorted(supplied + generated, key=lambda item:
                    {"error": 0, "blocked": 1, "warning": 2, "info": 3}.get(
                        str(item.get("severity", "error")), 1))
    state = _status(issues)
    anomalous = state != "passed"
    reported_status = report.get("status")
    diagnostics = {
        "diagnostic_gap": reported_status != "success" and not supplied,
        "issue_count": len(issues), "issues": [], "omitted_issue_count": len(issues),
        "issue_codes": sorted({issue["code"] for issue in generated}),
        "sample_count": 0, "sample_examples": [], "omitted_sample_count": 0,
        "comparisons": {}, "parameters": {}, "distribution_diagnostics": {},
        "constraint_diagnostics": {}, "invalid_predictions": [],
    }
    summary = {
        "schema_version": SCHEMA_VERSION, "run_id": run_id,
        **{key: report[key] if _text(report.get(key)) else None
           for key in (*IDENTITY_FIELDS, "deepnote_run_id")},
        "status": reported_status if reported_status in tuple(TERMINAL_STATUSES) else "unknown",
        "validation_status": state, "level": 2 if anomalous else 1,
        "tests": {}, "counts": {}, "provenance": {}, "metrics": {}, "gates": {},
        "full_evidence_path": f"{run_id}.full.json", "full_evidence_sha256": full_sha,
        "full_evidence_bytes": size, "summary_path": f"{run_id}.summary.json",
        "artifact_count": len(envelope["artifacts"]), "diagnostics": diagnostics,
        "omitted_sections": [],
    }

    for field, keys in (("tests", TEST_FIELDS), ("counts", COUNT_FIELDS),
                        ("provenance", PROVENANCE_FIELDS)):
        values = _json_object(report.get(field))
        for key in keys:
            value = values.get(key)
            if ((field == "provenance" and _uri(value)) or
                    (field != "provenance" and type(value) is int and 0 <= value <= 10**18)):
                _extend_bounded(summary, summary[field], key, value)

    samples = report.get("samples", [])
    if not isinstance(samples, list):
        samples = []
    diagnostics["sample_count"] = len(samples)
    if anomalous:
        limits = envelope["preview_limits"]
        for issue in issues[:limits["issues"]]:
            _extend_bounded(summary, diagnostics["issues"], 0, _issue_preview(issue))
        invalid = next((item["affected_indices"] for item in generated
                        if item["code"] == "INVALID_PROBABILITY"), [])
        for index in invalid[:limits["samples"]]:
            example = {"index": index, "row": _excerpt(report["probabilities"][index], 350)}
            _extend_bounded(summary, diagnostics["invalid_predictions"], 0, example)
        for sample in samples[:limits["samples"]]:
            _extend_bounded(summary, diagnostics["sample_examples"], 0, _excerpt(sample, 350))
    diagnostics["omitted_issue_count"] -= len(diagnostics["issues"])
    diagnostics["omitted_sample_count"] = len(samples) - len(diagnostics["sample_examples"])

    sections = [(name, summary) for name in ("gates", "metrics", "provenance")]
    if anomalous:
        sections = [(name, diagnostics) for name in (
            "comparisons", "distribution_diagnostics", "constraint_diagnostics", "parameters",
        )] + sections
    for name, container in sections:
        values = _json_object(report.get(name))
        for key, value in values.items():
            if key in container[name]:
                continue
            if _text(key) and len(_json_bytes(value)) <= 600 and (
                value is None or isinstance(value, (str, int, float, bool)) or
                (name == "comparisons" and _comparison_valid(_json_object(value)))
            ):
                _extend_bounded(summary, container[name], key, value)
        if len(container[name]) != len(values):
            summary["omitted_sections"].append(name)
    return summary


def publish_report(
    report: Mapping[str, Any],
    output_dir: str | Path,
    *,
    artifacts: Mapping[str, str | Path] | None = None,
    max_issues: int = 3,
    max_samples: int = 2,
    emit_stdout: bool = True,
) -> dict[str, Any]:
    """Publish complete archived evidence and then a bounded report."""
    run_id = _run_id(report.get("run_id"))
    if any(type(limit) is not int or limit < 0 for limit in (max_issues, max_samples)):
        raise ValueError("preview limits must be nonnegative integers")
    nonfinite = []
    payload = _normalize(dict(report), nonfinite)
    _json_bytes(payload)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    _sync_directory(root.parent)
    archived = {}
    missing = []
    for name, source in sorted((artifacts or {}).items()):
        if not _text(name):
            raise ValueError("artifact role must be a nonempty short string")
        try:
            archived[name] = _archive_artifact(root, Path(source))
        except OSError as exc:
            missing.append({"name": name, "error_type": type(exc).__name__,
                            "errno": exc.errno})
    envelope = {
        "schema_version": SCHEMA_VERSION, "report": payload,
        "preview_limits": {"issues": min(max_issues, 12), "samples": min(max_samples, 8)},
        "nonfinite_paths": nonfinite, "artifacts": archived, "missing_artifacts": missing,
        "generated_issues": _audit(payload, nonfinite, missing, archived),
    }
    full = _json_bytes(envelope)
    path = root / f"{run_id}.full.json"
    _publish_bytes(path, full)
    summary = _summary(envelope, _digest(full), len(full))
    compact = _json_bytes(summary)
    if len(compact) > MAX_SUMMARY_BYTES:
        raise EvidenceError("summary exceeds the transport budget")
    _publish_bytes(root / summary["summary_path"], compact)
    if emit_stdout:
        print(compact.decode("ascii"), end="")
    return summary


def _read_record(path: Path, label: str) -> tuple[dict, bytes]:
    try:
        if path.is_symlink():
            raise EvidenceError(f"invalid {label}: symbolic link")
        data = path.read_bytes()
        value = json.loads(data)
        if not isinstance(value, dict) or _json_bytes(value) != data:
            raise EvidenceError(f"invalid or truncated {label}: {path.name}")
    except FileNotFoundError:
        raise EvidenceError(f"missing {label}: {path.name}") from None
    except (OSError, ValueError):
        raise EvidenceError(f"invalid or truncated {label}: {path.name}") from None
    return value, data


def _load_evidence(root: Path, run_id: str, expected_sha256: str | None) -> tuple[dict, dict]:
    evidence, full = _read_record(root / f"{run_id}.full.json", "full evidence")
    sha256 = _digest(full)
    if expected_sha256 is not None and sha256 != expected_sha256:
        raise EvidenceError(f"full evidence digest mismatch: {run_id}")
    if (evidence.get("schema_version") != SCHEMA_VERSION or
            _json_object(evidence.get("report")).get("run_id") != run_id):
        raise EvidenceError(f"invalid evidence schema or identity: {run_id}")
    try:
        summary = _summary(evidence, sha256, len(full))
        for name, artifact in evidence["artifacts"].items():
            path = root / f"artifact-{artifact['sha256']}"
            try:
                valid = (path.name == artifact["path"] and bool(_SHA256.fullmatch(artifact["sha256"]))
                         and not path.is_symlink()
                         and _file_ref(path) == (artifact["sha256"], artifact["bytes"]))
            except OSError:
                valid = False
            if not valid:
                raise EvidenceError(f"missing or corrupt artifact: {name}")
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise EvidenceError(f"malformed full evidence: {run_id}") from exc
    return evidence, summary


def verify_report(output_dir: str | Path, run_id: str, *, expected_sha256: str | None = None,
                  expected_deepnote_run_id: str | None = None) -> dict:
    """Verify the canonical summary, evidence digest, optional binding, and every artifact."""
    run_id = _run_id(run_id)
    root = Path(output_dir)
    summary, compact = _read_record(root / f"{run_id}.summary.json", "summary")
    digest = summary.get("full_evidence_sha256")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise EvidenceError(f"invalid evidence digest in summary: {run_id}")
    if expected_sha256 is not None and digest != expected_sha256:
        raise EvidenceError(f"independent evidence digest mismatch: {run_id}")
    evidence, rebuilt = _load_evidence(root, run_id, digest)
    if len(compact) > MAX_SUMMARY_BYTES or summary != rebuilt:
        raise EvidenceError(f"summary does not match complete evidence: {run_id}")
    if expected_deepnote_run_id is not None:
        actual = summary["deepnote_run_id"]
        if actual is None:
            try:
                receipt, _ = _read_record(root / f"{run_id}.binding.json", "run binding")
            except EvidenceError as exc:
                raise EvidenceError(f"unverified execution identity: {exc}") from None
            if (receipt.get("notebook_id"), receipt.get("run_id"),
                    receipt.get("full_evidence_sha256")) == (summary["notebook_id"], run_id, digest):
                actual = receipt.get("deepnote_run_id")
        if actual != expected_deepnote_run_id:
            raise EvidenceError(f"execution identity mismatch: {run_id}")
    return evidence


def recover_summary(output_dir: str | Path, run_id: str, *, expected_sha256: str) -> dict:
    """Rebuild a missing summary using an independently held digest."""
    run_id = _run_id(run_id)
    if not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256):
        raise ValueError("recovery requires a trusted SHA-256 digest")
    root = Path(output_dir)
    _, summary = _load_evidence(root, run_id, expected_sha256)
    _publish_bytes(root / summary["summary_path"], _json_bytes(summary))
    return summary


def bind_run(output_dir: str | Path, run_id: str, notebook_id: str, deepnote_run_id: str) -> dict:
    """Bind a correlation ID using the caller's trusted create_run/get_run receipt."""
    root = Path(output_dir)
    evidence = verify_report(root, run_id)
    report = evidence["report"]
    if not _text(notebook_id) or not _text(deepnote_run_id) or report.get("notebook_id") != notebook_id:
        raise EvidenceError("execution identity mismatch in requested binding")
    if report.get("deepnote_run_id") not in (None, deepnote_run_id):
        raise EvidenceError("execution identity mismatch in requested binding")
    receipt = {"run_id": run_id, "notebook_id": notebook_id, "deepnote_run_id": deepnote_run_id,
               "full_evidence_sha256": _digest(_json_bytes(evidence))}
    _publish_bytes(root / f"{run_id}.binding.json", _json_bytes(receipt))
    return receipt


def _unique_pairs(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, help="Verified durable evidence directory")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--input", help="Complete report JSON path")
    action.add_argument("--verify", metavar="RUN_ID", help="Verify an archived report and artifacts")
    action.add_argument("--recover", metavar="RUN_ID", help="Rebuild a missing summary")
    parser.add_argument("--expected-sha256", help="Independently held full evidence digest")
    parser.add_argument("--deepnote-run-id", help="Expected official execution ID during verification")
    parser.add_argument("--max-issues", type=int, default=3)
    parser.add_argument("--max-samples", type=int, default=2)
    args = parser.parse_args()
    if args.recover:
        if not args.expected_sha256:
            parser.error("--recover requires --expected-sha256")
        print(_json_bytes(recover_summary(args.output_dir, args.recover,
                                          expected_sha256=args.expected_sha256)).decode(), end="")
    elif args.verify:
        evidence = verify_report(args.output_dir, args.verify, expected_sha256=args.expected_sha256,
                                 expected_deepnote_run_id=args.deepnote_run_id)
        print(json.dumps({"verified_run_id": args.verify, "artifacts": len(evidence["artifacts"]),
                          "missing_at_capture": len(evidence["missing_artifacts"])}))
    else:
        report = json.loads(Path(args.input).read_text(encoding="utf-8"),
                            object_pairs_hook=_unique_pairs)
        summary = publish_report(report, args.output_dir, max_issues=args.max_issues,
                                 max_samples=args.max_samples)
        if summary["level"] == 2:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
