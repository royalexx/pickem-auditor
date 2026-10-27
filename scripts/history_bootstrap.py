#!/usr/bin/env python3
"""Losslessly restore trusted legacy history into a GitHub Actions workspace.

The immutable, complete October 26 archive is stored in the private
``data/history-archive`` Git branch. This script verifies the checksummed
segments before selectively restoring *operational* history and original
forecasts. All 7,905 other files stay accessible in the immutable archive.

No forecasts, engine parameters, probabilities or timestamps are reestimated.
Existing target files always win, so a rerun cannot regress newer history.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

EXPECTED_SCHEMA = "pickem-history-full-v1"
SEED_FILES = ("data/prop_snapshots.jsonl", "data/archive_manifest.json", "data/handoff-summary.json")
SEED_DIRS = ("data/usage", "data/season")


class HistoryError(RuntimeError):
    """Archive cannot be validated or restored safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bootstrap(archive_dir: Path, destination: Path) -> dict:
    archive_dir = archive_dir.resolve()
    destination = destination.resolve()
    manifest = json.loads((archive_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != EXPECTED_SCHEMA:
        raise HistoryError("HISTORY_ARCHIVE_SCHEMA_UNRECOGNIZED")
    parts = manifest.get("files")
    if not isinstance(parts, list) or len(parts) != 90:
        raise HistoryError("HISTORY_ARCHIVE_SEGMENT_COUNT_INVALID")
    if sorted(x["path"] for x in parts) != [
        f"archive/2026-10-26/part{i:03d}.bin" for i in range(90)
    ]:
        raise HistoryError("HISTORY_ARCHIVE_SEGMENT_NAMES_INVALID")

    with tempfile.TemporaryDirectory(prefix="pickem-history-") as scratch:
        tmp = Path(scratch)
        archive = tmp / "pickem-history.tar.zst"
        with archive.open("wb") as output:
            for item in sorted(parts, key=lambda x: x["path"]):
                piece = archive_dir / Path(item["path"]).name
                if not piece.is_file() or piece.stat().st_size != item["bytes"]:
                    raise HistoryError("HISTORY_ARCHIVE_SEGMENT_MISSING_OR_INVALID")
                if _sha256(piece) != item["sha256"]:
                    raise HistoryError("HISTORY_ARCHIVE_SEGMENT_CHECKSUM_MISMATCH")
                with piece.open("rb") as source:
                    shutil.copyfileobj(source, output)
        if archive.stat().st_size != manifest.get("bytes") or _sha256(archive) != manifest.get("sha256"):
            raise HistoryError("HISTORY_ARCHIVE_GLOBAL_CHECKSUM_MISMATCH")
        restored = tmp / "unpacked"
        restored.mkdir()
        cmd = ["tar", "-I", "zstd", "-xf", str(archive), "-C", str(restored),
               *SEED_FILES, *SEED_DIRS]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=180)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise HistoryError(f"HISTORY_ARCHIVE_EXTRACT_FAILED: {type(exc).__name__}") from exc

        snap = restored / "data/prop_snapshots.jsonl"
        if not snap.is_file():
            raise HistoryError("HISTORY_ARCHIVE_SNAPSHOTS_MISSING")
        with snap.open("r", encoding="utf-8") as file:
            forecast_count = sum(bool(line.strip()) for line in file)
        if forecast_count != 1492:
            raise HistoryError("HISTORY_ARCHIVE_FORECAST_COUNT_MISMATCH")
        receipt = {"schema": EXPECTED_SCHEMA, "archive_sha256": manifest["sha256"],
                   "forecast_rows_original": forecast_count, "existing_files_preserved": 0,
                   "files_restored": 0, "seeded_from_2026_10_26": True}
        for name in SEED_FILES:
            original = restored / name
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                receipt["existing_files_preserved"] += 1
            else:
                shutil.copy2(original, target)
                receipt["files_restored"] += 1
        for name in SEED_DIRS:
            root = restored / name
            if not root.exists():
                continue
            for original in root.rglob("*"):
                if not original.is_file():
                    continue
                target = destination / name / original.relative_to(root)
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    receipt["existing_files_preserved"] += 1
                else:
                    shutil.copy2(original, target)
                    receipt["files_restored"] += 1
        receipt_path = destination / "reports/history_bootstrap.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt))
        return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", required=True, type=Path)
    parser.add_argument("--destination", default=".", type=Path)
    args = parser.parse_args()
    try:
        bootstrap(args.archive_dir, args.destination)
    except (HistoryError, OSError, ValueError, KeyError) as exc:
        print(f"HISTORY_BOOTSTRAP_FAILED: {exc}", flush=True)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())