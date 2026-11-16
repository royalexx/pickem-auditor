# NBA V2.5 — Independent P6 adversarial QA (PRE-G0, research-only)

**Date:** 2026-11-16 (UTC)  
**Auditor:** separate ChatGPT QA/test-authoring execution; no claim of external cryptographic signature or independent organization  
**Target:** PR #147, `nba-sojc-contract/2.0.0`  
**Original contract branch/base SHA:** `3f38ef9d1f6f2e50623a5623fb5826efc67cf7b2`  
**Exactly executed QA code SHA:** `d234e004444be4c34b0dbe6d400b9ba7493d75ea`  
**Deepnote detached, read-only run:** `6246bed9-6015-4161-bf7d-983c7844565a`, notebook `3ee864052c29492c80d8bcb7e267869c`, project `9cc31536-93be-44db-bdeb-06fba3f61410`.  
**QA receipt:** `docs/nba_architecture/P6_PRE_G0_QA_RECEIPT_20261116.json`.  
**Scope limitation:** P6 was requested **after G0**, but G0 is still BLOCKED under PR #147 and review issue #149. This is isolated early testing, not formal P6 authorization or G1 acceptance. The specifically named parallel prompt packet was not present in the available project uploads; user P6 message and inspected v2 branch/gate documents supply test requirements.

## Independent test outcome

Four separate commands were executed against a fresh SHA-verified clone of the exact QA commit:

```bash
python -m unittest discover -s tests/nba_architecture -p 'test_v2_contracts.py' -v
python -m unittest discover -s tests/nba_architecture -p 'test_p6_independent_controls.py' -v
python -m unittest discover -s tests/nba_architecture -p 'test_p6_math_references.py' -v
python -m unittest discover -s tests/nba_architecture -p 'test_p6_red_counterexamples.py' -v
```

| Group | Tests | Observed | Meaning |
|---|---:|---|---|
| Existing v2 producer contract | 105 | PASS | Reproduced author tests from exact QA commit |
| Independently authored pregame/identity/physics guards | 25 | PASS | Scoped positive and mutation controls |
| Independently derived Poisson/NB/joint mathematical references | 11 | PASS | Reference oracle verified, **not** deployed C scorer |
| Independently authored deliberately red counterexamples | 4 | **FAIL** | All four expected rejections were **not raised** |

Environment: Python 3.12.16, Deepnote ephemeral clone, project storage mounted read-only. The first independent numerical run mistakenly expected an NB(2, p=0.5) RMSE of sqrt(6); the correct variance is 4, mean is 2, so E[Y²]=8, and the QA-only expectation was corrected to sqrt(8). The rerun reproduced all 141 passing controls and four genuine red tests. **No forecasting implementation or production configuration was edited.**

## Four executable integrity findings

**QA-G0-01 — SOURCE REVISION CHAIN (P0/P1 source owner).** A historical v2 source receipt with `source_revision=2` and `supersedes_receipt_sha256='d'*64`, but with no predecessor in the supplied source set, passes `validate_pregame`. The code explicitly contemplates externally held predecessors, so the missing local parent is not automatically proof that the original external ledger is corrupt. However, the validator does **not** require a resolvable, independently authenticated parent or byte receipt; the artifact alone cannot certify the correction chain. Require an external manifest/vault lookup or reject unverifiable revision chains. Reproducer `test_revision_two_without_verifiable_parent_must_not_pass`.

**QA-G0-02 — OUT PLAYER PLAYS (P3 O / P4 J owner).** Changing a prospective roster availability to `out`, resealing its pregame snapshot, and building correctly bound J draws allows that player to remain `PLAYED`. No source-evidence distinction separates verified unavailable from unconfirmed reported status at this boundary. Require typed, evidenced availability semantics and a hard exclusion where an authoritative out status is valid; otherwise propagate uncertainty and abstention. Reproducer `test_out_player_must_not_appear_in_joint_draw`.

**QA-G0-03 — J MARGINAL UNBOUND (P4 J / P5 C owner).** A same-scenario J marginal with PMF weights swapped from 0.4/0.6 to 0.6/0.4 is accepted by `validate_distribution(d,p)` when the optional `scenarios` argument is omitted, even though `validate_distribution(d,p,scenarios)` rejects it. Require an immutable resolved scenario reference for every authoritative J distribution before scoring or optimizing; do not treat a syntactically plausible SHA as proof of sample derivation. Reproducer `test_joint_distribution_must_not_pass_without_same_draw_witness`.

**QA-G0-04 — DNP COUNT CONTRADICTION (P1 outcomes / P5 C owner).** A settlement object combining `status='settled'`, `participation='DNP'` and `actual=12` passes `validate_evaluation`. DNP/played-zero/played must not collapse during label construction; preserve product-specific void rules separately. Reproducer `test_postgame_dnp_must_not_be_a_settled_played_count`.

