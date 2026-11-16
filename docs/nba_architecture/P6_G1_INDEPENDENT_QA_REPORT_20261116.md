# NBA V2.5 — P6 independent mathematical, software and temporal-data audit

**Audit date:** 2026-11-16 (UTC). **Scope:** research-only, pre-G0 prerequisite. **Formal G1 decision:** **NO-GO / BLOCKED**.  
**Auditor independence:** dedicated QA branch and independently authored/adapted counterexamples, not a claim of separate legal entity, institutional signature, or acceptance on behalf of S/O/G/J/C engineers.  
**Exact source candidate:** `59d28dc23be97de2a6a82d22be8338151e31f5b6` (draft G0 PR #157; still unaccepted).  
**Exactly tested P6 code:** `5ce05bf31b6efc3b70114be56a496fb74c00d649`.  
**GitHub QA branch:** `audit/nba-p6-g1-current-candidate-20261116`.  
**Detached immutable read-only Deepnote execution:** `92e6fd19-e7ec-4075-b1b0-9de6298277cf`, project `9cc31536-93be-44db-bdeb-06fba3f61410`, notebook `4a81f01248174418853964b2578b5d6b`.  
**Requirements:** Python 3.12.16; numpy 2.3.5; scipy 1.17.0; jsonschema 4.26.0. Dependencies were installed to an isolated ephemeral target directory, not into the project storage.  
**Test command:** `python -m unittest discover -s tests/nba_architecture -p 'test_*.py' -q`.  
**Actual outcome:** **327/327 PASS**, exit code 0, no failure, 7.583 s. Full-suite combined stdout/stderr SHA-256 `feae6c9b39637d11be6b18e13c0b888dc9e6b8b193151a5767b353c580223d98`. This is a test-execution receipt, **not** G0 acceptance or fitted-model evidence.

## Gate history and adversarial change control

The earlier independent P6 draft (#152) tested an *older* v2 contract, finding four accepted invalid states (orphan source correction, verified OUT player playing, unbound J marginal, DNP counted as settled). The old failure report, red tests and independent Deepnote receipt remain immutable on that old branch. The intervening G0 candidate #156 was rejected independently for conservation-law marginal incompatibility and positive count with impossible exposure. Draft #157 proposes owner repairs. The current P6 branch was created **from #157's exact commit**, and the older independent controls were ported **without modifying any model or contract source files**.

New exact-error assertions distinguish valid rejections from incidental schema failures. The four former red tests are now green against #157. This is **regression closure evidence for the tested fixtures only**; the required independent G0 acceptance remains open (issue #149, PR #157 draft). No theorem of overall soundness is claimed.

## Executed test inventory

| Test group | Count | Outcome | Interpretation |
|---|---:|---|---|
| Core G0/architecture test directory excluding P6 | 267 | PASS | Producer/contract regression baseline on pinned candidate |
| `test_p6_independent_controls.py` | 25 | PASS | Temporal, identity, source hash, stat consistency, minutes, seed, probability, immutability |
| `test_p6_math_references.py` | 11 | PASS | Independent Poisson/NB/CRPS/PIT/energy/variogram and Monte Carlo/clustering references |
| `test_p6_red_counterexamples.py` | 4 | PASS | Four previously witnessed invalid acceptances now reject |
| `test_p6_g1_specificity_and_scores.py` | 20 | PASS | Exact rejection codes, NB CRPS rational, point-vs-draw scoring semantics |
| **Complete** | **327** | **PASS** | P6 has **60** tests; includes tests carried forward from previous independent branch |

The candidate's declared test requirements are pinned and were verified inside the detached run. The install emitted unrelated TensorFlow/Deepnote-toolkit dependency warnings for their global requirements; the isolated audit process loaded the exact pinned NumPy/SciPy/jsonschema versions and ran all 327 tests.

## Evidence-backed adversarial matrix

**PASS means the specified finite synthetic v2 contract boundary passed adversarial controls, not that genuine data, adapters, fitted predictions, or source authenticity have passed.**

| Integrity family / threat | Synthetic boundary result | G1 engineering status | Specific proof / missing evidence |
|---|---|---|---|
| Future target outcome and same-game information | **PASS** | **BLOCKED** | Explicit target-game features rejected; no independent historical source/feature producer replay to rule out mislabeled future fields |
| Realized target-game minutes leakage | **PASS** | **BLOCKED** | Closed field keys and `actual_minutes` name rejected; cannot prove a benignly named value is actually pregame without authentic source lineage |
| Wrong player/team identity, duplicated roster IDs | **PASS** | **BLOCKED** | Duplicate and team mismatch fixtures rejected; cross-shard official player identity/trades unverified |
| Missing, postfreeze or timezone-naive timestamps | **PASS** | **BLOCKED** | Rejected exact time, training cutoff, missing UTC and source clock mutations; actual first-publication and availability receipts not independently audited |
| Forged, corrupted source receipt and revision chain | **PASS** | **BLOCKED** | SHA mismatch and orphan correction rejected; raw original bytes and external immutable predecessor vault still unavailable |
| Duplicate J scenario IDs | **PASS** | **BLOCKED** | Same-bundle duplicate IDs rejected; global duplicate NBA game/forecast rows across historical partitions require canonical registry |
| DNP/played-zero/played settlement | **PASS** | **BLOCKED** | DNP with settled positive count rejected; real game DNP/void, source corrections and marketplace-specific terms are not integrated here |
| PMF integer support, mass, zero/tail and triplet | **PASS** | **BLOCKED** | Negative/duplicate support, invalid mass and coherent Over/Under/Push checked; no fitted S full-PTS/REB/AST/3PM distribution evidence |
| Regulation/overtime team-minute sum | **PASS** | **BLOCKED** | 240 per team in regulation, 265 in one 5-min overtime, fraction/minute-law feasibility tested; no real rotation evidence |
| Exactly five players simultaneously on court | **BLOCKED** | **BLOCKED** | Aggregate minute conservation does not supply substitution/interval witnesses; cannot infer five concurrent players from sums |
| Shooting FGA/FGM/PTS/FT, AST/rebound/steal/block constraints | **PASS** | **BLOCKED** | Count identities and conservative opportunity bounds checked; event-by-event shot, live rebound and credited assist ledger absent |
| Same-scenario PR/PA/RA/PRA, J PMF witness | **PASS** | **BLOCKED** | Composite counts derive from same primitive draw; forged PMF weights rejected and missing J witness fails closed; actual integrated S/O/J physics not witnessed |
| Seed and freeze/SHA reproducibility | **PASS** | **BLOCKED** | Deterministic seed, canonical hash, write-once conflicts tested; original source archive not authenticated byte-for-byte |
| Exact mathematical score oracles | **PASS** | **BLOCKED** | Independent reference functions pass; no accepted real C scorer implementation against these oracles |
| C pipeline-choice graph | **PASS (contract intent)** | **BLOCKED** | `S_ONLY`, `S_O`, `S_O_J` are **complete pipeline alternatives**; no accepted optimizer enforcing this graph |
| Game/date statistical independence | **PASS (reference)** | **BLOCKED** | 10,000 simulated paths across 2 games yield only 2 observed game clusters; real C bootstrap and CV implementation absent |
| Weight training, W0–W4, cached PMF precision | **NOT EXECUTED** | **BLOCKED** | Historical weight optimization and Monte Carlo convergence experiment expressly outside this P6/G0 task |

**Observed status distinction:** At the exact newer contract SHA, no newly discovered critical violation was proven by these tests. Prior defects were caught and regression tests pass. **BLOCKED is not a disguised FAIL**: the missing source/fit/optimizer/timeline artifacts prevent G1 verification.

## Independent mathematics, scorer semantics

1. **Poisson** `lambda=1, observed y=0`: exact NLPD = 1; predicted mean = 1; absolute error and *single-observation point-forecast RMSE contribution* = 1; signed bias = +1. The expected squared error of a **random predictive draw** is 2 (square-root = `sqrt(2)`); it is **not** the same definition of point RMSE. Full-count CRPS = `1 - exp(-2)*(I0(2)+I1(2)) = 0.47622238819739127`.
2. **Negative binomial** `r=2, success-probability p=0.5`, `y=0`, PMF `P(Y=k)=(k+1)/2^(k+2)`: mean 2, variance 4, NLPD `ln(4)`, point MAE and RMSE contribution 2, signed bias +2. Expected random-draw squared error = 8 (square-root `sqrt(8)`). Independent exact CRPS `sum_(k>=0) P(Y>k)^2 = 26/27` (proved by geometric-series identities and independently checked numerically).
3. **Two-outcome joint** `P((0,0))=P((2,2))=1/2`, observation `(0,2)`: Energy Score with Euclidean distance `2 - sqrt(2)/2`; single-pair unnormalized `VS_0.5=2`. Alternative independent coupling with the same marginals scores differently.
4. **Randomized PIT** for support {0: .25, 2: .75}, observed 2, uniform draw .37 is `.25 + .37*.75 = .5275`. Exact P(Over), P(Under), P(Push) are extracted from the same PMF.
5. **Monte Carlo**: for fixed Bernoulli p, binomial Monte Carlo SE at 5,000 scenarios is **twice** that at 20,000; these scenarios are numerical integration paths, not additional independent NBA game outcomes.

**C owner instruction:** Implement ordinary point MAE/RMSE against the predictive mean separately from posterior/predictive expected draw loss; label any distributional expected loss explicitly. Compare **complete distributions from S_ONLY, S_O, S_O_J**, not their shared S/O/J stages as independent votes. Use game/date blocks, chronological origin, and one observed game only once for inference (not each MC path). These are acceptance requirements, **not findings from executing a nonexistent accepted C optimizer**.

## Family-by-family engineering-readiness gate

| Owner/family | Independent current G1 status | Required before re-review |
|---|---|---|
| **G0 / P0 integrator** | **BLOCKED** | Genuine independent acceptance of source candidate at exact SHA, verified versioned schema/goldens and open review #149; PR #157 unmerged draft |
| **P1 source / canonical features** | **BLOCKED** | Exact raw original source bytes; SHA proof, revision history, as-of availability, player identity, duplicate-game/shard registry and pregame snapshot API conformance |
| **P2 S outcomes** | **BLOCKED** | Callable complete PTS/REB/AST/3PM integer PMFs, model/fit training-cutoff receipts, numerics, tail and zero guarantees, synthetic adapters |
| **P3 O opportunity** | **BLOCKED** | Proper participation/DNP states, played-conditional minute laws, coherent G-keyed exposure distributions, real rotations and interval five-on-court witnesses |
| **P4 G/J joint simulation** | **BLOCKED** | Exact G/O/S source-bound integrated scenarios, same-scenario combos, official shooting/rebound accounting, runtime/seed/hashes, temporal and five-on-court physical witness |
| **P5 C evaluation/optimization** | **BLOCKED** | Accepted scorer warehouse, reference-score tests, chronology, CRPS/NLPD/MAE/RMSE/PIT, ES/VS, optimizer dependency graph, game/date bootstrap and MC path non-replication |
| **P6 independent QA** | **SHADOW TESTED** | 327 tests passing at exact tested QA commit; pre-G0 status and missing end-to-end family evidence prevent formal G1 approval |

## Owner routing and rollback

- **P0/P1 source engineering:** Reproduce source-byte hash and predecessor receipt chain, validate identity collisions and no retroactive historical certification. Contract-level repairs of old QA-G0-01 are green; actual source vault still needed.
- **P2 S:** Submit complete predictive PMFs and provenance. Verify actual-minutes never enter pregame features even when renamed or derived through a join.
- **P3 O:** Provide actual minute distributions, DNP ambiguity policy, pointwise five-on-court interval schedule and overtime conservation. Old QA-G0-02 is now green.
- **P4 G/J:** Provide original G/O witnesses and join closure; demonstrate event accounting and same-draw stat combos. Old QA-G0-03 is now green.
- **P5 C:** Supply scorer+optimizer code for independent numerical matching, complete-pipeline regularized simplex optimization, clustered cross-validation and 5k/20k precision fixture. Old QA-G0-04 is green; predictive scoring semantics remain untested.
- **Release custodian:** Keep G0 independently unapproved, G1/G2 unauthorized, previous red and accepted artifacts immutable; do not merge this QA PR into production.

**Rollback:** Close the new P6 draft PR without merging. Its QA-only branch is based on the unapproved PR #157 source commit. Preserve old P6 #152 red findings and new P6 receipts; no production, forecasts, notebook schedules, historical outcome data, model mathematics or weights were modified.

## Formal independent recommendation

**G0:** NOT ACCEPTED by P6; only separate independent G0 reviewer can grant contract approval.  
**G1:** **NO-GO / BLOCKED** for source/S/O/J/C and for formal P6 gate; research-only QA tests are engineering-ready as a test harness, not an acceptance of families.  
**G2/P8/P9/P10/P11:** NOT AUTHORIZED.  
**Historical predictive validation:** NOT PERFORMED. **Monte Carlo weight fitting:** NOT PERFORMED. **Production/Tier approval:** NOT GRANTED.

The next bounded action is an **independent exact-SHA G0 acceptance**, followed by family owners' G1 artifact submissions and a new independent P6 conformance pass on those artifacts. Never interpret 327 passing synthetic tests as calibrated or profitable NBA forecasts.

### Sources and limitations

Primary inspected repository sources: `v2/nba_architecture/v2_contracts.py`, `families_v2.py`, `exposure_v2.py`, `schema-2.0.0.json`, `docs/nba_architecture/GATE_BOUNDARIES_V2.md`, the older P6 PR #152 test/review packet, rejected G0 PR #156, and repair draft PR #157. The user's named "NBA parallel execution packet" was not found among the available attached files; the P6 user directive and repository G0 contract were used as the operative task specification. An owner-authored or AI-authored record is not a third-party certificate.
