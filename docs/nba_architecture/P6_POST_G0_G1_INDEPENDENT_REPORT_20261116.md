# NBA V2.5 P6 — Post-G0 independent G1 adversarial audit (2026-11-16)

**Gate verdict: G0 PASS (previously independently accepted); G1 NO-GO / BLOCKED for P1–P5 owner readiness; P6 synthetic QA harness TESTED/PASS.**
**Scope:** mathematical, software, temporal and provenance red-team of frozen contract and available owner evidence. **Not** a historical predictive study, optimizer fit, model promotion or production authorization.

## Provenance and authorization

- Source candidate reviewed: G0 SHA \`59d28dc23be97de2a6a82d22be8338151e31f5b6\`, contract \`nba-sojc-contract/2.0.0\`; accepted independently in PR #161 and closed issue #149. Immutable G0 acceptance receipt raw SHA256 \`a90dbe624b44013d6eaf03163726fcfe1cd9f7055b2d657a7d3fed100d3f519d\`.
- Pre-existing P6 branch: \`audit/nba-p6-g1-current-candidate-20261116\`; 327/327 independent+upstream tests previously run at \`5ce05bf31b6efc3b70114be56a496fb74c00d649\` in Deepnote run \`92e6fd19-e7ec-4075-b1b0-9de6298277cf\`. That earlier report's claim **"G0 not accepted"** is historical and superseded; the test findings remain frozen.
- **New isolated post-G0 P6 branch:** \`audit/nba-p6-post-g0-independent-g1-20261116\`, forked from the existing P6-only research branch; **exactly tested commit** \`27990afa4f1c8736d89358ab883e029539453582\`.
- **New independent tests:** \`tests/nba_architecture/test_p6_post_g0_reference_and_boundaries.py\`: 23 new controls. This branch inherits 327 pre-existing G0/P6 regression tests. No owner forecasting/collector/scorer implementation changed.
- Independent Deepnote clone from exact tested GitHub SHA, notebook \`ba96223e01ae4d03aedf6f85ddb73d2e\`, detached **read-only** run \`7e29e3e7-abb5-43d0-b63a-69d4702cfc2a\`; test command \`python -m unittest discover -s tests/nba_architecture -p 'test_*.py' -q\`.
- **Observed outcome:** 350/350 PASS, 0 failed/errors/skipped, exit code 0, 7.260 seconds. Complete command stdout+stderr SHA256 \`426ac54995817052cffe6a5a87278df36cdb0aef7c354d75ca7f3577eb77ae43\`. Python 3.12.16; NumPy 2.3.5; SciPy 1.17.0; jsonschema 4.26.0. Isolated \`pip --target\` dependencies were used; unrelated global TensorFlow/Deepnote requirements triggered resolver warnings, but tested process imported the pinned requirements successfully.
- SHA256 of newly tested QA file: \`03459760f1d829c63afcf892be35c5b74cdc277360d37f63fa556b62b0d7401e\`. G0 source file SHA256 receipts are in the accompanying JSON.

The named “NBA parallel execution packet” was not among the inspectable conversation uploads. The user's P6 directive plus the independently accepted repository v2.0.0 contract, GATE_BOUNDARIES_V2 and previous P6 owner handoff are the tested operational specification. Do not claim to have independently read a missing packet.

## Evidence-backed adversarial matrix

| Attack / mathematical issue | Observed | Family implication |
|---|---|---|
| Post-event feature available under innocent feature name; missing original feature clock | **PASS**: both resealed mutations rejected | G0 temporal validation works on tested fixture; real source publication timestamps still P1 BLOCKED |
| Forged unresealed raw receipt; postgame feature alias; orphan correction | **PASS** (current/new + inherited red regressions) | Original raw-byte external trust and complete correction vault still P1 BLOCKED |
| Wrong player/team, duplicated player ID, stale or mismatched scenario identities | **PASS** against synthetic contract mutations | Cross-shard player/trade/global duplicate-game registry still P1 BLOCKED |
| Negative PMF mass, wrong normalization, zero/tail/support | **PASS** contract rejects; full integer numerical reference oracles PASS | Fitted S PTS/REB/AST/3PM with cutoff and provenance still P2 BLOCKED |
| Evidence-bound OUT, DNP, played-zero participation and impossible positive counts | **PASS** inherited G0/P6 conformance | Genuine O participation/rotation evidence still P3 BLOCKED |
| 240 regulation, 265 one-OT, 290 two-OT, 315 three-OT minute identity | **PASS** independent arithmetic; existing G0 law feasibility regression PASS | Aggregate proof does NOT establish five concurrent players |
| **Explicit six-on-floor counterexample**: 6 players x 40 minutes = 240 team-minutes with 6 active during [0,40), none for [40,48) | **PASS: reference interval checker rejects despite aggregate 240** | **P3/P4 G1 BLOCKED:** requires actual substitution/interval witness for all 48+5xOT minutes, not a G0 defect |
| 2PM/3PM/FGA/FGM/FTA/PTS; assists/rebounds; same-draw PRA | **PASS** inherited conservation tests; new made-threes and independent PRA mutations rejected | Real game event/shooting and source-bound J simulator still P4 BLOCKED |
| SHA/seed and changed game key | **PASS** on deterministic finite fixture | Real source-/model-artifact hashes and scenario replay still blocked for owner adapters |
| Poisson \`lambda=2\`, \`y=3\`: NLPD | **PASS**, exact \`2 - 3 ln 2 + ln(3!)\` | Numeric reference only; real C scoring adapter P5 BLOCKED |
| Poisson CRPS: independent CDF and pairwise-distance formulas | **PASS** across y=0/1/3/7 | C scorer integration P5 BLOCKED |
| NB(r=2,p=.5), y=0: CRPS = 26/27; NLPD=ln(4) | **PASS** CDF + distance identities | C full-count kernel P5 BLOCKED |
| NB(r=3,p=.4), y=2: log PMF and CRPS independent identities | **PASS** | C fitted scorer P5 BLOCKED |
| Small joint two-atom ES = \`2 - sqrt(2)/2\`, VS_0.5 = 2; compare independent coupling | **PASS**, dependence changes both scores despite same marginals | C joint score provider P5 BLOCKED |
| Randomized PIT / Over Under Push / point-vs-draw RMSE | **PASS** mathematical oracles; inherited threshold tests | C actual PIT, interval, NLPD and MAE/RMSE implementation P5 BLOCKED |
| 5,000 vs 20,000 MC paths | **PASS**: fixed-p SE ratio 2 exactly | Not a run of 5k/20k full J scenario precision experiments |
| 10,000 paths over two games, duplicated path replication | **PASS**: exactly two observed game clusters; game-level score unchanged by replication | Cannot treat scenarios as independent outcomes; actual C resampling P5 BLOCKED |
| S_ONLY, S_O, S_O_J pipeline graph | **PASS** reference dependency graph, stages disjoint from complete pipeline IDs | Real regularized simplex optimizer and chronological CV P5 BLOCKED |

**Interpretation:** These finite reference controls are reproducible and support G0 contract regression stability and P6 test-harness readiness. They do not independently certify real NBA historical features, fitted families, full game rotations or a callable C optimizer. A passing reference assertion such as “the three complete pipeline names are not stage labels” cannot verify an optimizer that is absent.

## G1 family decision matrix

| Workstream | P6 G1 verdict | Evidence required before PASS |
|---|---|---|
| **P0/G0 accepted contract** | **PASS for exact accepted SHA only** | Any contract revision requires a new independent review; old FAIL reports retained |
| **P1 canonical NBA source** | **BLOCKED** | Verifiable raw source bytes/chain/hash/availability, pregame snapshot generation and outcome vault segregation, player/trade identity and duplicate-game tests |
| **P2 S distribution family** | **BLOCKED** | Runnable complete PTS/REB/AST/3PM distributions and numerical oracle, explicit fit cutoff, leak-free O/J input and deterministic seeds |
| **P3 O opportunity family** | **BLOCKED** | Callable conditional minutes and participation laws, DNP ambiguity semantics, shared-G conservation and five-on-floor **time-interval** witness |
| **P4 G/J simulator** | **BLOCKED** | Original S/O/G-bound primitive scenarios, 2-team shot/rebound/assist event accounting, same-scenario combos, full regulation/OT substitution witness, original hash replay |
| **P5 C evaluator/optimizer** | **BLOCKED** | Callable full-score implementations, point/draw loss separation, immutable distribution warehouse, chronological full-pipeline simplex constraint, game/date bootstrap and cached PMF numerical precision |
| **P6 independent QA** | **PASS: test-harness engineering**, **G1 system gate remains NO-GO** | Re-run after P1–P5 deliver version-pinned artifacts; review each owner branch independently |

At inspection time, \`research/nba-p3-o-family-g1-20261116\` and \`research/nba-p5-c-scoring-optimization-g1-20261116\` compared **identical** to the accepted G0 SHA (zero diff), so neither provided newly implemented G1 evidence then. Existing P1/P2 preparatory PRs #150/#158 predate G0 and explicitly do not deliver engineering-complete adapters. No accepted P4 G1 submission identified. These are time-specific repository observations, not definitive claims about future owner commits.

## Bugs, limitations and ownership routing

1. **No new critical G0 implementation bug proven** in this 350-test execution. Four older P6 invalid-acceptance bugs are covered by green exact-SHA regression tests on the accepted repaired contract; the old red evidence stays immutable.
2. **P1:** Block source authenticity without independently inspectable original bytes and chronological receipt chains; never relabel retrospective pregame proxy as certified original.
3. **P2:** Do not accept any model using target-game actual minutes, final usage or same-game outcome in its training/prediction feature manifest; fit cutoff must be prior to forecast.
4. **P3/P4:** Close the five-concurrent-players proof gap with legal full-clock substitution intervals; 240+25xOT sums are necessary but not sufficient. Submit actual scenario IDs, two-team identities and shooting/rebound/assist ledgers.
5. **P5:** Implement C on whole distributions supplied by complete pipelines, not votes from S/O/J stages. Report scores at **game/date observations**, never thousands of numerical Monte Carlo paths; validate independent oracles and expected finite-M uncertainty.

All findings route to existing issue #160. No owner source, likelihood, minute allocator, joint generator, calibration code, collector, existing test, frozen forecast, release gate or automation was silently repaired.

## Formal recommendation

- **G0:** technical PASS already independently established for \`59d28dc...\`; accepted G0 is not reopened by this P6 extension.
- **P6 standalone test-suite readiness:** PASS, exactly 350/350 checks at \`27990afa...\`. The P6 implementation is a useful adversarial harness.
- **G1 overall:** **NO-GO / BLOCKED** for P1/P2/P3/P4/P5 engineering readiness, pending callable source/family/evaluator artifacts and independent QA against their exact SHAs. Neither a synthetic green suite nor an empty owner branch merits a PASS.
- **G2 and historical P8/P9/P10, weights, prospective model quality, Tier/release:** NOT AUTHORIZED by this QA packet. Historical scoring, weight fitting, forecast/model changes, and production approval **not performed**.
- **Rollback:** close this draft QA PR without merge, leaving accepted G0 and earlier P6 evidence untouched. Retain this immutable exact-commit execution receipt and reopen P6 gate after each owner submits reproducible artifacts.

**Reviewer limitation:** This report is an independent, isolated QA role with real executable adversarial evidence, not a claim of external institutional certification or acceptance by the absent source/S/O/J/C implementers.
