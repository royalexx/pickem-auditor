"""Fail-closed, cross-detached-run-attested project storage for NBA/NHL P0.

Does not infer durability from /work existence, resolved-prefix equality, or
NBA_PILOT_DURABLE_STORAGE_ATTESTED. Root must be the approved Deepnote project
alias, with original bytes independently verified from two separate executions.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import hashlib
import json
import os

from .contracts import AdmissionError, canonical_bytes, utc, validate_record

PROJECT_ID="9cc31536-93be-44db-bdeb-06fba3f61410"
APPROVED_ROOT=Path("/work")
PROOF="research/p0_integration_integrity/probe_20261121"
EXPECTED_WRITER_RECEIPT_SHA="e5fe4929c23f8b7aac9680d59e30083ee891ed46755322fb3e8a4220e7140c13"
NAMESPACES={
 "SourceReceipt":"sources","PregameFeatureSnapshot":"features",
 "ModelArtifact":"models","ForecastSnapshot":"forecasts","MarketQuote":"quotes",
 "OutcomeRecord":"outcomes","SettlementRecord":"settlements",
 "TrainingUpdateReceipt":"training","ExperimentManifest":"experiments"
}

def _reject(message):
    raise AdmissionError(message)

def _safe_path(requested, *, existing=True):
    logical=APPROVED_ROOT
    path=Path(requested)
    if not path.is_absolute() or ".." in path.parts:
        _reject("UNAPPROVED_LOGICAL_PATH")
    if path!=logical and logical not in path.parents:
        _reject("UNAPPROVED_LOGICAL_ROOT")
    approved=logical.resolve(strict=True)
    # A verified /work alias may itself be a symlink; nested ones may not.
    rel=path.relative_to(logical)
    current=logical
    for part in rel.parts:
        current=current/part
        if current.is_symlink():
            _reject("UNSAFE_NESTED_SYMLINK")
    canonical=path.resolve(strict=existing)
    if canonical==Path("/tmp") or Path("/tmp") in canonical.parents:
        _reject("EPHEMERAL_STORAGE_FORBIDDEN")
    if canonical!=approved and approved not in canonical.parents:
        _reject("STORAGE_ESCAPE")
    return canonical

def _load_json(path):
    p=Path(path)
    if not p.is_file() or p.is_symlink():
        _reject("ATTESTATION_FILE_MISSING_OR_SYMLINK")
    try:
        return json.loads(p.read_bytes())
    except (OSError,ValueError) as exc:
        raise AdmissionError("ATTESTATION_CORRUPTED") from exc

def attest_project_storage(root="/work", *, project_id=PROJECT_ID):
    """Verify actual archived cross-run SHA proof, not an environment bypass.

    This validates project-specific content recovery and guard-negative tests.
    It cannot by itself prove future backup retention or authenticate the
    external Deepnote run IDs; those are recorded in the P0 audit receipt.
    """
    if project_id!=PROJECT_ID:
        _reject("WRONG_DEEPNOTE_PROJECT_ID")
    canonical=_safe_path(root)
    actual_root=APPROVED_ROOT.resolve(strict=True)
    proof_dir=APPROVED_ROOT/PROOF
    _safe_path(proof_dir)
    write_path=proof_dir/"first_run_receipt.json"
    read_path=proof_dir/"second_run_verification.json"
    writer=_load_json(write_path)
    reader=_load_json(read_path)
    writer_raw=write_path.read_bytes()
    if hashlib.sha256(writer_raw).hexdigest()!=EXPECTED_WRITER_RECEIPT_SHA:
        _reject("WRITER_RECEIPT_SHA_MISMATCH")
    if writer.get("schema")!="PA_P0_STORAGE_WRITE_V1" or \
       reader.get("schema")!="PA_P0_CROSS_RUN_STORAGE_VERIFICATION_V1" or \
       writer.get("project_id")!=PROJECT_ID or reader.get("project_id")!=PROJECT_ID:
        _reject("PROJECT_ATTESTATION_IDENTITY_MISMATCH")
    if writer.get("resolved_root")!=str(actual_root) or \
       reader.get("root_resolved")!=str(actual_root) or \
       writer.get("logical_root")!=str(APPROVED_ROOT):
        _reject("RESOLVED_PROJECT_ALIAS_MISMATCH")
    if reader.get("status")!="CROSS_DETACHED_RUN_STORAGE_PASS" or \
       reader.get("append_only_recovery")!="PASS" or \
       reader.get("writer_receipt_sha256")!=EXPECTED_WRITER_RECEIPT_SHA:
        _reject("CROSS_RUN_ATTESTATION_NOT_PASSED")
    if utc(writer["written_at_utc"])>=utc(reader["read_at_utc"]):
        _reject("CROSS_RUN_TIME_INVALID")
    if not writer.get("no_clobber") or not isinstance(reader.get("rejections"),dict) or \
       not {"tmp","unverified_mount","symlink_escape","inner_symlink","overwrite"}.issubset(reader["rejections"]):
        _reject("MISSING_NEGATIVE_STORAGE_TESTS")
    for relfield,digestfield in [
        ("payload_relpath","payload_sha256"),
        ("preexisting_anchor_relpath","preexisting_anchor_sha256")
    ]:
        rel=writer[relfield]
        if not isinstance(rel,str) or rel.startswith("/") or \
           ".." in Path(rel).parts or "\\" in rel:
            _reject("UNSAFE_ATTESTATION_SOURCE_PATH")
        file=APPROVED_ROOT/rel
        _safe_path(file)
        if not file.is_file() or file.is_symlink():
            _reject("ATTESTATION_SOURCE_GONE")
        actual=hashlib.sha256(file.read_bytes()).hexdigest()
        if actual!=writer[digestfield] or actual!=reader[("payload_sha256_verified" if relfield=="payload_relpath" else "anchor_sha256_verified")]:
            _reject("CROSS_RUN_HASH_CHANGED:"+relfield)
    if (APPROVED_ROOT/writer["payload_relpath"]).stat().st_size!=writer["payload_bytes"]:
        _reject("ATTESTATION_PAYLOAD_LENGTH_CHANGED")
    # st_dev and st_ino vary between Deepnote detached mount namespaces.
    # Do not require equality of those process-local diagnostic identifiers.
    return {"status":"STORAGE_ATTESTED_FOR_PROJECT_PATH",
            "logical_root":str(APPROVED_ROOT),"resolved_root":str(actual_root),
            "requested":str(root),"verified_path":str(canonical),
            "project_id":PROJECT_ID,
            "writer_receipt_sha256":EXPECTED_WRITER_RECEIPT_SHA,
            "payload_sha256":writer["payload_sha256"],
            "source_anchor_sha256":writer["preexisting_anchor_sha256"],
            "reader_receipt_sha256":hashlib.sha256(read_path.read_bytes()).hexdigest()}

def append_immutable(root, kind, obj, *, project_id=PROJECT_ID):
    """Content-addressed write: O_EXCL/no symlink, atomic failure, fsync.

    Existing identical content is idempotent; conflicting content is rejected.
    No edit/delete/supersession in place is possible through this API.
    """
    attest_project_storage(root,project_id=project_id)
    validate_record(kind,obj)
    body=canonical_bytes(obj)
    digest=hashlib.sha256(body).hexdigest()
    base=APPROVED_ROOT/"research"/"p0_integrity_store"/NAMESPACES[kind]
    base.mkdir(parents=True,exist_ok=True)
    _safe_path(base)
    path=base/(digest+".json")
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"):
        flags|=os.O_NOFOLLOW
    try:
        fd=os.open(path,flags,0o640)
    except FileExistsError:
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            _reject("APPEND_ONLY_COLLISION_OR_CORRUPTION")
        return {"status":"IDEMPOTENT_EXISTING","relative_path":str(path.relative_to(APPROVED_ROOT)),
                "sha256":digest}
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        check=hashlib.sha256(path.read_bytes()).hexdigest()
        if check!=digest:
            _reject("WRITE_READBACK_HASH_MISMATCH")
        return {"status":"APPENDED","relative_path":str(path.relative_to(APPROVED_ROOT)),
                "sha256":digest}
    except Exception:
        # Do not delete a partial immutable write: quarantine and investigate.
        raise

def verify_immutable_record(root,kind,sha):
    attest_project_storage(root)
    if not isinstance(sha,str) or len(sha)!=64 or any(c not in "0123456789abcdef" for c in sha):
        _reject("INVALID_RECORD_SHA")
    path=APPROVED_ROOT/"research"/"p0_integrity_store"/NAMESPACES[kind]/(sha+".json")
    _safe_path(path)
    if not path.is_file() or path.is_symlink():
        _reject("IMMUTABLE_RECORD_MISSING")
    body=path.read_bytes()
    if hashlib.sha256(body).hexdigest()!=sha:
        _reject("IMMUTABLE_RECORD_HASH_CHANGED")
    data=json.loads(body)
    validate_record(kind,data)
    return data
