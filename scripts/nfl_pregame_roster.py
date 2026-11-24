"""Capture and independently replay the NFL game-active roster check.

This is an opt-in Phase 0R source check. It emits a sidecar for original
contracts and does not write forecast, settlement, or publication ledgers.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
from hashlib import sha256
import io
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from odds_providers import normalize_player, normalize_team
from phase0_input_capture import preserve, source_url, stamp, utc
from phase0_pre_eval import canonical_bytes
from pickem_math import snapshot_key

SCHEDULE = "https://github.com/nflverse/nfldata/raw/refs/heads/master/data/games.csv"
CROSSWALK = "https://github.com/nflverse/nflverse-data/releases/download/players/players.csv"
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"
GSIS = re.compile(r"00-\d{7}")
REQUIRED = ("schedule", "crosswalk", "roster")
MAX_BYTES = 16_000_000


def _now():
    return datetime.now(timezone.utc)


def _url(role, event_id):
    return {"schedule": SCHEDULE, "crosswalk": CROSSWALK,
            "roster": f"{SUMMARY}?event={event_id}"}[role]


def capture(root, event_id):
    """Timestamp completed reads and archive the original response bodies."""
    evidence = {"espn_event_id": event_id, "sources": {}}
    for role in REQUIRED:
        url = _url(role, event_id)
        entry = {"requested_url": url, "requested_at": stamp(_now())}
        try:
            with urlopen(Request(url, headers={"User-Agent": "pickem-auditor/1"}),
                         timeout=12) as response:
                raw = response.read(MAX_BYTES + 1)
                observed = _now()
            if len(raw) > MAX_BYTES:
                raise ValueError("source_too_large")
            entry["receipt"] = preserve(root, "NFL", role, raw, captured=observed,
                                        retrieved=observed, url=url)
        except (OSError, ValueError) as exc:
            entry.update(error=str(exc), failed_at=stamp(_now()))
        evidence["sources"][role] = entry
    return evidence


def _read_source(root, role, entry, event_id):
    receipt = entry.get("receipt")
    if not receipt:
        return None, None, f"NFL_{role.upper()}_SOURCE_MISSING"
    digest = receipt.get("content_sha256", "")
    url = _url(role, event_id)
    observed = utc(receipt.get("observed_at"))
    requested = utc(entry.get("requested_at"))
    if (not re.fullmatch(r"[a-f0-9]{64}", digest)
            or receipt.get("archive_path") != f"{role}/{digest}.bin"
            or receipt.get("source_id") != f"NFL_{role}_{digest[:24]}"
            or entry.get("requested_url") != url or receipt.get("source_url") != source_url(url)
            or receipt.get("status") != "verified" or requested is None
            or observed is None or utc(receipt.get("retrieved_at")) != observed
            or requested > observed):
        return None, None, f"NFL_{role.upper()}_RECEIPT_INVALID"
    try:
        raw = (root / receipt["archive_path"]).read_bytes()
        if sha256(raw).hexdigest() != digest:
            raise ValueError("receipt digest mismatch")
        value = json.loads(raw) if role == "roster" else list(
            csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        return value, observed, None
    except (OSError, UnicodeError, ValueError):
        return None, None, f"NFL_{role.upper()}_RECEIPT_BYTES_INVALID"


def _schedule_event(rows, event_id, contract):
    """Join on exact scheduled kickoff and oriented teams, with one row per ID."""
    start = utc(contract.get("event_start"))
    games = [r for r in rows if r.get("espn") == event_id]
    if len(games) != 1:
        return None, "NFL_EVENT_ID_AMBIGUOUS" if games else "NFL_EVENT_ID_UNMAPPED"
    game = games[0]
    try:
        kickoff = datetime.fromisoformat(f"{game['gameday']}T{game['gametime']}").replace(
            tzinfo=ZoneInfo("America/Toronto"))
    except (KeyError, ValueError):
        return None, "NFL_EVENT_ID_CONFLICT"
    candidates = [r for r in rows if all(r.get(k) == game.get(k) for k in
                                        ("gameday", "gametime", "away_team", "home_team"))]
    if len(candidates) != 1:
        return None, "NFL_EVENT_ID_AMBIGUOUS"
    if (kickoff != start or contract.get("game_date") != game.get("gameday")
            or game.get("game_type") != "REG"
            or (game.get("away_team"), game.get("home_team")) !=
            (contract.get("away_team"), contract.get("home_team"))
            or {contract.get("team"), contract.get("opponent")} !=
            {game.get("away_team"), game.get("home_team")}
            or not str(game.get("gsis", "")).isdigit()):
        return None, "NFL_EVENT_ID_CONFLICT"
    if contract.get("event_id_namespace") == "espn":
        if str(contract.get("event_id")) != event_id:
            return None, "NFL_EVENT_ID_CONFLICT"
    elif contract.get("event_id_namespace") != "propline" or not str(
            contract.get("event_id", "")).isdigit():
        return None, "NFL_EVENT_ID_UNMAPPED"
    return game, None


def _espn_nfl_team(value):
    code = normalize_team(value)
    return {"WSH": "WAS"}.get(code, code)


def _rosters(payload, event_id, contract):
    """Require explicit binary statuses and a full game-specific list for both clubs."""
    header = payload.get("header") if isinstance(payload, dict) else None
    header = header if isinstance(header, dict) else {}
    comps = header.get("competitions") or []
    if not isinstance(comps, list) or len(comps) != 1 or not isinstance(comps[0], dict):
        return {}, "NFL_ROSTER_EVENT_UNVERIFIED"
    comp = comps[0]
    try:
        clubs = {r["homeAway"]: _espn_nfl_team(r["team"]["abbreviation"])
                 for r in comp["competitors"]}
        kind = comp["status"]["type"]
        if (str(header.get("id")) != event_id or str(comp.get("id")) != event_id
                or len(comp["competitors"]) != 2
                or clubs != {"away": contract.get("away_team"), "home": contract.get("home_team")}
                or utc(comp.get("date")) != utc(contract.get("event_start"))):
            return {}, "NFL_ROSTER_EVENT_CONFLICT"
        if kind.get("state") != "pre" or kind.get("completed") is not False:
            return {}, "NFL_ROSTER_NOT_PREGAME"
    except (KeyError, TypeError, AttributeError):
        return {}, "NFL_ROSTER_EVENT_UNVERIFIED"
    rosters = {}
    ids = set()
    try:
        for group in payload.get("rosters") or []:
            team = _espn_nfl_team(group["team"]["abbreviation"])
            if team not in clubs.values() or team in rosters:
                return {}, "NFL_ROSTER_TEAM_CONFLICT"
            team_players = group["roster"]
            active = 0
            for player in team_players:
                athlete = player["athlete"]
                ident = str(athlete["id"])
                if (not ident.isdigit() or ident in ids or not normalize_player(athlete["displayName"])
                        or not isinstance(player.get("active"), bool)):
                    return {}, "NFL_ROSTER_PLAYER_STATUS_INCOMPLETE_OR_DUPLICATE"
                ids.add(ident)
                active += player["active"]
            if not 46 <= active <= 48:
                return {}, "NFL_GAME_ACTIVE_ROSTER_MANIFEST_MISSING"
            rosters[team] = team_players
    except (KeyError, TypeError, AttributeError, ValueError):
        return {}, "NFL_GAME_ACTIVE_ROSTER_MANIFEST_MISSING"
    if set(rosters) != set(clubs.values()):
        return {}, "NFL_GAME_ACTIVE_ROSTER_MANIFEST_MISSING"
    return rosters, None


def _crosswalk(rows):
    by_gsis, by_espn = defaultdict(set), defaultdict(set)
    names = defaultdict(set)
    for row in rows:
        gsis, espn = row.get("gsis_id") or "", row.get("espn_id") or ""
        if GSIS.fullmatch(gsis) and espn.isdigit():
            by_gsis[gsis].add(espn)
            by_espn[espn].add(gsis)
            names[(gsis, espn)].add(normalize_player(row.get("display_name")))
    return by_gsis, by_espn, names


def _identity(contract, crosswalk, roster):
    gsis = contract.get("player_id")
    by_gsis, by_espn, names = crosswalk
    ids = by_gsis.get(gsis, set())
    if not ids:
        return None, "NFL_ESPN_GSIS_ID_MAP_MISSING"
    if len(ids) != 1:
        return None, "NFL_PLAYER_ID_AMBIGUOUS"
    espn = next(iter(ids))
    name = normalize_player(contract.get("player"))
    if by_espn[espn] != {gsis}:
        return None, "NFL_PLAYER_ID_AMBIGUOUS"
    if not name or names[(gsis, espn)] != {name} or str(
            contract.get("espn_player_id") or espn) != espn:
        return None, "NFL_PLAYER_ID_CONFLICT"
    if roster:
        club = roster[contract["team"]]
        matches = [p for p in club if str(p["athlete"]["id"]) == espn]
        same_name = [p for p in club if normalize_player(p["athlete"]["displayName"]) == name]
        if len(same_name) > 1:
            return None, "NFL_PLAYER_ID_AMBIGUOUS"
        if matches != same_name or (not matches and any(
                str(p["athlete"]["id"]) == espn
                for players in roster.values() for p in players)):
            return None, "NFL_PLAYER_ID_CONFLICT"
        if not matches:
            return espn, "NFL_PLAYER_ROSTER_STATUS_MISSING"
        if not matches[0]["active"]:
            return espn, "NFL_PLAYER_INACTIVE"
    return espn, None


def audit(contracts, evidence, root):
    """Replay hashes and identities and retain simultaneous rejection reasons."""
    event_id = evidence["espn_event_id"]
    sources = evidence["sources"]
    records = {role: _read_source(root, role, sources.get(role, {}), event_id)
               for role in REQUIRED}
    schedule, crosswalk, payload = (records[role][0] for role in REQUIRED)
    crosswalk = _crosswalk(crosswalk) if crosswalk is not None else None
    rows = []
    for contract in contracts:
        reasons = [problem for _, _, problem in records.values() if problem]
        start = utc(contract.get("event_start"))
        forecast = utc(contract.get("forecast_at"))
        freeze = utc(contract.get("input_freeze_at"))
        decision = utc(contract.get("decision_cutoff_at"))
        if (not start or not forecast or forecast >= start or (freeze and freeze > forecast)
                or any(contract.get(k) is not None and v is None
                       for k, v in (("input_freeze_at", freeze), ("decision_cutoff_at", decision)))):
            reasons.append("NFL_ROSTER_CUTOFF_INVALID")
        if freeze is None:
            reasons.append("NFL_ORIGINAL_INPUT_FREEZE_MISSING")
        if start and forecast:
            cutoff = min(t for t in (start, forecast, freeze, decision) if t is not None)
            for role, (_, observed, _) in records.items():
                if observed and (observed > cutoff or observed >= start):
                    reasons.append(f"NFL_{role.upper()}_POSSESSED_AFTER_CUTOFF")
        game, roster, player = None, {}, None
        if schedule is not None:
            game, reason = _schedule_event(schedule, event_id, contract)
            if reason:
                reasons.append(reason)
        if payload is not None:
            roster, reason = _rosters(payload, event_id, contract)
            if reason:
                reasons.append(reason)
        else:
            reasons.append("NFL_GAME_ACTIVE_ROSTER_MANIFEST_MISSING")
        if crosswalk is not None:
            player, reason = _identity(contract, crosswalk, roster if game else {})
            if reason:
                reasons.append(reason)
        rows.append({
            "forecast_id": contract.get("forecast_id"), "contract_id": contract.get("contract_id"),
            "legacy_snapshot_key": snapshot_key(contract), "candidate_id": (contract.get("inputs") or {}).get("id"),
            "provider_event_id": contract.get("event_id"), "event_id_namespace": contract.get("event_id_namespace"),
            "espn_event_id": event_id if game else None, "nfl_gsis_game_id": game["gsis"] if game else None,
            "gsis_player_id": contract.get("player_id"), "espn_player_id": player,
            "team": contract.get("team"), "line": contract.get("reference_line"),
            "forecast_at": contract.get("forecast_at"),
            "input_freeze_at": contract.get("input_freeze_at"),
            "roster_verified": not reasons,
            "integrity_certified_in_original": contract.get("phase0r_original_source_certified") is True,
            "settled_in_original": contract.get("actual_stat") is not None,
            "rejection_reasons": sorted(set(reasons)),
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path, help="Original live-pool JSON.gz")
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--provider-event", required=True)
    parser.add_argument("--espn-event", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--replay", type=Path, help="Previously captured, independently pinned report")
    parser.add_argument("--replay-sha256", help="Expected SHA-256 of the report used for replay")
    args = parser.parse_args()
    raw = args.archive.read_bytes()
    if sha256(raw).hexdigest() != args.archive_sha256 or not args.espn_event.isdigit():
        parser.error("archive hash mismatch or invalid ESPN event ID")
    original = json.loads(gzip.decompress(raw))
    contracts = [r for r in original["forecasts"] if r.get("sport") == "NFL"
                 and str(r.get("event_id")) == args.provider_event]
    if not contracts or len({snapshot_key(r) for r in contracts}) != len(contracts):
        parser.error("cohort missing or duplicate legacy keys")
    if args.replay:
        manifest = args.replay.read_bytes()
        if sha256(manifest).hexdigest() != args.replay_sha256:
            parser.error("replay receipt SHA-256 mismatch")
        prior = json.loads(manifest)
        if prior["archive_sha256"] != args.archive_sha256:
            parser.error("replay refers to a different original archive")
        source_root = args.replay.parent
        evidence = prior["evidence"]
    else:
        args.out.mkdir(parents=True, exist_ok=True)
        source_root = args.out
        evidence = capture(source_root, args.espn_event)
    if evidence["espn_event_id"] != args.espn_event:
        parser.error("replay refers to a different ESPN event")
    rows = audit(contracts, evidence, source_root)
    report = {
        "archive_sha256": args.archive_sha256, "evidence": evidence, "rows": rows,
        "archived": len(rows),
        "frozen_predictions": len(rows) if original.get("predictions_are_frozen") is True else 0,
        "roster_verified": sum(r["roster_verified"] for r in rows),
        "integrity_certified": sum(r["integrity_certified_in_original"] for r in rows),
        "settled": sum(r["settled_in_original"] for r in rows),
        "unresolved_settlement": sum(not r["settled_in_original"] for r in rows),
        "rejection_counts": Counter(reason for row in rows for reason in row["rejection_reasons"]),
    }
    raw = canonical_bytes(report)
    digest = sha256(raw).hexdigest()
    if args.replay:
        if raw != manifest:
            parser.error("replayed report differs from original")
    else:
        with (args.out / f"{digest}.json").open("xb") as handle:
            handle.write(raw)
    print(digest, json.dumps({k: v for k, v in report.items() if k not in ("rows", "evidence")}))


if __name__ == "__main__":
    main()
