#!/usr/bin/env python3
"""Restore a read-only, SHA-pinned population snapshot from the private GitHub branch.

Cross-platform replacement for the Bash-only 'history_warehouse_store.sh load'.
Only regular files from data/bayesian_warehouse may be restored. Never commits,
pushes, merges, mutates an existing warehouse branch, or edits source records.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

SOURCE_REF = "refs/remotes/origin/data/bayesian-history"
SOURCE_BRANCH = "refs/heads/data/bayesian-history"
PREFIX = PurePosixPath("data/bayesian_warehouse")
EXPECTED_STATES = ("nhl.json", "nhl_recent.json", "nba.json", "nba_recent.json", "nfl.json")


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(root), *args],
                          text=True, capture_output=True, check=True)
    return proc.stdout.strip()


def _member_path(name: str) -> Path:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or path == PREFIX or path.parts[:2] != PREFIX.parts:
        raise ValueError("unsafe_historical_warehouse_archive_path")
    return Path(*path.parts)


def extract_verified_archive(archive: Path, root: Path) -> int:
    count = 0
    with tarfile.open(archive, "r:") as source:
        for member in source:
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError("unexpected_warehouse_symlink_or_special_archive_entry")
            relative = _member_path(member.name)
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            data = source.extractfile(member)
            if data is None:
                raise ValueError("warehouse_archive_file_has_no_content")
            with data, destination.open("wb") as target:
                shutil.copyfileobj(data, target)
            count += 1
    return count


def restore(root: Path, *, fetch: bool = True, source_commit: str | None = None) -> dict:
    """Load an exact historical commit when SOURCE_FREEZE_SHA is supplied.

    Re-running a failed fit must not silently substitute a newer history
    branch revision. Without a pin, the first job freezes the branch head
    and the workflow passes that SHA to every subsequent job.
    """
    root = root.resolve()
    if fetch:
        git(root, "fetch", "--quiet", "--no-tags", "origin",
            f"+{SOURCE_BRANCH}:{SOURCE_REF}")
    requested = source_commit if source_commit is not None else os.environ.get("SOURCE_FREEZE_SHA", "")
    if requested and not re.fullmatch(r"[0-9a-f]{40}", requested):
        raise ValueError("invalid_frozen_historical_source_sha")
    commit = requested or git(root, "rev-parse", "--verify", SOURCE_REF)
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("invalid_historical_source_commit")
    if requested:
        git(root, "cat-file", "-e", f"{commit}^{{commit}}")
        # A frozen history must still belong to the current source history.
        git(root, "merge-base", "--is-ancestor", commit, SOURCE_REF)
    location = git(root, "ls-tree", "-d", "--name-only", commit,
                   str(PREFIX))
    if str(PREFIX) not in location.splitlines():
        raise ValueError("missing_historical_warehouse_on_source_branch")

    with tempfile.TemporaryDirectory(prefix="pickem-history-") as tmp:
        archive = Path(tmp) / "warehouse.tar"
        git(root, "archive", "--format=tar", f"--output={archive}",
            commit, str(PREFIX))
        files = extract_verified_archive(archive, root)

    state_dir = root / Path(*PREFIX.parts) / "states"
    cursors = {}
    for name in EXPECTED_STATES:
        checkpoint = state_dir / name
        if not checkpoint.is_file():
            raise ValueError("warehouse_missing_required_state_" + name)
        obj = json.loads(checkpoint.read_text(encoding="utf-8"))
        if obj.get("schema") != "multi-sport-population-cursor-v1":
            raise ValueError("warehouse_invalid_state_schema_" + name)
        cursors[name.removesuffix(".json")] = obj["cursor"]

    report = {"schema": "windows_warehouse_snapshot_v1",
              "source_commit": commit, "source_branch": "data/bayesian-history",
              "files_restored": files, "source_cursors": cursors,
              "read_only": True, "fit_source_pinned": True,
              "source_freeze_enforced": bool(requested)}
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    result = restore(args.root)
    env_file = os.environ.get("GITHUB_ENV")
    if env_file:
        with open(env_file, "a", encoding="utf-8") as out:
            out.write(f"SOURCE_HEAD={result['source_commit']}\n")
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
