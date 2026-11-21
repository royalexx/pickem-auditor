"""Authentic NHL SOG provider-body capture and verification (P2 only).

An HMAC authenticates what this collector possessed, NOT when a sportsbook
first published it. No archived/offline input can mint a new live receipt.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
import hashlib
import hmac
import json
import os
from v2.p0_integrity.contracts import canonical_bytes, utc
from .source_pipeline import ROOT_NAMESPACE, SourceBlocked, require, stamp, digest, put_once, safe_relative, current_storage

URL = "https://api.prop-line.com/v1/sports/icehockey_nhl/odds"
PROOF_SCHEMA = "PA-P2-NHL-PROVIDER-COLLECTOR-HMAC/1"
KEY_ENV = "PICKEM_C03_COLLECTOR_HMAC_KEY_HEX"


def signing_key():
    from scripts.c03_live_transport import _key
    return _key()


def proof_payload(record):
    return {k: record[k] for k in (
        "schema", "source_url", "source_kind", "received_at", "archive_path",
        "sha256", "bytes", "http_status", "transport_semantics")}


def verify_original_provider(root, record, *, freeze, event_start, key_func=None):
    require(isinstance(record, dict) and record.get("schema") == PROOF_SCHEMA and
            record.get("source_url") == URL and
            record.get("source_kind") == "original_provider_http_bytes",
            "ORIGINAL_PROVIDER_PROOF_MISSING")
    require(record.get("transport_semantics") == "collector_tls_possession_only",
            "ORIGINAL_PROVIDER_CLOCK_CLAIM_UNSUPPORTED")
    received = utc(record["received_at"])
    require(received <= utc(freeze) < utc(event_start),
            "PROVIDER_SOURCE_AFTER_FREEZE")
    require(record.get("http_status") == 200, "PROVIDER_HTTP_FAILED")
    rel = record.get("archive_path")
    require(isinstance(rel, str) and rel.startswith(ROOT_NAMESPACE + "/provider/"),
            "PROVIDER_ARCHIVE_NAMESPACE_INVALID")
    raw = safe_relative(root, rel).read_bytes()
    require(digest(raw) == record.get("sha256") and
            len(raw) == record.get("bytes"), "PROVIDER_BODY_CORRUPT")
    require(isinstance(record.get("hmac_sha256"), str), "PROVIDER_HMAC_MISSING")
    key_func = key_func or signing_key
    expected = hmac.new(key_func(), canonical_bytes(proof_payload(record)),
                        hashlib.sha256).hexdigest()
    require(hmac.compare_digest(record["hmac_sha256"], expected),
            "PROVIDER_HMAC_INVALID")
    proof_path = record.get("proof_archive_path")
    require(isinstance(proof_path, str) and
            proof_path.startswith(ROOT_NAMESPACE + "/provider_proofs/"),
            "PROVIDER_PROOF_PATH_INVALID")
    proof_raw = safe_relative(root, proof_path).read_bytes()
    require(digest(proof_raw) == record.get("proof_sha256") and
            proof_raw == canonical_bytes({k: v for k, v in record.items()
                                         if k not in ("proof_archive_path","proof_sha256")}),
            "PROVIDER_PROOF_CORRUPT")
    return json.loads(raw)


def capture_original_provider(root, *, freeze, event_start, token,
                              opener=urlopen, key_func=signing_key):
    """Direct HTTPS before real event; never run when token or time is missing.

    Opt-in only, so this module does NOT create a second scheduled market
    collector. Existing canonical provider capture is preferable.
    """
    current_storage(root)
    require(datetime.now(timezone.utc) < utc(freeze) < utc(event_start),
            "PROVIDER_LIVE_CAPTURE_DEADLINE_EXPIRED")
    require(isinstance(token, str) and token.strip(), "PROVIDER_TOKEN_MISSING")
    request = Request(URL, headers={"Authorization": "Bearer " + token,
              "Accept": "application/json", "User-Agent": "pickem-auditor-P2/1"})
    with opener(request, timeout=12) as response:
        require(response.status == 200, "PROVIDER_HTTP_NOT_200")
        body = response.read()
    received = stamp(datetime.now(timezone.utc))
    require(utc(received) <= utc(freeze), "PROVIDER_CAPTURE_COMPLETED_TOO_LATE")
    require(body and body[:1] in (b"{", b"["), "PROVIDER_HTTP_BODY_INVALID")
    json.loads(body)
    path = ROOT_NAMESPACE + "/provider/" + digest(body) + ".json"
    put_once(root, path, body)
    record = {"schema": PROOF_SCHEMA, "source_url": URL,
              "source_kind": "original_provider_http_bytes",
              "received_at": received, "archive_path": path,
              "sha256": digest(body), "bytes": len(body),
              "http_status": 200, "transport_semantics": "collector_tls_possession_only"}
    record["hmac_sha256"] = hmac.new(key_func(),
        canonical_bytes(proof_payload(record)), hashlib.sha256).hexdigest()
    proof = canonical_bytes(record)
    proof_path = ROOT_NAMESPACE + "/provider_proofs/" + digest(proof) + ".json"
    put_once(root, proof_path, proof)
    record["proof_archive_path"] = proof_path
    record["proof_sha256"] = digest(proof)
    return record
