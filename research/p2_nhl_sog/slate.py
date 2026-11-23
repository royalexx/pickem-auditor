"""Build original, line-independent P2 player bundles for a scheduled NHL game."""
from __future__ import annotations

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from functools import lru_cache
from urllib.request import Request, urlopen

from v2.nhl_sog_exposure_shadow import (
    MAX_PEER_RATE_GAMES, MAX_RATE_GAMES, MIN_PEER_GAMES, MIN_PEERS,
)

from .history_bridge import (
    VerifiedGameHistories, available_history_players, checked_pool, load_signed_manifest,
)
from .quote_bridge import record_quote_candidate
from .source_pipeline import (
    FUTURE_STATES, OFFICIAL, SOURCE_FREEZE_MINUTES, UTC, SourceBlocked,
    attempt, build_bundle, capture_two_rosters, clock, current_storage,
    digest, parse_roster, safe_relative, signed_schedule_game,
)


def discover_slate_roster_skaters(games, *, opener=urlopen):
    """Get official roster IDs for prewarming only, without source admission."""
    teams = sorted({game[side] for game in games for side in ("home_team", "away_team")})

    def roster(team):
        request = Request(f"{OFFICIAL}/roster/{team}/current",
                          headers={"User-Agent": "pickem-auditor-P2-source/1"})
        with opener(request, timeout=12) as response:
            members = parse_roster(json.loads(response.read()), team)
        return {pid for pid, member in members.items() if member["position_group"] in {"F", "D"}}

    with ThreadPoolExecutor(max_workers=8) as workers:
        return set().union(*workers.map(roster, teams))


@lru_cache(maxsize=40_000)
def _study_observation(pool, relative_path, sha256):
    # This cache serves player selection only. Content and signed raw sources
    # are re-read through the verifying history bridge before bundle admission.
    raw = safe_relative(pool, relative_path).read_bytes()
    if digest(raw) != sha256:
        raise SourceBlocked("P2_HISTORY_OBSERVATION_SHA_MISMATCH")
    observation = json.loads(raw)
    return (str(observation["player_id"]), str(observation["event_id"]),
            observation["position_group"], observation["source_game_log_row"]["gameDate"])


def _eligible_history(entries, *, pool, player_id, freeze, game):
    """Prepare history selection from hashed observations, then reverify C03 in P2."""
    start = clock(game["start_at"])
    observations = []
    if not isinstance(entries, list):
        raise SourceBlocked("P2_SIGNED_PLAYER_HISTORY_SCHEMA_INVALID")
    for entry in entries:
        receipt = entry["observation_receipt"]
        if clock(receipt["received_at"]) > freeze:
            continue
        signed_pid, event_id, group, game_date = _study_observation(
            pool, receipt["archive_path"], receipt["content_sha256"],
        )
        if signed_pid != player_id:
            raise SourceBlocked("P2_HISTORY_POSITION_OR_IDENTITY_MISMATCH")
        if event_id == game["event_id"] or game_date >= start.date().isoformat():
            continue
        observations.append((game_date, event_id, group, entry))

    observations.sort(key=lambda row: (row[0], row[1]))
    if len({row[1] for row in observations}) != len(observations):
        raise SourceBlocked("P2_DUPLICATE_HISTORICAL_PLAYER_GAME")
    groups = {row[2] for row in observations}
    if not observations:
        raise SourceBlocked("P2_ORIGINAL_SIGNED_PLAYER_HISTORY_MISSING")
    if len(groups) != 1 or not groups <= {"F", "D"}:
        raise SourceBlocked("P2_HISTORY_POSITION_OR_IDENTITY_MISMATCH")
    return observations[0][2], [row[3] for row in observations[-MAX_RATE_GAMES:]]


def _peer_ids(verified, *, player_id, position_group):
    """Choose a deterministic leave-one-out pool from eligible source IDs."""
    candidates = [pid for pid, (group, _) in verified.items()
                  if pid != player_id and group == position_group]
    candidates.sort(key=lambda pid: (-len(verified[pid][1]), pid))
    selected = []
    played = 0
    for pid in candidates:
        selected.append(pid)
        played += min(len(verified[pid][1]), MAX_PEER_RATE_GAMES)
        if len(selected) >= MIN_PEERS and played >= MIN_PEER_GAMES:
            break
    return selected


def _reason(exc):
    if isinstance(exc, (SourceBlocked, ValueError)):
        return str(exc)[:180]
    return type(exc).__name__


