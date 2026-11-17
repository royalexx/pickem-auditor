# F-P5-01 author execution

Code SHA: `b58a1a085ccaf34d9963622a019b643557889647`.
Receipt: `../P5_F_P5_01_EXECUTION_RECEIPT_20261117.json`.
All 398 tests passed with zero failures, errors or skips: 267 G0, 48 P5,
83 unchanged independent P6 controls. Counts include inherited regressions;
they are not 398 new cases or observed NBA games.

The original P6 probe was extracted without alteration from QA audit head
`31435bd571ae1b4a9b7f1e1bbf05e55cef61126f` and has SHA-256
`fa8012e260a21caacb2fcebadc02a2deddaf957bc4425b8128dcae2c83ba9e52`.
The five `tests/nba_architecture/test_p6_*.py` controls were extracted from
that same head to an external directory. Their byte hashes match PR #168.
No P6 or G0 file was copied into or modified in the P5 branch.

From a clean checkout, extract the five P6 test files and probe from that audit
head to an external temporary directory. Set `PYTHONPATH` to include the P5
repository root and its `tests/nba_architecture` directory (the latter supplies
P6's existing `golden_v2` imports). Run:

```sh
python -m unittest discover -s tests/nba_architecture -v
python -m unittest discover -s tests/nba_c -v
python -m unittest discover -s /absolute/path/to/extracted_p6_controls -v
python /absolute/path/to/extracted_probe.py P5
```

The initial external P6 invocation omitted `tests/nba_architecture` from the
import path and failed discovery with `ModuleNotFoundError: golden_v2`.
The corrected invocation ran all 83 controls successfully; no control source
was changed. Earlier development runs also caught and corrected a syntax typo,
an integer-PMF traversal TypeError, and one rejection-code assertion mismatch.
The archived final logs here are from the clean, committed code SHA above.

`P6_negative_probe_before.log` documents the original fail-open at the prior
owner SHA. `P6_negative_probe.log` documents both quarantine rejection and exact
backdated-date `INVALID_CHRONOLOGY` rejection, plus four independent math oracles:

| Oracle | Result |
|---|---:|
| Poisson(1), CRPS at 0 | 0.47622238819739127 |
| NB(2, 0.5), CRPS at 0 | 0.962962962962963 |
| Two-atom joint ES at (0,2) | 1.2928932188134525 |
| Two-atom joint VS_0.5 at (0,2) | 2.0000000000000004 |

The joint law is 0.5 at (0,0) and 0.5 at (2,2). Targets are respectively
0.47622238819739127, 26/27, 2-sqrt(2)/2 and 2; absolute tolerance 1e-11.
Full-count scores, PIT/coverage, predictive-mean MAE/RMSE/bias, zero/tails,
coherent-scenario rejection, cached simplex optimization, block bootstrap and
5,000/20,000 precision controls pass. No historical data access or fitting.

This is author-side reuse of independent controls, **not independent P6
verification**. P6 must fetch and audit the exact final PR head recorded in the
PR update. Authentic P1/P2/P4 integration remains blocked and G1/G2 are not
self-approved. All changed paths are P5 source, tests or documentation.
