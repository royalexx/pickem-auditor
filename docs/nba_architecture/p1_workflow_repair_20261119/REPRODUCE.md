# Reproduce selector repair and conditional workflow decisions

Exact final tested implementation5af4072cf62951ec6cc5e21f0e1f82bcd452067c.
Python3.12, Poppler pdftotext; prior architecturedependencies required for fullsuite.

```sh
python -m unittest tests.nba_architecture.test_p1_injury_report_v2 -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=.:tests/nba_architecture python -m unittest discover -s tests/nba_architecture -v
sha256sum -c docs/nba_architecture/p1_workflow_repair_20261119/SHA256SUMS
```

Genuine executed publicCLI argv/exits are in owner/html_actual_command.json; stdout,
stderr and original rawindex/PDF/receipts preserved under owner/. Reproducing HTTP
acquisition requires a NEW explicit future freeze and NEW outputdirectory:

```python
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
from v2.nba_architecture.p1_injury_report_v2 import capture_latest
output = Path(tempfile.mkdtemp(prefix="p1-injury-v2-")) / "capture"
result = capture_latest(freeze_at=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(), output=output)
print(output, result["status"], result["errors"])
```

The example computes a new capture window; it cannot replay
original observations or certify a game forecast. owner/html_actual_command.json has
the exact original executed values. Do not overwrite committed evidence.

Selector scans completeuniquePDFURLs found in rawHTML (all occurrences separately
counted). Every eligible/rejecteduniqueURL remains in ledger; unsupported guides,
future clocks, invalidsource URLs and stale reports stay counted. Winner uses
parsed reportdatetime in America/New_York, not string sorting. Age60min is explicit
research freshness bound, not empirical publication-latency evidence. Indexactual
ingestion<=inputfreeze, reportactualingestion<=freeze, printedheader==filename
source-declared clock. Neither filename nor header is authenticated publication.
NewestHTTPfailure retains denial/error bytes and blocks; no stalepositivefallback.
All captures remain UNADMITTED. Final10selector methods and551architecture methods pass. Earlier7/8method and548/549suite receipts plus original malformed-href reds remain historical records. No source purity/legaleligibility inference.

Historical test uses unchanged oldcaptured index to show correct6:30PMselection;
that is deterministic selector replay, not recovery of missed6:30PMbody. Current
realreport capture establishes only current observed sourcebytes/header.
Rawbody hashes, sourcefile hashes and topfile hashes cover exact bytes; clocks
and canonicalJSONreceipt bindings from prior roots remain separate domains.
Old wrongreports, originalselector, frozenforecasts and originalgate evidence
remain unchanged. Independent eligibility/scope decision lives in independent/.
