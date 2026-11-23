# Codex Desktop + Deepnote: adaptive diagnostic output (research-only)

**Scope:** Opt-in engineering instrumentation for Pick'em Auditor. This document complements AGENTS.md and PA-V25-MASTER-2026-11-09 / v1.1. It does **not** change forecasting mathematics, source certification, release gates, live schedules, NUTS jobs, or existing Deepnote notebooks. No notebook is instrumented merely by merging this document.

## Objective and important limitation

Minimize **routine text sent to the coding model**, not scientific evidence. Store full evidence durably, return a compact machine-readable summary on success, escalate to targeted details on anomalies. This can reduce context size; it is not a guarantee about OpenAI billing or a hard cap on MCP responses.

AGENTS.md is an instruction to Codex, **not an MCP response filter**. Deepnote MCP get_run(snapshotDelivery="blocks") may still return outputs from all blocks (with large individual outputs abbreviated unless fullOutputs=true). For real savings, instrument notebook outputs, use the persistent short JSON summary, and ask for full snapshots only when justified.

## Codex Desktop setup (Windows)

1. Open the Git checkout of royalexx/pickem-auditor as the Codex Desktop workspace. The existing root AGENTS.md is the source of repo-specific instructions.
2. Connect Deepnote to Codex with its official MCP plugin or a supported remote MCP server configuration. Deepnote's current documented CLI sequence is:

   ~~~powershell
   codex plugin marketplace add deepnote/agent-plugins
   codex plugin add deepnote@deepnote
   codex mcp login deepnote
   ~~~

   Server endpoint: https://deepnote.com/mcp. Authenticate by OAuth where supported or securely supply a Deepnote workspace API key via client credentials. Never put a token in this repository, AGENTS.md, code, notebook output, CLI history, or run artifacts.
3. Have Codex verify workspace access using the Deepnote MCP get_me/get_project/get_notebook tools. A ChatGPT web connector authorization does **not** prove that the local Codex client's credentials work.
4. Git CLI is sufficient to commit and push local code. You do not need the GitHub MCP connector for routine local edits.

Official Deepnote documentation: https://deepnote.com/docs/deepnote-mcp and https://deepnote.com/docs/deepnote-api-runs.

## Three retrieval levels

| Level | Trigger | Codex requests | Evidence handling |
|---|---|---|---|
| L1 — concise | Successful/no critical anomaly | Run status and compact per-run summary JSON via read_file | Full raw evidence remains stored, linked by SHA-256 |
| L2 — targeted | Failed checks, warning, unusual metric, incomplete lineage | Failed stage, exact errors, traceback tail, affected identifiers, bounded examples, relevant get_run blocks (fullOutputs=false) | Keep whole failure evidence and all denominators |
| L3 — deep | L2 insufficient, reproducibility challenge or user specifically requests full detail | Relevant full snapshot/blocks (fullOutputs=true only when needed), relevant file ranges and earlier run receipts | Use explicit source hashes, immutable run IDs, no excessive unrelated logs |

**Always:** Inspect terminal run status, notebook/project identity, true tested git SHA, exact cohort/denominators, evidence hashes, input availability timestamps and independent gate status. A green kernel run is not statistical validation. Fail open neither on missing summaries nor on output truncation: say "summary unavailable/not instrumented" and diagnose by original evidence.

**Cost control:** Do not poll fast in a long loop, fetch all block outputs repeatedly, paste large DataFrames, or run an entire expensive notebook when a targeted authorized check suffices. When changing live notebook cells or running them, honor user authorization, running jobs, storage mode and pause/schedule guards. Detached readonly runs cannot be assumed to persist new output files into project storage; run snapshots may be retention-limited.

## Portable summary writer included in this repo

The pure-standard-library helper scripts/deepnote_diagnostic_report.py is an **opt-in** publisher. It writes complete, immutable JSON first, then prints a one-line compact summary. It also writes a **predictably named** <run_id>.summary.json for MCP read_file, and a content-addressed <run_id>-<sha>.full.json. Run ID reuse with different evidence is rejected. It does not silently discard errors, rejected rows, missingness, or statistical metrics. It cannot capture stdout from other noisy notebook blocks by itself.

### Instrument a pilot notebook (do not modify every notebook at once)

