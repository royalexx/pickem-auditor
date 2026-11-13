"""C03 independently verifiable transport attestation and raw ESPN claims.

A signed receipt binds actual collector TLS response body bytes to the
collector's UTC acquisition clock. HMAC is collector authentication, NOT
provider publication proof. Missing secret, source, clock or crosswalk => D.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from c03_context_cohorts import (CohortError, canonical, _utc, _safe_archive,
                                 capture_live_http_body, verify_receipt, SCHEMA_CLAIM)

SCHEMA="pickem_c03_collector_capture_hmac_v1"
SECRET_ENV="PICKEM_C03_COLLECTOR_HMAC_KEY_HEX"
HOSTS={"espn":{"site.api.espn.com"},
       "nhl_official":{"api-web.nhle.com","api.nhle.com"}}
FIELDS=("schema","source_id","source_namespace","source_kind","body_bytes",
        "body_sha256","archive_path","source_url","observed_at","received_at",
        "http_status","clock_semantics","source_publication_truth_verified")


def _key():
    value=os.environ.get(SECRET_ENV)
    if not isinstance(value,str) or len(value)!=64:
        raise CohortError("C03_COLLECTOR_SIGNING_KEY_UNAVAILABLE")
    try:key=bytes.fromhex(value)
    except ValueError as exc:
        raise CohortError("C03_COLLECTOR_SIGNING_KEY_INVALID") from exc
    if len(key)!=32 or key in (bytes(32),bytes([255])*32):
        raise CohortError("C03_COLLECTOR_SIGNING_KEY_INVALID")
    return key


def _signed_body(receipt):
    if not isinstance(receipt,dict) or any(k not in receipt for k in FIELDS):
        raise CohortError("C03_COLLECTOR_PROOF_FIELDS_MISSING")
    return {k:receipt[k] for k in FIELDS}


def _mac(receipt,key):
    return hmac.new(key,canonical(_signed_body(receipt)),hashlib.sha256).hexdigest()


def capture_signed_live(url,*,archive_root,source_namespace,source_id,
                        input_cutoff_at,event_start_at,timeout=12):
    """Only live direct-HTTPS capture can mint a transport signature."""
    key=_key()
    uri=urlsplit(url)
    if (uri.scheme!="https" or uri.username or uri.password or
            source_namespace not in HOSTS or uri.hostname not in HOSTS[source_namespace]):
        raise CohortError("C03_LIVE_HOST_NOT_ALLOWLISTED")
    if any(token in uri.query.lower() for token in ("api_key=","apikey=","token=","secret=")):
        raise CohortError("C03_LIVE_SECRET_QUERY_REFUSED")
    cutoff=_utc(input_cutoff_at,"cutoff")
    event=_utc(event_start_at,"event_start")
    if not datetime.now(timezone.utc)<cutoff<event:
        raise CohortError("C03_CAPTURE_CUTOFF_EXPIRED")
    receipt=capture_live_http_body(url,archive_root=archive_root,
             source_namespace=source_namespace,source_id=source_id,timeout=timeout)
    if _utc(receipt["received_at"],"received_at")>cutoff:
        raise CohortError("C03_SOURCE_COMPLETED_AFTER_CUTOFF")
    if receipt["source_url"]!=url:
        raise CohortError("C03_SOURCE_URL_DRIFT")
    receipt["transport_attestation"]="collector_signed_tls_bytes_v1"
    proof={"schema":SCHEMA,"receipt_fields":_signed_body(receipt),
           "hmac_sha256":_mac(receipt,key)}
    raw=canonical(proof)
    sha=hashlib.sha256(raw).hexdigest()
    path_rel="c03_collector_receipts/"+sha+".json"
    path=_safe_archive(archive_root,path_rel)
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open("xb") as f:f.write(raw)
    except FileExistsError:pass
    if path.read_bytes()!=raw:
        raise CohortError("C03_CAPTURE_PROOF_MUTATED")
    receipt["collector_proof_archive_path"]=path_rel
    receipt["collector_proof_sha256"]=sha
    return receipt


def verify_signed_capture(receipt,*,archive_root,freeze,event_start):
    """Independent verifier rechecks HMAC, raw bytes, and acquisition cutoff."""
    key=_key()
    doc=verify_receipt(receipt,archive_root=archive_root,
                       freeze=freeze,event_start=event_start)
    if receipt.get("transport_attestation")!="collector_signed_tls_bytes_v1":
        raise CohortError("C03_LIVE_TRANSPORT_UNATTESTED")
    sha=receipt.get("collector_proof_sha256")
    if not isinstance(sha,str) or len(sha)!=64:
        raise CohortError("C03_CAPTURE_PROOF_MISSING")
    path=_safe_archive(archive_root,receipt.get("collector_proof_archive_path"))
    if not path.is_file():raise CohortError("C03_CAPTURE_PROOF_ARCHIVE_MISSING")
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=sha:
        raise CohortError("C03_CAPTURE_PROOF_HASH_MISMATCH")
    try:p=json.loads(raw)
    except (ValueError,UnicodeDecodeError) as e:
        raise CohortError("C03_CAPTURE_PROOF_JSON_INVALID") from e
    if p.get("schema")!=SCHEMA or p.get("receipt_fields")!=_signed_body(receipt):
        raise CohortError("C03_CAPTURE_PROOF_DRIFT")
    if not hmac.compare_digest(str(p.get("hmac_sha256")),_mac(receipt,key)):
        raise CohortError("C03_CAPTURE_SIGNATURE_INVALID")
    return doc


def claim_from_espn_summary(receipt,*,archive_root,event_id,team_id,player_id,
                            kind="subject_status",freeze,event_start):
    """Exact summary JSON-pointer link: ESPN pregame roster active boolean."""
    if receipt.get("source_namespace")!="espn":
        raise CohortError("C03_ESPN_SOURCE_REQUIRED")
    doc=verify_signed_capture(receipt,archive_root=archive_root,
                              freeze=freeze,event_start=event_start)
    header=doc.get("header") if isinstance(doc,dict) else None
    if not isinstance(header,dict) or str(header.get("id"))!=str(event_id):
        raise CohortError("C03_ESPN_EVENT_ID_MISMATCH")
    comps=header.get("competitions") or []
    if not comps or (comps[0].get("status") or {}).get("type",{}).get("state")!="pre":
        raise CohortError("C03_ESPN_NOT_PREGAME")
    if kind not in ("subject_status","teammate_status"):
        raise CohortError("C03_CLAIM_KIND_INVALID")
    match=[]
    for i,roster in enumerate(doc.get("rosters") or []):
        if str((roster.get("team") or {}).get("abbreviation"))!=str(team_id):
            continue
        for j,entry in enumerate(roster.get("roster") or []):
            athlete=entry.get("athlete") or {}
            if str(athlete.get("id"))!=str(player_id):continue
            if type(entry.get("active")) is not bool:
                raise CohortError("C03_ESPN_ACTIVE_BOOL_MISSING")
            match.append((i,j,entry["active"]))
    if len(match)!=1:
        raise CohortError("C03_ESPN_IDENTITY_AMBIGUOUS_OR_ABSENT")
    i,j,active=match[0]
    prefix=f"/rosters/{i}"
    return {"schema":SCHEMA_CLAIM,"source_id":receipt["source_id"],
            "kind":kind,"event_id":str(event_id),"team_id":str(team_id),
            "player_id":str(player_id),"event_id_path":"/header/id",
            "team_id_path":prefix+"/team/abbreviation",
            "player_id_path":prefix+f"/roster/{j}/athlete/id",
            "value_path":prefix+f"/roster/{j}/active",
            "value_transform":"boolean_active_to_status_v1",
            "value":"active" if active else "out"}
