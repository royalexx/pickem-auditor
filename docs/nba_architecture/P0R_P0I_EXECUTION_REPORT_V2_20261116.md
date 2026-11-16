# NBA P0R/P0I recovery execution — November 16, 2026

**Stage A:** contract-engineering candidate ready for independent review. **Stage B:** independent audit unavailable. **New decision: G0 BLOCKED.** Historical G0 FAIL remains unchanged at `docs/nba_architecture/G0_HANDOFF.json` (Git blob `48933082f0cf89ec1dc473fd0e10c1ac64e5d01d`). The preserved v1 Python/schema/tests were not rewritten.

**Contract v2.0.0:** `v2/nba_architecture/v2_contracts.py`, `families_v2.py`, `schema-2.0.0.json`; ADR-0002 records breaking major-version migration. Historical reconstruction retains actual modern retrieval/observation/ingestion clocks and date-only as-of limitations; original prospective requires receipts strictly before decision freeze. Unknown publication remains null. Source corrections are chained and prohibit backdating. Strict envelope and source-feature fields reject hidden postgame data.

A complete PTS/REB/AST/3PM distribution is frozen **without** any bookmaker line. S-only, S+O and S+O+J outputs bind source/model lineages and O output SHA when dependent. G/O/J share scenarios, minutes and participation witnesses; J physical constraints enforce shooting, team minutes (240 + 25×OT), assists, rebounds and same-draw PR/PA/RA/PRA. Quotes are optional source-bound records; Over/Under/Push, DNP, zero minutes, void, settlement revisions and numerical weighted-MC uncertainty remain distinct. No S/O/J dependent-stage ensemble votes.

## Executed Stage A verification

Author-controlled SHA-pinned code commit: `35281d369ece4016fc6e6a5af8e938e04cc2ec30`; Deepnote unscheduled detached readonly run `94c6e777-9961-4b70-9249-87f2b0ddd532` in notebook `947a0ceac5694f01bc7d4ef57b40946a` (project `9cc31536-93be-44db-bdeb-06fba3f61410`).

```bash
python -m unittest discover -s tests/nba_architecture -p 'test_*.py' -v
python -m json.tool v2/nba_architecture/schema-2.0.0.json
```

**136 tests run; 136 pass, zero failed/error/skipped.** JSON Schema Draft 2020–12 structural check PASS; three synthetic golden examples both schema-valid and byte-for-byte reproducible. Actual environment Python 3.12.16, NumPy 1.26.4, SciPy 1.15.3, jsonschema 4.23.0.

Separate author-controlled Deepnote read-only regression run `6502f8aa-6b78-450d-9388-363e79ba85ca` pinned the untouched old WS1, WS2, WS4, WS5 research commits: **25+25+33+63=146 tests passed**. The first test-harness checkout omitted WS1 `population_normalizers.py` and WS5 pinned model and snapshot files; those missing **harness** inputs were corrected, with no upstream code edits. This proves old-version regression health only, **not** live v2 adapter interoperability or independent acceptance.

## Stage B review status

GitHub PR #147 had **zero submitted reviews** when checked. No separate independent reviewer, distinct auditor-authored positive/negative test suite, reviewer attestation or cryptographic signature was available. This implementation author's isolated Deepnote tests do not constitute an independent opinion. The detailed checklist is in `P0I_INDEPENDENT_REVIEW_REQUEST.md`. A separate unassigned review issue should point at the final frozen PR SHA.

The source-named NBA Parallel Architecture and Monte Carlo Execution Prompts packet and NBA G0 Recovery addendum were unavailable among mounted and search-accessible project attachments. Governing v1.1 master plan and AGENTS.md plus the explicit current directive were inspected, but packet-exact conformance cannot be claimed.

## G0 versus G1/G2 and future work

G0 is common-contract acceptance, **not fitted participation/S distributions, WS3 scientific fitting, J2 historical win, or prospective prediction success**. G1 family adapters, P1/P2 appearance fitting, accepted O/J conditional outcome models, source/eligibility capture and calibrated C scoring remain downstream. G2 integrated-source and scenario conformance is later. P1–P6 **not authorized** without independent G0 PASS. P8 2022–23 chronological replay, P9 regularized cached-complete-pipeline weight optimization, P10 frozen 2023–24 validation and P11 2026–27 prospective shadow remain gated. No training, historical outcome scoring, model weights, paid compute, NUTS restart, source collection scheduler or production/main changes performed.
