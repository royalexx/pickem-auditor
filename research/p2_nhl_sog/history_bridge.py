"""P2 bridge: re-use the verified native NHL signed historical observations.

Original game logs/profile/FINAL bytes are NOT recopied, rewritten, backdated
or reconstructed from box scores. P0 source receipt binds the original
verified archive and the original C03 collector-possession timestamp.
"""
from __future__ import annotations
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
import hashlib
import json
import os
import stat
from tempfile import SpooledTemporaryFile, gettempdir
from time import monotonic
import zipfile

from v2.nhl_sog_exposure_shadow import MAX_PEER_RATE_GAMES, MIN_PEER_GAMES, MIN_PEERS
from v2.p0_integrity.contracts import VERSION, canonical_bytes, validate_record
from v2.p0_integrity.storage import append_immutable, verify_immutable_record
from scripts.c03_live_transport import verify_signed_capture
from v2.nhl_sog_official_history_producer import independent_verify_observation_lineage
from .source_pipeline import (SourceBlocked, require, digest, clock, stamp,
                              current_storage, safe_relative, put_once,
                              ROOT_NAMESPACE, HEX)

def checked_pool(root, pool):
    current_storage(root)
    base = Path(root).resolve()
    p = Path(pool).resolve()
    require(p != base and p.is_relative_to(base), "UNAPPROVED_HISTORICAL_SOURCE_POOL")
    require(p.is_dir(), "HISTORICAL_ORIGINAL_SOURCE_POOL_MISSING")
    return p

def bridge_original_receipt(root, pool, original_receipt, *, freeze, event_start, kind):
    pool = checked_pool(root, pool)
    require(isinstance(original_receipt, dict), "SIGNED_ORIGINAL_RECEIPT_MISSING")
    try:
        raw_doc = verify_signed_capture(original_receipt, archive_root=pool,
                                        freeze=freeze, event_start=event_start)
    except Exception as exc:
        raise SourceBlocked("C03_HISTORICAL_PROOF_INVALID:" + type(exc).__name__) from exc
    received = clock(original_receipt.get("received_at"))
    require(received <= clock(freeze) < clock(event_start),
            "HISTORICAL_SOURCE_AFTER_FREEZE")
    path = (pool / original_receipt["archive_path"]).resolve()
    require(path.is_relative_to(pool) and path.is_file() and
            digest(path.read_bytes()) == original_receipt["body_sha256"],
            "HISTORICAL_BODY_SHA_MISMATCH")
    relative = str(path.relative_to(Path(root).resolve()))
    source_id = "nhl:history:" + kind + ":" + original_receipt["source_id"]
    rec = {
      "record_type": "SourceReceipt", "schema_version": VERSION,
      "receipt_id": "p2hist:" + digest(canonical_bytes(
          [kind, source_id, original_receipt["body_sha256"],
           original_receipt["received_at"]])),
      "source_id": source_id, "source_kind": "nhl_historical_" + kind,
      "source_available_at": stamp(received), "collected_at": stamp(received),
      "source_sha256": original_receipt["body_sha256"],
      "archive_path": relative, "provenance_class": "collector_possession"
    }
    validate_record("SourceReceipt", rec)
    out = append_immutable(root, "SourceReceipt", rec)
    return {"record": rec, "record_sha256": out["sha256"],
            "historical_source_url": original_receipt.get("source_url"),
            "verified_at_original_possession": original_receipt["received_at"],
            "publisher_release_time_verified": False}

