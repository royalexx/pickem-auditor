"""Fail-closed idempotent population observation reconciliation.

This module does NOT update Bayes/NUTS or modify observations. It distinguishes
exact serialized-payload retries from identity collisions with nonidentical
payloads. A conflicting group blocks the WHOLE day, not just the group.
"""
from __future__ import annotations
import hashlib
import json
from collections import defaultdict
from pathlib import Path

SCHEMA = "PA_WS1_POPULATION_QUARANTINE_V1"
KEY_FIELDS = ("sport", "stat", "game_id", "player_id")

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()

def identity(row):
    return tuple(str(row[k]) for k in KEY_FIELDS)

def reconcile_population(morning_docs, day, *, validator=None):
    """Returns complete immutable-evidence report and accepted rows; NEVER partial acceptance.

    Validator may raise for a malformed row: this records its digest and an
    invalid-source quarantine. Original metadata is not rewritten or normalized.
    """
    seen = {}
    by_key = defaultdict(dict)
    issues = []
    retries = 0
    receipt_fingerprints = []
    for di, doc in enumerate(morning_docs):
        docsha = digest(doc)
        receipt = doc.get("population_collection_receipt")
        receipt_fingerprints.append({"doc_index": di, "doc_sha256": docsha,
                                     "receipt_sha256": digest(receipt)})
        if not isinstance(receipt, dict) or receipt.get("status") != "complete":
            issues.append({"reason": "MORNING_SOURCES_INCOMPLETE_DO_NOT_UPDATE_POSTERIOR",
                           "doc_index": di, "doc_sha256": docsha})
            # Do not accept rows from a source without a completed receipt.
            continue
        for i, row in enumerate(doc.get("population", [])):
            row_sha = digest(row)
            ptr = {"doc_index": di, "row_index": i, "doc_sha256": docsha,
                   "row_sha256": row_sha,
                   "source_sha256": row.get("source_sha256") if isinstance(row,dict) else None}
            if not isinstance(row, dict):
                issues.append({**ptr, "reason": "POPULATION_ROW_NOT_OBJECT"})
                continue
            try:
                key = identity(row)
                if row.get("game_date") != day:
                    raise ValueError("POPULATION_GAME_DATE_CONFLICT")
                if validator is not None:
                    validator(row)
            except (KeyError, TypeError, ValueError) as exc:
                issues.append({**ptr, "reason": "INVALID_OR_MISDATED_POPULATION_ROW",
                               "error": str(exc)[:160]})
                continue
            by_key[key][row_sha] = row
            prior = seen.get(key)
            if prior is None:
                seen[key] = (row_sha, row)
            elif prior[0] == row_sha:
                retries += 1
            # If row differs, retain BOTH hashes; NEVER pick the last one.
    collisions = []
    for key, variants in sorted(by_key.items()):
        if len(variants) > 1:
            originals = list(variants.values())
            changed = sorted(set().union(*(r.keys() for r in originals)) -
                             {k for k in set().intersection(*(set(r.keys()) for r in originals))
                              if all(r.get(k)==originals[0].get(k) for r in originals)})
            collisions.append({
                "identity": dict(zip(KEY_FIELDS, key)),
                "variant_sha256": sorted(variants),
                "varying_fields": changed,
                "variant_source_hashes": sorted({str(v.get("source_sha256")) for v in originals}),
                "number_of_variants": len(variants)})
    blocked = bool(issues or collisions)
    accepted = [] if blocked else [seen[k][1] for k in sorted(seen)]
    metadata = {"schema": SCHEMA, "date": day,
                "status": "BLOCKED_QUARANTINED" if blocked else "ACCEPTED_EXACT_RETRIES_IDEMPOTENT",
                "document_receipts": receipt_fingerprints,
                "distinct_identity_count": len(seen),
                "exact_retry_count": retries,
                "conflicting_identity_count": len(collisions),
                "malformed_or_incomplete_count": len(issues),
                "quarantine": collisions,
                "rejections": issues,
                "posterior_update_allowed": not blocked,
                "originals_rewritten": False}
    metadata["report_sha256"] = digest(metadata)
    return accepted, metadata

def enforce_population(morning_docs, day, *, validator=None, quarantine_dir=None):
    accepted, report = reconcile_population(morning_docs, day, validator=validator)
    if report["status"] != "ACCEPTED_EXACT_RETRIES_IDEMPOTENT":
        if quarantine_dir is not None:
            dest = Path(quarantine_dir)
            dest.mkdir(parents=True, exist_ok=True)
            path = dest / (day + "-" + report["report_sha256"] + ".json")
            data = (json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\\n").replace("\\\\n","\\n").encode("utf-8")
            try:
                with path.open("xb") as fp:
                    fp.write(data)
            except FileExistsError:
                if path.read_bytes() != data:
                    raise ValueError("IMMUTABLE_QUARANTINE_REPORT_CONFLICT")
        if report["conflicting_identity_count"]:
            raise ValueError("CONFLICTING_DUPLICATE_POPULATION_OBSERVATION:"
                             + report["report_sha256"])
        raise ValueError("MORNING_SOURCES_INCOMPLETE_OR_INVALID_DO_NOT_UPDATE_POSTERIOR:"
                         + report["report_sha256"])
    return accepted

if __name__ == "__main__":
    raise SystemExit("Use reconcile_population() with original morning docs; never train from CLI.")
