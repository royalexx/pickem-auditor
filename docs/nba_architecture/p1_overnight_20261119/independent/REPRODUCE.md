# Independent reproduction and byte domains

From repository root, with Python and pdftotext:

```bash
PYTHONPATH=. python docs/nba_architecture/p1_overnight_20261119/independent/transport_probe.py
PYTHONPATH=. python docs/nba_architecture/p1_overnight_20261119/independent/source_probe.py
PYTHONPATH=. python docs/nba_architecture/p1_overnight_20261119/independent/public_mutations.py
sha256sum -c docs/nba_architecture/p1_overnight_20261119/independent/SHA256SUMS
```

transport.stdout verifies original compressed archive bytes after base64 decoding
all72parts. Locally transported chunk text has framing newline whitespace;
first strict concatenation failed (transport-first.stderr retained). Corrected
probe strips only ASCII space/CR/LF at part boundaries then strict-decodes and
checks original externally declared archiveSHA/size before reading tar. No source
body is normalized. Gzip-tar transport hashes are distinct from rawHTTP/PDF body
hashes and exact raw source/code/output file hashes.

source.stdout checks40receipt/body bindings, original pre-freeze ingestion,
36candidates, source-reader25rows/48min/0OT, bounded DNP/unknown populations and
the lexical injury selector discrepancy from the preserved index. Latest report
comparison uses filename wallclock only, with no invented publication/admission.
No additional report is fetched; missing original body remains missing.

public_mutations controls are explicitly synthetic attacks on actual new source
bytes. Legitimate native parsing is demonstrated; old admitted root deliberately
rejects this separate unreviewed game. New admission is not installed.
Actual hosted snapshots were independently read using Deepnote get_run with
snapshotDelivery=blocks for both published runIDs; no hosted run was started or
changed by reviewer. No implementation code was authored or repaired.