def capture_game_sources(root, *, game, freeze, signed_history_manifest_path,
                         signed_history_manifest_sha256, history_pool,
                         original_quote_by_player=None):
    """Capture one game's two official rosters and freeze every listed skater.

    The source owner supplies immutable signed history and may supply previously
    captured market offers. A quote reject is independent of SOG distribution
    eligibility. The freeze is a real UTC deadline and remains the same across
    all skaters in this game. No model or network market call is made here.
    """
    current_storage(root)
    records = []
    peer_attempt_hashes = []
    event_id = game["event_id"]
    freeze_at = clock(freeze)
    start = clock(game["start_at"])

    def finish(status, reasons=()):
        counts = dict(sorted(Counter(row["status"] for row in records).items()))
        receipt = attempt(
            root, "full_slate_game_sources", status, reasons,
            event_id=event_id, input_freeze_at=freeze, status_counts=counts,
            player_attempt_sha256s=[row["attempt_sha256"] for row in records],
            peer_attempt_sha256s=peer_attempt_hashes,
            history_manifest_sha256=signed_history_manifest_sha256,
        )["receipt"]
        return {"game": game, "status": status, "records": records,
                "reasons": list(reasons), "attempt_sha256": receipt["sha256"],
                "candidate_count": len(records), "status_counts": counts}

    if game["game_state"] not in FUTURE_STATES:
        return finish("BLOCKED_SOURCE", ("TARGET_NOT_PREGAME",))
    if not datetime.now(UTC) < freeze_at <= start - timedelta(minutes=SOURCE_FREEZE_MINUTES):
        return finish("MISSED_SOURCE_FREEZE_DEADLINE", ("SOURCE_FREEZE_WINDOW_CLOSED",))

    try:
        schedule = signed_schedule_game(root, game, day=game["scheduled_day"], freeze=freeze)
        rosters, members = capture_two_rosters(root, game, freeze=freeze)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return finish("BLOCKED_SOURCE", (_reason(exc),))

    indexed = {}
    failures = {}
    skaters = {pid: member for roster in members.values() for pid, member in roster.items()
               if member["position_group"] in {"F", "D"}}
    history_error = None
    try:
        pool = checked_pool(root, history_pool)
        history = load_signed_manifest(root, signed_history_manifest_path,
                                       signed_history_manifest_sha256)
        available = available_history_players(pool)
        if available is not None:
            history = {pid: history[pid] for pid in available if pid in history}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        history_error = _reason(exc)
        history = {}
    histories = (VerifiedGameHistories(root, pool, freeze=freeze, event_start=game["start_at"])
                 if history else None)
    for pid, entries in history.items():
        try:
            indexed[pid] = _eligible_history(entries, pool=pool, player_id=pid,
                                             freeze=freeze_at, game=game)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            failures[pid] = _reason(exc)

    # Confirm the selected peer pool once before constructing any player bundle.
    # Every original bundle and its independent forecast reader still reverify
    # the selected signed rows through their own admission path.
    screened = set()
    for pid, member in sorted(skaters.items()):
        group = member["position_group"]
        row = {"player_id": pid, "manifest_sha256": None,
               "quote_manifest_sha256": None, "quote_reasons": []}
        try:
            if datetime.now(UTC) >= freeze_at:
                raise SourceBlocked("SOURCE_FREEZE_WINDOW_CLOSED")
            if pid not in indexed:
                raise SourceBlocked(failures.get(pid, history_error or
                                                "P2_ORIGINAL_SIGNED_PLAYER_HISTORY_MISSING"))
            if indexed[pid][0] != group:
                raise SourceBlocked("P2_HISTORY_POSITION_OR_IDENTITY_MISMATCH")
            while True:
                peers = _peer_ids(indexed, player_id=pid, position_group=group)
                unchecked = set(peers).difference(screened)
                if not unchecked:
                    break
                for peer in sorted(unchecked):
                    try:
                        histories.verify(root, pool, indexed[peer][1], player_id=peer,
                                         group=group, freeze=freeze,
                                         event_start=game["start_at"])
                        screened.add(peer)
                    except (OSError, ValueError, KeyError, TypeError) as exc:
                        failures[peer] = _reason(exc)
                        del indexed[peer]
                        rejected = attempt(root, "full_slate_peer_source", "ABSTAIN",
                                           [failures[peer]], event_id=event_id,
                                           player_id=peer)["receipt"]
                        peer_attempt_hashes.append(rejected["sha256"])

            options = dict(
                game=game, schedule_source=schedule, rosters=rosters,
                roster_members=members, player_id=pid, history_entries=indexed[pid][1],
                peer_entries={peer: indexed[peer][1] for peer in peers},
                history_pool=pool, freeze=freeze, include_official_c03_receipts=True,
                _game_histories=histories,
            )
            result = build_bundle(root, **options)
            row.update(status=result["manifest"]["source_admission"],
                       manifest_sha256=result["receipt"]["sha256"], reasons=[])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            row.update(status="ABSTAIN_SOURCE_INVALID", reasons=[_reason(exc)])

        market = (original_quote_by_player or {}).get(pid)
        if market is not None and row["manifest_sha256"] is not None:
            try:
                team = member["team_id"]
                other = game["away_team"] if team == game["home_team"] else game["home_team"]
                checked = record_quote_candidate(
                    root, raw_ref=market["source"], offered=market["offer"],
                    player_id=pid, team=team, opponent=other, event_id=event_id,
                    start=game["start_at"], freeze=freeze,
                    official_profile_entry=indexed[pid][1][-1], history_pool=pool,
                )
                if checked["status"] == "VERIFIED":
                    evidence = checked["quote"]
                    quote_bundle = build_bundle(root, **options, quote=evidence["verified_quote"],
                                                quote_evidence=evidence)
                    row["quote_manifest_sha256"] = quote_bundle["receipt"]["sha256"]
                else:
                    row["quote_reasons"] = checked["attempt"]["reasons"]
            except (OSError, ValueError, KeyError, TypeError) as exc:
                row["quote_reasons"] = [_reason(exc)]

        receipt = attempt(
            root, "full_slate_player_sources", row["status"],
            row["reasons"] + row["quote_reasons"], event_id=event_id, player_id=pid,
            source_manifest_sha256=row["manifest_sha256"],
            quote_manifest_sha256=row["quote_manifest_sha256"],
        )["receipt"]
        row["attempt_sha256"] = receipt["sha256"]
        records.append(row)

    available = any(row["manifest_sha256"] is not None for row in records)
    return finish("SOURCE_READY" if available else "BLOCKED_SOURCE",
                  () if available else ("NO_VERIFIED_PLAYER_BUNDLES",))
