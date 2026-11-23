# Deepnote and Codex output management

Apply this policy to every NBA, NHL and NFL research market, forecasting model, validation notebook and Deepnote execution. Minimize what Codex routinely receives. Preserve the complete evidence required by the [governing V2.5 master plan](Pickem_Auditor_V2_5_Master_Implementation_Plan_v1_1_2026-11-10.md), including for failed, incomplete, and uninstrumented runs. Enable the publisher in an existing live notebook only after that notebook’s storage path, failure handling and recovery have been tested in isolation.

## Official MCP setup

Use the official Deepnote MCP integration in the actual Codex client. In a CLI-backed installation, Deepnote documents `codex plugin marketplace add deepnote/agent-plugins`, `codex plugin add deepnote@deepnote` and `codex mcp login deepnote`. The hosted endpoint is `https://deepnote.com/mcp`. Use OAuth or a key supplied through secure client configuration. Use `get_me` to verify workspace access, `get_project` for notebook identity, schedules and artifact paths, and `get_notebook` once before execution to verify the relevant inputs and code. Authorization in another Codex client does not establish authorization here. Keep credentials, bearer URLs, sensitive configuration and production secrets out of tool output and archives.

[Deepnote MCP documentation](https://deepnote.com/docs/deepnote-mcp) · [Deepnote run API](https://deepnote.com/docs/deepnote-api-runs)

## Retrieval and escalation

| Level | Trigger | Retrieval and decision |
| --- | --- | --- |
| 1 | Routine execution | Use `get_run({runId})` when terminal status is needed. Omit snapshot delivery for status-only checks. Use `read_file({projectId,path})` on the known `<correlation_id>.summary.json` without fetching block outputs first. Confirm `hasMore=false`, parse the complete compact JSON, and reconcile the notebook, actual execution ID, status and exact revision. Check provenance, denominator counts, metric and gate outcomes, and the evidence reference. |
| 2 | Warning, failure, invalid probabilities, failed invariant, missing provenance, failed or omitted required gate, significant regression, conflicting status, or missing or truncated receipt | Follow the issue codes, stage/test, traceback excerpt, records and matched comparison in the compact report. Read the smallest relevant durable file or range. Use a single `get_run({runId,snapshotDelivery:"blocks",fullOutputs:false})` if the report is insufficient or unavailable. Use `get_block` for block source and metadata. Compare the historical snapshot's content hash before using current source to explain historical output. For detached runs, never read live editor outputs as run evidence. |
| 3 | Level 2 cannot explain the anomaly, reproduce the result, or establish an independent audit | Retrieve the relevant original evidence and verify its length, SHA-256, run identity and artifact references. Use `list_notebook_runs` to select the accepted historical execution, then `get_run` for that execution. Prefer named files and selected ranges. If a required stored output is abbreviated, use `fullOutputs:true` justified by that gap. Use inline snapshot delivery when historical source is required and unavailable by a narrower route. |

When Deepnote reports `pending` or `running`, wait between status-only checks. Cache immutable artifacts by execution/correlation ID and digest and avoid fetching unchanged files twice. If the snapshot is pending after terminal execution, use the durable report first. Mark missing summaries, unavailable snapshots, mismatched hashes, or limited provenance as evidence gaps with the exact IDs and paths. A green kernel establishes only that the execution completed. A green transport receipt never substitutes for independent statistical or production gates.

`get_run` block delivery has no input to select block IDs. Large output objects can be abbreviated at the MCP boundary. Deepnote may also drop stdout/stderr before storing it, according to the live tool contract. `fullOutputs:true` can recover an abbreviated stored output but cannot restore text dropped during capture. Expiring snapshot URLs are not durable archives. The instruction and helper govern retrieval and notebook reporting. They do not impose a server-side MCP response cap. Treat a tool-level error, incomplete JSON, or truncation marker as a retrieval failure.

When a finding needs code work, reproduce it from immutable inputs, patch the appropriate code on an isolated Git branch, run the authorized bounded validation again using a new execution/correlation ID, and compare against the original and accepted baseline. Iterate until the failure is resolved or the specific permission, source, capacity or infrastructure blocker is documented. Ordinary escalation inside that task needs no extra approval. Schedule, release, live notebook and expensive training changes require their respective authorization.

## Publishing contract

The standard-library helper [deepnote_diagnostic_report.py](../scripts/deepnote_diagnostic_report.py) writes an evidence envelope and any declared file artifacts before it prints or publishes a canonical summary. The summary is at most 12 KiB in UTF-8 including its newline. Its relative paths can be resolved under the configured evidence directory. It preserves the execution status and emits a separate validation status with a retrieval level. A caller that expects a fatal execution error must still re-raise the original exception after publishing. The CLI exits 1 on Level 2 after saving the report. Existing notebooks are opt-in and should retain their original validators and exit behavior.

| Field | Producer contract |
| --- | --- |
| `run_id`, `notebook_id`, `deepnote_run_id` | Unique correlation ID, verified notebook ID, and actual platform execution ID if available from a documented trusted source. A caller-supplied correlation ID alone is never the execution ID. |
| `status`, `sport`, `market`, `model`, `model_version`, `git_sha` | Terminal execution state and exact tested identity. Use an explicit scope label for a suite spanning markets or models and include its per-market and per-model results in the evidence. |
| `tests`, `counts` | Passed, failed and skipped. Total, eligible, rejected, missing, unmatched and abstained. Include complete reconciliation, coverage breakdowns, rejected observations and counts by reason in the full evidence. Counts may overlap and must not be added as if disjoint. |
| `provenance` | `input_uri`, `input_sha256`, `output_uri`, `output_sha256`, and experiment-specific source receipt, model artifact, timing, seed and reproducibility fields. Retain authentic original bytes with verified timestamps, cutoffs and immutable forecast histories. Opaque external paths require verification with the authorized archive reader. |
| `metrics`, `gates`, `comparisons` | Primary compact metrics, explicit gate outcomes (`passed`, `failed`, `warning`, `blocked`, `skipped`, `not_applicable`), and applicable matched baseline comparisons. Include proper scores, calibration/coverage, convergence (R-hat, ESS, divergences, BFMI), support, cross-stat dependence, physical conservation, leakage and independent adversarial results as applicable. The existing validators govern those requirements. |
| `issues`, `samples`, `probabilities`, diagnostic sections | Capture every issue with code, severity, stage, test, message and complete traceback when available. Include relevant records, model parameters, distribution and constraint diagnostics. Optional `probabilities` records use `over`, `under`, `push` and a useful record ID. Keep the complete distributions, simulations, logs and original sources in the full payload or declared files. |

Each comparison contains `baseline_id`, `delta`, `ci_low`, `ci_high`, and optional `harm_threshold` (default 0). Orient all results so positive delta means harm. Compute the interval upstream using the accepted, preregistered matched-cohort procedure, including dependence, repeated-look and multiplicity controls where required. The helper flags `ci_low > harm_threshold` and preserves malformed or inconclusive inputs. It does not fit models, estimate intervals, define acceptance criteria, or decide whether absence of an optional diagnostic is appropriate. Surface any result missing from the validated experiment as a failed or blocked upstream gate. Host warnings and other upstream failures must be collected and passed through explicitly. Non-finite numbers in the envelope are represented by `NaN`, `Infinity` or `-Infinity` strings with typed paths identifying exactly where these substitutions occurred.

Use `publish_report(report, durable_path, artifacts={"source": source_path, "draws": draws_path})` after each input file has been closed and frozen. The helper preserves source bytes under a SHA-256 filename, verifies local content-addressed provenance references, and records unavailable artifacts explicitly. Full report JSON has a stable `<correlation_id>.full.json` path and a digest and byte count in the summary. On a hard stop before publication, recover from the upstream evidence and platform failure log. An absent receipt keeps that run unresolved. An artifact recorded as missing at capture stays missing even if the available evidence verifies. Never use a regenerated artifact as if it were the original.

The publisher requires a durable writable directory that supports filesystem synchronization and create-once files. It uses staged hard-link publication when available. On linkless mounts it claims the file with exclusive creation, synchronizes it, and checks the bytes by reading them back. Readers reject a partial write. A partial file is preserved for diagnosis and requires recovery at a separate verified location or a new run ID. Publishing uses a fixed run ID claim and never overwrites a conflicting file. The same bytes can be retried idempotently. Conflicting evidence under an existing run ID is rejected. Use a new ID for a genuinely different execution. A process that crashes before claiming an ID can leave unreferenced content-addressed files. Retain existing evidence and follow the store's retention rules. The filesystem owner still controls retention and access. For adversarial verification retain the expected digest in a separate trusted receipt, store, or commit.

## Run identity and durable recovery

For a notebook that accepts an input correlation ID, pass a unique value through `create_run(inputs=...)` using the exact input name from `get_notebook`. The caller already knows the target report path. Store both the correlation ID and official Deepnote run ID from the `create_run` and terminal `get_run` receipts. If the notebook cannot know the official ID during execution, the initial report leaves `deepnote_run_id` null. The controller writes a create-once `<correlation_id>.binding.json` containing `run_id`, `notebook_id`, `deepnote_run_id` and `full_evidence_sha256`, after reconciling both receipts. The Python `bind_run` helper can do this on a verified filesystem. With MCP project files, use `write_file` without overwrite and confirm the exact returned path and contents. Store or index the controller receipt by actual run ID so subsequent investigations can find the corresponding files. An unbound correlation receipt cannot independently establish Deepnote execution identity.

Use an authorized persistent project mount or other durable storage with verified retention and access for the entire evidence chain. For a detached `read_write` run, confirm persistence after terminal execution from outside that machine. A `readonly` run needs a separately authorized publication route outside the read-only mount. Temporary execution storage, binary blobs that cannot be accessed, and the expiring run snapshot alone do not satisfy recovery. `read_file` is suited to small text (maximum 64 KiB per response). For larger line-oriented text, use `startLine` and `endLine` and check `hasMore`; for large canonical JSON single lines or binary files use an approved archive reader or a verified compute-side streaming inspector. Exchange targeted calculations and SHA-256 receipts by default. Preserve full bytes in the trusted store and make them recoverable from the run identity.

Run `python scripts/deepnote_diagnostic_report.py --output-dir /durable/evidence --verify CORRELATION_ID --deepnote-run-id EXECUTION_ID --expected-sha256 TRUSTED_DIGEST` against restored archives. Verification reconstructs and compares the compact report and checks every archived artifact's hash and length. If only the summary is missing, use `--recover CORRELATION_ID --expected-sha256 TRUSTED_DIGEST` on the evidence directory. Recovery verifies the evidence and does not overwrite a damaged or conflicting summary. Preserve a corrupted file as incident evidence and reconstruct in a separate verified recovery location. If evidence or independent provenance is unavailable, record the precise missing item and keep validation blocked.

## Reproduce the isolated pilot

Run the focused tests offline before any hosted pilot. The fixture uses sixty synthetic games, one observation per game, with no live data or training.

```bash
python -m unittest discover -s tests -p test_deepnote_diagnostic_report.py -v
pilot_root=$(mktemp -d)
tested_sha=$(git rev-parse HEAD)
for case in normal failure drift; do
    python scripts/deepnote_diagnostic_pilot.py "$case" \
        --git-sha "$tested_sha" --output-dir "$pilot_root/$case" \
        --run-id "$case" --notebook-id offline-fixture --deepnote-run-id "offline-$case"
    status=$?
    if [ "$case" = failure ]; then test "$status" -eq 1 || exit 1
    else test "$status" -eq 0 || exit 1
    fi
    python scripts/deepnote_diagnostic_report.py --output-dir "$pilot_root/$case" \
        --verify "$case" --deepnote-run-id "offline-$case" || exit 1
done
```

For an authorized Deepnote pilot, create an unscheduled isolated project without production integrations. Install the exact tested helper and fixture sources, and check the SHA-256 of each before import. Run `run_fixture` for NBA normal, NHL controlled failure, and NFL subtle matched Brier regression. Use separate evidence directories and unique correlation IDs. Verify project-file access after completion. Retrieve the complete evidence once for each fixture and confirm the failed stage and offending row in the NHL fixture, and the affected stratum and original paired scores in the NFL fixture. Measure comparable model-visible payload sizes. Record actual run/notebook/project IDs, source commit, storage mode, source and evidence digests, results and blockers in the validation receipt. Keep the pilot artifacts and stop opting in to roll back instrumentation.

[November 23, 2026 hosted pilot validation receipt](DEEPNOTE_CODEX_OUTPUT_VALIDATION.md)