def verified_player_history(root, pool, entries, *, player_id, group,
                            freeze, event_start, derived_root=None, _bridge_cache=None):
    pool = checked_pool(root, pool)
    require(isinstance(entries, list), "SIGNED_HISTORICAL_ENTRIES_MISSING")
    out, refs, seen = [], {}, set()
    lineage_options = {"observation_root": derived_root} if derived_root is not None else {}
    for entry in entries:
        try:
            receipt = independent_verify_observation_lineage(
                entry, archive_root=pool, freeze=freeze, event_start=event_start,
                **lineage_options)
        except Exception as exc:
            raise SourceBlocked("ORIGINAL_HISTORICAL_LINEAGE_REJECTED:" +
                                type(exc).__name__) from exc
        raw = safe_relative(derived_root or pool, receipt["archive_path"]).read_bytes()
        require(digest(raw) == receipt["content_sha256"],
                "DERIVED_OBSERVATION_TAMPERED")
        obs = json.loads(raw)
        require(str(obs["player_id"]) == str(player_id) and
                obs["position_group"] == group and obs["played"] is True,
                "WRONG_HISTORICAL_PLAYER_POSITION_OR_PARTICIPATION")
        gid = str(obs["event_id"])
        require(gid not in seen and gid != str(obs.get("target_event_id")),
                "HISTORICAL_DOUBLE_COUNT_OR_TARGET_GAME")
        seen.add(gid)
        row = obs["source_game_log_row"]
        require(row.get("gameDate") < clock(event_start).date().isoformat() and
                clock(obs["event_ended_at"]) <= clock(freeze),
                "HISTORICAL_FINAL_NOT_AVAILABLE_PRE_FREEZE")
        names = {
            "profile": entry["raw_profile_receipt"],
            "game_log": entry["raw_log_receipt"],
            "final": entry["raw_final_receipt"]
        }
        ids = []
        for kind, original in names.items():
            proof_sha = original["collector_proof_sha256"]
            if proof_sha not in refs:
                key = kind, digest(canonical_bytes(original))
                if _bridge_cache is not None and key in _bridge_cache:
                    refs[proof_sha] = _bridge_cache[key]
                else:
                    refs[proof_sha] = bridge_original_receipt(
                        root, pool, original, freeze=freeze,
                        event_start=event_start, kind=kind)
                    if _bridge_cache is not None:
                        _bridge_cache[key] = refs[proof_sha]
            ids.append(refs[proof_sha]["record"]["receipt_id"])
        out.append({
            "game_id": gid, "game_date": row["gameDate"],
            "historical_team": row.get("teamAbbrev"),
            "shots_on_goal": obs["shots_on_goal"],
            "toi_minutes": obs["toi_minutes"],
            "observation_receipt_sha256": receipt["content_sha256"],
            "original_source_receipt_ids": ids,
            "signed_original_source_proofs": {
                kind: original["collector_proof_sha256"]
                for kind, original in names.items()}
        })
    return sorted(out, key=lambda x: (x["game_date"], x["game_id"])), [
        refs[k] for k in sorted(refs)]


class VerifiedGameHistories:
    """Reuse exact verified inputs inside one original game/freeze invocation."""

    def __init__(self, root, pool, *, freeze, event_start, derived_root=None):
        self.scope = (root, pool, freeze, event_start)
        self._derived_root = derived_root
        self._sources = {}
        self._players = {}

    def verify(self, root, pool, entries, *, player_id, group, freeze, event_start):
        require((root, pool, freeze, event_start) == self.scope,
                "P2_VERIFIED_HISTORY_SCOPE_MISMATCH")
        key = player_id, group, digest(canonical_bytes(entries))
        if key not in self._players:
            self._players[key] = verified_player_history(
                root, pool, entries, player_id=player_id, group=group,
                freeze=freeze, event_start=event_start, derived_root=self._derived_root,
                _bridge_cache=self._sources,
            )
        return self._players[key]

def _load_signed_manifest(root, manifest_rel, expected_sha256):
    current_storage(root)
    p = safe_relative(root, manifest_rel)
    raw = p.read_bytes()
    require(digest(raw) == expected_sha256, "SIGNED_HISTORY_MANIFEST_HASH_MISMATCH")
    doc = json.loads(raw)
    require(isinstance(doc, dict) and
            isinstance(doc.get("signed_observation_contracts_by_player"), dict),
            "SIGNED_HISTORY_MANIFEST_SCHEMA_INVALID")
    return p, doc


def load_signed_manifest(root, manifest_rel, expected_sha256):
    _, doc = _load_signed_manifest(root, manifest_rel, expected_sha256)
    return doc["signed_observation_contracts_by_player"]


