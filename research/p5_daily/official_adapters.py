"""P5 pure adapters to EXISTING independent NHL/NBA official final parsers.

No HTTP requests or duplicate acquisition; caller provides independently archived
raw final bytes, official game linkage, original availability and storage root.
No postgame evidence is ever fed into a pregame P1/P2 feature snapshot.
"""
from __future__ import annotations
import hashlib
import json

from v2.official_nba_nhl_capture import (
    nhl_stat_rows,nba_stat_rows,normalized_team,
    SettlementCaptureError,
)
from v2.p0_integrity.contracts import record, validate_record, utc

class OfficialAdapterError(ValueError):
    pass

STATS={
 "NBA":("points","rebounds","assists","threes","pr","pa","ra","pra"),
 "NHL":("shots on goal",),
}

def make_p0_official_final(*, raw, sport, event_id, official_game_id,
                           team_id, opponent_id, expected_player_ids,
                           event_start_at, official_first_observed_at,
                           original_archive_path, result_version="v1",
                           source_id=None):
    """Build verifiable P0 records from final official JSON already acquired.

    A mismatching player TEAM or missing player is UNKNOWN, *not* DNP.
    DNP requires separate positive official participation evidence; this
    adapter intentionally refuses to infer DNP from absent final box rows.
    """
    if sport not in STATS or not isinstance(raw,(bytes,bytearray)):
        raise OfficialAdapterError("OFFICIAL_INPUT_INVALID")
    if not all(isinstance(v,str) and v for v in (
        event_id,official_game_id,team_id,opponent_id,event_start_at,
        official_first_observed_at,original_archive_path,result_version)):
        raise OfficialAdapterError("OFFICIAL_IDENTITY_FIELDS_MISSING")
    if team_id==opponent_id or utc(official_first_observed_at)<=utc(event_start_at):
        raise OfficialAdapterError("OFFICIAL_CHRONOLOGY_OR_TEAMS_INVALID")
    try:
        source=json.loads(raw)
    except (ValueError,UnicodeDecodeError) as exc:
        raise OfficialAdapterError("OFFICIAL_BYTES_NOT_JSON") from exc
    teams={normalized_team(team_id,sport),normalized_team(opponent_id,sport)}
    if len(teams)!=2:
        raise OfficialAdapterError("OFFICIAL_EXPECTED_TEAMS_INVALID")
    if sport=="NHL":
        if str(source.get("id"))!=str(official_game_id):
            raise OfficialAdapterError("NHL_OFFICIAL_GAME_ID_MISMATCH")
        rows=nhl_stat_rows(source,expected_teams=teams)
    else:
        ids={str(h.get("id")) for h in source.get("header",{}).get("competitions",[])}
        if ids!={str(official_game_id)}:
            raise OfficialAdapterError("NBA_OFFICIAL_GAME_ID_MISMATCH")
        rows=nba_stat_rows(source,expected_teams=teams)
    raw_sha=hashlib.sha256(raw).hexdigest()
    source_receipt=record("SourceReceipt",
        receipt_id=source_id or "official:"+sport+":"+official_game_id+":"+result_version,
        source_id="official-final:"+sport+":"+official_game_id,
        source_kind=("nba_espn_final_summary" if sport=="NBA"
                     else "nhl_official_final_box"),
        source_available_at=official_first_observed_at,
        collected_at=official_first_observed_at,
        source_sha256=raw_sha,archive_path=original_archive_path,
        provenance_class="collector_possession")
    out=[]
    unknown=[]
    for player_id in sorted(set(str(x) for x in expected_player_ids)):
        r=rows.get(player_id)
        if r is None:
            unknown.append({"player_id":player_id,"reason":"NOT_IN_FINAL_PLAYED_BOX_NO_DNP_PROOF"})
            continue
        if normalized_team(r["team"],sport)!=normalized_team(team_id,sport):
            unknown.append({"player_id":player_id,"reason":"FINAL_PLAYER_TEAM_DISAGREES"})
            continue
        for stat in STATS[sport]:
            val=r.get(stat)
            if type(val) is not int or val<0:
                raise OfficialAdapterError("UNSUPPORTED_OR_MISSING_OFFICIAL_STAT:"+stat)
            out.append(record("OutcomeRecord",outcome_id="outcome:"+sport+":"+
               official_game_id+":"+player_id+":"+stat+":"+result_version,
               sport=sport,event_id=event_id,
               team_id=team_id,player_id=player_id,stat_key=stat,period="full",
               official_result_available_at=official_first_observed_at,
               official_source_receipt_id=source_receipt["receipt_id"],
               official_source_sha256=raw_sha,actual_value=val,
               participation="PLAYED",result_version=result_version,
               status="FINAL" if result_version=="v1" else "CORRECTED"))
    return {"schema":"PA-P5-OFFICIAL-ADAPTER/1",
            "evidence":"independent_archived_official_final",
            "official_event_id":official_game_id,
            "source_receipt":source_receipt,"outcome_records":out,
            "unresolved_players":unknown,"raw_sha256":raw_sha,
            "original_raw_archive_path":original_archive_path,
            "player_games_counted":len(set(x["player_id"] for x in out)),
            "source_verified_by_caller":False,
            "research_only":True}

def persist_admitted_official_bundle(bundle, *, root="/work"):
    """Archive raw bytes BEFORE P0 append; never trust an untethered digest.

    This P5 function does not fetch official results; existing collector is
    responsible for original raw file and accessible receipt clock.
    """
    from v2.p0_integrity.storage import append_immutable
    from v2.p0_integrity.contracts import verify_source_bytes
    verify_source_bytes(bundle["source_receipt"],root)
    source=append_immutable(root,"SourceReceipt",bundle["source_receipt"])
    recorded=[]
    for item in bundle["outcome_records"]:
        recorded.append(append_immutable(root,"OutcomeRecord",item))
    return {"source_receipt":source,"outcome_receipts":recorded,
            "unresolved_players":bundle["unresolved_players"],
            "research_only":True}
