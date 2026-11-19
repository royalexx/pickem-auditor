# Independent reproduction

From repository root with Python/pdftotext:

```bash
PYTHONPATH=. python docs/nba_architecture/p1_subset_acceptance_20261119/independent/handoff_probe.py
PYTHONPATH=. python docs/nba_architecture/narrow_default_20261119/independent/probe.py
PYTHONPATH=. python docs/nba_architecture/p1_overnight_20261119/independent/transport_probe.py
PYTHONPATH=. python docs/nba_architecture/p1_subset_acceptance_20261119/independent/postgame_probe.py
python -m unittest discover -s tests/nba_architecture -p 'test_p1_subset_capture_v1.py' -v
sha256sum -c docs/nba_architecture/p1_subset_acceptance_20261119/independent/SHA256SUMS
```

The first probe writes deterministic `.handoff.json` and read-only `.consumer.json`
for both originalpre snapshots; source files are asserted unchanged. Four methods
include actual inputs and clearly labeled synthetic payload/source attacks.
Subset9method suite is the prior independent public probe rerun; counts overlap
owner/regression cases and are not observed games. Postgame probe rederives all36
states from raw sources and verifies owner's corresponding full ledger.
Transport probe reconstructs original gzip-tar SHA/size and verifies manifests;
transport hash is distinct from raw HTTP/PDF bodies or canonical handoff hashes.

Actual supplementary current public producer command was:

```bash
python scripts/nba_p1_capture_subset.py --cohort docs/nba_architecture/p1_subset_acceptance_20261119/TONIGHT_COHORT.json --output docs/nba_architecture/p1_subset_acceptance_20261119/independent/current_capture
```

Use a new output path to rerun: capture outputs are create-only and source bodies/
clocks may change; after freeze it must record missed collection, not backfill.
This is a current source capture test, not the future scheduled18:05result.
Actual hosted probe snapshot was read-only get_run(snapshotDelivery=blocks), and
notebook code was read via get_notebook. Worker readback bytes match exacthash.
No hosted job, implementation or task was edited by independent reviewer.

Canonical handoff hash domain: sorted-key compact JSON with allow_nan=False,
excluding nothing from exact expected envelope reconstruction. Source_file_hashes
cover rawbody/receipt file bytes; cohort object and default-config SHA are bound
inside canonical payload/requests. Source authentication/model admission is not
granted by this hash. Current capture nestedSHA paths are relative to its own
dir; this independent SHA256SUMS paths are relative to repository root.
