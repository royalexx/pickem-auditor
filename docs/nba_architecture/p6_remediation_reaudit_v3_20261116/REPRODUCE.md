# Independent P6 v3 reproduction

G1 remains **NO-GO**. The runner's successful exit means it reproduced the complete expected finite evidence, including the two new owner failures; it is not a G1 pass. All forecasts, counts, fits and optimizer examples in these test programs are synthetic. The archive-byte step hashes compressed bytes without decompressing or scoring outcomes.

Use Python 3.12 with NumPy 2.3.5, SciPy 1.17.0 and jsonschema 4.26.0. Create a disposable virtual environment if those versions are not already available. No PyMC/NUTS or paid service is required.

From the new QA branch checkout, fetch the exact source objects and run the isolated harness. These commands create fresh directories and refuse to overwrite a prior output directory:

```bash
python - <<'PY'
import importlib.util, subprocess
from pathlib import Path
path=Path('scripts/nba_p6_g1_reaudit_runner_v3_20261116.py')
spec=importlib.util.spec_from_file_location('p6_runner',path)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
shas=set(m.PINS.values())|set(m.OLD.values())|{r[1] for r in m.UPSTREAM}|{m.QA_PIN,m.G0}
subprocess.run(['git','fetch','origin',*sorted(shas)],check=True)
PY
python scripts/nba_p6_g1_reaudit_runner_v3_20261116.py \
  --repo "$PWD" \
  --work-root "$PWD/work/p6-v3" \
  --output "$PWD/work/p6-v3-results"
```

`runner_results.json` reports exact owner heads, full commands, test counts, actual/expected exits and raw output digests. The published runner was itself executed successfully through **32 commands**; complete raw second-run logs are in `runner_validation/`. Its expected P2/P5 v3 exits are 2. It also checks the exact failing case names, so a different failure is not accepted as successful reproduction. Dedicated suite counts are 331/267/306/321/267 G0+owner architecture tests, five separate 83-test P6 executions, 9 P1 preflight, 30 S and 48 C tests, plus four accepted upstream suites. P4's optional declared-pin compatibility runner repeats overlapping suites.

The immutable original negative probe is verified before use:

```bash
sha256sum scripts/nba_p6_g1_owner_negative_probes_20261116.py
```

Expected raw digest is `fa8012e260a21caacb2fcebadc02a2deddaf957bc4425b8128dcae2c83ba9e52`. Historical prior-head P1/P5 probes exit 2; their current-head probes and separate green-after-fix wrappers exit 0. P2's original witness-free fixture rejects at both heads; legal two-OT acceptance belongs to the new witnessed tests.

To rerun just the independent adversarial program, execute it by absolute path from the exact corresponding owner checkout, with `PYTHONPATH=.:tests/nba_architecture` and a family argument P1, P2, P3, P4 or P5. The program prints valid JSON, using the string `Infinity` for infinite NLPD. It never writes owner implementation files.

For additional boundary and benchmark evidence, preserve the QA root before entering an owner checkout:

```bash
p6_qa_root="$PWD"
cd "$p6_qa_root/work/p6-v3/P3"
PYTHONPATH=.:tests/nba_architecture OPENBLAS_NUM_THREADS=1 \
  python "$p6_qa_root/docs/nba_architecture/p6_remediation_reaudit_v3_20261116/latest_interop_reproducer.py" \
  --p2-root "$p6_qa_root/work/p6-v3/P2"
cd "$p6_qa_root/work/p6-v3/P1"
PYTHONPATH=.:tests/nba_architecture OPENBLAS_NUM_THREADS=1 \
  python "$p6_qa_root/docs/nba_architecture/p6_remediation_reaudit_v3_20261116/latest_P1_boundaries_reproducer.py" \
  --p2-root "$p6_qa_root/work/p6-v3/P2" \
  --p3-root "$p6_qa_root/work/p6-v3/P3"
cd "$p6_qa_root/work/p6-v3/P4"
OPENBLAS_NUM_THREADS=1 python -m research.nba_p4_integration.benchmark \
  --output work/independent-p6-benchmark-v3
cd "$p6_qa_root"
```

Latest P3-to-P2 consumption should work on synthetic fixtures; latest authentic P1 source routes must reject/abstain. P4's declared consumer deliberately materializes its **old** pinned P2/P3 source. It cannot be counted as latest-head integration. To reproduce that incompatibility without bypassing pins:

```bash
python - <<'PY'
import shutil, subprocess, os
from pathlib import Path
root=Path.cwd(); combined=root/'work/p6-latest-modules/v2'
combined.mkdir(parents=True,exist_ok=False)
shutil.copytree(root/'work/p6-v3/P2/v2/nba_s_family',combined/'nba_s_family')
shutil.copyfile(root/'work/p6-v3/P3/v2/nba_o_family.py',combined/'nba_o_family.py')
code="from v2.nba_joint.integration import load_upstream; load_upstream("+repr(str(combined))+")"
r=subprocess.run(['python','-c',code],cwd=root/'work/p6-v3/P4',env=dict(os.environ,PYTHONPATH='.'),capture_output=True,text=True)
print(r.stderr)
assert r.returncode!=0 and 'J_UPSTREAM_CODE_PIN_P2' in r.stderr
PY
```

For the independent compressed archive-byte check, fetch the exact coverage/warehouse commits, then run the provided read-only verifier. It does not parse the underlying player outcomes:

```bash
git fetch origin 53c01a9eabb9ed09b5c3186eae0d086b07bcc891 97a8bb566826afe5a3e5a7b8c632043d8a1dca24
python docs/nba_architecture/p6_remediation_reaudit_v3_20261116/byte_verification_reproducer.py \
  --repo "$PWD" --output "$PWD/work/p6-byte-check-v3"
```

Expected: 99 files, 99 matching compressed digests, 39,916,715 bytes, `decompressed=false`, `historical_availability_certified=false`. No pregame chronology claim follows from these hashes.

Root repository import failure can be inspected without executing unrelated historical/modeling test bodies. From the pinned P2 checkout:

```bash
python - <<'PY'
import unittest
loader=unittest.TestLoader();suite=loader.discover('tests')
print('test objects:',suite.countTestCases(),'import errors:',len(loader.errors))
print(''.join(loader.errors))
raise SystemExit(2 if loader.errors else 0)
PY
```

Expected: 1,652 objects and 10 `golden_v2` import errors. Do not suppress these or present this as green repository-wide CI.

Logs contain paths and runtimes specific to their disposable environment. Their raw SHA-256 receipts intentionally bind those exact bytes. Compare stable fixture/scenario/model digests and semantic outcomes across environments; a runtime-dependent stdout digest need not equal a later rerun. Historical report stdout may include extra blank lines; fresh before/after receipts retain their own raw digests and do not replace old ones.

All failed/blocked criteria, exact responsible owner SHA and minimal requirements are in `criterion_ledger.json`. The original reports and negative script must remain unchanged. Never use these instructions to open historical scoring, fit historical weights, start G2, deploy or promote Tiers.
