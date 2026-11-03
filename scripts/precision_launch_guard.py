#!/usr/bin/env python3
"""Validate a one-time push-triggered training launch or an explicit recovery.

This file is intentionally independent of the PyMC environment so that a
self-hosted runner can validate the request before starting heavy work.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}\Z")
CAMPAIGN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")


SKIP_CLASSES = {
    "model_nonconvergence",
    "market_specific_source_gap",
    "market_specific_runtime",
}
REPAIR_STATUSES = {"attempt_failed", "no_safe_repair"}


def validate_skip_payload(payload: dict, *, index: int, code_sha: str,
                          source_sha: str, cutoff: str) -> str | None:
    """Require a signed-off-by-evidence skip for any explicit skip launch.

    A skipped market is never relabeled as converged, and a 'skip' request
    cannot change frozen history, cutoff, or model-code identity.
    """
    skip = payload.get("skip")
    if skip is None:
        return None
    if not isinstance(skip, dict) or index == 0:
        raise ValueError("invalid_skip_payload")
    prev = skip.get("from_index")
    if type(prev) is not int or prev != index - 1 or not 0 <= prev < 30:
        raise ValueError("skip_must_advance_exactly_one_market")
    run_id = skip.get("failed_run_id")
    if type(run_id) is not int or run_id <= 0:
        raise ValueError("invalid_failed_run_reference")
    reason = skip.get("reason")
    if not isinstance(reason, str) or not 12 <= len(reason.strip()) <= 700:
        raise ValueError("skip_must_record_specific_reason")
    if skip.get("failure_class") not in SKIP_CLASSES:
        raise ValueError("unsafe_or_unknown_market_skip_class")
    if skip.get("repair_status") not in REPAIR_STATUSES:
        raise ValueError("missing_or_invalid_repair_attempt_receipt")
    if (skip.get("code_sha") != code_sha
            or skip.get("source_sha") != source_sha
            or skip.get("as_of") != cutoff):
        raise ValueError("skip_attempt_changed_frozen_inputs")
    path = f".training-control/skips/market-{prev:02d}.json"
    if skip.get("report_path") != path:
        raise ValueError("skip_report_path_mismatch")
    return path


def verify_skip_receipt(payload: dict, *, report_path: str | None,
                        root: Path = Path(".")) -> None:
    """Check immutable market failure evidence before starting a successor."""
    if report_path is None:
        return
    record = json.loads((root / report_path).read_text(encoding="utf-8"))
    skip = payload["skip"]
    if (record.get("schema") != "pickem_precision_market_skip_v1"
            or record.get("campaign_id") != payload["campaign_id"]
            or record.get("to_index") != payload["index"]):
        raise ValueError("invalid_skip_failure_ledger")
    for key in ("from_index", "failed_run_id", "failure_class",
                "repair_status", "reason", "code_sha", "source_sha", "as_of"):
        if record.get(key) != skip[key]:
            raise ValueError("skip_failure_ledger_mismatch_" + key)


def resolve_request(payload: dict, *, event_sha: str) -> dict[str, str]:
    if not isinstance(payload, dict) or payload.get("schema") != "pickem_precision_campaign_launch_v1":
        raise ValueError("invalid_training_launch_schema")
    index = payload.get("index")
    if type(index) is not int or not 0 <= index < 31:
        raise ValueError("invalid_training_launch_index")
    cohort = str(payload.get("max_per_position", "0"))
    if cohort not in ("0", "15"):
        raise ValueError("invalid_training_launch_cohort")
    cutoff = payload.get("as_of")
    if not isinstance(cutoff, str):
        raise ValueError("missing_training_launch_cutoff")
    frozen_day = date.fromisoformat(cutoff)
    if not date(2023, 10, 1) < frozen_day <= date.today():
        raise ValueError("invalid_training_launch_cutoff")
    code_sha = payload.get("code_sha") or event_sha
    source_sha = payload.get("source_sha")
    if not isinstance(code_sha, str) or not SHA.fullmatch(code_sha):
        raise ValueError("invalid_training_launch_code_sha")
    if not isinstance(source_sha, str) or not SHA.fullmatch(source_sha):
        raise ValueError("missing_or_invalid_training_launch_source_sha")
    campaign_id = payload.get("campaign_id")
    if not isinstance(campaign_id, str) or not CAMPAIGN.fullmatch(campaign_id):
        raise ValueError("invalid_training_campaign_id")
    validate_skip_payload(payload, index=index, code_sha=code_sha,
                          source_sha=source_sha, cutoff=cutoff)
    return {
        "INDEX": str(index),
        "MAX_PER_POSITION": cohort,
        "CUTOFF": cutoff,
        "HOLDOUT_UNTIL": cutoff,
        "CODE_HEAD": code_sha,
        "SOURCE_FREEZE_SHA": source_sha,
        "CAMPAIGN_ID": campaign_id,
    }


def main() -> None:
    request = json.loads(Path(".training-control/start.json").read_text(encoding="utf-8"))
    values = resolve_request(request, event_sha=os.environ["GITHUB_SHA"])
    report_path = validate_skip_payload(
        request, index=request["index"], code_sha=values["CODE_HEAD"],
        source_sha=values["SOURCE_FREEZE_SHA"], cutoff=values["CUTOFF"])
    verify_skip_receipt(request, report_path=report_path)
    output = Path(os.environ["GITHUB_ENV"])
    with output.open("a", encoding="utf-8") as file:
        for key, value in values.items():
            file.write(f"{key}={value}\n")
    print("TRAINING_LAUNCH_VALIDATED " + json.dumps(values, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
