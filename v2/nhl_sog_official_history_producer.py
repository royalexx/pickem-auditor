"""NHL official-game-log SOG/TOI import, strictly shadow-only.

Consumes ORIGINAL signed NHL HTTPS game-log bytes and signed completed-game
landing bytes; never derives played-game outcomes from market lines or current
game. Depends on the future independently reviewed C03 collector transport
contract. A missing dependency or proof means ABSTAIN, never synthetic input.
"""
from __future__ import annotations

from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re

from .nhl_sog_exposure_shadow import ExperimentBlocked, _utc, _canonical, verify_observation


def _signed(receipt,archive_root,freeze,event_start):
    try:
        from c03_live_transport import verify_signed_capture
    except ImportError as exc:
        raise ExperimentBlocked("C03_SIGNED_COLLECTOR_NOT_IN_INTEGRATION_BASE") from exc
    try:
        return verify_signed_capture(receipt,archive_root=archive_root,
                                     freeze=freeze,event_start=event_start)
    except (OSError,TypeError,ValueError) as exc:
        raise ExperimentBlocked("AUTHENTIC_RAW_NHL_SOURCE_NOT_VERIFIED:"+str(exc)) from exc


def _toi(value):
    """Official NHL game-log TOI in MM:SS, reject zero/unknown/inconsistent."""
    if not isinstance(value,str) or not re.fullmatch(r"\d{1,2}:[0-5]\d",value):
        raise ExperimentBlocked("OFFICIAL_TOI_FORMAT_INVALID")
    mm,ss=(int(x) for x in value.split(":"))
    out=mm+ss/60
    if not 0<out<=65:
        raise ExperimentBlocked("OFFICIAL_TOI_PLAYED_RANGE_INVALID")
    return out


def _put_once(root,namespace,body):
    digest=hashlib.sha256(body).hexdigest()
    rel=namespace+"/"+digest+".json"
    target=Path(root).resolve()/rel
    target.parent.mkdir(parents=True,exist_ok=True)
    try:
        with target.open("xb") as fh:fh.write(body)
    except FileExistsError:pass
    if target.read_bytes()!=body:
        raise ExperimentBlocked("OFFICIAL_SOG_ARCHIVE_MUTATED")
    return rel,digest


