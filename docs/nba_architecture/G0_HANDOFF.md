# NBA V2.5 P0 — G0 handoff and signed-off audit receipt

**Decision: G0 FAIL** (November 16, 2026). The versioned engineering interface is staged and its focused tests pass, but required independent/team signoff, original pregame eligibility inputs, and scientific component readiness are absent. **No release or research-model adoption is authorized by this receipt.**

## Reproducible engineering evidence

- Repository: `royalexx/pickem-auditor`; branch: `research/nba-p0-sojc-architecture-g0-20261116`; base `main` commit `912bc7010058092ea735dcda0aa941429194474b`.
- Code and schema test commit: `cc760b9ea2c32db7655d6dc573d09fa6d5910488`.
- Deepnote project: `9cc31536-93be-44db-bdeb-06fba3f61410`; unscheduled notebook `5429ea77f5f54ccdb83e996fba072996`; detached **read-only** run `44dc42f2-2a73-45d9-bec0-d4065a17704a`.
- Final test: **29/29 Python unittest methods passed**, **0 failures/errors**, JSON Schema Draft 2020–12 structural check **PASS**. Actual files were read by exact Git commit and SHA256-printed in the run; hashes are in `G0_HANDOFF.json`.
- Regression history: initial 21/21; strengthened 25/26 and 28/29 test passes exposed two failure-reason/order mismatches, both corrected; final run 29/29. This is **not** a predictive validation or a complete existing-repository regression test.

## Ownership and graph

`WS1 source receipts & pregame snapshot -> {S statistical PMF, G shared game state}; (WS1 + G) -> O participation/minutes/allocated player opportunity; (S+G+O) -> J shared-scenario coherent primitive and combination statistics -> original-offer O/U/P -> C independent settlement, calibration and comparison -> later gated release.`

Family owners and exact write boundaries: WS1 source/provenance; S statistic likelihood/PMF; G/J shared state and joint outcomes; O appearance, minutes and rotations; C independent calibration/evaluation and immutable settlement linkage; P0 only common versioned interfaces/fixtures and architecture inventory; release custodian independently accepts gates. See `P0_CONTRACT_AND_OWNERSHIP.md` for all prohibitions and versioning.

## Outstanding blockers and disposition

1. The expressly named `NBA Parallel Architecture and Monte Carlo Execution Prompts` packet was not in the attached/project file set available in this session, so packet-exact implementation acceptance cannot be asserted.
2. All NBA WS1/WS2/WS4/WS5/Phase6–8 research PRs remain draft or stacked; none establishes independent code integration or a source-certified future participant universe.
3. WS1 original-source timestamp and league game-active eligibility certification remain incomplete; WS2 conditional M0 has no fitted P1/P2 appearance probabilities. A historical postgame participant oracle is not a valid pregame forecast.
4. NBA WS3 dedicated fitted stat outcome family is absent. WS5 J2 exists and passes mechanical checks, but its historical forecast performance regressed versus simpler J0; no real prospective J2 adoption.
5. Versioned source-to-S/O/G/J/C adapters have not been accepted by their respective owners against genuine shared fixtures. The P0 synthetic ten-player case establishes structural safety only.
6. No independent reviewer or team custodian has signed G0. This manifest contains a **procedural self-attestation** by the integrator, **not a cryptographic signature or independent acceptance**.

## Exact gate

**G0 = FAIL.** Required re-review sequence: each owner implements/verifies adapter against the 1.0.0 contract; WS1 supplies source-authenticated pregame player/event/market receipts and eligible roster evidence, O supplies supported participation method or retains abstention, J references exactly the same G/O scenario identities and distribution conditioning; C independently re-runs hostile and fixture checks, verifies final tested Git commit and quote/settlement joins. Only after an external signer records a new receipt could the gate move to PASS. The current FAIL record must be preserved, not rewritten.

**Signed-off-by:** NBA V2.5 lead architecture integrator — ChatGPT (procedural self-attestation, G0 FAIL; no independent signature).

**Safety:** No model training, weight optimization, probability promotion, existing engine modification, NUTS resume, new collector/scheduler, historical receipt rewrite or main-branch merge performed.
