#!/usr/bin/env python3
"""Persistent, checksum-verified freeze cache for self-hosted precision training.

One shared immutable historical archive per source commit; one output snapshot
per market/run. This is a replay checkpoint, NOT a resumable NUTS sampler state.
Cache lives outside Actions' cleaned workspace, normally in the user's home.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

HEX40 = re.compile(r"[0-9a-f]{40}\Z")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
SOURCE_PREFIX = ("data", "bayesian_warehouse")
STATE_NAMES = ("nhl.json", "nhl_recent.json", "nba.json",
               "nba_recent.json", "nfl.json")


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, item: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".pending")
    tmp.write_text(json.dumps(item, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def cachedir() -> Path:
    loc = os.environ.get("PICKEM_FREEZE_CACHE_ROOT")
    return Path(loc).expanduser().resolve() if loc else (Path.home() / "pickem-training-frozen-cache").resolve()


def freeze_id(name: str) -> str:
    if not SAFE_ID.fullmatch(name):
        raise ValueError("unsafe_frozen_campaign_or_run_identifier")
    return name


def source_sha() -> str:
    value = os.environ.get("SOURCE_FREEZE_SHA") or os.environ.get("SOURCE_HEAD", "")
    if not HEX40.fullmatch(value):
        raise ValueError("missing_or_invalid_frozen_source_sha")
    return value


def history_paths(cache: Path, source: str) -> tuple[Path, Path]:
    return cache / "history" / (source + ".tar"), cache / "history" / (source + ".json")


def archive_is_verified(cache: Path, source: str) -> tuple[bool, str]:
    archive, manifest = history_paths(cache, source)
    if not archive.is_file() or not manifest.is_file():
        return False, "cache_miss"
    try:
        record = json.loads(manifest.read_text(encoding="utf-8"))
        if (record.get("schema") != "precision_history_cache_v1"
                or record.get("source_sha") != source
                or record.get("size") != archive.stat().st_size
                or record.get("sha256") != sha256(archive)):
            return False, "history_cache_integrity_mismatch"
    except (OSError, ValueError, TypeError):
        return False, "history_cache_manifest_corrupt"
    return True, "verified"


def cache_history(root: Path, cache: Path, source: str) -> dict:
    valid, _ = archive_is_verified(cache, source)
    archive, manifest = history_paths(cache, source)
    if valid:
        return json.loads(manifest.read_text(encoding="utf-8"))
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="source-", suffix=".tar",
                                     dir=archive.parent, delete=False) as handle:
        tmp = Path(handle.name)
    try:
        subprocess.run(["git", "-C", str(root), "cat-file", "-e",
                        source + "^{commit}"], check=True)
        subprocess.run(["git", "-C", str(root), "archive", "--format=tar",
                        "--output=" + str(tmp), source, "data/bayesian_warehouse"],
                       check=True)
        if not tmp.stat().st_size:
            raise ValueError("empty_historical_source_archive")
        record = {"schema": "precision_history_cache_v1",
                  "source_sha": source, "size": tmp.stat().st_size,
                  "sha256": sha256(tmp),
                  "created_utc": datetime.now(timezone.utc).isoformat(),
                  "archive_format": "git_tar_verified_sha256"}
        os.replace(tmp, archive)
        write_json(manifest, record)
        return record
    finally:
        tmp.unlink(missing_ok=True)


def restore_history(root: Path, cache: Path, source: str) -> int:
    valid, reason = archive_is_verified(cache, source)
    if not valid:
        print("FROZEN_HISTORY_CACHE_UNAVAILABLE " + reason, flush=True)
        return 3  # Workflow falls back to SHA-pinned Git history loader.
    archive, _ = history_paths(cache, source)
    # Validate and stage the entire archive before touching the working data.
    with tempfile.TemporaryDirectory(prefix="pickem-frozen-") as temp:
        stage = Path(temp)
        with tarfile.open(archive, "r:") as stream:
            for member in stream:
                if member.isdir():
                    continue
                name = PurePosixPath(member.name)
                if (not member.isfile() or name.is_absolute()
                        or ".." in name.parts or name.parts[:2] != SOURCE_PREFIX):
                    raise ValueError("unsafe_member_in_frozen_history_archive")
                obj = stream.extractfile(member)
                if obj is None:
                    raise ValueError("missing_frozen_history_content")
                dest = stage.joinpath(*name.parts)
                dest.parent.mkdir(parents=True, exist_ok=True)
                with obj, dest.open("wb") as out:
                    shutil.copyfileobj(obj, out)
        extracted = stage / "data" / "bayesian_warehouse"
        for state in STATE_NAMES:
            file = extracted / "states" / state
            if not file.is_file():
                raise ValueError("frozen_history_missing_state_" + state)
            if json.loads(file.read_text(encoding="utf-8")).get("schema") != "multi-sport-population-cursor-v1":
                raise ValueError("frozen_history_invalid_state_" + state)
        destination = root / "data" / "bayesian_warehouse"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(extracted, destination)
    if os.environ.get("GITHUB_ENV"):
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as out:
            out.write("SOURCE_HEAD=" + source + "\n")
    print("FROZEN_HISTORY_CACHE_RESTORED source_sha=" + source, flush=True)
    return 0


def snapshot(root: Path, cache: Path, phase: str) -> dict:
    env = os.environ
    run_id = env.get("GITHUB_RUN_ID", "")
    index = env.get("INDEX", "")
    campaign = freeze_id(env.get("CAMPAIGN_ID") or "week-20261102")
    code = env.get("CODE_HEAD", "")
    source = source_sha()
    if not run_id.isdigit() or not index.isdigit() or not 0 <= int(index) < 31:
        raise ValueError("invalid_frozen_run_or_market_index")
    if not HEX40.fullmatch(code):
        raise ValueError("invalid_frozen_code_sha")
    source_dir = root / "reports" / "precision_training" / run_id
    if not source_dir.is_dir():
        raise ValueError("missing_frozen_training_report_directory")
    if cache.is_relative_to(source_dir) or source_dir.is_relative_to(cache):
        raise ValueError("freeze_cache_must_be_outside_training_report_directory")
    # Store the source data only once per fixed SHA; reuse across all markets.
    hist = cache_history(root, cache, source)
    dst = cache / "campaigns" / campaign / f"market-{int(index):02d}" / ("run-" + run_id)
    outputs = dst / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    inventory = {}
    for file in source_dir.rglob("*"):
        if (not file.is_file() or file.is_symlink()
                or file.name in ("freeze_cache.json",)
                or file.name.endswith(".pending")):
            continue
        rel = file.relative_to(source_dir)
        target = outputs / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        # Do not trust a partially-written posterior as resumable sampling state.
        shutil.copy2(file, target)
        if sha256(file) != sha256(target):
            raise ValueError("frozen_training_output_copy_digest_mismatch")
        inventory[rel.as_posix()] = {"sha256": sha256(target),
                                    "size": target.stat().st_size}
    record = {"schema": "precision_market_frozen_state_v1",
              "campaign_id": campaign,
              "run_id": int(run_id),
              "market_index": int(index),
              "sport": env.get("SPORT"), "stat": env.get("STAT"),
              "phase": phase,
              "model_code_sha": code, "source_sha": source,
              "as_of_exclusive": env.get("CUTOFF"),
              "history_archive_sha256": hist["sha256"],
              "history_archive_size": hist["size"],
              "history_archive": str(history_paths(cache, source)[0]),
              "local_state_file": str(dst / "state.json"),
              "output_inventory": inventory,
              "preflight_outcome": env.get("VALIDATE_RESULT"),
              "fit_outcome": env.get("FIT_RESULT"),
              "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
              "resume_mode": "restart_market_from_frozen_inputs",
              "nuts_iteration_checkpoint": False,
              "accepted_as_converged": False,
              "publication_eligible": False}
    write_json(dst / "state.json", record)
    write_json(source_dir / "freeze_cache.json", record)
    print("PERSISTENT_FROZEN_STATE_SAVED " + json.dumps({
        "run_id": run_id, "index": index, "phase": phase,
        "code_sha": code, "source_sha": source,
        "state": record["local_state_file"]}, sort_keys=True), flush=True)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("restore-history", "snapshot"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--phase", choices=("prepared", "final"), default="final")
    args = parser.parse_args()
    root = args.root.resolve()
    cache = cachedir()
    if args.command == "restore-history":
        return restore_history(root, cache, source_sha())
    snapshot(root, cache, args.phase)
    return 0


if __name__ == "__main__":
    sys.exit(main())
