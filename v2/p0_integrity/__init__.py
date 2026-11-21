"""Research-only shared immutable source/forecast/settlement contract gateway.

No production certification, weights, schedules or automatic model promotion.
"""
from .contracts import (AdmissionError, SCHEMAS, VERSION, admit_forecast,
                        canonical_bytes, record, reject_duplicate_records,
                        sha256, validate_record, verify_source_bytes)
from .storage import attest_project_storage, append_immutable, verify_immutable_record
