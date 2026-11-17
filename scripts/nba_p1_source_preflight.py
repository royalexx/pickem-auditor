"""Read-only, fail-closed preflight of NBA historical shard receipts.

This is NOT a P1 pregame feature generator and does not bypass G0 acceptance.
Point --manifest to the existing WS1 coverage.json; --warehouse-root is the
root of an immutable checkout of data/bayesian-history at its recorded SHA.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

VERSION = "nba-p1-prerequisite-source-preflight/1.0"
STATS = frozenset(("assists", "blocks", "pa", "points", "pr", "pra",
                   "ra", "rebounds", "steals", "threes", "turnovers"))
SEASONS = frozenset(str(y) for y in range(2019, 2028))


def preflight(manifest: dict, warehouse_root: Path) -> dict:
    if not isinstance(manifest, dict) or manifest.get("schema") != "nba-ws1-coverage-audit/1":
        raise ValueError("INVALID_WS1_COVERAGE_SCHEMA")
    entries = manifest.get("source_manifest")
    if not isinstance(entries, list) or not entries:
        raise ValueError("MISSING_SOURCE_MANIFEST")
    paths = set()
    results = []
    for item in entries:
        if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
            raise ValueError("UNEXPECTED_MANIFEST_FIELDS")
        name, length, digest = item["path"], item["bytes"], item["sha256"]
        if not isinstance(name, str):
            raise ValueError("INVALID_SHARD_PATH")
        parts = Path(name).parts
        if (len(parts) != 6 or parts[:4] != ("data", "bayesian_warehouse", "populations", "nba")
                or parts[4] not in STATS or parts[5] not in {f"{y}.jsonl.gz" for y in SEASONS}):
            raise ValueError("UNSAFE_OR_UNEXPECTED_SHARD_PATH")
        if name in paths:
            raise ValueError("DUPLICATE_SHARD_PATH")
        paths.add(name)
        if type(length) is not int or length < 1 or not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("INVALID_SHA_OR_SIZE")
        file = warehouse_root.joinpath(*parts)
        if not file.is_file():
            results.append({"path": name, "status": "MISSING"})
            continue
        hasher = hashlib.sha256()
        size = 0
        with file.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(block)
                size += len(block)
        computed = hasher.hexdigest()
        status = "VERIFIED_SHA256" if (computed == digest and size == length) else "HASH_OR_SIZE_MISMATCH"
        results.append({"path": name, "status": status, "observed_bytes": size,
                        "observed_sha256": computed})
    missing_stats = sorted((stat, season) for stat in STATS for season in SEASONS
                           if f"data/bayesian_warehouse/populations/nba/{stat}/{season}.jsonl.gz" not in paths)
    statuses = {s: sum(r["status"] == s for r in results) for s in
                ("VERIFIED_SHA256", "MISSING", "HASH_OR_SIZE_MISMATCH")}
    approved = (not missing_stats and statuses["VERIFIED_SHA256"] == len(results)
                and len(results) == len(STATS) * len(SEASONS))
    return {"schema": VERSION, "status": "SOURCE_BYTES_VERIFIED" if approved else "BLOCKED",
            "source_profile": "historical_reconstruction",
            "pregame_original_capture_certified": False,
            "expected_files": len(STATS) * len(SEASONS), "manifest_files": len(entries),
            "missing_stat_seasons": [f"{stat}/{season}" for stat, season in missing_stats],
            "counts": statuses, "files": results,
            "warning": "Content-hash verification does not establish historical availability clocks, legal game-day rosters or G0 acceptance."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--warehouse-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = preflight(json.loads(args.manifest.read_text(encoding="utf-8")),
                           args.warehouse_root)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema": VERSION, "status": "BLOCKED", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["status"] == "SOURCE_BYTES_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