## Positive and blocked controls

| Boundary | Observed | Decision |
|---|---|---|
| Pregame model/source clocks; post-event features; UTC; player/team identities | Mutations rejected | PASS (synthetic contract tests) |
| Repeated player ID; source receipt hash mismatch; conflicting immutable freeze write | Rejected | PASS |
| Regulation 240 player-minutes per team; one five-minute OT 265 per team; altered minute totals | Enforced on 12 synthetic roster entries | PASS for totals only |
| Five simultaneously on court through real lineup intervals | No interval-level on-court witness in v2 contract | BLOCKED |
| FGA=2PA+3PA, FGM=2PM+3PM, PTS=2×2PM+3×3PM+FTM, AST ≤ team FGM, rebounds, same-draw combinations | Synthetic arithmetic mutations rejected | PASS for encoded equalities |
| Cross-team rebound availability and actual event-by-event shot accounting | Not represented by full play/event ledger | BLOCKED |
| Exact source-byte SHA against original archive (not just signed receipt fields) | Original source raw bytes not verified by this test run | BLOCKED |
| Source corrections and global duplicate event/contract/forecast identity across shards | Requires canonical registry and original source vault | BLOCKED |
| Poisson CRPS (at λ=1, y=0): 0.47622238819739127 | CDF sum = independent Bessel identity = pairwise distance | PASS reference |
| NB(r=2,p=.5) y=0: NLPD=ln4, MAE=2, RMSE=sqrt8, bias=+2 | Independent recurrence / second-moment oracle | PASS reference |
| Small two-state joint: ES((0,2)) = 2-sqrt2/2; VS_0.5=2 | Independently calculated | PASS reference |
| Randomized PIT, integer zero/tail, 5,000 vs 20,000 binomial MC SE ratio = 2 | Reference arithmetic only | PASS reference |
| C learned weights, temporal cross-fitting, simplex optimizer, game/date-block bootstrap, real cached-PMF precision | No accepted v2 P5 implementation supplied for integration | BLOCKED |
| S/O/J dependency vote check | Inspected v2 modes encode `S_ONLY`, `S_O`, `S_O_J`; independent stage vote would be a violation | PASS architecture intent; optimizer enforcement BLOCKED |
| Game/date independence | 10,000 illustrative scenario paths span just 2 games/dates, not 10,000 independent observations | PASS reference; C actual enforcement BLOCKED |

**Critical scope warning:** An aggregate team-minute sum does not by itself prove five players were simultaneously on the court at each instant. Likewise synthetic self-consistency does not certify official historical boxscores or prove model skill. The tests make no 2022–23/2023–24 predictive accuracy claims.

## Family-by-family engineering readiness

| Owner | Current recommendation | Reason |
|---|---|---|
| P1 canonical source / temporal identity | **BLOCKED** | Actual WS1 v2 original-clock/receipt adapter not accepted; QA-G0-01 needs audit-proof predecessor |
| P2 S statistical likelihoods | **BLOCKED** | v2 PMF shape passes, but no accepted complete fitted PTS/REB/AST/3PM producer or real training-cutoff evidence |
| P3 O participation and minutes | **FAIL / BLOCKED** | QA-G0-02 boundary permits reported out to play; accepted P1/P2 participation and G-keyed minutes-law adapter absent |
| P4 G/J shared simulator | **FAIL / BLOCKED** | QA-G0-03 unbound J PMF; physical totals pass but no genuine five-on-court intervals or accepted real S integration |
| P5 C evaluator/optimizer | **FAIL / BLOCKED** | QA-G0-04 DNP contradiction, no accepted v2 scorer/optimizer, no assurance against shared-upstream double voting or pseudo-replication |
| P6 independent QA | **SHADOW TESTED, G1 BLOCKED** | Reproducible new suite delivered; four independent red cases unresolved; formal G0 clearance missing |

## Gate and owner handoff

**Independent technical recommendation: G0 FAIL on the tested candidate boundary, pending severity triage and documented closure of the four concrete counterexamples.** This audit records real executable evidence but is not a cryptographically signed third-party organization acceptance. The original G0 FAIL, P0R candidate, owner acceptance and P0I BLOCKED receipts must remain unchanged.

**Formal G1 recommendation: NO-GO.** No G1 promotion or G2 integration, historical predictive validation, Monte Carlo family-weight fitting, optimizer adoption, Tier/production release, or merged forecast-math change is authorized. Workstream owners should submit minimal separate fixes and original evidence; independent QA then re-runs these reproductions at their exact new code SHAs. This QA PR deliberately retains failing tests to prevent the defects from being hidden by synthetic green-only results.

**Rollback:** close the draft P6 QA PR (no production code touched), preserving immutable SHA-pinned Deepnote run and append-only QA receipts. Do not merge red tests as a green release claim.
