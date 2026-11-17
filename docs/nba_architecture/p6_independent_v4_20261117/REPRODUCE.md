# Reproduce independent P6 v4

Final recommendation is **G1 NO-GO**. Expected negative/quarantine outcomes
are evidence, not successful source admission. All fitting/optimization inputs
are synthetic. Never decompress or score historical/holdout archive shards.

Use Python 3.12, NumPy 2.3.5, SciPy 1.17.0, jsonschema 4.26.0 and mpmath 1.3.0.
Complete observed package/environment metadata is in
`execution_v1/environment.json`. Use fresh disposable directories; do not
replace a published receipt or reuse an output directory.

## Source preparation

From a clone with the Git objects, fetch all exact submissions and create a
detached **QA executable source** checkout. The later report commits are
documentation/evidence successors; the executable source below is the tested
version.

```bash
git fetch origin \
  c51c6f08f9009274258062cc5f3425e1f1567893 \
  6dee6e09fa786479dc2e163a33e14257f207b35e \
  7145c9dd734d00b5b4a451cfc1f730cd4967762d \
  4d4d594fd7c88cdb3149cafd35515d5a65412b87 \
  50d2b3874c7c14c9b73bdf13e441957986b88acd \
  fe46965394ea0f48ef5e9da501ec8ca9e441ce47 \
  eb0882b5011f2004c5eaf27cccfdc6297704f261 \
  865bdb8f4770ac28262e49c3b4901cf1d72a22fb \
  cb3ff8279bc7f4cc7b86a519a1e386ddbe37ae93 \
  c14b5584c30f8fbca3eb2e51acfaea24c40eff29
git worktree add --detach work/p6-qa-source c51c6f08f9009274258062cc5f3425e1f1567893
git worktree add --detach work/p6-assembly 6dee6e09fa786479dc2e163a33e14257f207b35e
```

Set absolute paths to the object database, QA checkout and assembly checkout:

```bash
p6_repo="$PWD"
p6_qa="$PWD/work/p6-qa-source"
p6_assembly="$PWD/work/p6-assembly"
cd "$p6_qa"
```

**Use the prebuilt published assembly 6dee.** The QA checkout deliberately
preserves the historical assembler to keep the frozen pre-QC manifest valid.
Do not rebuild the final assembly with that historical `git add -A` builder.
If regeneration is necessary, use both assembler and verifier from fixed
root commit `7145c9dd734d00b5b4a451cfc1f730cd4967762d` in its own checkout.

The historical `SHA256SUMS_PRE_P6_V2` raw digest is
`f29ac4a6e39162bd55d5acc0fbf536579da98b3510023e1a0b06c156eb7a0b71`.
Its paths resolve against frozen `70d37e9...` blobs or this QA source checkout,
which preserves those bytes. The later root repair packet has its own manifest,
`cff5ad5d2df55f6e38aa88fcad1aba58b0f220a9d26d7956819e4c331438fafd`,
and must be checked against root packet `4d4d594...`, not substituted for f29.

## New independent adversarial and numerical checks

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python scripts/nba_p6_independent_checks_v4_20261117.py \
  --assembly "$p6_assembly" \
  --expected-assembly 6dee6e09fa786479dc2e163a33e14257f207b35e \
  --output "$p6_qa/work/new-independent-result.json"
```

Expected: all eleven sections PASS. `evidence` verifies the entire committed
source population and modes, original negative-probe SHA, accepted G0, both
historical manifests, P1 raw inventory/403 bytes and P3 appended documentation
receipt. The `joint` section includes actual n32 O2 rejection as its expected
negative control. `incompatibility` proves a necessary marginal condition is
violated; its PASS does **not** accept the constrained-law proposal.

Sections can be run individually with `--section evidence`, `physical`,
`scores`, `quarantine`, `cutoff`, `optimizer`, `native`, `joint`, `replay`,
`incompatibility` or `discovery`. The output file is create-only.

To reproduce the first independent red, create a separate checkout of
`d46f5322b47367ba601b05197cef8404758da23d` and run `--section evidence`
with `--expected-assembly d46f5322b47367ba601b05197cef8404758da23d`.
Expected FAIL for the four missing mapped P2 reports. The immutable exact
first QA source is `f79d621...`; its original failed output and separate NO-GO
are retained under `red_v1/`. Do not replace them with the r3 result.

## Exact owner suites, original negatives and native boundaries

```bash
python scripts/nba_g1_pre_p6_v4_20261116.py \
  --repo "$p6_repo" \
  --pins docs/nba_architecture/g1_orchestration_v4_20261116/submission_pins_pre_p6_r2.json \
  --work-root "$p6_qa/work/fresh-owners" \
  --output "$p6_qa/work/fresh-owner-results"
python scripts/nba_p6_g1_reaudit_runner_v3_20261116.py \
  --repo "$p6_repo" --work-root "$p6_qa/work/historical-owners" \
  --output "$p6_qa/work/historical-results"
