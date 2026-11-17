# Fresh full audit v5 reproduction

Expected decision: **26 PASS, 2 FAIL, 8 BLOCKED; G1 NO-GO**.
Standard-suite success reproduces finite controls; the new independent programs
then expose the two reopened correctness criteria. No owner repair occurred.

Use Python3.12 with NumPy2.3.5, SciPy1.17.0, jsonschema4.26.0 and mpmath1.3.0.
Observed versions are in `environment.json`. All fits/optimization inputs are
synthetic. Do not execute historical predictive training/evaluation, decompress
holdout warehouse shards, restart NUTS or change schedules/release settings.

## Exact source

The fresh full runner executed at
`32243941a92559ff11b2640582e4fa6cd0f4ef1e`. Adversaries were committed before
their executions at c70b4fd, d1ca72f, 821aafb and64aa822 (full SHAs below).
The latest complete executable QA source is
**`64aa8228f99f524fbe88c099579e6ba24a5c3eb8`**, containing byte-identical
versions of the earlier executed files. Later audit publication commits add
documentation/evidence only. Exact raw hashes are in
`source_execution_provenance.json` and every individual execution receipt.

From a repository clone, fetch this QA source and all current owner objects:

```bash
git fetch origin \
  64aa8228f99f524fbe88c099579e6ba24a5c3eb8 \
  6dee6e09fa786479dc2e163a33e14257f207b35e \
  50d2b3874c7c14c9b73bdf13e441957986b88acd \
  fe46965394ea0f48ef5e9da501ec8ca9e441ce47 \
  eb0882b5011f2004c5eaf27cccfdc6297704f261 \
  865bdb8f4770ac28262e49c3b4901cf1d72a22fb \
  cb3ff8279bc7f4cc7b86a519a1e386ddbe37ae93 \
  c14b5584c30f8fbca3eb2e51acfaea24c40eff29
git worktree add --detach work/full-audit-qa 64aa8228f99f524fbe88c099579e6ba24a5c3eb8
```

Set absolute paths before changing directory:

```bash
p6_repo="$PWD"
p6_qa="$PWD/work/full-audit-qa"
cd "$p6_qa"
```

Freshly re-fetch PR167/165/166/164/163/171 heads. If any differ from the pinned
population, inspect the drift and build/review a new exact assembly rather than
pretending6dee contains later code. The runner refuses an unequal fresh pin set.
The `initial_pins.json` file records the API observations actually used here.

Fetch missing historical objects in the old runner's PINS/OLD/UPSTREAM/QA_PIN/
G0 constants before reproduction. They are fixed exact commits. Preserve all
old reports and fixtures. The original negative probe remains raw SHA256
`fa8012e260a21caacb2fcebadc02a2deddaf957bc4425b8128dcae2c83ba9e52`.

## Comprehensive fresh authorized execution

Use nonexistent work/output directories:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python scripts/nba_p6_full_blocker_audit_runner_20261117.py \
  --repo "$p6_repo" \
  --work "$p6_qa/work/fresh-disposable" \
  --output "$p6_qa/work/fresh-execution" \
  --pins docs/nba_architecture/p6_full_blocker_audit_20261117/initial_pins.json
```

Expected runner exit0, 26 top-level expected outcomes: current24→boundary5,
historical32, shared17, independent11, actual P4 256-seed study plus all96/
conditioning/independent-reference commands, and opaque99 archive-byte check.
The full runner preserves separate stdout/stderr and hashes. It creates
different disposable assembly roots for commands generating upstream files,
so independent processes do not race over those runtime copies.

Expected shared counts: root1 with PYTHONPATH unset; architecture513; S61;
C76; ten previously inspected, byte-identical offline suites56 methods;
compilation and two Bash syntax checks. No unrelated root test bodies are run.
The offline history bootstrap restores only a newly generated temporary
synthetic archive. The warehouse check hashes compressed historical blobs
without decompression or scoring.

Authentic boundary: exit2 inside the boundary runner,
`OFFICIAL_SOURCE_EVIDENCE_REQUIRED`, attempted26, no snapshot, stop before G.
Synthetic handoff cases are separate. Historical runner exit0 means expected
historical reds/case names were faithfully reproduced; it does not turn the
old failures into accepted owner behavior.

The inherited current-owner runner's `qa_code_commit` field records `--repo`
HEAD. Use the outer full-audit `qa_source_commit`, exact script path/raw hashes
and `source_execution_provenance.json` to identify the executing QA checkout.
This distinction does not alter owner source or a past receipt.

## New red reproductions

The assembly created by the full runner is at
`work/fresh-disposable/assembly_independent`. The baseline below must contain
both actual P1 and P2 modules. A standalone P2 worktree lacks the P1 comparison
module imported by the first adversary.

```bash
p6_assembly="$p6_qa/work/fresh-disposable/assembly_independent"
mkdir -p work/new-red-results
OPENBLAS_NUM_THREADS=1 python scripts/nba_p6_true_zero_display_adversary_20261117.py \
  --owner-root "$p6_assembly" --output work/new-red-results/p2.json