Ensure the tested repository helper is actually present on the Deepnote machine (for example by the project's already-approved Git import/sync workflow); verify the source SHA before importing. Do not assume a GitHub commit automatically updates a live Deepnote notebook.

Near the end of the notebook (and also in its exception handler), write:

~~~python
from scripts.deepnote_diagnostic_report import publish_report

report = {
    "run_id": external_report_run_id,        # unique safe ID supplied for this invocation
    "notebook_id": expected_notebook_id,     # fixed verified Deepnote identity
    "status": execution_status,             # success / warning / error / blocked
    "sport": sport,
    "market": market,
    "model": model_id,
    "git_sha": actual_running_commit_sha,
    "tests": {"passed": passed, "failed": failed, "skipped": skipped},
    "counts": {
        "source_rows": source_rows,
        "eligible": eligible,
        "rejected": rejected,
        "unmatched": unmatched,
    },
    "metrics": scored_metrics,              # finite scalar values, not entire data tables
    "provenance": {
        "source_sha256": original_source_sha,
        "model_sha256": model_artifact_sha,
        "input_freeze_at": actual_input_freeze_at,
    },
    "issues": failure_records,              # each with code/message/optional traceback
    "samples": bounded_diagnostic_rows,     # full list saved but not printed on success
}
compact = publish_report(
    report,
    output_dir="reports/deepnote_diagnostics",  # must be persistent project storage
)
~~~

Variables in this example **must** be supplied by the actual notebook/runner. Never invent source hashes, freeze timestamps, metric values, tests, errors or outcomes. On a fatal error, capture exception/traceback in failure_records and re-raise after writing the report; do not suppress the failing notebook state.

To reduce noise from expensive fit/code cells, write verbose stdout/stderr and long intermediate arrays to **persistent, access-controlled artifacts** instead of printing them. Never discard an exception traceback or skip a test merely to fit an output budget. Avoid including tokens, API credentials, raw secrets, or sensitive notebook inputs in full artifacts.

To make the compact report accessible **without first downloading all block outputs**, define an input-block variable (such as external_report_run_id) and pass a unique ID with create_run(inputs=...) from the calling agent. Then MCP read_file(projectId, path="reports/deepnote_diagnostics/<external_report_run_id>.summary.json") fetches only the summary. The ID is a report correlation ID; it is **not automatically the Deepnote runId**. Preserve both in the full receipt when available. If the notebook does not support that input yet, inspect its output through get_run with fullOutputs=false once; do not claim the small-file retrieval path already works.

For read_write detached execution, confirm the directory is on **persistent project storage**, not a temporary filesystem. For readonly execution, save evidence to a separately authorized durable store or rely on the actual Deepnote snapshot subject to its retention; the helper will not magically persist across machines. Larger full files may exceed MCP read_file's per-call text limit (64 KiB); use targeted line ranges where possible or an authorized snapshot/export mechanism. Never assume every binary artifact is readable through MCP.

### Local offline check

~~~powershell
python -m unittest discover -s tests -p test_deepnote_diagnostic_report.py -v
~~~

The tests cover success/noisy payload, full evidence retention, failure escalation, truncation counters, missing diagnostics, NaN fail-closed, run ID collision, path traversal, and tamper detection. They are software tests, **not** evidence that a real Deepnote notebook has executed successfully.

## Mandatory pilot acceptance before expanding to other markets

Run the pilot **only after an explicit user request** and verify the connection and affected notebook first:

1. **Normal:** successful notebook; confirm L1 summary is small, authentic counts/metrics/hashes are present and full evidence can be recovered.
2. **Controlled failure:** introduce an isolated test-only exception/invalid value; confirm failing status, traceback preservation, complete failed-test count, run receipt and lossless evidence.
3. **Subtle anomaly:** force an isolated out-of-range probability or invalid source-time fixture; confirm Codex escalates to L2, inspects exact relevant evidence, and refuses scientific certification.
4. **Recovery:** use L3 as needed, restore the notebook, rerun bounded tests, and independently verify evidence/provenance. Do not overwrite existing archived forecasts or amend historical receipts.

Record the exact Deepnote notebook/project IDs, run IDs, true commit SHA, test outcomes, report SHA-256, changed files, output sizes before/after, and whether live or readonly storage and recovery actually worked. Roll back by stopping use of this optional helper and reverting only the pilot instrumentation; preserve all original run archives.

**Status at initial GitHub commit:** helper/documentation/tests prepared; no existing Deepnote notebook or schedule changed and **no live MCP pilot certified**.
