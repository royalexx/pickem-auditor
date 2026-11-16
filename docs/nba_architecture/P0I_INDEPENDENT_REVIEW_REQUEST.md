# P0I — independent adversarial audit request (unassigned)

**Target repository:** royalexx/pickem-auditor, draft PR #147, research/nba-p0-sojc-architecture-g0-20261116.

## Independence condition
Assign an auditor who did **not** author, edit, or direct the P0R source and tests. The author may only provide source/doc links, reproducibility manifests and failing-case explanations. A Deepnote run by the same author or a different notebook is **not independent**. Do not reuse an author-authored "review verdict" as independent approval. If no separate reviewer is available, mark G0 **BLOCKED** and leave this request open.

## Frozen review artifacts
- Exact final SHA must be copied from PR #147 **after** the P0R freeze, not taken from this template.
- Fetch \`v2/nba_architecture/v2_contracts.py\`, \`schema-2.0.0.json\`, committed synthetic golden fixtures in \`tests/nba_architecture/golden_v2\`, both old and new G0 records, \`ADR_0002_V2_OFFER_FREE_SOURCE_PROFILES.md\`, \`CONFORMANCE_BLOCKERS_V2.md\`.
- Verify each raw source byte hash and GitHub commit manifest; inspect original prior workstream branches #137–#146 and historic Bayesian code.
- Use a distinct analysis/execution context under the reviewer’s control; do not overwrite the author's frozen output path.

## Ten required adversarial challenges
1. Source origin/availability: historical proxy 2022–23 with actual 2026 retrieval, prospective original pre-freeze; try to transform proxy into original.
2. Timestamp semantics: unknown and untrusted published-at, inversions, fake earlier observation, unlinked source correction, model fit after freeze.
3. Offer-free and offer-bound: PTS/REB/AST/3PM no offered line, original exact quote side probabilities; no synthetic economic claim.
4. S-only, S+O and J-derived marginal supports, conditioning, uncertainty, pipeline lineage; no dependent-family double vote.
5. DNP vs played-zero, participation probability unknown vs 0/1, product void rules separate.
6. Home/away IDs, team minutes 240+25×OT, unique player/scenario IDs, exact G/O joins.
7. PTS=2×2PM+3×3PM+FTM, FGA and 3PA constraints, rebounds, assists, PR/PA/RA/PRA from same draw.
8. SHA create-once byte immutability, linked revisions, deterministic seeds, migration without v1 rewriting.
9. Real WS1/WS2/WS4/WS5 + Phase6–8 adapter blockers versus demonstrated actual consumption; supply independent precise evidence for any blocker removal.
10. Future chronological Monte Carlo feasibility without outcome leakage or optimizer fitting during G0.

Construct **new** positive and negative cases not copied verbatim from the author’s 31/v2 tests. Run:
\`\`\`bash
python -m unittest discover -s tests/nba_architecture -p 'test_*.py' -v
python -m json.tool v2/nba_architecture/schema-2.0.0.json >/dev/null
\`\`\`
plus reviewer-authored adversarial suites and the scoped WS1/WS2/WS4/WS5 source-branch compatibility test commands in the candidate manifest. Verify Python/jsonschema/NumPy/SciPy versions.

## Independent decision artifact
Write **new append-only** \`docs/nba_architecture/G0_INDEPENDENT_<reviewer_id>_<date>.json\` with reviewer identity/role, exact reviewed Git SHA, source/tree/file SHAs, original test additions and commands, reproducible test counts/exceptions, 10 challenge verdicts, every WS1/S/O/G/J/C conformance status, SHA of the author's candidate, limitations, and \`G0_PASS\` or \`G0_FAIL\` or \`G0_BLOCKED\`. Recorded technical attestation is acceptable if transparently attributed; a cryptographic signature must be actually verifiable. Do not alter existing FAIL/candidate records.

**No new workstreams start from G0 author receipt alone.**