```

Expected exit2. Source c70b4fd7732b810d34357ca4a5dd8b9500cf25fb tests five
cases: two positive15-second controls, known raw0/display0 rejection, and two
red raw0/display0.25 or0.5 acceptances. Its literal `P2_source_sha` field names
the red baseline fe469; actual executed source bytes/hash and assembly SHA are
also recorded. Do not treat that literal as repaired-head provenance. Future
owners must add a separate green regression with actual new source pins.

```bash
OPENBLAS_NUM_THREADS=1 python scripts/nba_p6_raw_display_matrix_20261117.py \
  --assembly "$p6_assembly" --output work/new-red-results/matrix.json
```

Expected exit2; source d1ca72f88dd5ddae1f2c6683f9eb818d14b2f618.
224 synthetic cases cover eight exact clocks ×14 displays ×two retained-stat
profiles. P2 disagrees with actual P1 ten times; P5 prior attachment has three
false rejections and public outcome validation one false acceptance. All are
within the two reopened criteria. Tiny positive raw clocks that underflow a
float remain positive in exact Fraction arithmetic.

```bash
OPENBLAS_NUM_THREADS=1 python scripts/nba_p6_hidden_credit_rounding_adversary_20261117.py \
  --assembly "$p6_assembly" --output work/new-red-results/p5-public.json
```

Expected exit2; source821aafb34de8d592ceb6ecd81606baa746dc7e09. Ten public
cases invoke actual P1 export, actual P2 synthetic fit, public P5 `put_s`,
public outcome validator and `put_p1`. Correct full-credit15-second controls
pass; valid omitted-stat subminute prior sources falsely reject; exact30-second
hidden-credit outcome is falsely accepted. Scoring remains BLOCKED/scoredFalse.
Synthetic fitted payload bytes, source manifests, full inputs and hashes are
retained; no historical outcome is used for fitting.

```bash
OPENBLAS_NUM_THREADS=1 python scripts/nba_p6_rounding_status_alias_adversary_20261117.py \
  --assembly "$p6_assembly" --output work/new-red-results/p5-status.json
```

Expected exit2; source64aa8228f99f524fbe88c099579e6ba24a5c3eb8. Four public
prior-intake cases show that changing a caller label to
`OFFICIAL_BOX_RECONCILED` lets the invalid exact30-second/display0/hidden-credit
case pass; the correct ADJUDICATED label rejects even the legal15-second case.
This is the same F-P5-05 defect. Fix source-derived boundary and status together,
not an allowlist. Preserve each old red; do not overwrite outputs with a later
green version or reinterpret missing credits as DNP.

## Numerical/hash interpretation

Fresh actual P4 outputs retain256 seeds/1,024 paths, all96 normalized PMFs,
zero observed games, no O resampling/scenario discard and semantic replay
`5de46126c5158d061d9f327f3e78c1faa123970ccf1a7fba80cb61cbed28b262`.
Maxmean discrepancy11.3679975911/maxempiricalTV0.4767262428 persist. Raw
compressed SHA is67b3cec65ba5f41312b8a33adc04ad7aa59ff7d5736c8dc9733718d1a015f87e;
raw uncompressed SHAc0fb12cddb697aee7421239f923a71a4ab46f1b19ef6ffc955820fb0e79f8be7.
Runtime-bearing raw hashes may differ across reruns; semantic replay removes
performance only. All raw outputs remain losslessly retained.

Archive integrity is99 compressed shards/39,916,715bytes only. HTTP/export/raw
artifact hashes, parsed canonical hashes, Git blobs and semantic replay are
separate domains. The coordinator's connected artifact file is explicitly
tool-returned UTF8 text, not original provider HTTP bytes or an admitted fit.

Validate this publication's SHA256SUMS from repository root. The old f29
manifest remains a70d37e9 source snapshot; the root repair manifestcff5ad belongs
to4d4d594. The exact prebuilt final assembly is6dee; do not use the historical
ignored-report assembler preserved on the QA branch to recreate it.
