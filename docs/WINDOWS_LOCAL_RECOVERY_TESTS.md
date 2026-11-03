# Windows local rerun — November 2 recovery branch

This is an **offline test-only** procedure. It does not train models, use API
keys, activate scheduled GitHub Actions, or promote any Tier or calibration
certificate.

## Why the first user run failed

The supplied Windows log (Python 3.13 from WindowsApps) reported 14 tests:
10 passes, 1 persistence fixture failure and 3 errors.

- `test_nov2_calibration_proposals` was interrupted while importing
  `unittest.mock` -> `asyncio` (`KeyboardInterrupt`). The test also had an
  independent tuple-as-context-manager bug, fixed on this branch.
- Both xarray tests then encountered partially initialized `asyncio` modules
  (`NameError: coroutines/base_events`). They were **not evaluated**. Use a
  clean Python process/isolated venv, and don't count those as numerical failures.
- The isolated Git persistence fixture mistakenly committed forecasts to
  `main` before the first save, failed to copy the required transition helper,
  and used escaped literal backslash-n values instead of proper JSONL newlines.
  The fixture now creates a real data-branch first save, with stable LF bytes
  across Git for Windows and improved stdout/stderr failure diagnostics.

## On the Dell (PowerShell)

```powershell
# Run from the root of your existing pickem-auditor checkout
git switch review/nov2
git pull --ff-only
py -0p
```

Use **Python 3.12** for parity with `.github/workflows/ci.yml`, if installed.
Do not mix the old Windows Store Python 3.13 user-site packages with this venv.

```powershell
py -3.12 -m venv .venv-recovery
$py = ".\.venv-recovery\Scripts\python.exe"
& $py -m pip install -r requirements-nfl-inference.txt
& $py -m pip install xarray
$env:OPENBLAS_NUM_THREADS = "1"
$env:OMP_NUM_THREADS = "1"

# Confirm fresh asyncio/xarray imports before running the suite
& $py -c "import asyncio; from unittest.mock import patch; import xarray; print('IMPORTS_OK')"

# Separate Python processes prevent interrupted imports contaminating
# unrelated test modules. Each command is read-only to repo source/history.
& $py -m unittest discover -s tests -p test_nov2_calibration_proposals.py -v
& $py -m unittest discover -s tests -p test_nov2_recovery_numerics.py -v
& $py -m unittest discover -s tests -p test_nov2_shadow_persistence.py -v
& $py -m unittest discover -s tests -p 'test_nov2_*.py' -v
```

Git for Windows **Git Bash**, `git`, and a normal executable `python` on
the Bash PATH are needed by `shadow_store.sh`. A Windows Python venv may be
exposed differently in Git Bash; the improved assertion prints both stdout
and stderr if the save still fails. Never hide errors or disable the immutable
forecast/certificate guards to get a green test.

If Python 3.12 is unavailable, run `py -0p` and install an isolated 3.12
interpreter before doing the final compatibility check. Python 3.13 can be
tried in a clean venv, but a failed import is an environment result and cannot
certify the Bayesian numerical suite.

Only after targeted tests pass, run
`& $py -m unittest discover -s tests -v`. Full suite may require additional
packages documented in repository requirements. Keep PR #55 draft until the
full suite and clean-runner persistence test are verified.
