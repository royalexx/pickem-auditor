# Independent G0 review and repair — November 16, 2026

**G0_REPAIRED_PENDING_INDEPENDENT_ACCEPTANCE**. Reviewer: independent ChatGPT/Codex session, mathematical/software/source-integrity contract auditor; subsequently repair author. No independent acceptance of these repairs is asserted. Governing plan PA-V25-MASTER-2026-11-09 / v1.1. Engineering-contract scope only; no training, scoring, production authorization, or merge.

Reviewed PR #153 head: ae4fb339a1acb8b6e113c9ed47e84004017db3dd, verified live through GitHub. Base (PR #147 architecture): 3f38ef9d1f6f2e50623a5623fb5826efc67cf7b2. Eight-file repair diff inspected; production engines/collectors were absent from that diff. Live main observed at 912bc7010058092ea735dcda0aa941429194474b. Current code/tree, not prior PASS narratives, governed findings.

QA branch research/nba-g0-independent-qa-20261116 at 10315b6 preserves six original challenges and the five failing negative cases. Repair branch research/nba-g0-final-repairs-20261116; substantive repaired implementation and expanded tests pinned at **8474ee55ff926e1f8c0b83e5b3c9a77c4c03516a**. Later commits add evidence only. Rollback: use the reviewed ae4fb339 tree; retain failure evidence and do not claim acceptance.

## Discovered defects and repairs

All reproducers use correctly resealed synthetic payloads, so content hashes do not detect them. `test_independent_final_20261116.py` contains the minimal reproductions. `red.log` preserves actual pre-repair exceptions and failures.

1. **Shared rebound opportunity duplication** — `validate_scenarios`: one own miss could generate both an offensive rebound and the opponent's defensive rebound because each was bounded separately. Repair additionally bounds their sum by misses of the shooting team. Conservative FTA maxima remain necessary bounds, not a play-by-play witness.
2. **Self-assist** — `validate_scenarios`: the sole field-goal scorer could claim the sole assist while meeting the team assist cap. Repair bounds each player's assists by all teammates' FGM. Together with total assists <= total FGM this enforces the aggregate no-self-assist matching constraint.
3. **Joint conditioning relabel** — `validate_distribution`: a marginal could change unconditional to participation-conditional while retaining the same draws. Repair requires exact equality with bundle conditioning. This does not fit participation or prove a producer's conditioning claim.
4. **Joint uncertainty inflation** — `validate_distribution`: count/ESS and associated zero-event bound could be internally consistent but disagree with actual weighted draws. Repair recomputes draw count, ESS and maximum marginal standard error. An additional regression rejects zeroed SE. Weighted ESS remains explicitly heuristic, not evidence of independent historical games or MC mixing.
5. **Null-line push bypass** — `validate_evaluation`: an offered outcome equal to the original integer line could be labeled settled by omitting the repeated evaluation line. Repair always uses the frozen view line for push classification. Existing null repeated-line ordinary settlements remain compatible.

The previous seven repairs remain exercised by the unchanged adversarial and closure suites. Original G0 FAIL and previous P0I BLOCKED files are byte-identical to the PR #147 base; raw SHA-256 values appear in receipt.json. No original evidence has been overwritten.

## Ten review families

“PASS” here means observed engineering checks after repair, **not independent acceptance** of author-modified code or a proof that all possible adversarial cases were exhausted.