python scripts/nba_g1_boundary_qc_v4_20261116.py \
  --repo "$p6_repo" \
  --pins docs/nba_architecture/g1_orchestration_v4_20261116/submission_pins_pre_p6_r2.json \
  --owner-checkouts "$p6_qa/work/fresh-owners" \
  --output "$p6_qa/work/fresh-boundaries"
```

Fetch any missing historical object listed in the old runner's PINS/OLD/
UPSTREAM/QA_PIN/G0 constants before running it. Expected: 24 current-owner
commands green, 32 historical expected outcomes including the exact old red
case names/exits, and five boundary outcomes. The authentic boundary must
return `OFFICIAL_SOURCE_EVIDENCE_REQUIRED`, 26 attempted entries, no snapshot,
before G. Synthetic handoff cases are separate. The native C test has 21 cases
and archives all 96 actual J distributions.

The unchanged probe must hash to:

```text
fa8012e260a21caacb2fcebadc02a2deddaf957bc4425b8128dcae2c83ba9e52  scripts/nba_p6_g1_owner_negative_probes_20261116.py
```

The inherited current-owner runner labels the `--repo` HEAD as
`qa_code_commit`. The final independent `qa_source_execution.json` separately
records the actual executing QA checkout and raw executable hashes. Compare
raw code hashes, exact owner heads and semantic outcomes; do not infer reviewer
authorship or acceptance from a helper's legacy field name.

## Root discovery and inspected offline checks

From exact assembly 6dee, **unset PYTHONPATH** for root discovery:

```bash
cd "$p6_assembly"
env -u PYTHONPATH OPENBLAS_NUM_THREADS=1 python -m unittest discover \
  -s tests -p test_nba_root_discovery_v4.py -v
PYTHONPATH=.:tests/nba_architecture OPENBLAS_NUM_THREADS=1 \
  python -m unittest discover -s tests/nba_architecture -v
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 python -m unittest discover -s tests/nba_s_family -v
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 python -m unittest discover -s tests/nba_c -v
```

Expected counts: 1, 513, 61, 76. Dedicated-suite PYTHONPATH must not mask the
historical golden_v2 root failure. The original P2 checkout at `7ca4269...`
has 1,652 root-discovered objects and ten import errors with PYTHONPATH unset.
Discovery alone does not execute unrelated historical/modeling test bodies.

The ten inspected offline suites are `test_network_receipt.py`,
`test_morning_preflight_recovery.py`, `test_engine_contracts.py`,
`test_verify_sports.py`, `test_history_bootstrap.py`,
`test_verify_history_invariants.py`, `test_afternoon_reuse.py`,
`test_auto_research.py`, `test_odds_quota_guard.py`, `test_morning_no_odds.py`.
Execute each with `python -m unittest discover -s tests -p NAME -v`;
56 methods total. They use temporary synthetic files, injected/mocked network
providers and synthetic numerical fitting only. Never substitute unrelated
root suites that perform historical evaluation or training.

Also run `python -m compileall -q scripts tests v2`,
`bash -n scripts/shadow_store.sh`, and
`bash -n scripts/history_warehouse_store.sh`. The full 17 command arrays,
expected counts, raw logs and hashes are in `final_v2/assembly_r3_checks/`.

## Actual P4 study and independent raw-output analysis

From exact P4 owner `865bdb8...`, with its declared exact P2/P3 Git objects:

```bash
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 python -m research.nba_p4_latest.repeated_seeds \
  --output work/new-independent-256-seed-study
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 python -m research.nba_p4_latest.pool_joint_outputs \
  --input-dir work/new-independent-256-seed-study --output-dir work/new-independent-all96
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 python -m research.nba_p4_latest.reference_conditioning \
  --output work/new-independent-conditioning.json
```

Then from QA source c51 run:

```bash
OPENBLAS_NUM_THREADS=1 python scripts/nba_p6_repeated_map_reference_v4_20261117.py \
  --input /absolute/path/to/new-independent-256-seed-study \
  --output /new/path/independent-reference.json
```

Expected: 256 J seeds, 1,024 weighted paths, 96 normalized PMFs, zero observed
games, no O resampling/scenario discard, max mean discrepancy 11.3679975911,
empirical TV 0.4767262428. Semantic replay excludes performance only and is
`5de46126c5158d061d9f327f3e78c1faa123970ccf1a7fba80cb61cbed28b262`.
All 48 unconditional public P2 calls abstain; the played-conditional reference
maximum PMF error is 3.7402e-12. Neither result admits genuine q=1.

The archive-byte integrity reproducer from original audit remains available:

```bash
python docs/nba_architecture/p6_remediation_reaudit_v3_20261116/byte_verification_reproducer.py \
  --repo "$p6_repo" --output work/new-opaque-archive-check
```

It hashes 99 compressed blobs/39,916,715 bytes only; it does not decompress,
parse, score or certify their historical availability.

Raw HTTP/export/artifact/output-byte SHA256, parsed canonical content hashes,
Git blob IDs and semantic replay hashes are distinct domains. Runtime-bearing
raw logs and gzip outputs can legitimately differ between executions; retain
both raw receipts and compare their separately documented stable semantics.
Validate this independent publication's `SHA256SUMS` from repository root.
