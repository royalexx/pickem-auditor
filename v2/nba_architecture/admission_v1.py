"""Capability-specific source admission, bound to an independently reviewed root.

Historical content admission never grants pregame availability, a fitted model,
complete correction history or roster eligibility. Callers cannot pass a trust
registry, reviewer name, approval flag, hash allowlist or source-status label.
"""
from pathlib import Path
import hashlib
import json

from .v2_contracts import req, instant
from .gamebook_v1 import read_final_box

VERSION='nba-source-capability-admission/1.0.0'
ROOT=Path(__file__).resolve().parents[2]
REGISTRY=ROOT/'docs/nba_architecture/substantive_remediation_20261117/admitted_source_registry.json'
# Root digest is installed only after independent exact-byte review. An empty
# root is deliberately incapable of admitting sources on caller assertions.
REVIEWED_REGISTRY_SHA256='a27161a3a10118304482de090f2b3929808a8450c0ff9bb6b34d115a5c96b6a2'
HISTORICAL_CAPABILITIES=frozenset(('OFFICIAL_PRINTED_DURATION','OFFICIAL_PRINTED_BOX_SCORE','OFFICIAL_PRINTED_DNP_ROWS'))


def admit_gamebook(raw,receipt,*,required_capability):
    req(required_capability in HISTORICAL_CAPABILITIES,'ADMISSION_UNSUPPORTED_CAPABILITY')
    req(REVIEWED_REGISTRY_SHA256 is not None,'ADMISSION_INDEPENDENT_ROOT_UNAVAILABLE')
    registry_raw=REGISTRY.read_bytes()
    req(hashlib.sha256(registry_raw).hexdigest()==REVIEWED_REGISTRY_SHA256,'ADMISSION_ROOT_CHANGED')
    root=json.loads(registry_raw);digest=hashlib.sha256(raw).hexdigest()
    entry=root['sources'].get(digest)
    req(entry is not None and required_capability in entry['capabilities'],'ADMISSION_SOURCE_OR_CAPABILITY_UNREVIEWED')
    req(receipt['url']==entry['url'] and receipt['retrieved_at']==entry['retrieved_at'],'ADMISSION_CAPTURE_IDENTITY')
    proof=ROOT/entry['independent_receipt_path']
    req(proof.is_file() and hashlib.sha256(proof.read_bytes()).hexdigest()==entry['independent_receipt_sha256'],'ADMISSION_REVIEW_RECEIPT_CHANGED')
    extracted=read_final_box(raw,receipt)
    req(hashlib.sha256(Path(__import__('v2.nba_architecture.gamebook_v1',fromlist=['__file__']).__file__).read_bytes()).hexdigest()==entry['reader_raw_sha256'],'ADMISSION_READER_CHANGED')
    return dict(schema=VERSION,capability=required_capability,source_raw_sha256=digest,
        independent_root_sha256=REVIEWED_REGISTRY_SHA256,independent_receipt_sha256=entry['independent_receipt_sha256'],
        source=extracted,original_pregame_available_at=None,original_pregame_certified=False,
        correction_history_complete=None,external_player_identity_admitted=False,
        fitted_model_admitted=False,upstream_training_rows_admitted=0)
