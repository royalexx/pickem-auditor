#!/usr/bin/env python3
"""Attempt one current-day source-native NHL SOG NB2 shadow from frozen origins.

Reads the earliest original NHL SOG Gamma daily batch for the *actual* local
calendar day, revalidates signed official sources, original offer and frozen
plugin-Poisson control, and appends a new separately labeled NB2 research
receipt only if still pregame. Zero eligible sources produces an ABSTAIN audit.
The historical Phase1/legacy NB2 notebook is deliberately not replayed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v2.nhl_sog_nb2_source_native import run_day, NativeNB2Blocked


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--code-commit", required=True, help="Full git commit of this source version")
    args = p.parse_args(argv)
    try:
        result = run_day(args.project_root, now=datetime.now(timezone.utc),
                         code_sha=args.code_commit)
        print("NHL_SOG_NB2_SOURCE_NATIVE " + json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "FROZEN_NATIVE_NB2_RESEARCH" else 2
    except (NativeNB2Blocked, TypeError, OSError, KeyError, ValueError) as exc:
        print("NHL_SOG_NB2_SOURCE_NATIVE_BLOCKED " + type(exc).__name__ + ":" +
              str(exc)[:200], file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
