#!/usr/bin/env python3
"""Research packet schema, validation, and merge into pipeline batch input."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

FRESHNESS_MINUTES = 60
MAX_QUOTE_WORDS = 25

CONFIDENCE_LEVELS = frozenset({"confirmed", "reported", "inferred"})
AVAILABILITY_STATUS = frozenset({"out", "doubtful", "questionable", "active"})
PRIMARY_SOURCE_KIND = frozenset({"league", "team", "beat"})
MECHANISM_TYPES = frozenset({"workload", "scheme", "role", "weather", "pace"})
PRECIP_INTENSITY = frozenset({"none", "light", "moderate", "heavy"})

LINEUP_FIELDS = ("projected_lines", "pairs", "pp1", "goalie_confirmed")
WEATHER_FIELDS = (
    "sustained_wind_mph",
    "gust_mph",
    "precip_prob",
    "precip_intensity",
    "window",
    "indoor",
)
OPTIONAL_WEATHER_FIELDS = ("snow",)
ENVIRONMENT_FIELDS = ("spread", "total", "back_to_back", "rest_days")
OPTIONAL_ENVIRONMENT_FIELDS = (
    "spread_home",
    "spread_away",
    "third_in_four",
    "away_back_to_back",
    "away_rest_days",
    "away_third_in_four",
)
AVAILABILITY_FIELDS = ("status", "primary_source")

# Host patterns for primary-source confirmation on role changes.
PRIMARY_DOMAIN_PATTERNS = (
    # NHL's official modern stats API is nhle.com, not nhl.com.
    re.compile(r"^api-web\.nhle\.com$", re.I),
    re.compile(r"(^|\.)nba\.com$", re.I),
    re.compile(r"(^|\.)nhl\.com$", re.I),
    re.compile(r"(^|\.)nfl\.com$", re.I),
    re.compile(r"(^|\.)espn\.com$", re.I),
    re.compile(r"^site\.api\.espn\.com$", re.I),
    re.compile(r"(^|\.)weather\.gov$", re.I),
    re.compile(r"(^|\.)nws\.noaa\.gov$", re.I),
)

TEAM_DOMAIN_HINT = re.compile(
    r"(^|\.)((?:[a-z0-9-]+\.)?(?:nba|nhl|nfl)\.com|"
    r"celtics|lakers|warriors|knicks|nets|heat|bulls|bucks|raptors|"
    r"bruins|rangers|mapleleafs|canadiens|oilers|flames|"
    r"patriots|chiefs|eagles|cowboys|packers|49ers|steelers)\.",
    re.I,
)


class PacketError(ValueError):
    pass


def _parse_time(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise PacketError("retrieved_at must be a non-empty string")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise PacketError(f"retrieved_at is not ISO-8601: {value}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _domain(url: str) -> str:
    parsed = urlparse(url.strip())
    host = (parsed.netloc or parsed.path.split("/")[0]).lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _underdog_url(url: str) -> bool:
    return "underdog" in _domain(url)


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def _is_fact(value: Any) -> bool:
    return isinstance(value, dict) and "fact" in value and "value" in value


def _coerce_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("yes", "true", "1"):
            return True
        if low in ("no", "false", "0"):
            return False
    return None


def _coerce_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _is_primary_domain(url: str, source_kind: str | None = None) -> bool:
    host = _domain(url)
    if any(pat.search(host) for pat in PRIMARY_DOMAIN_PATTERNS):
        return True
    if source_kind == "league":
        return any(
            host == suffix or host.endswith("." + suffix)
            for suffix in ("nba.com", "nhl.com", "nfl.com", "mlb.com")
        )
    if source_kind == "team" and TEAM_DOMAIN_HINT.search(host + "."):
        return True
    return False


@dataclass
class ValidationIssue:
    path: str
    message: str


@dataclass
class ValidatedFact:
    path: str
    value: Any
    source_url: str
    retrieved_at: datetime
    confidence: str
    primary_source_kind: str | None = None


@dataclass
class ValidatedPacket:
    raw: dict
    facts: dict[str, ValidatedFact] = field(default_factory=dict)
    mechanisms: dict[str, list[dict]] = field(default_factory=dict)
    role_changes: dict[str, dict] = field(default_factory=dict)
    index: dict[str, Any] = field(default_factory=dict)


def _validate_fact(
    path: str,
    fact: Any,
    issues: list[ValidationIssue],
    *,
    require_fresh: bool,
    now: datetime,
) -> ValidatedFact | None:
    if fact is None:
        return None
    if not _is_fact(fact):
        issues.append(ValidationIssue(path, "expected a fact object or null"))
        return None
    quote = fact.get("quote", "")
    if quote is not None and _word_count(str(quote)) > MAX_QUOTE_WORDS:
        issues.append(ValidationIssue(path, f"quote exceeds {MAX_QUOTE_WORDS} words"))
    conf = fact.get("confidence")
    if conf not in CONFIDENCE_LEVELS:
        issues.append(ValidationIssue(path, f"confidence must be one of {sorted(CONFIDENCE_LEVELS)}"))
    url = fact.get("source_url")
    if not isinstance(url, str) or not url.strip():
        issues.append(ValidationIssue(path, "missing or empty source_url"))
        url = ""
    else:
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "").lower()
        try:
            address = ipaddress.ip_address(host)
            private_host = not address.is_global
        except ValueError:
            private_host = False
        if (parsed.scheme not in ("https", "http") or not host
                or "." not in host or host == "localhost" or private_host
                or parsed.username is not None or parsed.password is not None):
            issues.append(ValidationIssue(path, "source_url must be an absolute public HTTP(S) URL"))
        elif _underdog_url(url):
            issues.append(ValidationIssue(path, "source_url domain may not contain underdog"))
    retrieved_raw = fact.get("retrieved_at")
    retrieved: datetime | None = None
    try:
        if retrieved_raw is None:
            raise PacketError("missing")
        retrieved = _parse_time(str(retrieved_raw))
    except PacketError:
        issues.append(ValidationIssue(path, "missing or unparseable retrieved_at"))
    if require_fresh and retrieved is not None:
        age_min = (now - retrieved).total_seconds() / 60.0
        if age_min < -5:
            issues.append(ValidationIssue(path, "retrieved_at is in the future"))
        if age_min > FRESHNESS_MINUTES:
            issues.append(
                ValidationIssue(
                    path,
                    f"retrieved_at older than {FRESHNESS_MINUTES} minutes ({age_min:.1f}m)",
                )
            )
    return ValidatedFact(
        path=path,
        value=fact.get("value"),
        source_url=url.strip() if url else "",
        retrieved_at=retrieved or datetime.min.replace(tzinfo=timezone.utc),
        confidence=str(conf) if conf in CONFIDENCE_LEVELS else "reported",
        primary_source_kind=fact.get("primary_source_kind"),
    )


def _mechanism_identity(mech: dict) -> str:
    """Research event identity, not publication identity (two URLs != two mechanisms)."""
    event = str(mech.get("event_id") or "").strip().casefold()
    if event:
        from effect_ledger import canonical
        return "event:" + canonical(event)
    description = " ".join(str(mech.get("description") or "").casefold().split())
    return f"fallback:{mech.get('type')}:{description}"


def _check_mechanism_duplicates(
    mech_path: str,
    mechanisms: list[Any],
    issues: list[ValidationIssue],
) -> None:
    if not isinstance(mechanisms, list):
        issues.append(ValidationIssue(mech_path, "expected a list of mechanisms"))
        return
    seen: set[str] = set()
    for idx, mech in enumerate(mechanisms):
        if not isinstance(mech, dict):
            issues.append(ValidationIssue(f"{mech_path}[{idx}]", "mechanism must be an object"))
            continue
        if not str(mech.get("description") or "").strip():
            issues.append(ValidationIssue(f"{mech_path}[{idx}].description", "nonempty description required"))
        ident = _mechanism_identity(mech)
        if ident in seen:
            issues.append(ValidationIssue(f"{mech_path}[{idx}]", "duplicate causal mechanism event; merge supporting sources"))
        seen.add(ident)
        sources = mech.get("sources") or []
        if not isinstance(sources, list):
            issues.append(ValidationIssue(f"{mech_path}[{idx}].sources", "expected a list"))
        elif not sources:
            issues.append(ValidationIssue(f"{mech_path}[{idx}].sources", "at least one supporting source required"))


def validate_packet(
    packet: dict,
    *,
    now: datetime | None = None,
) -> tuple[ValidatedPacket | None, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    if not isinstance(packet, dict):
        return None, [ValidationIssue("$", "packet must be a JSON object")]
    now = now or datetime.now(timezone.utc)

    availability = packet.get("availability") or {}
    if not isinstance(availability, dict):
        issues.append(ValidationIssue("availability", "expected an object"))
        availability = {}

    validated = ValidatedPacket(raw=packet)
    validated.index = packet.get("index") if isinstance(packet.get("index"), dict) else {}

    fact_store: dict[str, ValidatedFact] = {}

    for player, entry in availability.items():
        if not isinstance(entry, dict):
            issues.append(ValidationIssue(f"availability.{player}", "expected an object"))
            continue
        for fname in AVAILABILITY_FIELDS:
            path = f"availability.{player}.{fname}"
            vf = _validate_fact(path, entry.get(fname), issues, require_fresh=True, now=now)
            if vf:
                fact_store[path] = vf
                if fname == "status" and vf.value not in AVAILABILITY_STATUS:
                    issues.append(
                        ValidationIssue(path, f"status value must be one of {sorted(AVAILABILITY_STATUS)}")
                    )
                if fname == "primary_source" and vf.value not in PRIMARY_SOURCE_KIND:
                    issues.append(
                        ValidationIssue(
                            path,
                            f"primary_source value must be one of {sorted(PRIMARY_SOURCE_KIND)}",
                        )
                    )

    lineup = packet.get("lineup") or {}
    if not isinstance(lineup, dict):
        issues.append(ValidationIssue("lineup", "expected an object"))
        lineup = {}
    for team, entry in lineup.items():
        if not isinstance(entry, dict):
            issues.append(ValidationIssue(f"lineup.{team}", "expected an object"))
            continue
        for fname in LINEUP_FIELDS:
            path = f"lineup.{team}.{fname}"
            vf = _validate_fact(path, entry.get(fname), issues, require_fresh=True, now=now)
            if vf:
                fact_store[path] = vf

    weather = packet.get("weather") or {}
    if not isinstance(weather, dict):
        issues.append(ValidationIssue("weather", "expected an object"))
        weather = {}
    for game, entry in weather.items():
        if not isinstance(entry, dict):
            issues.append(ValidationIssue(f"weather.{game}", "expected an object"))
            continue
        for fname in WEATHER_FIELDS + OPTIONAL_WEATHER_FIELDS:
            if fname in OPTIONAL_WEATHER_FIELDS and fname not in entry:
                continue
            path = f"weather.{game}.{fname}"
            vf = _validate_fact(path, entry.get(fname), issues, require_fresh=True, now=now)
            if vf:
                fact_store[path] = vf
                if fname == "precip_intensity" and vf.value not in PRECIP_INTENSITY:
                    issues.append(
                        ValidationIssue(
                            path,
                            f"precip_intensity must be one of {sorted(PRECIP_INTENSITY)}",
                        )
                    )

    environment = packet.get("environment") or {}
    if not isinstance(environment, dict):
        issues.append(ValidationIssue("environment", "expected an object"))
        environment = {}
    for game, entry in environment.items():
        if not isinstance(entry, dict):
            issues.append(ValidationIssue(f"environment.{game}", "expected an object"))
            continue
        for fname in ENVIRONMENT_FIELDS + OPTIONAL_ENVIRONMENT_FIELDS:
            if fname in OPTIONAL_ENVIRONMENT_FIELDS and fname not in entry:
                continue
            path = f"environment.{game}.{fname}"
            vf = _validate_fact(path, entry.get(fname), issues, require_fresh=True, now=now)
            if vf:
                fact_store[path] = vf

    mechanisms = packet.get("mechanisms") or {}
    if not isinstance(mechanisms, dict):
        issues.append(ValidationIssue("mechanisms", "expected an object"))
        mechanisms = {}
    for key, mech_list in mechanisms.items():
        path = f"mechanisms.{key}"
        _check_mechanism_duplicates(path, mech_list, issues)
        if not isinstance(mech_list, list):
            continue
        cleaned: list[dict] = []
        for idx, mech in enumerate(mech_list):
            if not isinstance(mech, dict):
                continue
            mtype = mech.get("type")
            if mtype not in MECHANISM_TYPES:
                issues.append(
                    ValidationIssue(f"{path}[{idx}].type", f"type must be one of {sorted(MECHANISM_TYPES)}")
                )
            side = mech.get("supports_side")
            if side not in ("over", "under"):
                issues.append(ValidationIssue(f"{path}[{idx}].supports_side", "must be over or under"))
            sources = mech.get("sources") or []
            valid_sources: list[ValidatedFact] = []
            if isinstance(sources, list):
                for s_idx, src in enumerate(sources):
                    vf = _validate_fact(
                        f"{path}[{idx}].sources[{s_idx}]",
                        src,
                        issues,
                        require_fresh=False,
                        now=now,
                    )
                    if vf and vf.source_url:
                        valid_sources.append(vf)
            cleaned.append(
                {
                    "description": mech.get("description", ""),
                    "event_id": mech.get("event_id"),
                    "type": mtype,
                    "supports_side": side,
                    "sources": valid_sources,
                }
            )
        validated.mechanisms[key] = cleaned

    role_changes = packet.get("role_changes") or {}
    if not isinstance(role_changes, dict):
        issues.append(ValidationIssue("role_changes", "expected an object"))
        role_changes = {}
    for player, entry in role_changes.items():
        if not isinstance(entry, dict):
            issues.append(ValidationIssue(f"role_changes.{player}", "expected an object"))
            continue
        confirmed = entry.get("confirmed_by_primary_source")
        if not isinstance(confirmed, bool):
            issues.append(
                ValidationIssue(f"role_changes.{player}.confirmed_by_primary_source", "must be a boolean")
            )
            confirmed = False
        old_vf = _validate_fact(
            f"role_changes.{player}.old_role_n",
            entry.get("old_role_n"),
            issues,
            require_fresh=False,
            now=now,
        )
        new_vf = _validate_fact(
            f"role_changes.{player}.new_role_n",
            entry.get("new_role_n"),
            issues,
            require_fresh=False,
            now=now,
        )
        primary_urls: list[str] = []
        for vf in (old_vf, new_vf):
            if vf and vf.source_url:
                primary_urls.append(vf.source_url)
        if confirmed:
            if old_vf is None or _coerce_number(old_vf.value) is None or new_vf is None or _coerce_number(new_vf.value) is None:
                issues.append(
                    ValidationIssue(
                        f"role_changes.{player}",
                        "confirmed_by_primary_source=true requires numeric old_role_n and new_role_n facts",
                    )
                )
            has_primary = any(_is_primary_domain(url) for url in primary_urls)
            if not has_primary:
                issues.append(
                    ValidationIssue(
                        f"role_changes.{player}",
                        "confirmed_by_primary_source=true requires a primary-domain source_url",
                    )
                )
        validated.role_changes[player] = {
            "confirmed_by_primary_source": confirmed,
            "old_role_n": old_vf,
            "new_role_n": new_vf,
        }

    player_context = packet.get("player_context") or {}
    if isinstance(player_context, dict):
        for player, entry in player_context.items():
            if not isinstance(entry, dict):
                continue
            for fname, fact in entry.items():
                path = f"player_context.{player}.{fname}"
                vf = _validate_fact(path, fact, issues, require_fresh=True, now=now)
                if vf:
                    fact_store[path] = vf

    scouting = packet.get("scouting", {})
    if not isinstance(scouting, dict):
        issues.append(ValidationIssue("scouting", "expected an object"))
    else:
        from scouting_engine import DIMENSIONS
        for key, entry in scouting.items():
            if not isinstance(entry, dict):
                issues.append(ValidationIssue(f"scouting.{key}", "expected an object"))
                continue
            evidence = entry.get("evidence", {})
            if not isinstance(evidence, dict):
                issues.append(ValidationIssue(f"scouting.{key}.evidence", "expected an object"))
                continue
            for dimension in DIMENSIONS:
                path = f"scouting.{key}.evidence.{dimension}"
                vf = _validate_fact(path, evidence.get(dimension), issues,
                                    require_fresh=True, now=now)
                if vf:
                    fact_store[path] = vf

    if isinstance(scouting, dict):
        for key, entry in scouting.items():
            supporting = entry.get('supporting_stats', {}) if isinstance(entry, dict) else {}
            if not isinstance(supporting, dict):
                issues.append(ValidationIssue(f'scouting.{key}.supporting_stats', 'expected an object'))
                continue
            for check, fact in supporting.items():
                path = f'scouting.{key}.supporting_stats.{check}'
                vf = _validate_fact(path, fact, issues, require_fresh=True, now=now)
                if vf:
                    fact_store[path] = vf

    validated.facts = fact_store
    if issues:
        return None, issues
    return validated, []


def _parse_prep_id(row_id: str) -> tuple[str, str, str, str] | None:
    parts = row_id.split("|")
    if len(parts) != 4:
        return None
    return parts[0], parts[1], parts[2], parts[3]


def _mechanism_key(sport: str, player: str, stat: str, side: str) -> str:
    return f"{sport}|{player}|{stat}|{side}"


def _distinct_mechanism_sources(mech_list: list[dict], target_side: str) -> int:
    """Number of independently described causal events with actual supporting sources.

    Multiple URLs for one event do not multiply the count. A single real source
    can support two independently identified events. The validator rejects
    duplicate event IDs (or identical type/description fallback identities).
    """
    events: set[str] = set()
    for mech in mech_list:
        if mech.get("supports_side") != target_side:
            continue
        if not any(isinstance(src, ValidatedFact) and src.source_url for src in (mech.get("sources") or [])):
            continue
        events.add(_mechanism_identity(mech))
    return len(events)


def _weather_checked(validated: ValidatedPacket, game_key: str | None) -> bool:
    if not game_key:
        return False
    indoor = validated.facts.get(f"weather.{game_key}.indoor")
    if indoor is None:
        return False
    if _coerce_bool(indoor.value) is True:
        return True
    if _coerce_bool(indoor.value) is not False:
        return False
    # The full forecast window, sustained wind, gust, precipitation chance and
    # intensity are all required. Missing one is unresolved, not clear weather.
    keys = (
        f"weather.{game_key}.window",
        f"weather.{game_key}.sustained_wind_mph",
        f"weather.{game_key}.gust_mph",
        f"weather.{game_key}.precip_prob",
        f"weather.{game_key}.precip_intensity",
    )
    return all(path in validated.facts for path in keys)


def merge_into_pipeline(
    validated: ValidatedPacket,
    prep_rows: list[dict],
) -> list[dict]:
    """Merge validated packet facts into prep pipeline rows. Never fabricates values."""
    packet = validated.raw
    index = validated.index or {}
    by_player = index.get("by_player") if isinstance(index.get("by_player"), dict) else {}
    by_player_id = index.get("by_player_id") if isinstance(index.get("by_player_id"), dict) else {}

    out: list[dict] = []
    for row in prep_rows:
        if not isinstance(row, dict):
            continue
        merged = dict(row)
        # Rebuild packet-owned fields from their original inputs on every merge.
        # Resolving a fact must clear its previous veto without clearing an
        # independent operator/collector veto.
        from pickem_math import CONTEXT_FIELDS
        owned = set(CONTEXT_FIELDS) | {'hard_veto','data_veto','role_change',
                 'availability_issue','weather_issue','role_window_issue','identity_issue'}
        prior = merged.pop('research_merge_base', None)
        if prior is not None:
            if not isinstance(prior, dict) or set(prior)-owned:
                raise PacketError('invalid research merge provenance')
            for key in owned:
                merged.pop(key, None)
            merged.update(prior)
        merged['research_merge_base'] = {key: merged[key] for key in owned if key in merged}
        previous_research_flags=merged.pop('research_soft_flags',0)
        if (isinstance(previous_research_flags,bool) or not isinstance(previous_research_flags,int) or
            not 0<=previous_research_flags<=int(merged.get('soft_flags') or 0)):
            raise PacketError('invalid research soft-flag accounting')
        merged['soft_flags']=int(merged.get('soft_flags') or 0)-previous_research_flags
        # The validated packet is authoritative; do not retain an earlier scout.
        merged.pop("scouting", None)
        merged.pop('event_context',None)
        row_id = merged.get("id") or ""
        parsed = _parse_prep_id(row_id) if row_id else None
        if not parsed:
            merged["data_veto"] = True
            merged["identity_issue"] = "UNPARSEABLE_CANDIDATE_ID"
            out.append(merged)
            continue
        sport, player, stat, side = parsed
        stable = f"{sport}|{merged.get('player_id')}" if merged.get("player_id") not in (None, "") else ""
        pinfo = by_player_id.get(stable) if stable and isinstance(by_player_id.get(stable), dict) else None
        if pinfo is None:
            pinfo = by_player.get(player) if isinstance(by_player.get(player), dict) else {}
        identity_conflict = (
            (merged.get("game_date") and merged["game_date"] != packet.get("date"))
            or (merged.get("player_id") and pinfo.get("player_id") and str(merged["player_id"]) != str(pinfo["player_id"]))
            or             pinfo.get("sport") not in (None, "", sport)
            or (merged.get("team") and pinfo.get("team") and merged["team"] != pinfo["team"])
            or (merged.get("event_id") and pinfo.get("event_id") and merged["event_id"] != pinfo["event_id"])
        )
        if identity_conflict:
            merged["data_veto"] = "yes"
            merged["identity_issue"] = "AMBIGUOUS_PLAYER_OR_GAME"
            pinfo = {}
        team = pinfo.get("team")
        game_key = pinfo.get("game")

        ctx: dict[str, Any] = {}

        if game_key:
            for fname in WEATHER_FIELDS + OPTIONAL_WEATHER_FIELDS:
                if fname == "window":
                    continue
                vf = validated.facts.get(f"weather.{game_key}.{fname}")
                if not vf:
                    continue
                if fname == "indoor":
                    indoor = _coerce_bool(vf.value)
                    if indoor is not None:
                        ctx["outdoor"] = not indoor
                elif fname == "precip_intensity":
                    ctx["precip_intensity"] = vf.value
                elif fname == "snow":
                    snow_val = _coerce_bool(vf.value)
                    if snow_val is not None:
                        ctx["snow"] = snow_val
                elif fname in ("sustained_wind_mph", "gust_mph", "precip_prob"):
                    num = _coerce_number(vf.value)
                    if num is not None:
                        ctx[fname] = num

            away_team = game_key.split("@", 1)[0] if "@" in game_key else ""
            is_away = (pinfo.get("is_home") is False) or (
                bool(team) and team == away_team
            )

            # Resolve team-specific spread
            spread_vf = None
            negate_spread = False
            if is_away:
                spread_vf = validated.facts.get(f"environment.{game_key}.spread_away")
                if spread_vf is None:
                    spread_vf = (validated.facts.get(f"environment.{game_key}.spread_home")
                                 or validated.facts.get(f"environment.{game_key}.spread"))
                    negate_spread = True
            else:
                spread_vf = (
                    validated.facts.get(f"environment.{game_key}.spread_home")
                    or validated.facts.get(f"environment.{game_key}.spread")
                )
            if spread_vf is not None:
                num = _coerce_number(spread_vf.value)
                if num is not None:
                    ctx["spread"] = -num if negate_spread else num

            # Resolve team-specific rest flags
            b2b_key = "away_back_to_back" if (is_away and f"environment.{game_key}.away_back_to_back" in validated.facts) else "back_to_back"
            b2b_vf = validated.facts.get(f"environment.{game_key}.{b2b_key}")
            if b2b_vf is not None and not (is_away and b2b_key == "back_to_back"):
                b = _coerce_bool(b2b_vf.value)
                if b is not None:
                    ctx["back_to_back"] = b

            t34_key = "away_third_in_four" if (is_away and f"environment.{game_key}.away_third_in_four" in validated.facts) else "third_in_four"
            t34_vf = validated.facts.get(f"environment.{game_key}.{t34_key}")
            if t34_vf is not None and not (is_away and t34_key == "third_in_four"):
                b = _coerce_bool(t34_vf.value)
                if b is not None:
                    ctx["third_in_four"] = b

        if team:
            gvf = validated.facts.get(f"lineup.{team}.goalie_confirmed")
            if gvf:
                b = _coerce_bool(gvf.value)
                if b is not None:
                    ctx["goalie_confirmed"] = b

        # Workload / role context from optional player_context facts (overrides game defaults).
        pctx = packet.get("player_context") or {}
        if isinstance(pctx, dict) and isinstance(pctx.get(player), dict):
            for field_name, fact in pctx[player].items():
                vf = validated.facts.get(f"player_context.{player}.{field_name}")
                if not vf:
                    continue
                if field_name in (
                    "minutes_tonight",
                    "ice_time_tonight",
                    "snap_pct_tonight",
                    "route_pct_tonight",
                    "spread",
                    "sustained_wind_mph",
                    "gust_mph",
                    "precip_prob",
                    "role",
                ):
                    num = _coerce_number(vf.value)
                    if num is not None:
                        ctx[field_name] = num
                    elif field_name == "role" and isinstance(vf.value, str):
                        ctx[field_name] = vf.value.strip().lower()
                elif field_name in (
                    "outdoor",
                    "back_to_back",
                    "third_in_four",
                    "goalie_confirmed",
                    "expected_starting_qb",
                    "is_starter",
                    "team_is_underdog",
                    "snow",
                ):
                    b = _coerce_bool(vf.value)
                    if b is not None:
                        ctx[field_name] = b

        mech_key = _mechanism_key(sport, player, stat, side)
        scout = (packet.get("scouting") or {}).get(mech_key)
        if isinstance(scout, dict) and not identity_conflict:
            # A scouting key includes sport, player, stat and side, so estimates
            # cannot silently migrate across stats or prop directions.
            merged["scouting"] = scout
            merged['event_context']=scout.get('event_context')
        mech_list = validated.mechanisms.get(mech_key, [])
        merged["mechanisms"] = _distinct_mechanism_sources(mech_list, side)

        rc = validated.role_changes.get(player)
        if rc and rc.get("confirmed_by_primary_source"):
            merged["role_change"] = True
            old_vf = rc.get("old_role_n")
            new_vf = rc.get("new_role_n")
            # Role-change counts are evidence, not replacement sample statistics.
            # Means and Ns must originate from the same non-overlapping game windows.
            old_n = _coerce_number(old_vf.value) if isinstance(old_vf, ValidatedFact) else None
            new_n = _coerce_number(new_vf.value) if isinstance(new_vf, ValidatedFact) else None
            if (old_n is None or new_n is None or
                    merged.get("baseline_n") != old_n or merged.get("recent_n") != new_n):
                merged["data_veto"] = "yes"
                merged["role_window_issue"] = "ROLE_WINDOWS_NOT_RECOMPUTED"
            # Never update baseline_n or recent_n in isolation.

        # Availability qualitative flags (player questionable/doubtful).
        availability_key = stable if stable and f"availability.{stable}.status" in validated.facts else player
        status_vf = validated.facts.get(f"availability.{availability_key}.status")
        if status_vf and not identity_conflict:
            event_context=dict(merged.get('event_context') or {})
            original=((packet.get('availability') or {}).get(availability_key) or {}).get('status')
            if original:event_context['subject_status']=original
            merged['event_context']=event_context
        extra_soft = 0
        if identity_conflict:
            status_vf = None
        if status_vf and status_vf.value == "out":
            merged["hard_veto"] = "yes"
            merged["availability_issue"] = "PLAYER_OUT"
        elif not status_vf or status_vf.confidence != "confirmed":
            merged["data_veto"] = "yes"
            merged["availability_issue"] = "STATUS_NOT_VERIFIED"
        elif status_vf.value in ("questionable", "doubtful"):
            extra_soft += 1
        if team and isinstance(by_player, dict):
            teammate_questionable=False
            seen_teammates=set()
            for other, oinfo in list(by_player_id.items())+list(by_player.items()):
                if not isinstance(oinfo,dict):continue
                other_id=str(oinfo.get('player_id') or '')
                if other == player or other_id and other_id==str(merged.get('player_id')):
                    continue
                if (oinfo.get('sport') not in (None,'',sport) or oinfo.get("team") != team or
                    oinfo.get('game') and game_key and oinfo['game']!=game_key):
                    continue
                other_stable=f'{sport}|{other_id}' if other_id else ''
                status_key=other_stable if other_stable and f'availability.{other_stable}.status' in validated.facts else other
                ostatus = validated.facts.get(f"availability.{status_key}.status")
                if not ostatus:continue
                identity=other_stable or other
                if identity in seen_teammates:continue
                seen_teammates.add(identity)
                if ostatus and ostatus.value=='out' and oinfo.get('player_id'):
                    fact=((packet.get('availability') or {}).get(status_key) or {}).get('status')
                    if fact:
                        event_context=dict(merged.get('event_context') or {})
                        events=list(event_context.get('events',[]))
                        if not any(str(e.get('player_id'))==str(oinfo['player_id']) for e in events):
                            events.append(dict(player_id=str(oinfo['player_id']),availability=fact,
                                               effective_at=fact.get('effective_at')))
                        event_context['events']=events
                        merged['event_context']=event_context
                if ostatus and ostatus.value in ("questionable", "doubtful"):
                    teammate_questionable=True
            extra_soft+=int(teammate_questionable)
        merged["soft_flags"] = int(merged.get("soft_flags") or 0) + extra_soft
        merged['research_soft_flags']=extra_soft

        # Missing venue classification or incomplete outdoor forecast is unresolved.
        if sport in ("NFL", "NHL") and (ctx.get("outdoor") is None or
                ctx.get("outdoor") is True and not _weather_checked(validated, game_key)):
            merged["data_veto"] = "yes"
            merged["weather_issue"] = "VENUE_OR_FORECAST_UNVERIFIED"

        for key, value in ctx.items():
            merged[key] = value

        out.append(merged)
    return out


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_no,line in enumerate(path.read_text(encoding="utf-8").splitlines(),1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload,dict):raise PacketError(f'{path.name}:{line_no}: expected a candidate object')
        rows.append(payload)
    return rows


def cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        sys.stderr.write(f"validate: file not found: {path}\n")
        return 1
    packet = load_json(path)
    now = _parse_time(args.now) if args.now else datetime.now(timezone.utc)
    validated, issues = validate_packet(packet, now=now)
    if issues:
        for issue in issues:
            sys.stderr.write(f"{issue.path}: {issue.message}\n")
        return 1
    sys.stdout.write(json.dumps({"ok": True, "facts": len(validated.facts)}, indent=2) + "\n")
    return 0


def cmd_gaps(args: argparse.Namespace) -> int:
    packet_path = Path(args.packet)
    if not packet_path.exists():
        sys.stderr.write(f"gaps: packet not found: {packet_path}\n")
        return 1
    packet = load_json(packet_path)
    shortlist_ids: list[str] = []
    candidate_rows=[]
    if args.prep:
        prep_path = Path(args.prep)
        if not prep_path.exists():
            sys.stderr.write(f"gaps: prep not found: {prep_path}\n")
            return 1
        for row in load_jsonl(prep_path):
            row_id = row.get("id")
            if isinstance(row_id, str) and row_id.strip():
                shortlist_ids.append(row_id.strip())
                candidate_rows.append(row)
    if args.shortlist:
        for path in args.shortlist:
            for row in load_jsonl(Path(path)):
                row_id = row.get("id")
                if isinstance(row_id, str) and row_id.strip():
                    shortlist_ids.append(row_id.strip())
                    candidate_rows.append(row)
    if args.scan:
        shortlist_ids = []  # prep supplies lookup data; scan defines research scope
        scan = load_json(Path(args.scan))
        if not isinstance(scan.get("shortlist"), list):
            sys.stderr.write("gaps: scan JSON must contain a shortlist array\n")
            return 1
        for row in scan.get("research_candidates", scan["shortlist"]):
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                shortlist_ids.append(row["id"])
                if not any(r.get("id") == row["id"] for r in candidate_rows):
                    candidate_rows.append(row)
    if not shortlist_ids:
        sys.stderr.write("gaps: provide --scan or --shortlist (the real Stage D shortlist)\n")
        return 1
    from context_feeds import gap_paths_for_shortlist

    gaps = gap_paths_for_shortlist(packet, shortlist_ids,candidate_rows=candidate_rows)
    now=datetime.now(timezone.utc)
    validated,issues=validate_packet(packet,now=now)
    gaps.extend({'path':issue.path,'reason':'packet_validation','detail':issue.message} for issue in issues)
    if args.prep and not issues:
        import pickem_math as pm
        from usage_baseline import using_directory
        for row in merge_into_pipeline(validated,candidate_rows):
            if row.get('id') not in shortlist_ids:continue
            try:
                with using_directory(packet_path.parent):result=pm.evaluate_candidate(row,now=now)
                context=result.get('shared_context') or {}
                if not context.get('eligible',True):
                    gaps.append({'path':f"scouting.{row['id']}.event_context",'reason':context.get('reason'),
                                 'detail':context.get('detail')})
                if not (result.get('engine_a') or {}).get('reliable'):
                    gaps.append({'path':f"prep.{row['id']}",'reason':'engine_a_source_or_sample_not_reliable'})
            except (ValueError,TypeError) as exc:
                gaps.append({'path':f"prep.{row.get('id')}",'reason':'pipeline_input_invalid','detail':str(exc)})
    payload = {"date": packet.get("date"), "shortlist_count": len(set(shortlist_ids)), "gaps": gaps}
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


def candidate_packet(packet: dict, row: dict) -> dict:
    """Validate relevant facts without letting an unrelated fixture stop a row.

    Retain every same-game availability fact, including teammates absent from
    the odds board. Unknown identities remain in scope rather than disappearing.
    """
    parsed = _parse_prep_id(row.get('id') or '')
    if not parsed or not isinstance(packet, dict):
        return packet
    sport, player, _, _ = parsed
    index = packet.get('index') or {}
    if not isinstance(index, dict):
        return packet
    names = index.get('by_player') or {}
    stable = index.get('by_player_id') or {}
    if not isinstance(names, dict) or not isinstance(stable, dict):
        return packet
    identity = f"{sport}|{row.get('player_id')}"
    meta = stable.get(identity) or names.get(player) or {}
    if not isinstance(meta, dict):
        return packet
    game, team = meta.get('game'), meta.get('team')
    if not game or not team:
        return packet
    scoped = dict(packet)
    for section, keys in [('scouting',{row['id']}), ('mechanisms',{row['id']}),
                          ('role_changes',{player}), ('player_context',{player}),
                          ('lineup',{team}), ('weather',{game}), ('environment',{game})]:
        value = packet.get(section)
        if isinstance(value, dict):
            scoped[section] = {k:v for k,v in value.items() if k in keys}
    availability = packet.get('availability')
    if isinstance(availability, dict):
        scoped['availability'] = {}
        for key, value in availability.items():
            info = stable.get(key) or names.get(key) or {}
            other_game = info.get('game') if isinstance(info, dict) else None
            if not other_game or other_game == game or key in (player, identity):
                scoped['availability'][key] = value
    return scoped


def prepare_candidates(packet, rows, now, *, require_market_clock=False):
    merged, errors = [], []
    for row in rows:
        if require_market_clock and not row.get('market_retrieved_at'):
            errors.append({'ok':False,'id':row.get('id'),'final_rank':'Unranked',
                           'reason':'MARKET_TIMESTAMP_MISSING',
                           'error':'Refresh quotes and rebuild prep; relative age alone cannot date a saved price.'})
            continue
        validated, issues = validate_packet(candidate_packet(packet, row), now=now)
        if issues:
            errors.append({'ok':False,'id':row.get('id'),'final_rank':'Unranked',
                           'reason':'RESEARCH_PACKET_INVALID',
                           'validation_issues':[{'path':i.path,'message':i.message} for i in issues]})
        else:
            merged.extend(merge_into_pipeline(validated, [row]))
    return merged, errors


def cmd_to_pipeline(args: argparse.Namespace) -> int:
    packet_path = Path(args.packet)
    prep_path = Path(args.prep)
    if not packet_path.exists():
        sys.stderr.write(f"to-pipeline: packet not found: {packet_path}\n")
        return 1
    if not prep_path.exists():
        sys.stderr.write(f"to-pipeline: prep not found: {prep_path}\n")
        return 1
    packet = load_json(packet_path)
    now = _parse_time(args.now) if args.now else datetime.now(timezone.utc)
    validated, issues = validate_packet(packet, now=now)
    if issues and args.command != 'audit':
        sys.stderr.write("to-pipeline: packet failed validation; fix before merge\n")
        for issue in issues:
            sys.stderr.write(f"  {issue.path}: {issue.message}\n")
        return 1
    prep_rows = load_jsonl(prep_path)
    if not prep_rows:
        sys.stderr.write('audit: BLOCKED (NO_CANDIDATES); empty prep is not a successful audit\n')
        return 1
    if args.command == 'audit':
        merged, validation_errors = prepare_candidates(packet, prep_rows, now, require_market_clock=not bool(args.now))
    else:
        merged = merge_into_pipeline(validated, prep_rows)
    if args.command == "audit":
        import pickem_math as pm
        failed = bool(validation_errors)
        from usage_baseline import using_directory
        if getattr(args,'collect_lineups',False):
            from lineup_feeds import prepare
            with using_directory(packet_path.parent):
                collection=prepare(merged)
            sys.stderr.write(json.dumps({'lineup_collection':collection})+'\n')
        from research_tasks import reconcile
        reconcile(prep_rows, merged + validation_errors)
        evaluated_rows = list(validation_errors)
        for row in merged:
            try:
                with using_directory(packet_path.parent):
                    evaluated=pm.evaluate_candidate(row,now=now)
                evaluated_rows.append(evaluated)
            except (ValueError, TypeError) as exc:
                failed = True
                evaluated_rows.append({"ok": False, "id": row.get("id"), "final_rank":"Unranked", "reason":"PIPELINE_INPUT_INVALID", "error": str(exc)})
        checked = reconcile(prep_rows, evaluated_rows)
        for result in evaluated_rows:
            sys.stdout.write(json.dumps(result) + "\n")
        sys.stdout.flush()
        sys.stderr.write(json.dumps({"audit_reconciliation": checked}) + "\n")
        return 1 if failed else 0
    for row in merged:
        sys.stdout.write(json.dumps(row, separators=(",", ":")) + "\n")
    return 0


def empty_template(date: str) -> dict:
    return {
        "date": date,
        "index": {"by_player": {}},
        "availability": {},
        "lineup": {},
        "weather": {},
        "environment": {},
        "mechanisms": {},
        "role_changes": {},
        "player_context": {},
        "scouting": {},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="research_packet.py")
    sub = parser.add_subparsers(dest="command", required=True)

    val = sub.add_parser("validate", help="Validate a research packet JSON file.")
    val.add_argument("path", help="Path to data/research_<date>.json")
    val.add_argument("--now", default=None, help="ISO timestamp for freshness checks.")

    merge = sub.add_parser("to-pipeline", help="Merge packet into prep JSONL pipeline rows.")
    merge.add_argument("--packet", required=True)
    merge.add_argument("--prep", required=True)
    merge.add_argument("--now", default=None)

    audit = sub.add_parser("audit", help="Validate, merge and evaluate a packet in one offline step.")
    audit.add_argument("--packet", required=True)
    audit.add_argument("--prep", required=True)
    audit.add_argument("--now", default=None)
    audit.add_argument("--collect-lineups",action="store_true",help="Collect needed source lineup histories before evaluation (network)")

    gaps = sub.add_parser("gaps", help="List null packet fields for a prep/scan shortlist.")
    gaps.add_argument("--packet", required=True, help="Path to data/research_<date>.json")
    gaps.add_argument("--prep", default=None, help="Path to prep JSONL (pipeline rows).")
    gaps.add_argument("--shortlist", nargs="*", default=None, help="Optional shortlist-only JSONL files.")
    gaps.add_argument("--scan", default=None, help="Stage D scan JSON containing its actual shortlist array.")

    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return cmd_validate(args)
        if args.command == "gaps":
            return cmd_gaps(args)
        if args.command in ("to-pipeline", "audit"):
            return cmd_to_pipeline(args)
    except (OSError,json.JSONDecodeError,PacketError) as exc:
        sys.stderr.write(f'{args.command}: {exc}\n')
        return 1
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
