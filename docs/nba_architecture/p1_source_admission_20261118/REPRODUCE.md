# Reproduction

Authority PA-V25-MASTER-2026-11-09 / v1.1. Python3.12, Poppler pdftotext,
NumPy2.3.5/SciPy1.17.0/jsonschema. From repository root:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=.:tests/nba_architecture python -m unittest tests.nba_architecture.test_p1_listed_source_v1 tests.nba_architecture.test_p1_capture_v1 -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=.:tests/nba_architecture python -m unittest discover -s tests/nba_architecture -v
python docs/nba_architecture/p1_source_admission_20261118/independent/probe.py
sha256sum -c docs/nba_architecture/p1_source_admission_20261118/SHA256SUMS
```

Owner raw commands/stdout/stderr and exact tested SHA: owner/receipt.json.
owner/run.py writes outputs; use a disposable checkout or copy script to a new
output directory to preserve committed evidence. The pre-install failure is
intentional and retained. Earlier manifest attempts used the wrong cwd; corrected
root checks verify both original manifests, and all failures remain preserved.

Public API: p1_listed_source_v1.listed_population_receipt(pdf_bytes,
normalized_pdf_receipt, espn_bytes, exact_espn_receipt). For preserved PDF receipt,
copy sha256 into raw_sha256 as documented in the original protocol. The ESPN
receipt binding hashes compact sorted-key UTF8 JSON; raw source/body hashes are
SHA256 of exact body bytes. File bindings and SHA256SUMS hash exact repository
file bytes, including newlines. These domains are distinct. Root trust module
pins exact registry bytes; registry pins reader/helper/cohort/contract/profile.
Changing labels, resealing attacker bytes or naming a reviewer cannot admit them.

The wrapper returns whole-bundle rejection counts. Invalid JSON has an unknown
row denominator, never zero; full eligible roster size remains unknown. Source
clocks are supplied only where recorded by actual capture; ESPN first capture
has start/end, no original ingestion observation, so ingestion stays null. HTTP
Date is preserved in headers and never promoted to source publication.

Fresh capture helper: p1_capture_v1.capture(url, new_directory). It records real
start/end and local ingestion; create-only directories preserve old receipts.
HTTP errors retain body/status/headers. Captures are UNADMITTED and never create
pregame availability or correction-completeness assertions. The demonstrated
fresh historical fetch is modern corroboration, not a prospective cohort.

Rollback: discard isolated branch. Existing G0, accounting repairs, original n32
red, old admission APIs, frozen forecasts and all prior packets remain unchanged.
