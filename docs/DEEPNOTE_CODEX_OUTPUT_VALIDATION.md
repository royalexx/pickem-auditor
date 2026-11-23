# Deepnote output protocol validation receipt

- **Date** November 23, 2026 (America/Toronto)
- **Governing plan** PA-V25-MASTER-2026-11-09 / v1.1
- **Scope and status** Phase 1 reporting infrastructure, implemented and tested offline and through the official Deepnote MCP integration. The isolated pilot is synthetic and shadow-only. Independent scientific review and individual live-notebook adoption remain outside this pilot.

- Branch `codex/deepnote-adaptive-output-20261123`. [Draft PR #210](https://github.com/royalexx/pickem-auditor/pull/210)
- Verified `main` baseline `912bc7010058092ea735dcda0aa941429194474b`.
- Exact pilot implementation revision `9ae370f3a27237383b069f98bbb41a2d246b0459`. Both Python files were checked by SHA-256 in each notebook before importing them.
- Reporter SHA-256 `f0a3f09e1ea73945c7e6b58fb7550010870a6397ed5ef3b66cf7055de2b9a239`.
- Fixture SHA-256 `f72a3fa49b62c7357d700673185102c8f77e42a20f74163fa76e2e500c43c4ee`.
- Focused offline suite **18 passed**. Clean isolated worktree suite **1,620 passed, 9 skipped, 11,661 subtests passed**. The 9 skips require optional scientific dependencies (PyMC, ArviZ, xarray, and the statistical audit stack). A first run from the workspace checkout tripped the repository content scanner on third-party packages under the pre-existing untracked `.venv`. Running from a clean worktree with the same interpreter resolved that environmental failure.

## Hosted runs and recovery

Dedicated Stonks project **Pick’em Auditor V2.5 — Deepnote diagnostic protocol pilot 2026-11-23**, ID `4b96f05e-bfa5-464f-aa63-030961df0bbf`. All three notebooks were unscheduled, and the project had no attached integrations. The CPU runs used detached `read_write` project storage. Each case has 60 synthetic observations, one per game. All are eligible, with zero missing, rejected, unmatched, or abstained. The expected failed case stopped before scoring its invalid population. There were no real offers, authentic forecast receipts, trained models, or production changes.

| Fixture | Notebook ID | Actual Deepnote run ID | Kernel and validation | Evidence SHA-256 |
| --- | --- | --- | --- | --- |
| NBA normal | `3612b88ad74b40ceaabd72c6bc0e9ba0` | `b3f8094a-76c4-4aa8-9289-f9484c46c5b2` | Success. L1, passed. 2 passed, 0 failed, 0 skipped. | `ae49bde75ca2f4e6457a3b3543c7d9ac5d3bc63806006f21ce06afc3b6b34628` |
| NHL invalid probability | `02515e7d8fe5462287b6d82166e0ac2e` | `5ff4c729-b00b-4a92-a9f8-e5a32a15ab02` | Error. L2, failed. 1 passed, 1 failed, 0 skipped. Recovered complete traceback, stage `probability_validation`, test `probability_bounds`, and game 07 with Over 1.02 and Under −0.02. | `0461ce8f56ddfab7c8a39c7e15bfaeda04706436d4ebe1fc86822ef014265b18` |
| NFL matched Brier regression | `e880cd75ae2c45c0aa47678c45c52d08` | `97a1e06d-cf95-4aed-a49f-3f33bd065e9a` | Success. L2, failed. 2 passed, 0 failed, 0 skipped. Paired candidate-minus-baseline Brier +0.00819583, synthetic 95% interval [0.00511137, 0.01128029]. L3 recovery of all paired scores attributed the change to the away stratum (+0.01639167 vs home 0). | `ffa6065dc53dcbc025cfafa4b130d5760a11b3f4b20137ca89b3704dbfedfe1c` |

Each case uses `pilot-20261123-v2/<case>` and correlation ID `pilot-20261123-v2-<case>`, where the case names are `normal`, `failure`, and `drift`. The summary, evidence, and execution binding files are named with the correlation ID followed by `.summary.json`, `.full.json`, and `.binding.json`. After terminal status, MCP `read_file` recovered each complete file and both original JSON artifacts. Local verification reconstructed each summary, matched platform and correlation identities using its binding, and checked exact lengths and SHA-256. Persisted bindings were read back byte-for-byte. The common source digest is `dc0dc09b7067b42b4bf6ec5a01cae51606e23521439171470b560262d1d90435`. Output digests in case order are:

- NBA `c7647f68e08adadfa30934e4f7e95f74cc2a575e599358ed0c017f096b729cac`
- NHL `db658076faf761eb94ec30d2230879b6a4a9597bd603cf2b173f55fbe52ed522`
- NFL `88d61a05e226b3fdaa2242f2aff0763b4164a20aa2021e15688dc3fa9573617d`

Initial NBA attempt `316e30be-ce88-4980-855d-bff8af1b5296` failed because the project mount rejected hard links with `EOPNOTSUPP`. The revised writer uses exclusive creation with fsync and exact readback where hard links are unavailable. The retry used a new correlation ID. Transient submission rate limits cleared by spacing requests. Neither failed submission returned a run ID. Historical listing produced detached notebook IDs different from the original notebook IDs. The verified bindings use the notebook and run IDs returned by `get_run`, matched against the original notebook target. The failure block was verified with `get_block`. No full snapshot was needed for any recovery.

## Measured output size

For each completed case, both paths use the real MCP `read_file` response for the same run. The verbose reference is the full evidence envelope and the optimized path is the initial compact summary. Bytes include UTF-8 encoding. Tokens use `o200k_base` via `gpt-tokenizer` 3.4.0 on the compactly serialized MCP structured response (`content`, line bounds, and `hasMore`). These are comparative payload counts. Client framing, status calls, separate bindings, later L3 reads, and billing are outside the measurement.

| Fixture | Full → compact file bytes | Full → compact structured response bytes | Full → compact structured response tokens | Measured token reduction |
| --- | ---: | ---: | ---: | ---: |
| NBA normal | 31,581 → 1,623 | 34,238 → 1,836 | 9,167 → 590 | 93.6% |
| NHL failure | 26,730 → 2,674 | 28,651 → 3,025 | 7,268 → 888 | 87.8% |
| NFL regression | 33,592 → 2,049 | 36,269 → 2,310 | 9,789 → 713 | 92.7% |

To repeat the calculation, serialize each `read_file` structured response with JSON separators `(",", ":")` and no ASCII escaping beyond normal JSON, then measure its UTF-8 bytes and feed that exact string to the named tokenizer. This comparison concerns initial retrieval. If an investigation calls for additional evidence, that evidence still needs to be retrieved and checked.

## Boundaries and rollback

The observed persistence test establishes post-run access on this project's detached writable mount. It does not establish long-term retention, large or binary retrieval through MCP, or persistence on a read-only or differently configured project. Before opt-in elsewhere, validate that notebook's complete artifact set, durable archive, permissions, failure capture, and recovery path. The synthetic fixture confirms the reporting workflow and layered diagnosis. Scientific model acceptance, independent validation and release authority still follow the governing plan. Roll back by stopping use of the optional publisher and retaining all evidence and prior receipts. [Output policy and operator instructions](DEEPNOTE_CODEX_OUTPUT_POLICY.md)
