"""Research-only NFL QB prop starter/backup participation gate.

A 2023 carry-forward roster is NOT a 2024 pregame verified starter. Archived
postgame box scores are NEVER eligible as original pregame evidence. This gate
preserves every proposed original QB contract and abstains by default unless
an exact event/team/player source was captured in advance and explicitly
reported a CONFIRMED starter, not a depth-chart projection.

Strictly NOT a promotion/production gate by itself. The source adapter must
independently verify upstream provider semantics before assigning authority.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
import json
import math

SCHEMA="nfl_p2_explicit_pregame_qb_starter_gate_v1"
RECEIPT_SCHEMA="nfl_p2_original_qb_starter_source_receipt_v1"
QB_MARKETS=frozenset(("pass attempts","completions","passing yards",
                     "qb rushing attempts","qb rushing yards"))
APPROVED_HOSTS=frozenset(("nfl.com","www.nfl.com","static.www.nfl.com"))
SOURCE_CONFIRMATION="explicit_starting_qb_named_for_this_game"


class QBStarterEvidenceError(ValueError):
    pass


def _utc(value,name):
    if not isinstance(value,str):
        raise QBStarterEvidenceError("missing_"+name)
    try:
        value=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise QBStarterEvidenceError("invalid_"+name) from exc
    if value.tzinfo is None or value.utcoffset() is None:
        raise QBStarterEvidenceError("naive_"+name)
    return value.astimezone(timezone.utc)


def _name(value,name):
    if not isinstance(value,str) or not value.strip():
        raise QBStarterEvidenceError("missing_"+name)
    return value


def _official_url(value):
    if not isinstance(value,str):
        raise QBStarterEvidenceError("missing_source_url")
    try:
        parts=urlsplit(value)
        port=parts.port  # Access itself can raise ValueError on malformed ports.
    except ValueError as exc:
        raise QBStarterEvidenceError("invalid_source_url") from exc
    if (parts.scheme!="https" or parts.hostname not in APPROVED_HOSTS or
            parts.username is not None or parts.password is not None or
            port not in (None,443)):
        raise QBStarterEvidenceError("not_approved_original_league_source")
    return value


def _read_original(receipt,root):
    rel=receipt.get("original_raw_archive_path")
    if (not isinstance(rel,str) or not rel or rel.startswith("/") or
            "\\" in rel or ".." in Path(rel).parts):
        raise QBStarterEvidenceError("unsafe_original_archive_path")
    root=Path(root).resolve()
    path=(root/rel).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise QBStarterEvidenceError("missing_original_source_bytes")
    raw=path.read_bytes()
    expected=receipt.get("original_raw_sha256")
    if (not isinstance(expected,str) or len(expected)!=64 or
            hashlib.sha256(raw).hexdigest()!=expected):
        raise QBStarterEvidenceError("original_source_sha_mismatch")
    if len(raw)>4_000_000 or len(raw)<20:
        raise QBStarterEvidenceError("original_source_bytes_unusable")
    try:doc=json.loads(raw)
    except (TypeError,ValueError) as exc:
        raise QBStarterEvidenceError("original_source_schema_unrecognized") from exc
    if not isinstance(doc,dict):
        raise QBStarterEvidenceError("original_source_not_object")
    return doc


def verify_exact_starter(receipt,*,root,game_id,team_id,freeze_at,kickoff_at,
                         max_age_hours=6):
    """Return exact source-bound selected QB, or raise.

    This interface deliberately recognizes only a game-specific, explicit
    league feed claim. An inactive list, static depth chart, roster rank,
    completed boxscore or a source without native starter semantics MUST
    fail instead of being reinterpreted as a confirmed starting QB.
    """
    if not isinstance(receipt,dict) or receipt.get("schema")!=RECEIPT_SCHEMA:
        raise QBStarterEvidenceError("missing_qualified_starter_source_receipt")
    if receipt.get("source_kind")!="original_league_explicit_starting_qb":
        raise QBStarterEvidenceError("source_does_not_explicitly_confirm_starting_qb")
    _official_url(receipt.get("source_url"))
    event=_name(game_id,"event_id")
    team=_name(team_id,"team_id")
    if str(receipt.get("game_id"))!=event or receipt.get("team_id")!=team:
        raise QBStarterEvidenceError("receipt_event_or_team_mismatch")
    start=_utc(kickoff_at,"kickoff")
    frozen=_utc(freeze_at,"forecast_freeze")
    captured=_utc(receipt.get("captured_at"),"original_collector_capture")
    if not captured<=frozen<start:
        raise QBStarterEvidenceError("source_captured_after_forecast_or_game_started")
    if frozen-captured>timedelta(hours=max_age_hours):
        raise QBStarterEvidenceError("source_stale_at_forecast")
    published=receipt.get("published_at")
    if published is not None and _utc(published,"provider_publication")>captured:
        raise QBStarterEvidenceError("provider_publication_after_collector_capture")
    doc=_read_original(receipt,root)
    if doc.get("game_id")!=event or doc.get("team_id")!=team:
        raise QBStarterEvidenceError("raw_source_does_not_match_event_team")
    if doc.get("status")!=SOURCE_CONFIRMATION:
        raise QBStarterEvidenceError("source_is_projection_not_confirmation")
    player=_name(doc.get("starting_qb_player_id"),"starting_qb_player_id")
    if receipt.get("starting_qb_player_id")!=player:
        raise QBStarterEvidenceError("source_and_receipt_starter_identity_mismatch")
    if doc.get("published_at")!=receipt.get("published_at"):
        raise QBStarterEvidenceError("source_publication_claim_mismatch")
    if doc.get("is_postgame") is not False:
        raise QBStarterEvidenceError("postgame_record_not_pregame_evidence")
    return {
        "game_id":event,"team_id":team,"starting_qb_player_id":player,
        "source_sha256":receipt["original_raw_sha256"],
        "source_possession_at":receipt["captured_at"],
        "upstream_publication_independently_verified":False,
        "starter_claim_requires_source_adapter_verification":True,
    }


def audit_qb_candidates(*,candidates,original_receipts,source_root,
                        freeze_at,kickoff_at):
    """One event/team only: record ALL candidates, with honest abstention.

    Designed to be called before inference. Never filters out unsuccessful
    backtests after their actual box scores are known.
    """
    if not isinstance(candidates,list):
        raise QBStarterEvidenceError("candidate_pool_must_be_list")
    known=set()
    legal=[]
    for row in candidates:
        if not isinstance(row,dict):
            raise QBStarterEvidenceError("invalid_original_candidate")
        if row.get("market") not in QB_MARKETS:
            raise QBStarterEvidenceError("wrong_non_qb_market")
        event=_name(row.get("game_id"),"game_id")
        team=_name(row.get("team"),"team")
        pid=_name(row.get("player_id"),"player_id")
        line=row.get("research_line")
        if isinstance(line,bool) or not isinstance(line,(int,float)) or not math.isfinite(line):
            raise QBStarterEvidenceError("invalid_original_line")
        key=(event,team,pid,row["market"],float(line))
        if key in known:
            raise QBStarterEvidenceError("duplicate_original_qb_candidate")
        known.add(key)
        legal.append((row,key))
    if len({(k[0],k[1]) for row,k in legal})>1:
        raise QBStarterEvidenceError("audit_requires_one_game_team")
    receipt=None
    if isinstance(original_receipts,dict) and legal:
        key=legal[0][1]
        receipt=original_receipts.get((key[0],key[1]))
    failure=None
    source=None
    if receipt is None:
        failure="qualified_original_starter_receipt_missing"
    else:
        try:
            source=verify_exact_starter(
                receipt,root=source_root,game_id=legal[0][1][0],
                team_id=legal[0][1][1],freeze_at=freeze_at,
                kickoff_at=kickoff_at)
        except QBStarterEvidenceError as exc:
            failure=str(exc)
    out=[]
    reasons=Counter()
    for row,key in legal:
        status="source_qualified_candidate_only"
        reason=None
        if failure:
            status="abstain"
            reason=failure
        elif key[2]!=source["starting_qb_player_id"]:
            status="abstain"
            reason="not_the_explicit_pregame_named_starter"
        reasons[reason or status]+=1
        out.append({"game_id":key[0],"team":key[1],"player_id":key[2],
                    "market":key[3],"line":key[4],
                    "status":status,"reason":reason,
                    "original_forecast_modified":False,
                    "production_eligible":False})
    return {
        "schema":SCHEMA,
        "original_candidates":len(candidates),
        "qualified_candidate_count":sum(r["status"]=="source_qualified_candidate_only" for r in out),
        "abstentions":dict(sorted(reasons.items())),
        "original_universe_preserved":len(out)==len(candidates),
        "original_source":source,
        "individual_candidate_ledger":out,
        "actual_2024_results_consulted":False,
        "pre_game_source_truth_independently_verified":False,
        "is_a_production_prediction":False,
        "tier1_tier2_authorized":False,
    }
