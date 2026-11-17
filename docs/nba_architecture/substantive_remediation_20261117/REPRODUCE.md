# Substantive G1 remediation reproduction

Executable candidate: 9e8145972077a598687eaabdbc559f3cbce5e4d7.
Base: cea11ebf5c11f59c1f62a78c86892451f614a670 (PR175).
Governing PA-V25-MASTER-2026-11-09 / v1.1. Accepted G0 remains59d28dc unchanged.
Use Python3.12, NumPy2.3.5, SciPy1.17.0, jsonschema4.26.0 and mpmath1.3.0;
`pdftotext` from Poppler is needed for original PDF extraction.

From a clean exact executable checkout:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=.:tests/nba_architecture \
python -m unittest discover -s tests/nba_architecture -v
```

Expected529methods pass. Dedicated new controls:

```bash
OPENBLAS_NUM_THREADS=1 PYTHONPATH=.:tests/nba_architecture \
python -m unittest tests.nba_architecture.test_exposure_certificate_v1 tests.nba_architecture.test_gamebook_v1 -v
```

Expected16methods pass; controls overlap architecture counts. The new O2 producer
is `v2.nba_o_certified`, and the new validator entrypoint is
`v2.nba_architecture.families_certified_v1`. Existing producers/validators are
unchanged. The certificate receipt names whether exact-mass bounded certificate
or original complete floating LP succeeded; it never infers genuine q.

The new `admission_v1.admit_gamebook` accepts only the exact independently
reviewed PDF/capture for three printed-content capabilities. Read the preserved
`source_search/nba_pdf.raw` bytes and `nba_pdf.receipt.json`; copy its `sha256`
to `raw_sha256` before calling. Set required_capability to one of
OFFICIAL_PRINTED_DURATION, OFFICIAL_PRINTED_BOX_SCORE or OFFICIAL_PRINTED_DNP_ROWS.
The registry is fixed in code; callers cannot override it. Output continues to
report original_pregame_certified=False and upstream_training_rows_admitted=0.

`gamebook_identity_v1.join_game_ids` separately checks the listed26rows against
exact ESPN raw content and receipt, using team/jersey/name and all box counts.
This helper is not included in the three admitted capabilities; it supplies no
future target roster or dated transfer evidence. Source event time retains its
original minute precision and supplies only a local calendar-date join.

Independent exact candidate, original old budget red, fresh public root checks,
manual/network official source checks and adversarial probes are preserved in
`independent/`. See its portable scripts, decisions and numeric contract limits.
All old audits, source inventories, owner branches and accepted G0 remain
unchanged. New raw source searches include failed HTTP403/400/timeouts. These
are evidence of bounded attempts, not a claim that every possible source was
searched. Existing conditional-minute fit text is preserved in its actual
TOOL_RETURNED_UTF8_PROJECT_FILE_TEXT domain, not providerHTTPbytes or an admitted fit.

No historical fitting/scoring, holdout decompression, NUTS, weights, operational
schedule, merge or production/Tier change is part of this packet. Rollback:
discard this branch; neither prior APIs nor trusted production were changed.
