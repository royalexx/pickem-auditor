# NBA V2.5 P3 — O-family G1 engineering handoff (2026-11-16)

**Owner:** P3 opportunity research. **Status:** IMPLEMENTED + author-tested shadow; **formal G1: BLOCKED_BY_REAL_EVIDENCE_AND_INDEPENDENT_QA**. No model promotion, scoring, historical minutes comparison or publication. Draft changes are based on the **independently accepted G0 exact SHA** `59d28dc23be97de2a6a82d22be8338151e31f5b6` (PR #157; signoff PR #161), not on the older `main`. PR targets G0's accepted branch until that branch lands.

## Implementation inventory and ownership

| Path | Purpose |
|---|---|
| `v2/nba_opportunity.py` | Exact, unchanged reuse of WS2 v1 `MinuteLaw`, `capped_allocation`, `lineup_segments`; imported from `research/v25-nba-ws2-minutes-opportunity-20261115`, original Git blob `55360fd8bab49fd20f1af04493532fee5237b1ec`. Existing WS2 M0/M1/M2 fit code is retained, not run. |
| `v2/nba_o_family.py` | New research-only O0/O1/O2 G0 contract producer, strict prior/source adapter, shared-G scenario witness, SHA-sealed auxiliary opportunity/share scenario bundle, create-only freezing |
| `tests/nba_architecture/test_p3_o_family.py` | Adversarial synthetic-contract tests for source clocks, DNP/played-zero, roster feasibility, minutes conservation, OT, shares, lineup-witness identity, reproducibility and WS2 adaptation |
| `docs/nba_architecture/P3_O_FAMILY_MANIFEST_20261116.json` | Frozen input expectations, declared limitations, initial test receipt and G1 gaps |

**Exclusive P3 boundary:** no production collectors, source capture, model-fit commands, statistical S likelihoods, J outcome conversion, C scores/calibration, legacy models, probability weights, forecast history or schedules are changed.

## APIs and exact semantics

`build_opportunity(p, g, priors, *, model, seed, variant, home_team_id, home_team_source_receipt_sha256) -> (o, sidecar)`.

- `p` is the **complete G0 v2.0.0 pregame** object, including source receipts and roster identities; `g` is the single previously generated G0 shared game state, with unchanged scenario IDs, weights, home/away possessions, overtime and model provenance. `validate_pregame`, `validate_game_state` and `validate_opportunity` run, including G0's finite joint minute-law feasibility test.
- `priors` has **exactly one entry per G0 roster player**; every entry has an exact `source_snapshot_sha256`, a bound source receipt hash, `available_at`, `training_cutoff_at`, probability/basis, WS2 conditional-minute parameters, played-zero/early-exit probability, role scenario states, share parameters and uncertainty flags. Unexpected keys, missing roster players, missing or future clocks, wrong G0 snapshot, actual target minutes and future model fitting fail closed. This prior is model input, not authenticated merely by a valid hash.
- Each G scenario receives **one team-participation/role draw per player**, conditional on a feasible five-player rotation. After bounded attempts, infeasible scenarios fail closed rather than inventing replacements. Each selected `PLAYED` player receives positive minutes; `DNP` and `PLAYED_ZERO_MINUTES` both have zero exposure but different semantics. Out or legally ineligible players cannot play. Unknown participation remains `null` in canonical output when only historical scenario priors exist.
- `capped_allocation` projects WS2 drawn minutes on the constrained team simplex; `lineup_segments` constructs a five-on-court witness with every player's total exposure no greater than `48+5*OT`. Each team has **exactly `240+25*OT` player-minutes**. Projections change player marginals; therefore the exported **full conditional minutes distribution** (`discrete_minutes` atoms/mass) is rebuilt from the *same joint, conserving, weighted G scenario ensemble*, NOT mislabeled as the original independently sampled WS2 marginal. All weights belong to G; no weight optimization.
- Auxiliary `sidecar` exposes scenario-keyed player minutes, role-state label, possession shares and projected possession-opportunity allocations, exact G/O content SHA joins, lineup witness, and feasibility-rejection attempt count. It carries `prior_manifest` plus canonical `prior_sha256` for replay, is SHA-sealed and remains `SHADOW_NOT_CERTIFIED`. `validate_sidecar` checks source/G/O joins, both teams, same scenario/OT, nonnegative shares, exact possession-pool sum, DNP zero share and reconstructable five-on-court witness. S and J consume these **opportunity inputs**; P3 does not generate points, rebounds, assists or threes likelihoods.
- `freeze_outputs(folder, p, g, o, sidecar)` writes separate immutable, exact-hash filenames using G0 create-only semantics. Identical reruns are idempotent; conflicts reject overwrites.
- `ws2_priors_from_forecasts(p, forecasts, *, source_receipt_sha256, participation_prior_overrides)` is a strict WS2 v1 bridge. It requires all roster players, exact raw-source SHA matching the G0 receipt (not a parsed-JSON hash), full game/team/freeze/model lineage and separately evidence-bound explicit missing-participation prior overrides. Existing WS2 `confirmed_inactive` or `active_roster_eligible=False` claims are not promoted without corresponding G0 evidence. It never calls an injury data provider or fabricates unknown numeric participation.

### Variant readiness

| Variant | Research engineering state | G1 empirical/source blocker |
|---|---|---|
| **O0** | Implemented; simple conditional minute control, G-bound conserved scenario allocation, full finite conditional marginal | Authentic P1 player/roster inputs and participation prior validation; no predictive superiority claim |
| **O1** | Implemented; reuses WS2 beta/truncated-lognormal probabilistic minutes, full conserved finite law from scenario ensemble | Historical WS2 law provenance and fitting cutoff verification; prospective participation P1/P2 are not independently fitted/certified |
| **O2** | Implemented as optional role/early-exit and share uncertainty scenario extension, not an automatically accepted upgrade | Pregame-verified role/injury/trade evidence, fitted transition frequencies, early-exit distribution and usage/share concentration calibration are unavailable; **research-only conditional** |

**Important limitation:** finite weighted G scenario atoms represent a *numerically defined research forecast distribution*, not a learned or independently calibrated population minute law. Bounded rejection sampling conditions original participation Bernoulli priors on feasible team rotations. The realized finite-scenario participation probability is not automatically a fitted P1/P2; unknown evidence explicitly remains unknown. A game with too few participants or infeasible caps fails closed. Five-on-court interval witnesses prove mathematical exposure feasibility, not an observed or realistic substitution schedule. Some high-dimensional discrete-law scenarios may exceed the G0 LP verification budget and be blocked even if physically feasible.

## Source and temporal limitations

- The imported WS2 forecasting/feature methods are prior-only. They do **not** certify authentic original historical pregame injury reporting, trade roster membership, inactive lists, real lineup certainty, or fitted participation probability. `participation_evidence="unknown"` and `participation_probability=null` are correct without separately source-backed fit evidence.
- A verified `participation_basis="verified_pregame_fit"` input is only an adapter **claim**; P1/independent QA must audit fit data, all training cutoffs, independent source capture and posterior uncertainty. The synthetic test that supplies this basis does not certify real probabilities.
- G0 historical reconstruction profiles are not genuinely certified original source captures. A prior-game date cannot reconstruct otherwise unknown historical injury availability timestamps. No target game's final rotation, played minutes, possessions, scores or game statistics are inputs.
- The provided `home_team_source_receipt_sha256` is presence-checked, but independent P1 must authenticate that it actually identifies the game's home team. Original WS1 only exposes incomplete v2 timestamp fields, so the live adapter bridge is not accepted by this author.
- Back-to-back/rest, new roles, trades and injuries are **represented only through source-provided, pregame prior parameters and flags**. No unsupported deterministic penalty or numeric probability is inferred from text. The `role_states` are scenario prior inputs, not real-source derived fit parameters.
- Unknown, DNP, played-zero and played are preserved separately; products may later void DNP under terms only assessed by the C/settlement owner, never by this module.

## Exact execution evidence

The last **full test suite actually executed** was at SHA **`0df0aaa2bd111c6f8e9e6c6e7e82f2252396967c`** in detached, readonly Deepnote run **`6b6c41e1-a7ce-4dba-9057-56ba01d9c99a`**. Result **282/282 PASS** (267 inherited G0 and 15 P3), 0 failures/errors/skips, Python 3.12.16, NumPy 1.26.4, SciPy 1.15.3, jsonschema 4.23.0. Combined stdout/stderr SHA-256 **`0369491c3d4bfd3fc7636db4ab41292f16bca6433d635440e919b399604ade96`**. Preliminary P3-only run **`7d51c89b-0ca2-467a-aa9e-5c035d29f8ea`** passed 15/15.

A subsequent version added `prior_manifest`/SHA binding and a **sixteenth replay/tamper test**. The final version has **NOT** been freshly rerun yet: Deepnote blocked an additional detached execution with **Team Trial limit of five parallel running projects**, and the attempted live run returned **rate limited**. Accordingly **the 282/282 receipt does not attest the later commits**, and no 283/283 assertion or formal G1 signoff is made. Run the exact final branch head before any acceptance. No historical predictive evaluation was performed.

Reproduce in a clean checkout of this branch:

```bash
python -m unittest discover -s tests/nba_architecture -p 'test_*.py' -v
python -m unittest discover -s tests/nba_architecture -p 'test_p3_o_family.py' -v
```

Before review, record actual `git rev-parse HEAD`, raw source/test SHA-256 and stdout/stderr SHA-256. Re-run the existing WS2 `tests/test_nba_opportunity.py` independently with its extra research dependencies if available.

## G1 decision / owner handoffs

**P3 current: TESTED_SHADOW but G1 NOT ACCEPTED.** All G0 mathematical constraints exercised by the preceding exact-head run passed. G1 needs: (1) full post-manifest-change fresh suite and replay; (2) independent reviewer adversarial approval against the *final* commit; (3) canonical P1 authenticated actual pregame source/eligibility/availability and original clock adapter; (4) fitted P1/P2 participation and valid conditional minutes law at stated cutoff, with missing evidence retained as abstention; (5) P4 consumer read and physical/team-conservation witness on a real-source shadow snapshot, never a result-enhanced pseudo-pregame proxy.

**P1:** deliver source-authenticated named roster/trade eligibility, original injury/rotation news and UTC availability, prior minutes/role/possession histories, independent source SHA, home/away, B2B rest and DNP semantics; reconstructing pregame past games is not retrospective certification.

**S/P2:** consume O minute distribution or exact O scenario values; never count S, O and J as independent ensemble votes; no S likelihood in P3.

**J/P4:** consume the **same G scenario IDs and exact O participant/minute shares**, no resampling or double-counted participation. Actual shot and rebound physical ledgers remain J-owned.

**C/P5 and independent P6:** test calibration only later under the approved chronological experiment; verify original source clocks, exact SHA, all abstentions, alternate OT scenarios, wrong team / team substitution witness, DNP/played-zero, duplicate IDs and unable-to-fit law coupling. P6 retains independent gate authority; author tests are not independent acceptance.

Rollback: close P3 draft PR / delete only this isolated branch after archiving receipts. G0 accepted branch and `main` are unchanged. Do not merge, deploy or restart automated production/retraining based on this handoff.