| Family | Reviewed-head result → repaired checks | Evidence and limits |
|---|---|---|
| 1 Repository/history integrity | PASS → PASS | Live head pinned, eight-file prior diff; only contract module and new tests changed substantively here; preserved-history byte checks and raw file hashes |
| 2 Source profiles and temporal boundary | PASS structural → PASS structural | Existing historical/prospective, future-feature, publication, retrieval/ingestion and correction tests rerun. Retrospective date proxies explicitly uncertified; local date and source truth require external corroboration |
| 3 Player/game/model identity | PASS exercised → PASS exercised | Existing cross-object identity and lineage negatives rerun; synthetically bound IDs do not authenticate real rosters |
| 4 Complete predictive PMFs | FAIL → PASS exercised | Four primitives offer-free, integer support, normalization and tails tested; repaired conditioning join. Analytic error bounds are producer declarations, not proof of fitted-law correctness |
| 5 S/O/G/J architecture | PASS interface → PASS interface | Complete pipeline modes represented, dependent stages are lineage, not votes. Actual adapters and optimizer integration remain G1/G2 |
| 6 Participation/minutes | PASS aggregate → PASS aggregate | DNP/played-zero distinction, unknown P1/P2, eligibility, OT and minute conservation tests. Aggregate minutes admit a five-on-court allocation; no actual rotation chronology represented |
| 7 Joint physical constraints | FAIL → PASS exercised | New shared-rebound and self-assist negatives, feasible positive counterpart; original scoring/shot/composite/same-draw tests. Not full possession-by-possession NBA officiating or overtime trajectory verification |
| 8 Original offer and settlement | FAIL → PASS exercised | New null-line bypass; unchanged quote/player/game/line/terms/void/DNP tests. Settlement API consumes previously validated frozen objects: hashes alone are not authenticity, legal interpretation, or official-result verification |
| 9 Numerical uncertainty and references | FAIL → PASS exercised | Recomputed J count/ESS/SE; independent factorial Poisson and closed-form NB(r=2,p=.4) triplets vs SciPy at 0, 2, 2.5; small weighted joint fixture. No predictive accuracy claim |
| 10 Reproducibility/downstream boundary | PASS tests; acceptance pending | 181 tests, 146 upstream tests, Draft202012 schema and fixture object validation, three exact-byte goldens. Adapter capability gaps retained in CONFORMANCE_BLOCKERS_V2.md |

## Execution and hash semantics

`receipt.json` pins the repaired code/test commit, Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0, jsonschema 4.26.0, raw-file SHA-256 values, fixture hashes, and exact unittest output hash. `green.log`: 181 tests, zero failures/errors/skips. Baseline at ae4fb339: 172 tests passed locally before repair. Expanded suite adds nine tests; six original red cases included five failures and one positive control. Existing test files and goldens remain unchanged. `reproduce.py` runs schema checks, validates every golden contract object with format checking, compares canonical regeneration bytes, reruns unittest, and verifies preserved evidence.

`upstream.json` and WS*.log record fresh separate exact-SHA original-version runs: WS1 25/25; WS2 25/25; WS4 33/33; WS5 63/63. They are not v2 conformance tests. `run_upstream.py` reproduces those checkouts from a local full Git clone.

Git commit SHA identifies a Git object; raw-file SHA-256 hashes stored file bytes; contract content_hash hashes canonical JSON excluding itself; receipt_sha256 hashes the source receipt payload excluding itself. These values are not interchangeable.

Deepnote project 9cc31536-93be-44db-bdeb-06fba3f61410 was inspected through MCP; prior detached run 60cf75ab-5fb2-4cad-b9ad-1d3a5804617a snapshot reported 172/172 at ae4fb339. It remains prior author evidence. This review's fresh execution is local cloud Python, not a claimed new Deepnote run. No production notebook or schedule was executed or changed. No attestation of current operational collector health or training-pause enforcement is made.

## Next reviewer handoff — ready to paste

Act as a new independent NBA G0 mathematical/software/source-integrity auditor. Review royalexx/pickem-auditor branch research/nba-g0-final-repairs-20261116. Substantive repaired code/test SHA: 8474ee55ff926e1f8c0b83e5b3c9a77c4c03516a; inspect latest evidence-only head too. Review the complete original architecture and PR #153 ae4fb339, then the five new repairs. Do not trust this report's PASS checks. Reproduce red cases at QA SHA 10315b6 and green cases at repaired SHA, run unittest discovery, reproduce.py, Draft202012 and byte-for-byte goldens; inspect exact hashes and preserved FAIL/BLOCKED evidence. Challenge other source, conditioning, G/O/J reference, physical feasibility and immutable settlement assumptions independently. Keep G0 distinct from G1 adapter/fit/calibration obligations in CONFORMANCE_BLOCKERS_V2.md. If no further blocking defect remains and you make no substantive repairs, publish independent exact-SHA G0 acceptance and update #149/#153/new repair PR. If you repair code, repeat the independent handoff rule. Do not merge, train, optimize, score historical skill, authorize production, or treat this author's post-repair tests as independent acceptance. P1–P6 remain gated until that acceptance.