def import_signed_official_history(*,player_id,position_group,gamelog_receipt,
                                   completed_game_receipts,archive_root,
                                   input_freeze_at,event_start_at):
    """Link signed official gameLog rows to independent signed final game states.

    Official final status first observed at collection time is a conservative
    bound on actual game end, NOT an invented exact final-horn timestamp.
    """
    player_id=str(player_id)
    if position_group not in ("F","D") or not player_id.isdigit():
        raise ExperimentBlocked("NHL_OFFICIAL_PLAYER_OR_POSITION_UNVERIFIED")
    url=(gamelog_receipt or {}).get("source_url") or ""
    prefix="https://api-web.nhle.com/v1/player/"+player_id+"/game-log/"
    if not url.startswith(prefix) or not re.fullmatch(
            r"\d{8}/2",url[len(prefix):]):
        raise ExperimentBlocked("NHL_OFFICIAL_GAMELOG_URL_IDENTITY_INVALID")
    raw=_signed(gamelog_receipt,archive_root,input_freeze_at,event_start_at)
    entries=raw.get("gameLog") if isinstance(raw,dict) else None
    if not isinstance(entries,list) or not entries:
        raise ExperimentBlocked("NHL_OFFICIAL_GAMELOG_EMPTY_OR_INVALID")
    if not isinstance(completed_game_receipts,dict):
        raise ExperimentBlocked("NHL_GAME_FINAL_SOURCE_MANIFEST_MISSING")
    freeze=_utc(input_freeze_at,"freeze")
    observed=datetime.now(timezone.utc)
    if observed>freeze:
        raise ExperimentBlocked("OFFICIAL_HISTORY_IMPORT_AFTER_FREEZE")
    if len(entries)>100:
        raise ExperimentBlocked("OFFICIAL_GAMELOG_IMPLAUSIBLY_LONG")
    returned=[]
    seen=set()
    for entry in entries:
        if not isinstance(entry,dict):
            raise ExperimentBlocked("OFFICIAL_GAMELOG_ROW_INVALID")
        game_id=str(entry.get("gameId") or "")
        if not game_id.isdigit() or game_id in seen:
            raise ExperimentBlocked("OFFICIAL_GAME_ID_INVALID_OR_DUPLICATE")
        seen.add(game_id)
        shots=entry.get("shots")
        if isinstance(shots,bool) or type(shots) is not int or shots<0:
            raise ExperimentBlocked("OFFICIAL_SHOTS_INVALID_OR_MISSING")
        minutes=_toi(entry.get("toi"))
        source=completed_game_receipts.get(game_id)
        if source is None:
            raise ExperimentBlocked("OFFICIAL_FINAL_GAME_RECEIPT_MISSING:"+game_id)
        if source.get("source_url")!=(
                "https://api-web.nhle.com/v1/gamecenter/"+game_id+"/landing"):
            raise ExperimentBlocked("OFFICIAL_FINAL_EVENT_URL_IDENTITY_MISMATCH")
        final_doc=_signed(source,archive_root,input_freeze_at,event_start_at)
        if (not isinstance(final_doc,dict) or
                str(final_doc.get("id"))!=game_id or
                final_doc.get("gameState") not in ("OFF","FINAL")):
            raise ExperimentBlocked("OFFICIAL_GAME_NOT_IN_FINAL_STATE:"+game_id)
        final_seen=_utc(source.get("received_at"),"final_observed_at")
        log_seen=_utc(gamelog_receipt.get("received_at"),"game_log_received")
        if not final_seen<=observed<=freeze or log_seen>observed:
            raise ExperimentBlocked("OFFICIAL_FINAL_HISTORY_CHRONOLOGY_INVALID")
        obs={"schema":"v25_nhl_sog_observation_v1",
             "player_id":player_id,"event_id":game_id,
             "position_group":position_group,"toi_minutes":minutes,
             "shots_on_goal":shots,"played":True,
             "event_ended_at":source["received_at"],
             "event_end_clock_semantics":"official_final_state_first_observed_not_exact_final_horn",
             "source_game_log_sha256":gamelog_receipt["body_sha256"],
             "source_final_sha256":source["body_sha256"],
             "source_game_log_row":entry,
             "source_final_received_at":source["received_at"],
             "source_game_log_received_at":gamelog_receipt["received_at"]}
        rel,digest=_put_once(archive_root,"nhl_sog_official_derived",_canonical(obs))
        receipt={"archive_path":rel,"content_sha256":digest,
                 "source_kind":"collector_observed_bytes","source_url":url,
                 "received_at":observed.isoformat()}
        verify_observation(receipt,archive_root,input_freeze_at)
        returned.append({"observation_receipt":receipt,"raw_log_receipt":gamelog_receipt,
                         "raw_final_receipt":source})
    return returned


def independent_verify_observation_lineage(entry,*,archive_root,freeze,event_start):
    """Reject a tampered derived record even if its own digest is recomputed."""
    rec=entry.get("observation_receipt")
    obs=verify_observation(rec,archive_root,freeze)
    rawlog=_signed(entry.get("raw_log_receipt"),archive_root,freeze,event_start)
    rawfinal=_signed(entry.get("raw_final_receipt"),archive_root,freeze,event_start)
    if (str(rawfinal.get("id"))!=obs["event_id"] or
            rawfinal.get("gameState") not in ("OFF","FINAL") or
            obs.get("source_game_log_sha256")!=entry["raw_log_receipt"]["body_sha256"] or
            obs.get("source_final_sha256")!=entry["raw_final_receipt"]["body_sha256"]):
        raise ExperimentBlocked("OFFICIAL_SOG_DERIVED_ORIGIN_MISMATCH")
    matching=[x for x in rawlog.get("gameLog",[]) if str(x.get("gameId"))==obs["event_id"]]
    if len(matching)!=1 or matching[0]!=obs.get("source_game_log_row") or (
            matching[0].get("shots")!=obs["shots_on_goal"] or
            _toi(matching[0].get("toi"))!=obs["toi_minutes"]):
        raise ExperimentBlocked("OFFICIAL_SOG_TOI_ORIGIN_VALUE_MISMATCH")
    return rec
