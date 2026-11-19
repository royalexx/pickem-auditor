# Independent P4 reproduction

```bash
OPENBLAS_NUM_THREADS=1 PYTHONPATH=. python docs/nba_architecture/p1_p5_handoffs_20261119/independent/p4/probe.py
OPENBLAS_NUM_THREADS=1 python -m unittest tests.nba_architecture.test_subset_p4_v1 -v
sha256sum -c docs/nba_architecture/p1_p5_handoffs_20261119/independent/p4/SHA256SUMS
```

The probe consumes original P1/P3 wires from independent/p3/final_05b44764 and
rederives P2 from the original source/capture/cohort. P3 native computation in
readback uses the recorded original23:05:41forecast context; it is deterministic
verification, not a new live forecast or source backdate. Source files/model/code
remain unchanged. Synthetic forgery controls are clearly separated from genuine
actual minute laws. p4.json canonical hash is not general source/model admission.
No statistic PMF or joint scenario is generated. Raw file hashes below cover
exact disk bytes; source/P3/native artifact hash domains retain their prior meaning.
