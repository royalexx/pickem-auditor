"""P2-02 as-of participation source gate: real roster/role receipts or abstain.

Unlike the previous two-game box-score roster proxy this module never infers
a current injury, inactive status, or route from past target statistics.
Historical snaps are allowed as *previous-game* exposure labels only and
cannot be silently relabeled as receiver routes. Historical weekly rosters
without authentic pregame capture timestamps are unverified research data.

This module does not grant Phase 0R publication certification.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import math
from typing import Any

class SourceGateError(ValueError):
    pass

def _at(value: Any, field: str) -> datetime:
    if not isinstance(value,str):
        raise SourceGateError("timestamp_missing:"+field)
    try:
        d=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise SourceGateError("timestamp_invalid:"+field) from exc
    if d.tzinfo is None or d.utcoffset() is None:
        raise SourceGateError("timestamp_not_utc_aware:"+field)
    return d.astimezone(timezone.utc)

def _text(value: Any, field: str):
    if not isinstance(value,str) or not value.strip():
        raise SourceGateError("missing_identity:"+field)
    return value

def _sha(value: Any, field: str):
    if not isinstance(value,str) or len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise SourceGateError("source_digest_missing:"+field)

def _nonneg(value,field):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
        raise SourceGateError("invalid_exposure:"+field)
    return float(value)

def validate_asof_roster(
        *, event_id: str, team_id: str, freeze_at: str, kickoff_at: str,
        roster_events: list[dict], expected_players: list[str],
        strict_capture: bool = True) -> dict:
    """Use real named roster receipts before freeze; unknown != out.

    Statuses only become certifiable when the *original capture* is before
    freeze. Retrospective official modification timestamps alone cannot
    establish the model actually possessed that information in 2024.
    """
    _text(event_id,"event_id")
    _text(team_id,"team_id")
    freeze=_at(freeze_at,"freeze_at")
    kickoff=_at(kickoff_at,"kickoff_at")
    if freeze>=kickoff:
        raise SourceGateError("forecast_after_kickoff")
    if not isinstance(roster_events,list) or not isinstance(expected_players,list):
        raise SourceGateError("missing_roster_universe")
    if len(expected_players)!=len(set(expected_players)):
        raise SourceGateError("duplicate_player_candidates")
    accepted=defaultdict(list)
    rejection=defaultdict(int)
    for row in roster_events:
        if not isinstance(row,dict):
            raise SourceGateError("invalid_roster_record")
        allowed={"event_id","team_id","player_id","role","availability","source_type",
                 "published_at","captured_at","content_sha256","retro_archive_only"}
        if set(row)!=allowed:
            raise SourceGateError("roster_field_contract_changed")
        if row["event_id"] != event_id or row["team_id"] != team_id:
            raise SourceGateError("foreign_game_roster_record")
        player=_text(row["player_id"],"player_id")
        _text(row["role"],"role")
        if row["role"] not in ("WR","RB","TE"):
            raise SourceGateError("unregistered_role")
        if row["source_type"] not in ("official_injury_report","official_roster_snapshot","beat_lineup_source","depth_chart_snapshot"):
            raise SourceGateError("unverifiable_roster_source_type")
        if row["availability"] not in ("available","uncertain","verified_out"):
            raise SourceGateError("availability_must_not_be_inferred")
        _sha(row["content_sha256"],"roster_sha256")
        published=_at(row["published_at"],"published_at")
        captured=_at(row["captured_at"],"captured_at")
        if published>captured:
            raise SourceGateError("source_captured_before_published")
        if published>freeze:
            raise SourceGateError("future_published_roster_status")
        if captured>freeze:
            if strict_capture:
                raise SourceGateError("retro_captured_roster_cannot_claim_asof")
            rejection["retrospective_record_not_verified_at_forecast"]+=1
            continue
        if row["retro_archive_only"] is True:
            if strict_capture:
                raise SourceGateError("retro_archive_not_source_certificate")
            rejection["no_original_capture"]+=1
            continue
        if row["retro_archive_only"] is not False:
            raise SourceGateError("unverified_archive_flag")
        accepted[player].append((published,captured,row))
    roster=[]
    for player in expected_players:
        _text(player,"expected_player")
        items=accepted.get(player)
        if not items:
            roster.append({"player_id":player,"status":"unknown",
                           "reason":"no_proven_pregame_status",
                           "prediction_eligible":False,"role":None})
            continue
        # Same-time contradicting reports => uncertainty, not zero.
        items.sort(key=lambda x:(x[0],x[1]))
        row=items[-1][2]
        if len(items)>1 and items[-2][0:2]==items[-1][0:2] and items[-2][2]["availability"]!=row["availability"]:
            raise SourceGateError("same_timestamp_contradictory_roster_status")
        roster.append({"player_id":player,"status":row["availability"],
                       "role":row["role"],"reason":"documented_pregame_status",
                       "prediction_eligible":row["availability"]!="uncertain",
                       "original_source_sha256":row["content_sha256"]})
    return {
        "event_id":event_id,"freeze_at":freeze.isoformat(),
        "roster":roster,"n_expected":len(expected_players),
        "n_verified":sum(p["status"]!="unknown" for p in roster),
        "n_unknown":sum(p["status"]=="unknown" for p in roster),
        "n_explicit_out":sum(p["status"]=="verified_out" for p in roster),
        "n_uncertain":sum(p["status"]=="uncertain" for p in roster),
        "rejected_source_reasons":dict(rejection),
        "source_capture_time_verified":strict_capture,
        "invented_activity_from_targets":False,
    }

def validate_lagged_participation(
        *, event_id: str, freeze_at: str, history: list[dict]) -> dict:
    """Historical snaps are observed exposure; never fake routes from them."""
    freeze=_at(freeze_at,"freeze")
    if not isinstance(history,list):
        raise SourceGateError("lagged_participation_not_list")
    seen=set();allowed={"player_id","team_id","event_id","event_start_at",
        "result_available_at","exposure_kind","offense_snaps","routes",
        "source_sha256","source_captured_at"}
    n_snaps=n_routes=0
    for row in history:
        if not isinstance(row,dict) or set(row)!=allowed:
            raise SourceGateError("historical_participation_schema_error")
        key=(_text(row["player_id"],"player"),_text(row["event_id"],"event"))
        if key in seen:raise SourceGateError("duplicate_past_player_event")
        seen.add(key)
        if row["event_id"]==event_id:
            raise SourceGateError("current_game_realized_exposure_forbidden")
        if _at(row["event_start_at"],"historic_start")>=freeze:
            raise SourceGateError("future_event_in_exposure_history")
        if _at(row["result_available_at"],"historic_result_available")>freeze:
            raise SourceGateError("future_exposure_publication")
        if _at(row["source_captured_at"],"historical_capture")>freeze:
            raise SourceGateError("historical_exposure_not_owned_at_freeze")
        _sha(row["source_sha256"],"exposure_sha256")
        if row["exposure_kind"]=="snap_counts":
            if row["routes"] is not None:
                raise SourceGateError("snap_count_mislabeled_as_routes")
            _nonneg(row["offense_snaps"],"snaps")
            n_snaps+=1
        elif row["exposure_kind"]=="verified_receiver_routes":
            if row["routes"] is None:
                raise SourceGateError("routes_not_observed")
            _nonneg(row["routes"],"routes")
            n_routes+=1
        else:
            raise SourceGateError("unsupported_participation_exposure_kind")
    return {"historical_records":len(history),"prior_snap_exposures":n_snaps,
            "prior_verified_routes":n_routes,
            "route_challenger_eligible":n_routes>0,
            "postgame_exposure_used_in_current_forecast":False,
            "snaps_not_automatically_routes":True}
