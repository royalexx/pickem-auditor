"""One-off migration for legacy rows in data/prop_snapshots.jsonl."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pickem_math as pm


def migrate_row(row: dict) -> dict:
    if not isinstance(row, dict):
        raise pm.PickemError("snapshot must be a JSON object")
    if row.get("schema_version") == pm.SNAPSHOT_SCHEMA_VERSION:
        return row
    out = dict(row)
    if out.get("schema_version") is None:
        out["schema_version"] = 1
    side = str(out.get("side") or "over").strip().lower()
    if isinstance(out.get("books"), str):
        out["books"] = pm.convert_books(
            out["books"],
            side=side,
            line=out.get("reference_line"),
            retrieved_at=out.get("retrieved_at"),
            lenient=True,
        )
    elif out.get("books") is None:
        out["books"] = []
    elif not isinstance(out.get("books"), list):
        out["books"] = pm.convert_books(
            out["books"],
            side=side,
            line=out.get("reference_line"),
            retrieved_at=out.get("retrieved_at"),
            lenient=True,
        )
    if out.get("q_win") is None and out.get("q_model") is not None:
        try:
            out["q_win"] = pm._optional_unit("q_win", out["q_model"])
        except pm.PickemError:
            pass
    if out.get("q_grade") is None and out.get("q_model") is not None:
        try:
            out["q_grade"] = pm._optional_unit("q_grade", out["q_model"])
        except pm.PickemError:
            pass
    if out.get("derived_flags") is None:
        out["derived_flags"] = []
    out.setdefault("actual_stat", None)
    out.setdefault("closing_line", None)
    out.setdefault("closing_q_market", None)
    out.setdefault("outcome", None)
    out.setdefault("settled_at", None)
    return out


def migrate_text(text: str) -> tuple[str, int]:
    rows = []
    for line_no, line, row in pm.iter_snapshot_lines(text):
        rows.append(migrate_row(row))
    body = "".join(pm.dump_snapshot(row) for row in rows)
    return body, len(rows)


def migrate_file(path: Path, *, dry_run: bool = False) -> int:
    path = Path(path)
    if not path.exists():
        raise pm.PickemError(f"snapshot file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    migrated, count = migrate_text(raw)
    if not dry_run and migrated != raw.replace("\r\n", "\n").replace("\r", "\n"):
        with pm.locked_snapshot(path, create=False) as (handle, _locked_text):
            handle.seek(0)
            handle.truncate(0)
            handle.write(migrated)
            handle.flush()
            import os

            os.fsync(handle.fileno())
    elif not dry_run:
        normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
        if normalized != raw:
            with pm.locked_snapshot(path, create=False) as (handle, _locked_text):
                handle.seek(0)
                handle.truncate(0)
                handle.write(normalized)
                handle.flush()
                import os

                os.fsync(handle.fileno())
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy prop snapshot rows.")
    parser.add_argument(
        "--path",
        default=str(pm.DEFAULT_SNAPSHOT_PATH),
        help="prop_snapshots.jsonl path",
    )
    parser.add_argument("--dry-run", action="store_true", help="report counts without writing")
    args = parser.parse_args(argv)
    try:
        count = migrate_file(Path(args.path), dry_run=args.dry_run)
    except pm.PickemError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"migrated={count} path={args.path} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
