"""NFL Sunday WS1: immutable original-offer universe and fail-closed source contract.

Research only. Never publishes predictions, recalibrates the 60/40 ensemble or
treats collector possession as proof of upstream publication.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import math
import re
import unicodedata

VERSION = "nfl_20261115_source_control_v1"
DAY = "2026-11-15"
TZ = ZoneInfo("America/Toronto")
# Locked independently against the NFL 2026 Week 10 schedule.
FIXTURES = (
    ("NE", "DET", "09:30"), ("KC", "ATL", "13:00"),
    ("HOU", "CLE", "13:00"), ("MIN", "GB", "13:00"),
    ("MIA", "IND", "13:00"), ("CAR", "NO", "13:00"),
    ("BUF", "NYJ", "13:00"), ("JAX", "TEN", "13:00"),
    ("LAR", "ARI", "16:05"), ("SEA", "LV", "16:05"),
    ("SF", "DAL", "16:25"), ("PIT", "CIN", "20:20"),
)
SUPPORTED = frozenset((
    "receptions", "receiving yards", "rushing yards", "passing yards",
    "pass attempts", "completions", "rush attempts", "tackles + assists",
))
SHADOW_ONLY = frozenset((
    "passing touchdowns", "rushing touchdowns", "receiving touchdowns",
    "offensive touchdowns", "anytime touchdown", "targets",
    "solo tackles", "tackle assists",
))
QB_STATS = frozenset((
    "pass attempts", "completions", "passing yards", "passing touchdowns",
    "rush attempts", "rushing yards", "rushing touchdowns",
))
QB_ONLY_STATS = frozenset((
    "pass attempts", "completions", "passing yards", "passing touchdowns",
))
LEGACY_MODELS = (
    "Engine_A", "Engine_B", "Bayesian_A", "Bayesian_B",
    "NUTS_strict", "Consensus_60_40", "Market",
)
TACKLE_FIELDS = (
    "def_tackles_solo", "def_tackles_with_assist", "def_tackle_assists",
)

def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")

def digest(obj):
    return sha256(canonical(obj)).hexdigest()

def instant(value, label="time"):
    if not isinstance(value, str):
        raise ValueError(label + ":missing")
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError(label + ":invalid") from e
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError(label + ":naive")
    return d.astimezone(timezone.utc)

def utc(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def expected_events():
    return [{
        "away": away, "home": home,
        "scheduled_kickoff": utc(datetime.fromisoformat(
            DAY + "T" + hhmm + ":00").replace(tzinfo=TZ)),
        "fixture_key": "|".join((DAY, away, home)),
    } for away, home, hhmm in FIXTURES]

def _name(value):
    raw = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return re.sub(r"[^a-z0-9]", "", raw.encode("ascii", "ignore").decode())

def roster_index(rosters):
    """Only independently source-bound records; no unknown identity fallback."""
    out = defaultdict(list)
    for team, packet in rosters.items():
        for athlete in packet.get("athletes", []):
            if not isinstance(athlete, dict):
                continue
            player = athlete.get("fullName") or athlete.get("displayName")
            pid = athlete.get("id")
            if player and pid and packet.get("receipt_sha256"):
                out[(team, _name(player))].append({
                    "espn_player_id": str(pid),
                    "name": player,
                    "position": str((athlete.get("position") or {}).get("abbreviation")
                                    or athlete.get("position_abbrev") or "").upper(),
                    "roster_status": athlete.get("status"),
                    "roster_receipt_sha256": packet["receipt_sha256"],
                })
    return out

def _validate_receipt(record, freeze, event_start):
    if not isinstance(record, dict):
        return "SOURCE_RECEIPT_MISSING"
    sha = record.get("sha256")
    if not isinstance(sha, str) or not re.fullmatch("[a-f0-9]{64}", sha):
        return "SOURCE_HASH_MISSING"
    try:
        received = instant(record.get("source_received_at"), "source_received_at")
        frozen = instant(freeze, "input_freeze_at")
        kickoff = instant(event_start, "event_start_at")
    except ValueError:
        return "INVALID_SOURCE_TIMESTAMP"
    if received > frozen:
        return "SOURCE_AFTER_FREEZE"
    if frozen >= kickoff:
        return "EVENT_STARTED"
    if record.get("source_bytes_verified") is not True:
        return "SOURCE_BYTES_UNVERIFIED"
    return None

def validate_frozen_forecast(row):
    """A predicted probability is certified only with complete separate model lineage."""
    required = ("candidate_id", "event_id", "player_id", "stat", "period",
                "line", "quote_id", "source_sha256", "model_training_cutoff_at",
                "input_freeze_at", "forecast_at", "event_start_at")
    missing = [k for k in required if row.get(k) is None]
    if missing:
        return False, "MISSING_FORECAST_FIELDS:" + ",".join(missing)
    try:
        cutoff = instant(row["model_training_cutoff_at"])
        freeze = instant(row["input_freeze_at"])
        forecast = instant(row["forecast_at"])
        start = instant(row["event_start_at"])
        received = instant(row.get("source_received_at"))
    except ValueError as e:
        return False, "INVALID_FORECAST_TIMESTAMP:" + str(e)
    if not received <= freeze <= forecast < start:
        return False, "INVALID_SOURCE_FREEZE_FORECAST_ORDER"
    if cutoff > freeze:
        return False, "POST_FREEZE_TRAINING_CUTOFF"
    if not re.fullmatch("[a-f0-9]{64}", str(row["source_sha256"])):
        return False, "SOURCE_SHA_INVALID"
    return True, "CHRONOLOGY_OK"

def tackle_total(source):
    """All three distinct NFL defensive tackle credits are required."""
    values = []
    for key in TACKLE_FIELDS:
        value = source.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if not math.isfinite(value) or not float(value).is_integer():
            return None
        if value < 0 or value > 200:
            return None
        values.append(int(value))
    total = sum(values)
    return total if total <= 200 else None

def frozen_control():
    return {model: {"probability": None, "status": "NOT_ORIGINALLY_FROZEN"}
            for model in LEGACY_MODELS}

def normalize_roster_status(status):
    if isinstance(status, dict):
        status = status.get("type") or status.get("name") or status.get("description")
    return str(status or "").strip().lower()

def eligibility(player, stat, qb1=None, injury_status=None):
    """Conservative participation label, not a guessed injury probability."""
    if player is None:
        return "IDENTITY_UNVERIFIABLE", None, "PLAYER_ID_UNVERIFIED"
    injury = normalize_roster_status(injury_status)
    roster = normalize_roster_status(player.get("roster_status"))
    if injury in ("out", "inactive", "injured reserve", "ir") or roster in ("inactive", "injured reserve", "injured-reserve", "suspended", "practice-squad"):
        return "VERIFIED_OUT", 1.0, "PREGAME_OUT_SOURCE"
    if stat in QB_STATS and player.get("position") == "QB":
        if qb1 is None or qb1.get("espn_player_id") is None:
            return "STARTER_UNVERIFIABLE", None, "INDEPENDENT_QB1_UNAVAILABLE"
        if str(qb1["espn_player_id"]) != str(player["espn_player_id"]):
            return "BACKUP_INELIGIBLE", 1.0, "DEPTH_CHART_NOT_QB1"
        if injury in ("questionable", "doubtful"):
            return "UNCERTAIN_PARTICIPATION", None, "QB1_INJURY_UNCERTAINTY"
        return "EXPECTED_STARTER_SOURCE_BACKED", None, "QB1_DEPTH_CHART_NOT_FINAL_ACTIVE"
    if injury in ("questionable", "doubtful"):
        return "UNCERTAIN_PARTICIPATION", None, "INJURY_RISK_NOT_QUANTIFIED"
    return "ROSTER_MEMBER_GAME_ACTIVE_UNCONFIRMED", None, "NO_PREGAME_INACTIVE_CONFIRMATION"

def build_universe(*, events, quotes, quote_receipts, rosters,
                   depth_qbs, injuries, nfl_rows, freeze_at, code_sha,
                   original_offer_source="propline"):
    """One immutable candidate per exact original book, line and two-sided price."""
    instant(freeze_at)
    event_by_pair = {}
    for event in events:
        for a, b in ((event["away"], event["home"]), (event["home"], event["away"])):
            event_by_pair[(a, b)] = event
    roster = roster_index(rosters)
    stats_by_key = defaultdict(list)
    for x in nfl_rows:
        stats_by_key[(str(x.get("team") or ""), _name(x.get("player")))].append(x)
    rows, rejected, collisions = [], [], set()
    seen = {}
    for quote in quotes:
        raw = dict(quote)
        reason = None
        if raw.get("sport") != "NFL":
            reason = "NOT_NFL"
        team, opponent = str(raw.get("team") or ""), str(raw.get("opponent") or "")
        raw_teams = raw.get("event_teams")
        pair = [str(t) for t in raw_teams] if isinstance(raw_teams, list) else []
        if len(pair) != 2 or len(set(pair)) != 2:
            reason = reason or "PROVIDER_EVENT_TEAM_PAIR_UNVERIFIABLE"
        elif team and team not in pair:
            reason = reason or "PROVIDER_TEAM_EVENT_PAIR_CONFLICT"
        elif not team:
            # PropLine's paired O/U outcomes often omit team entirely. Resolve
            # only when exactly one of the *two original event teams* contains
            # the uniquely ID'd player in independently captured ESPN rosters.
            supported = [t for t in pair if len(roster.get((t, _name(raw.get("player"))), [])) == 1]
            ambiguous = [t for t in pair if len(roster.get((t, _name(raw.get("player"))), [])) > 1]
            if len(supported) == 1 and not ambiguous:
                team = supported[0]
                opponent = next(t for t in pair if t != team)
            else:
                reason = reason or "CROSS_TEAM_ROSTER_IDENTITY_UNVERIFIABLE"
        if not opponent and team in pair and len(pair) == 2:
            opponent = next(t for t in pair if t != team)
        if opponent and pair and opponent not in pair:
            reason = reason or "PROVIDER_OPPONENT_EVENT_PAIR_CONFLICT"
        event = event_by_pair.get((team, opponent))
        if event is None:
            reason = reason or "EVENT_IDENTITY_UNVERIFIABLE"
        elif not event.get("schedule_verified") or not event.get("espn_event_id"):
            reason = reason or "SCHEDULE_SOURCE_UNVERIFIED"
        elif raw.get("event_start") and instant(raw["event_start"]) != instant(event["scheduled_kickoff"]):
            reason = reason or "EVENT_KICKOFF_CONFLICT"
        stat = str(raw.get("stat") or "")
        if stat not in SUPPORTED:
            reason = reason or "MARKET_UNSUPPORTED_BY_SOURCE_CONTRACT"
        if (raw.get("line") is None or isinstance(raw.get("line"), bool)
                or not isinstance(raw.get("line"), (int, float))
                or not math.isfinite(raw.get("line")) or raw.get("line") < 0):
            reason = reason or "LINE_INVALID"
        if any(raw.get(k) is None for k in ("book", "over_odds", "under_odds", "event_id")):
            reason = reason or "QUOTE_IDENTITY_OR_PRICES_MISSING"
        if not all(isinstance(raw.get(k), (int, float)) and not isinstance(raw.get(k), bool)
                   and math.isfinite(raw[k]) for k in ("over_odds", "under_odds")):
            reason = reason or "INVALID_QUOTE_ODDS"
        # A single original bulk provider response is the root for all quotes.
        receipt = quote_receipts.get(original_offer_source)
        problem = (_validate_receipt(receipt, freeze_at, event["scheduled_kickoff"])
                   if event else "EVENT_UNAVAILABLE")
        reason = reason or problem
        if not raw.get("event_id"):
            reason = reason or "PROVIDER_EVENT_ID_MISSING"
        key = (raw.get("event_id"), team, _name(raw.get("player")),
               stat, raw.get("book"), raw.get("line"))
        terms = (raw.get("over_odds"), raw.get("under_odds"))
        if key in seen:
            reason = reason or ("DUPLICATE_QUOTE" if seen[key] == terms
                                else "CONFLICTING_DUPLICATE_QUOTE")
            collisions.add(key)
        else:
            seen[key] = terms
        players = roster.get((team, _name(raw.get("player"))), [])
        if len(players) != 1:
            player = None
            reason = reason or "PLAYER_ROSTER_IDENTITY_UNVERIFIABLE"
        else:
            player = players[0]
        qbid = depth_qbs.get(team)
        inj = injuries.get(team, {}).get(str(player.get("espn_player_id"))) if player else None
        elig, participation_risk, elig_reason = eligibility(player, stat, qbid, inj)
        if stat in QB_ONLY_STATS and player is not None and player.get("position") != "QB":
            reason = reason or "PASSING_STAT_ON_NONQB_IDENTITY"
        hist = stats_by_key.get((team, _name(raw.get("player"))), [])
        hist_match = hist[0] if len(hist) == 1 else None
        if hist_match and hist_match.get("stat") != stat:
            stat_match = [h for h in hist if h.get("stat") == stat]
            hist_match = stat_match[0] if len(stat_match) == 1 else None
        identity = {
            "provider_event_id": str(raw.get("event_id") or ""),
            "event_id": event.get("espn_event_id") if event else None,
            "event_id_namespace": "espn",
            "player_id": player.get("espn_player_id") if player else None,
            "player_id_namespace": "espn",
            "nflverse_player_id": hist_match.get("player_id") if hist_match else None,
            "book": raw.get("book"), "stat": stat, "period": "full_game",
            "line": raw.get("line"), "over_odds": raw.get("over_odds"),
            "under_odds": raw.get("under_odds"), "team": team,
            "opponent": opponent,
        }
        quote_id = digest({"identity": identity, "quote_source_sha256":
                           receipt.get("sha256") if receipt else None})
        candidate_id = digest({"quote_id": quote_id,
                               "event": identity["event_id"],
                               "player": identity["player_id"]})
        shadow_eligible = (
            reason is None and elig in (
                "EXPECTED_STARTER_SOURCE_BACKED",
                "ROSTER_MEMBER_GAME_ACTIVE_UNCONFIRMED",
            )
        )
        row = {
            "schema": VERSION, "candidate_id": candidate_id, "quote_id": quote_id,
            **identity,
            "sport": "NFL", "date": DAY,
            "scheduled_kickoff": event.get("scheduled_kickoff") if event else None,
            "event_start_at": event.get("scheduled_kickoff") if event else None,
            "player": raw.get("player"), "position": player.get("position") if player else None,
            "team_identity_basis": ("independent_unique_espn_roster_on_provider_event_pair"
                                    if not raw.get("team") and team else "provider_explicit_team"),
            "original_quote": raw,
            "source_sha256": receipt.get("sha256") if receipt else None,
            "source_received_at": receipt.get("source_received_at") if receipt else None,
            "source_archive_path": receipt.get("archive_path") if receipt else None,
            "source_publication_at": None,
            "source_publication_truth_verified": False,
            "original_quote_reported_at": raw.get("retrieved_at"),
            "original_quote_reported_time_semantics": "provider_or_collector_fallback_unverified",
            "roster_receipt_sha256": player.get("roster_receipt_sha256") if player else None,
            "player_historical_stat_cutoff_at": None,
            "model_training_cutoff_at": None,
            "input_freeze_at": freeze_at,
            "forecast_at": None,
            "eligibility_status": elig,
            "participation_risk_probability": participation_risk,
            "eligibility_reason": elig_reason,
            "source_validation_failure": reason,
            "source_certified": reason is None,
            "availability_certified": False,
            "c03_strict_source_applied": False,
            "forecast_eligible": False,
            "research_shadow_eligible": shadow_eligible,
            "research_shadow_status": ("SOURCE_BOUND_ROLE_CONDITIONAL_UNCERTIFIED"
                                       if shadow_eligible else "RESEARCH_SHADOW_ABSTAIN"),
            "forecast_eligibility_reason": reason or elig_reason or "MODEL_AND_TRAINING_CUTOFF_NOT_FROZEN",
            "research_only": True,
            "production_ranking_allowed": False,
            "settlement_semantics": ("THREE_COMPONENT_SOURCE_DEFINED_BOOK_RULES_UNVERIFIED"
                                     if stat == "tackles + assists"
                                     else "PRODUCT_SPECIFIC_RULES_UNVERIFIED"),
            "frozen_control": frozen_control(),
            "code_commit_sha": code_sha,
        }
        rows.append(row)
        if reason:
            rejected.append({"quote_id": quote_id, "candidate_id": candidate_id,
                             "reason": reason})
    # Any conflict poisons all copies of the same quote key.
    if collisions:
        for row in rows:
            q = row["original_quote"]
            key = (q.get("event_id"), str(q.get("team") or ""),
                   _name(q.get("player")), str(q.get("stat") or ""),
                   q.get("book"), q.get("line"))
            if key in collisions:
                row["source_certified"] = False
                row["research_shadow_eligible"] = False
                row["research_shadow_status"] = "RESEARCH_SHADOW_ABSTAIN"
                row["source_validation_failure"] = "QUOTE_IDENTITY_COLLISION"
                row["forecast_eligibility_reason"] = "QUOTE_IDENTITY_COLLISION"
        rejected = [{"quote_id": r["quote_id"], "candidate_id": r["candidate_id"],
                     "reason": r["source_validation_failure"]}
                    for r in rows if r["source_validation_failure"]]
    ids = [r["candidate_id"] for r in rows]
    counts = Counter((r["stat"] for r in rows))
    failures = Counter(r["source_validation_failure"] for r in rows
                       if r["source_validation_failure"])
    return {
        "schema": VERSION, "date": DAY, "timezone": "America/Toronto",
        "code_sha": code_sha, "input_freeze_at": freeze_at,
        "scope": "complete original provider quotes, all lines, both sides paired",
        "sources": quote_receipts,
        "events": events,
        "quote_observations": len(quotes),
        "unique_candidate_ids": len(set(ids)),
        "attempted_contracts": len(rows),
        "source_certified_quotes": sum(r["source_certified"] for r in rows),
        "research_shadow_eligible_quotes": sum(r["research_shadow_eligible"] for r in rows),
        "forecast_eligible_contracts": sum(r["forecast_eligible"] for r in rows),
        "market_coverage": dict(sorted(counts.items())),
        "failures": dict(sorted(failures.items())),
        "rejections": rejected,
        "candidates": rows,
        "handoff": {
            "schema": VERSION, "source_control_immutable": True,
            "parallel_workstreams": ["simple_models", "opportunity_models", "joint_models"],
            "identity_fields": ["candidate_id", "event_id", "player_id", "stat",
                                "period", "line", "quote_id", "source_sha256"],
            "no_original_source_recapture": True,
            "no_production_promotion": True,
        },
    }

def write_immutable(path, payload):
    path = Path(path)
    body = canonical(payload) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(body)
    except FileExistsError:
        if path.read_bytes() != body:
            raise ValueError("IMMUTABLE_TARGET_ALREADY_DIFFERS")
    if path.read_bytes() != body:
        raise ValueError("IMMUTABLE_TARGET_MUTATED")
    return sha256(body).hexdigest()

def freeze_manifest(root, universe):
    body_sha = digest(universe)
    target = Path(root) / "source_control" / "captures" / (body_sha + ".json")
    file_sha = write_immutable(target, universe)
    return {"path": str(target), "file_sha256": file_sha,
            "canonical_sha256": body_sha, "schema": VERSION}
