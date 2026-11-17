"""Independent PRE-EVENT official NHL team-roster evidence for research shadows.

The sportsbook's team label is NOT independent membership evidence.
Use the public NHL-hosted team current-roster response, captured BEFORE the
specific experimental forecast and event. This certifies team membership,
NOT actual starter status or projected participation.
"""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
from pathlib import Path
import hashlib
import json
import re


class RosterEvidenceError(ValueError):
    pass


def utc(instant):
    if not isinstance(instant,str) or not instant:
        raise RosterEvidenceError("missing_utc_timestamp")
    try:d=datetime.fromisoformat(instant.replace("Z","+00:00"))
    except ValueError as exc:raise RosterEvidenceError("bad_utc_timestamp") from exc
    if d.tzinfo is None:
        raise RosterEvidenceError("roster_clock_lacks_timezone")
    return d.astimezone(timezone.utc)


def team_code(team):
    if not isinstance(team,str) or not re.fullmatch(r"[A-Z]{3}",team):
        raise RosterEvidenceError("roster_team_not_canonical_nhl_code")
    return team


def roster_url(team):
    return "https://api-web.nhle.com/v1/roster/"+team_code(team)+"/current"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def roster_members(raw):
    try:doc=json.loads(raw)
    except (TypeError,ValueError) as exc:raise RosterEvidenceError("invalid_official_roster_json") from exc
    if not isinstance(doc,dict):
        raise RosterEvidenceError("official_roster_not_object")
    members={}
    for role,kind in (("forwards","skater"),("defensemen","skater"),
                      ("goalies","goalie")):
        values=doc.get(role)
        if not isinstance(values,list):
            raise RosterEvidenceError("official_roster_role_missing:"+role)
        for item in values:
            if not isinstance(item,dict):
                raise RosterEvidenceError("invalid_official_roster_row")
            player_id=item.get("id")
            if isinstance(player_id,bool):
                raise RosterEvidenceError("boolean_roster_player_id")
            try:key=str(int(player_id))
            except (TypeError,ValueError) as exc:
                raise RosterEvidenceError("roster_player_id_missing") from exc
            if int(key)<=0 or key in members:
                raise RosterEvidenceError("duplicate_or_invalid_roster_player_id")
            members[key]=kind
    if len(members)<10 or not any(k=="skater" for k in members.values()):
        raise RosterEvidenceError("implausibly_empty_official_roster")
    return members


def verify_receipt(receipt, *, source_root, forecast_at, event_start,
                   max_age_hours=6):
    if not isinstance(receipt,dict) or receipt.get("schema")!=(
        "nhl_independent_current_roster_receipt_v1"):
        raise RosterEvidenceError("wrong_roster_receipt_schema")
    team=team_code(receipt.get("team"))
    if receipt.get("source_url")!=roster_url(team):
        raise RosterEvidenceError("roster_source_not_official_team_endpoint")
    location=receipt.get("raw_archive_path")
    if not isinstance(location,str) or not location or (
            location.startswith("/") or "\\" in location
            or ".." in Path(location).parts):
        raise RosterEvidenceError("unsafe_roster_archive_path")
    root=Path(source_root).resolve()
    file=(root/location).resolve()
    if not file.is_relative_to(root) or not file.is_file():
        raise RosterEvidenceError("missing_independent_roster_bytes")
    raw=file.read_bytes()
    if len(raw)!=receipt.get("bytes") or digest(raw)!=receipt.get("sha256"):
        raise RosterEvidenceError("official_roster_sha_or_length_mismatch")
    observed=utc(receipt.get("retrieved_at"))
    forecast=utc(forecast_at)
    event=utc(event_start)
    if observed>forecast or forecast>=event:
        raise RosterEvidenceError("not_genuinely_pregame_roster_evidence")
    if (forecast-observed)>timedelta(hours=max_age_hours):
        raise RosterEvidenceError("independent_roster_source_too_old")
    return roster_members(raw)


def membership_status(player_id, player_team, opponent_team, *, receipts,
                      source_root, forecast_at, event_start):
    """Require both independent rosters, avoiding mistaken opposing-team IDs.

    A failed lookup produces an explicit blocked status. The caller records
    the original contract and abstains; never silently switches teams.
    """
    team=team_code(player_team);opponent=team_code(opponent_team)
    if team==opponent:raise RosterEvidenceError("identical_team_and_opponent")
    if not isinstance(receipts,dict):
        raise RosterEvidenceError("independent_roster_receipts_missing")
    for code in (team,opponent):
        if code not in receipts:
            raise RosterEvidenceError("independent_roster_team_missing:"+code)
    ours=verify_receipt(receipts[team],source_root=source_root,
                        forecast_at=forecast_at,event_start=event_start)
    theirs=verify_receipt(receipts[opponent],source_root=source_root,
                          forecast_at=forecast_at,event_start=event_start)
    pid=str(player_id)
    if pid in theirs:
        return {"status":"blocked_opponent_roster_identity_conflict",
                "original_team":team,"official_current_opponent":opponent}
    if ours.get(pid)!="skater":
        return {"status":"blocked_unverified_skaters_team_membership",
                "original_team":team}
    return {"status":"pre_event_team_membership_confirmed",
            "team":team,"player_id":pid,
            "is_confirmed_to_play":False,
            "is_confirmed_starter":False}
