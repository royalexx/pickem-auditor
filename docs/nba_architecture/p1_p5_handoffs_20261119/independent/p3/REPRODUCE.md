# Independent P3 reproduction

From repository root:

```bash
OPENBLAS_NUM_THREADS=1 PYTHONPATH=. python docs/nba_architecture/p1_p5_handoffs_20261119/independent/p3/probe.py
OPENBLAS_NUM_THREADS=1 python -m unittest tests.nba_architecture.test_subset_p3_v1 tests.nba_architecture.test_p3_o_family -v
OPENBLAS_NUM_THREADS=1 PYTHONPATH=. python docs/nba_architecture/p1_p5_handoffs_20261119/independent/p3/dnp_credit_red.py
sha256sum -c docs/nba_architecture/p1_p5_handoffs_20261119/independent/p3/SHA256SUMS
```

DNP red intentionally FAILS against immutable b415e8bf Git source; final probe
passes contradictory-DNP-as-UNKNOWN and local denominator preservation controls.
The genuine final execution used actual_probe.py with output argument
`docs/nba_architecture/p1_p5_handoffs_20261119/independent/p3/final_05b44764`;
rerun with a new output dir, and before target only to claim current inference.
It has create-only output; source/cohort/model bytes are unchanged. Current-clock
forecast generation after target must fail; read_p3 replay uses the recorded
original forecast_at context and is explicitly verification, not a new forecast.
The ordinary probe replays original frozen context and performs clearly synthetic
mutation controls, never source recertification or new fitted artifact admission.

Root p3.json/actual_receipt.json/public.* are earlier b415 execution/control bytes;
final_05b44764 and final-public.* are final accepted execution/controls. Both are
retained. Raw SHA domains cover exact model/native/input/receipt bytes; native
forecast provenance's canonical artifact hash is distinct from raw savedmodelSHA.
Model/HTTP originals remain archived outside this independent directory, referenced
by final output source_manifest and P1 raw source-file hashes. No historical
forecast scoring, raw warehouse decompression or replacement fitting is performed.
