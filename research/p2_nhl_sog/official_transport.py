"""NHL-only C03 capture adapter: official NHL API requires a proper User-Agent.

Uses the existing C03 archive_response, exact signed-body definition, HMAC,
and independent verifier. Does NOT edit shared C03 or mint publisher release
timestamps. No historical backdating or injected raw response is accepted.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import hashlib

from scripts.c03_context_cohorts import (
    CohortError, archive_response, canonical, _utc, _safe_archive, write_archive_bytes
)
from scripts.c03_live_transport import (
    HOSTS, SCHEMA, _signed_body, _key, _mac, verify_signed_capture
)

USER_AGENT = "pickem-auditor-P2-NHL-source/1"
ALLOWED = {"api-web.nhle.com", "api.nhle.com"}


def capture_signed_nhl_p2(url, *, archive_root, source_namespace,
                          source_id, input_cutoff_at, event_start_at,
                          timeout=12):
    """Synchronous signed live HTTPS possession with robust NHL request headers."""
    key = _key()
    uri = urlsplit(url)
    if (uri.scheme != "https" or uri.hostname not in ALLOWED or
            uri.username or uri.password or uri.fragment or
            source_namespace != "nhl_official"):
        raise CohortError("P2_NHL_LIVE_HOST_OR_NAMESPACE_INVALID")
    if any(k in uri.query.lower() for k in
           ("api_key=", "apikey=", "secret=", "token=")):
        raise CohortError("P2_NHL_SECRET_QUERY_REFUSED")
    freeze = _utc(input_cutoff_at, "input_freeze_at")
    start = _utc(event_start_at, "event_start_at")
    if not datetime.now(timezone.utc) < freeze < start:
        raise CohortError("P2_NHL_ORIGINAL_CAPTURE_DEADLINE_EXPIRED")
    observed = datetime.now(timezone.utc)
    req = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": USER_AGENT
    })
    try:
        with urlopen(req, timeout=timeout) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(32_000_001)
    except (OSError, ValueError, TimeoutError) as exc:
        raise CohortError("P2_NHL_ORIGINAL_HTTPS_FAILED:" +
                          type(exc).__name__) from exc
    received = datetime.now(timezone.utc)
    if (status != 200 or "json" not in content_type.lower() or
            not raw or len(raw) > 32_000_000 or received > freeze):
        raise CohortError("P2_NHL_HTTP_JSON_OR_CUTOFF_INVALID")
    stamp = lambda t: t.isoformat().replace("+00:00", "Z")
    receipt = archive_response(
        raw, archive_root=archive_root, source_url=url,
        observed_at=stamp(observed), received_at=stamp(received),
        source_id=source_id, source_namespace="nhl_official",
        http_status=status)
    receipt["transport_attestation"] = "collector_signed_tls_bytes_v1"
    proof = {
        "schema": SCHEMA, "receipt_fields": _signed_body(receipt),
        "hmac_sha256": _mac(receipt, key)
    }
    bytes_proof = canonical(proof)
    proof_sha = hashlib.sha256(bytes_proof).hexdigest()
    proof_rel = "c03_collector_receipts/" + proof_sha + ".json"
    path = _safe_archive(archive_root, proof_rel)
    write_archive_bytes(path, bytes_proof,
                        mismatch="P2_NHL_C03_PROOF_IMMUTABLE_COLLISION", sync=True)
    receipt["collector_proof_archive_path"] = proof_rel
    receipt["collector_proof_sha256"] = proof_sha
    verify_signed_capture(receipt, archive_root=archive_root,
                          freeze=input_cutoff_at, event_start=event_start_at)
    return receipt