def _restore_history_archive(root, source, entries, restored_rel, *, label="full"):
    started = monotonic()
    last_report = started
    paths = [Path(entry.filename) for entry in entries]
    folders = {parent: safe_relative(root, str(Path(restored_rel) / parent))
               for parent in {path.parent for path in paths}}
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)
    targets = [folders[path.parent] / path.name for path in paths]

    def restore(pair):
        entry, target = pair
        original = source.read(entry)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(target, flags, 0o640)
        except FileExistsError:
            require(not target.is_symlink() and target.read_bytes() == original,
                    "P2_SIGNED_HISTORY_RESTORE_PARTIAL_OR_DIFFERENT")
            return True
        with os.fdopen(descriptor, "wb") as output:
            output.write(original)
        return False

    print(f"NHL_SOG_HISTORY_RESTORE_START scope={label} entries={len(entries)}", flush=True)
    count = 0
    reused = 0
    with ThreadPoolExecutor(max_workers=24) as workers:
        pending = {workers.submit(restore, pair) for pair in zip(entries, targets)}
        while pending:
            done, pending = wait(pending, timeout=15, return_when=FIRST_COMPLETED)
            try:
                reused += sum(work.result() for work in done)
            except BaseException:
                for work in pending:
                    work.cancel()
                raise
            count += len(done)
            now = monotonic()
            if count == len(entries) or now - last_report >= 15:
                print(f"NHL_SOG_HISTORY_RESTORE_PROGRESS scope={label} entries={count}/{len(entries)} "
                      f"reused={reused} elapsed_seconds={now - started:.1f}", flush=True)
                last_report = now


def _subset_history_entries(source, entries, signed_history, selected_players):
    """Use source roster IDs as an I/O hint, then retain position-peer reserve."""
    members = {entry.filename: entry for entry in entries}
    selected = set(selected_players) & set(signed_history)
    by_group = {"D": [], "F": []}
    for player_id, history in signed_history.items():
        if not isinstance(history, list) or not history:
            continue
        try:
            receipt = history[0]["observation_receipt"]
            raw = source.read(members[receipt["archive_path"]])
            if digest(raw) != receipt["content_sha256"]:
                continue
            observation = json.loads(raw)
            group = observation["position_group"]
            if str(observation["player_id"]) == player_id and group in by_group:
                by_group[group].append((min(len(history), MAX_PEER_RATE_GAMES), player_id))
        except (OSError, ValueError, TypeError, KeyError):
            continue

    for peers in by_group.values():
        played = 0
        for count, (games, player_id) in enumerate(sorted(peers, key=lambda row: (-row[0], row[1])), 1):
            selected.add(player_id)
            played += games
            # Extra peers protect the minimum against leave-one-out and
            # individual receipt rejections during independent verification.
            if count >= MIN_PEERS + 10 and played >= MIN_PEER_GAMES + 40:
                break

    selected_entries = set()
    for player_id in sorted(selected):
        for history_row in signed_history[player_id]:
            if not isinstance(history_row, dict):
                continue
            for receipt_kind in ("observation_receipt", "raw_profile_receipt",
                                 "raw_log_receipt", "raw_final_receipt"):
                receipt = history_row.get(receipt_kind)
                if not isinstance(receipt, dict):
                    continue
                for field in ("archive_path", "collector_proof_archive_path"):
                    path = receipt.get(field)
                    if isinstance(path, str) and path in members:
                        selected_entries.add(path)

    require(bool(selected_entries), "P2_SIGNED_HISTORY_SUBSET_EMPTY")
    print(f"NHL_SOG_HISTORY_SUBSET players={len(selected)}/{len(signed_history)} "
          f"entries={len(selected_entries)}/{len(entries)}", flush=True)
    return [entry for entry in entries if entry.filename in selected_entries], sorted(selected)


