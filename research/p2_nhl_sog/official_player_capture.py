"""P2 official NHL skater profile/log/final acquisition; no forecasting.

Uses the existing C03 live signed transport and the existing independent
historical importer. Final-state receipts are required for every admitted
played game; logs without a final witness remain incomplete.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
import re

from v2.nhl_sog_official_history_producer import import_signed_official_history
from .source_pipeline import (SourceBlocked, require, clock, capture_official,
                              retrieve_source, OFFICIAL, attempt, current_storage)

def capture_player_inputs(root, *, game, player_id, team, position_group,
                          freeze, capture=None, verify=None):
    """Only authentic official player ID and official regular-season data."""
    current_storage(root)
    pid = str(player_id)
    require(re.fullmatch(r"[0-9]{4,12}", pid) is not None,
            "INVALID_OFFICIAL_PLAYER_ID")
    require(position_group in ("F", "D"), "UNSUPPORTED_NHL_SOG_POSITION")
    season = str(game.get("official_season"))
    require(re.fullmatch(r"[0-9]{8}", season) is not None,
            "OFFICIAL_NHL_SEASON_ID_MISSING")
    common = {"event_start_at": game["start_at"], "input_freeze_at": freeze}
    if capture is not None:
        common["capture"] = capture
    if verify is not None:
        common["verify"] = verify
    p = capture_official(root, OFFICIAL + "/player/" + pid + "/landing",
            source_kind="nhl_player_profile", source_id="nhl:profile:" + pid,
            **common)
    profile = p["document"]
    require(str(profile.get("playerId")) == pid,
            "SIGNED_OFFICIAL_PROFILE_PLAYER_MISMATCH")
    actual = "D" if profile.get("position") == "D" else (
        "F" if profile.get("position") in ("C", "L", "R", "LW", "RW")
        else None)
    require(actual == position_group, "SIGNED_PROFILE_POSITION_MISMATCH")
    r = capture_official(root,
            OFFICIAL + "/player/" + pid + "/game-log/" + season + "/2",
            source_kind="nhl_player_regular_season_game_log",
            source_id="nhl:game-log:" + pid + ":" + season, **common)
    rows = r["document"].get("gameLog")
    require(isinstance(rows, list), "SIGNED_GAME_LOG_ROWS_MISSING")
    seen, days = set(), defaultdict(set)
    for row in rows:
        gid = str(row.get("gameId") or "")
        day = row.get("gameDate")
        require(gid.isdigit() and gid != game["event_id"] and gid not in seen,
                "SIGNED_GAME_LOG_DUPLICATE_OR_TARGET")
        require(isinstance(day, str) and day < game["local_date"],
                "SIGNED_GAME_LOG_NOT_PAST")
        shots = row.get("shots")
        require(type(shots) is int and shots >= 0,
                "SIGNED_HISTORICAL_SHOTS_INVALID")
        toi = row.get("toi")
        require(isinstance(toi, str) and
                re.fullmatch(r"[0-9]{1,2}:[0-5][0-9]", toi) is not None,
                "SIGNED_HISTORICAL_TOI_INVALID")
        seen.add(gid)
        days[day].add(gid)
    return {
        "player_id": pid, "team_id": team, "position_group": position_group,
        "original_profile": p, "original_log": r,
        "days_requiring_independent_final_witness": {
            day: sorted(ids) for day,ids in sorted(days.items())},
        "eligible_prior_game_count": len(rows),
        "game_participation_asserted": False,
        "played_history_ready": False,
        "source_stage": "ORIGINAL_PROFILE_AND_LOGS_ONLY"
    }


def capture_final_witnesses(root, *, game, history_input, freeze,
                            max_days=None, capture=None, verify=None):
    """Capture OFF/FINAL witnesses at their actual possession timestamps."""
    current_storage(root)
    days = history_input["days_requiring_independent_final_witness"]
    chosen = list(sorted(days))[:max_days] if max_days else sorted(days)
    outputs, missing = {}, []
    for day in chosen:
        opts = {"event_start_at": game["start_at"],
                "input_freeze_at": freeze}
        if capture is not None: opts["capture"] = capture
        if verify is not None: opts["verify"] = verify
        try:
            s = capture_official(root, OFFICIAL + "/score/" + day,
                 source_kind="nhl_prior_game_final",
                 source_id="nhl:historical-final:" + day, **opts)
            found = {
                str(x.get("id")): x for x in s["document"].get("games", [])
                if str(x.get("id")) in days[day] and
                   x.get("gameState") in ("OFF","FINAL")
            }
            require(set(found) == set(days[day]),
                    "SIGNED_FINAL_WITNESS_GAME_MISSING")
            # Existing importer needs a signed individual FINAL game-body,
            # not a daily scoreboard receipt. Return only source candidates,
            # never fake an individual gamecenter receipt.
            outputs[day] = {
                "signed_score_source_sha256": s["p0_sha256"],
                "validated_final_game_ids": sorted(found),
                "original_daily_C03_receipt": s["c03_receipt"]
            }
        except Exception as exc:
            missing.append({"day": day, "reason": type(exc).__name__ +
                            ":" + str(exc)[:160], "game_ids": sorted(days[day])})
    return {
        "source_stage": "ORIGINAL_DAILY_FINAL_WITNESSES_PARTIAL",
        "source_daily_final_receipts": outputs,
        "missing_final_days": missing,
        "individual_gamecenter_final_receipts_required": True,
        "ready_for_original_history_import": False
    }


def acquire_player_provenance(root, *, game, player_id, team,
                              position_group, freeze,
                              capture=None, verify=None):
    try:
        inputs = capture_player_inputs(
            root, game=game, player_id=player_id, team=team,
            position_group=position_group, freeze=freeze,
            capture=capture, verify=verify)
        witnesses = capture_final_witnesses(
            root, game=game, history_input=inputs, freeze=freeze,
            capture=capture, verify=verify)
        output = {**inputs, **witnesses}
        receipt = attempt(root, "official_player_acquisition",
                          "VERIFIED_INCOMPLETE", [
            "ORIGINAL_GAMECENTER_FINAL_RECEIPTS_AND_P0_HISTORY_BRIDGE_PENDING"],
            event_id=game["event_id"], player_id=str(player_id),
            source_sha256s=[inputs["original_profile"]["p0_sha256"],
                            inputs["original_log"]["p0_sha256"]])
        return {"source": output, "attempt": receipt}
    except Exception as exc:
        receipt = attempt(root, "official_player_acquisition", "REJECTED", [
            type(exc).__name__ + ":" + str(exc)[:170]
        ], event_id=game["event_id"], player_id=str(player_id))
        return {"source": None, "attempt": receipt}
