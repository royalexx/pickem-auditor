# WS6 independent weather audit — November 15, 2026, 15:42:09 UTC

**Blocked by data; shadow only. No weather improvement was estimated. PR #135 stays draft and unmerged.**

| Integration result | Count |
|---|---:|
| Original observations inherited intact | 1,845 |
| Existing S2 / C2 nonpush references | 1,672 / 1,767 |
| Existing J1 / J2 / J3 | 58 / 58 / 0 |
| Delivered O1 / O2 / O3 / O4 / O5 forecasts | 0 each |
| Authenticated fitted weather forecasts | 0 |
| Actual unchanged fallback forecasts | 0 |
| Exact neutral/weather pairs | 0 |
| Prior S2/C2/J1/J2 exact intersection | 49 |
| Independently weather-certified exposure | 0 of 12 events; 0 of 1,845 observations |

These are delivered-artifact counts at the stated cutoff. Source acquisition was
still in progress. The original model counts come from the authoritative prior
WS6 audit; this audit did not rehash the large original ledger.

WS3's original delivery bytes independently match
`77cafef1de283810cff6c93400fd536c703ad4bca27ed43b990b7a9fbfae4501`.
Its source code explicitly implements an unchanged control with unfitted zero
weather coefficients. It reports zero actual neutral, weather and fallback
forecasts. Synthetic fallback tests must not become actual forecast counts.
The newer WS3 source audit run `5bec00ce-4f1c-4992-94bf-549fb24dead2`
passed 31 synthetic tests, then failed with `KeyError: None` on unresolved event
identity. It did not supply a successful source audit or a forecast freeze.

WS1 has newly archived probe/raw sources, but no weather feature pin was visible
in the cutoff inventory. Source issuance, target valid interval, feature freeze,
stadium coordinates/roof and complete original byte integrity cannot all be
authenticated. Every exposure remains unverified. A probe receipt is not a
certified model feature. In particular, the Cleveland probe retrieval at
`2026-11-15T15:37:42.707016Z` follows all existing original S2/J1/J2 forecast
timestamps. Reject its use in those original freezes even if its issue time was
earlier. A later legitimate pregame prediction must have a separate version.

All seven components—team volume, pass/run allocation, player usage, efficiency,
defensive involvement, role/game-state uncertainty, and joint simulation—are
`WEATHER_EFFECT_NOT_ESTIMATED`, with zero matched pairs. Distribution and score
differences are **null**, not zero. No official postgame scoring occurred.
C2 remains conditional on nonpush; it has no invented push distribution.

## Append-only comparison and limitations

[Reference ledger](freeze/comparison_reference_ledger_1845.jsonl) contains exactly
1,845 rows, each addressing the unchanged original observation by parent SHA-256
and zero-based index. It inherits every original field, probability, timestamp,
rejection and model abstention. It adds an unavailable weather-audit state.
It is a logical append-only comparison, **not a newly materialized or reverified
copy of the original probability ledger**.

- Parent: `242c4404a6b1505844528ee7096f86060f459df6517f0420f618deef8888fbba`.
- New reference ledger: `4c60e0c21125010487c772ce222a6abc1ea441a87c8eed16c43dce1467b69dfd`.
- New comparison freeze index: `1e683c58cd4bae99221eb23a1dd26283962670b5a1c12ac53f96b5d82c9fde11`.

[Machine report](freeze/independent_weather_audit_report.json) contains counts,
timestamps, training-cutoff visibility, all rejection/abstention denominators,
component states and scoring prerequisites. [Per-event references](per_event_source_model_references.json)
retain the 11 existing J1/J2 source-input/output SHA-256s, exact kickoff,
creation time, training cutoff and code commit, alongside explicit missing
weather hashes for all 12 events. These neutral references are inherited prior
audit evidence, not newly rehashed original model files. Available new WS1
source receipts are included as unverified raw-source claims.

## Independent tests and Deepnote

68 local checks passed: 29 existing WS6, 8 new append-only adversarial checks,
and 31 frozen WS3 neutral/weather regressions. New tests reject parent tampering,
row reordering, denominator changes, injected weather predictions, bad parent
references, duplicate/nonfinite JSON and overwriting an existing freeze. They
also verify original probabilities and abstentions survive materialization.
These are integrity tests, not evidence of predictive accuracy.

WS6 notebook `502eb773a98c49bdaed45a6016fe8353` was created and inspected.
Its detached read-only run creation was rejected: **Rate limit exceeded**.
No WS6 run ID exists. Original successful WS6 join run remains
`27267e1d-377c-40a8-a566-47a297fb4eeb`.
WS4 weather inspection run `7d72644f-da42-423d-92cf-fb14125a7577` was still
running when checked; no success is assumed. Final source/model rehashing and
full-ledger materialization remain blocked by runtime/data access.

When runtime is available, execute the inspected offline audit and materialize
only from the exact parent bytes:

```sh
python research/ws6_nfl_sunday_20261115/weather_append_only_v1.py \
  --report reports/nfl_20261115_ws6_weather_audit_v1/audit_report_input.json \
  --parent reports/nfl_20261115_ws6_real_comparison/canonical_s2_c2_j1_j2_original_forecast_comparison_v1/comparison_ledger_1845.jsonl \
  --destination reports/nfl_20261115_ws6_weather_materialized_v1
```

This only appends audit fields; it never reconstructs forecasts. A future weather
pin or model output requires a **new** audit version and independent validation,
not editing this cutoff snapshot. Preserve original forecast cutoffs and starter
conditioning. Score only official, source-certified applicable settlements on
identical contracts with paired game-clustered intervals. One Sunday cannot
establish a statistical winner or justify production promotion.

Governing authority: `PA-V25-MASTER-2026-11-09 / v1.1`; bounded Phase 0R/1
source/probability integrity and Phase 1.5 attribution. No model training,
WS6 weather collection, original model edits, promotion or merge. Rollback:
discard these additive research files; all prior freezes remain unchanged.
