# P5 v4 reproduction — synthetic engineering only

Use Python3.12, NumPy2.3.5, SciPy1.17.0 and jsonschema4.26.0. From the P5 owner
branch checkout, fetch the exact owner/audit objects and run:

```bash
git fetch origin 50d2b3874c7c14c9b73bdf13e441957986b88acd fe46965394ea0f48ef5e9da501ec8ca9e441ce47 eb0882b5011f2004c5eaf27cccfdc6297704f261 865bdb8f4770ac28262e49c3b4901cf1d72a22fb ddc60a83f6c9a2b863f5e7a44823bffa3b01e048
OPENBLAS_NUM_THREADS=1 python -m unittest discover -s tests/nba_c -v
OPENBLAS_NUM_THREADS=1 python -m unittest discover -s tests/nba_architecture -v
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 python scripts/nba_p5_native_handoff_verify_v1.py \
  --repo "$PWD" \
  --p1-sha 50d2b3874c7c14c9b73bdf13e441957986b88acd \
  --p2-sha fe46965394ea0f48ef5e9da501ec8ca9e441ce47 \
  --p3-sha eb0882b5011f2004c5eaf27cccfdc6297704f261 \
  --p4-sha 865bdb8f4770ac28262e49c3b4901cf1d72a22fb \
  --output work/p5-native-v4-fresh
```

Expected:76 C tests,267 G0 tests and21 native cases pass. Counts repeat shared
controls; observed NBA games=0. The native runner materializes actual owner
modules from exact Git objects and refuses abbreviations and existing output
directories. Use a new directory for another execution. It never substitutes
live owner worktree files, alternative forecasts or historical training data.

The21 cases include actual P1 source/vault exports, actual P2 S_ONLY, actual P3
O2→P2 played-conditional S_O, preserved unknown unconditional participation
abstention and all96 actual latest P4 same-draw distributions. P4's current
fixture_v2 artifact bytes are used; no old artifact hash is relaxed. P1 native
outcome clocks remain missing and unscored. Real native intake rejects. These
cases are separate from an authentic integrated case, which remains blocked at
missing source admission. Native success is not independent G1 acceptance.

Materialize unchanged P6 controls and probes directly from the audit object:

```bash
python - <<'PY'
from pathlib import Path
import hashlib,subprocess
pin='ddc60a83f6c9a2b863f5e7a44823bffa3b01e048'
root=Path('work/p5-p6-v4-fresh');root.mkdir(parents=True,exist_ok=False)
controls=root/'controls';controls.mkdir()
for name in ('test_p6_g1_specificity_and_scores.py','test_p6_independent_controls.py',
             'test_p6_post_g0_reference_and_boundaries.py','test_p6_red_counterexamples.py',
             'test_p6_math_references.py'):
    (controls/name).write_bytes(subprocess.check_output(['git','show',pin+':tests/nba_architecture/'+name]))
for name in ('nba_p6_g1_owner_negative_probes_20261116.py',
             'nba_p6_g1_remediation_adversarial_v3_20261116.py'):
    raw=subprocess.check_output(['git','show',pin+':scripts/'+name]);(root/name).write_bytes(raw)
    if 'owner_negative' in name:
        assert hashlib.sha256(raw).hexdigest()=='fa8012e260a21caacb2fcebadc02a2deddaf957bc4425b8128dcae2c83ba9e52'
PY
PYTHONPATH=.:tests/nba_architecture OPENBLAS_NUM_THREADS=1 python -m unittest discover -s work/p5-p6-v4-fresh/controls -v
PYTHONPATH=.:tests/nba_architecture OPENBLAS_NUM_THREADS=1 python work/p5-p6-v4-fresh/nba_p6_g1_owner_negative_probes_20261116.py P5
PYTHONPATH=.:tests/nba_architecture OPENBLAS_NUM_THREADS=1 python work/p5-p6-v4-fresh/nba_p6_g1_remediation_adversarial_v3_20261116.py P5
```

Expected:83 P6 controls pass; original P5 probe exits0; v3 P5 program passes10/10
and exits0. The historical nested-outcome red receipt and immutable old fixtures
remain under `../f_p5_02_evidence/`. Original F-P5-01 tests and backdated fixture
remain byte-identical to e46abace.

The raw synthetic native archive retains every actual source, fitted artifact,
code, prediction, G/O/J and separate outcome object from the final run. Its
compressed SHA is in `receipt.json`; code/test/fixture hashes and empty inherited
G0/original-regression diffs are separately inventoried. Verify this directory
with `sha256sum -c SHA256SUMS` from this directory.

The criterion ledger records author-tested repairs and the authentic evidence /
independent contract prerequisite B-P5-01 as BLOCKED. Only separate P6 can award
independent acceptance. G2, historical fitting/scoring, W4, deployment, schedule
changes and Tier promotion remain unauthorized.
