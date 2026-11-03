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
    output = Path(os.environ["GITHUB_ENV"])
    with output.open("a", encoding="utf-8") as file:
        for key, value in values.items():
            file.write(f"{key}={value}\n")
    print("TRAINING_LAUNCH_VALIDATED " + json.dumps(values, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