def available_history_players(pool):
    """Return the exact published source IDs for a deliberately partial cache."""
    pool = Path(pool)
    if pool.parent.parent.name not in {"verified_history_subsets", "verified_history_subset_recovery"}:
        return None
    marker = pool / "_verified_archive.json"
    if not marker.with_suffix(".json.complete").is_file():
        marker = pool / "_verified_raw_archive.json"
    raw = marker.read_bytes()
    require(marker.with_suffix(".json.complete").read_text() == digest(raw),
            "P2_SIGNED_HISTORY_SUBSET_MARKER_INVALID")
    record = json.loads(raw)
    selected = record.get("available_player_ids")
    require(record["archive_sha256"] == pool.parent.name and
            record["subset_request_sha256"] == pool.name and
            isinstance(selected, list) and all(isinstance(pid, str) for pid in selected) and
            selected == sorted(set(selected)),
            "P2_SIGNED_HISTORY_SUBSET_IDENTITY_INVALID")
    return set(selected)


def open_history_sources(root, manifest_rel, expected_sha256, history_pool, *,
                         selected_players=None, derived_cache=None):
    """Resolve original loose receipts or restore bytes from their exact ZIP.

    The original C03 receipt paths and hashes remain unchanged. ZIP contents
    are still independently reverified by the same P2/P4 receipt readers.
    """
    manifest_path, doc = _load_signed_manifest(root, manifest_rel, expected_sha256)
    bundle = doc.get("source_bundle")
    if bundle is None:
        require(derived_cache is None, "P2_DERIVED_CACHE_REQUIRES_SIGNED_ZIP")
        return checked_pool(root, history_pool)

    if derived_cache is not None:
        temp_root = Path(gettempdir()).resolve()
        derived_cache = Path(derived_cache).resolve()
        require(derived_cache != temp_root and derived_cache.is_relative_to(temp_root),
                "P2_DERIVED_CACHE_MUST_BE_EPHEMERAL")
        derived_cache.mkdir(parents=True, exist_ok=True)

    require(isinstance(bundle, dict) and bundle.get("format") ==
            "exact_original_receipts_and_derived_zip_v1",
            "P2_SIGNED_HISTORY_BUNDLE_FORMAT_INVALID")
    wanted = bundle.get("sha256")
    require(isinstance(wanted, str) and HEX.fullmatch(wanted) and
            bundle.get("path") == f"history_bundles/{wanted}.zip",
            "P2_SIGNED_HISTORY_BUNDLE_POINTER_INVALID")
    require(manifest_path.parent.name == "daily_history_manifests",
            "P2_SIGNED_HISTORY_BUNDLE_MANIFEST_LOCATION_INVALID")
    original_pool = checked_pool(root, manifest_path.parent.parent)
    archive = safe_relative(original_pool, bundle["path"])
    archive_identity = {"format": bundle["format"], "archive_sha256": wanted}
    if selected_players is None:
        candidates = (f"{ROOT_NAMESPACE}/verified_history_bundles/{wanted}",
                      f"{ROOT_NAMESPACE}/verified_history_recovery/{wanted}")
    else:
        selected_players = sorted({str(player_id) for player_id in selected_players})
        require(bool(selected_players), "P2_SIGNED_HISTORY_SUBSET_ROSTERS_EMPTY")
        scope = digest(canonical_bytes({"requested_player_ids": selected_players,
                                       "peer_reserve_policy": "same-position-ranked-v1"}))
        archive_identity["subset_request_sha256"] = scope
        candidates = (f"{ROOT_NAMESPACE}/verified_history_subsets/{wanted}/{scope}",
                      f"{ROOT_NAMESPACE}/verified_history_subset_recovery/{wanted}/{scope}")

    print(f"NHL_SOG_HISTORY_ARCHIVE_VERIFY compressed_bytes={archive.stat().st_size}", flush=True)
    with archive.open("rb") as handle, SpooledTemporaryFile(max_size=32_000_000) as local:
        for folder in candidates if derived_cache is None else ():
            verified_rel = f"{folder}/_verified_archive.json"
            verified = safe_relative(root, verified_rel)
            if verified.is_file() and verified.with_suffix(".json.complete").is_file():
                require(hashlib.file_digest(handle, "sha256").hexdigest() == wanted,
                        "P2_SIGNED_HISTORY_BUNDLE_SHA_MISMATCH")
                if selected_players is None:
                    archive_record = canonical_bytes(archive_identity)
                else:
                    available_history_players(verified.parent)
                    archive_record = verified.read_bytes()
                put_once(root, verified_rel, archive_record)
                print("NHL_SOG_HISTORY_RESTORE_CACHE_HIT", flush=True)
                return checked_pool(root, verified.parent)

        checksum = hashlib.sha256()
        for chunk in iter(lambda: handle.read(4_000_000), b""):
            checksum.update(chunk)
            local.write(chunk)
        require(checksum.hexdigest() == wanted, "P2_SIGNED_HISTORY_BUNDLE_SHA_MISMATCH")
        with zipfile.ZipFile(local) as source:
            entries = source.infolist()
            require(entries and len({entry.filename for entry in entries}) == len(entries)
                    and sum(entry.file_size for entry in entries) <= 1_000_000_000,
                    "P2_SIGNED_HISTORY_BUNDLE_ENTRY_LIMIT_INVALID")
            allowed = {"raw_http_body", "c03_collector_receipts", "nhl_sog_official_derived"}
            for entry in entries:
                path = Path(entry.filename)
                require(not entry.is_dir() and not path.is_absolute() and
                        ".." not in path.parts and "\\" not in entry.filename and
                        len(path.parts) >= 2 and path.parts[0] in allowed and
                        entry.filename == path.as_posix() and
                        not stat.S_ISLNK(entry.external_attr >> 16),
                        "P2_SIGNED_HISTORY_BUNDLE_ENTRY_INVALID")

            if selected_players is not None:
                entries, selected = _subset_history_entries(
                    source, entries, doc["signed_observation_contracts_by_player"],
                    selected_players,
                )
                archive_identity["available_player_ids"] = selected
            archive_record = canonical_bytes(archive_identity)

            marker_name = "_verified_archive.json"
            if derived_cache is not None:
                derived = [entry for entry in entries
                           if entry.filename.startswith("nhl_sog_official_derived/")]
                entries = [entry for entry in entries
                           if not entry.filename.startswith("nhl_sog_official_derived/")]
                require(bool(derived and entries), "P2_SIGNED_HISTORY_SPLIT_EMPTY")
                _restore_history_archive(derived_cache, source, derived, ".", label="derived")
                marker_name = "_verified_raw_archive.json"

            for folder in candidates:
                verified_rel = f"{folder}/{marker_name}"
                try:
                    cached = safe_relative(root, verified_rel).with_suffix(".json.complete")
                    fully_cached = safe_relative(root, f"{folder}/_verified_archive.json")
                    if (derived_cache is not None and
                            fully_cached.with_suffix(".json.complete").is_file()):
                        put_once(root, f"{folder}/_verified_archive.json", archive_record)
                        return checked_pool(root, fully_cached.parent)
                    if not cached.is_file():
                        _restore_history_archive(root, source, entries, folder,
                                                 label="raw" if derived_cache is not None else "full")
                    put_once(root, verified_rel, archive_record)
                except SourceBlocked as exc:
                    if folder == candidates[0] and exc.code in {
                        "P2_SIGNED_HISTORY_RESTORE_PARTIAL_OR_DIFFERENT",
                        "IMMUTABLE_PARTIAL_OR_INTERRUPTED_SOURCE",
                    }:
                        print("NHL_SOG_HISTORY_RESTORE_ISOLATED_RECOVERY", flush=True)
                        continue
                    raise
                return checked_pool(root, safe_relative(root, folder))

def signed_original_profile_name(pool, entry, *, freeze, event_start):
    """Only names taken from the signed official NHL profile are source-bound."""
    from scripts.c03_live_transport import verify_signed_capture
    receipt = entry["raw_profile_receipt"]
    data = verify_signed_capture(receipt, archive_root=pool,
                                 freeze=freeze, event_start=event_start)
    first, last = data.get("firstName"), data.get("lastName")
    if isinstance(first, dict): first = first.get("default")
    if isinstance(last, dict): last = last.get("default")
    require(isinstance(first, str) and isinstance(last, str) and
            bool(first.strip()) and bool(last.strip()),
            "SIGNED_OFFICIAL_PROFILE_NAME_UNAVAILABLE")
    return first.strip() + " " + last.strip()
