# Restricted demonstration execution

Authority PA-V25-MASTER-2026-11-09 / v1.1. Policy113fcce2, separate policy review
2b780855, exact executable/tested SHA a8696fccb1eba992f1249e94c45e84bab558a836.
PR177 parent77fbc4b2 preserved. Old admission roots/readers remain unchanged.

From repository root, Python3.12 with prior NumPy/SciPy/jsonschema dependencies
and Poppler pdftotext:

```sh
PYTHONPATH=. python -m unittest tests.nba_architecture.test_p1_bounded_demo_v1 -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=.:tests/nba_architecture python -m unittest discover -s tests/nba_architecture -v
sha256sum -c docs/nba_architecture/p1_bounded_exclusions_20261118/SHA256SUMS
```

owner/run.py reproduces actual positive/late/altered source outputs and both
suites. It writes outputs; run in disposable checkout to preserve committed
receipts. owner/receipt.json records argv/exits/exact tested SHA and raw streams.
Public API is p1_bounded_demo_v1.demonstrate(pdf,pdf_receipt,espn,espn_receipt).
Original source inputs are the unchanged fixed bytes admitted in PR177 under
docs/nba_architecture/substantive_remediation_20261117/source_search/.
Read nba_pdf.raw, nba_pdf.receipt.json (copy sha256 to raw_sha256), espn2018.raw
and espn2018.receipt.json. All input/output and code hashes cover exact file
bytes; canonical receipt bindings retain PR177's separate compact sortedJSON
domain. No new source authenticity or correction ancestry is asserted.

Actual26rows =24included ordinary PLAYED +2explicit DNP +0excluded. This is a
working restricted historical content demonstration. It does not show a real
outlier removed or quantify selection bias beyond these listed rows. Synthetic
policy boundaries are separate controls. Altered/late inputs reject the whole
26-row source before any exclusions. Every admitted original row is preserved
in source_row and in source_admission; target eligible roster count stays null.

B-P1-01 and B-P1-02 remain BLOCKED; G1 NO-GO. This is no gate amendment, original
pregame reconstruction, fitted forecast or scoring experiment. No model/weight
fitting, holdout scoring/decompression, schedule change, merge/deployment/Tier
promotion. Rollback: discard isolated branch.
