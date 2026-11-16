# Repair of the independent minute-law / exposure FAIL

The user-supplied independent review rejects PR #156 at **e1983b2d0b94742dfb1bf411694dc46c7cad1ac6**. That rejection remains valid for that SHA. `INDEPENDENT_FAIL.txt` preserves the supplied report byte-for-byte. This new branch contains the repairs and author-run evidence; **it does not approve or close G0**. A separate reviewer must assess the new exact SHA before technical G0 PASS. Governing scope remains PA-V25-MASTER-2026-11-09 / v1.1, isolated Phase 0R contract engineering.

## Reproduction before repair

The rejected checkout freshly passed all 242 existing tests. Adding six new test methods reproduced 21 invalid-acceptance assertions: the report's F1 at O, full forecast and C; its F2 across eight markets at full forecast and original-quote-bound C; incompatible marginal masses despite attainable atoms; and an analytic count-mass/exposure mismatch. The report's 47-check campaign was supplied as prose plus F1/F2 executable reproductions; the unavailable original code for the other checks is not claimed as freshly executed here.

`baseline.log`, `red.log`, `tiny-overtime-red.log` and `tiny-unknown-red.log` preserve red evidence. `red-exact-sha.log` and `red_receipt.json` additionally reproduce the six original new methods on the rejected implementation in a separate detached checkout, recording 21 expected failing assertions and zero unexpected errors. `reproduce_red.py` recreates that check without touching the repair checkout. The initial implied-bound test fixture mistakenly called five conditional 48-minute laws "fixed" while their participation was unknown. Its acceptance was legitimate. That fixture was corrected to declare their participation certain, while a separate positive test preserves the legitimate unknown-participation exchange. `implied-bound-red.log` and the interim failure logs are retained as working-tree debugging history, **not evidence of an additional original contract defect**. No existing assertions or old tests were removed or weakened.

## F1: existence of a conserving joint exposure law

A normalized conditional law is insufficient if its atoms cannot coexist with the team's conserved pool. The new `exposure_v2.validate_exposure_coupling` enumerates conserving allocations from each player's declared discrete support, preserving DNP and played-zero as different states. It uses G's positive-probability overtime states; states with the same overtime duration can share the same conditional exposure law because no finer conditional law is declared by this versioned O interface.

For each team, let x[g,a] be joint mass of conserving allocation a in G overtime state g, and q[i] the player's participation probability. A known q is fixed; an unknown q is an existential variable in [0,1]. The feasibility constraints are:

- x[g,a] >= 0, with sum over allocations a equal to G's declared state probability.
- For each played atom m, the player's marginal mass is q[i] * f[i,m].
- The player's DNP marginal is 1-q[i]. The zero-minute played atom retains its own q[i] * f[i,0] mass.
- Every allocation conserves 240+25*OT team minutes, and every individual state respects the corresponding 48+5*OT cap.

This is a finite linear feasibility problem. SciPy HiGHS is used to find and numerically verify a feasible joint measure, not to fit model weights, alter forecasts or optimize historical performance. No independence between players is assumed. Checking both teams against the same G-state probabilities permits a global coupling conditional on G.

Every positive-weight O witness must have positive probability in at least one compatible coupling. Separate witness-support solutions can be averaged: linear constraints are preserved, and all finitely many observed states then have positive probability simultaneously. **Their empirical frequencies are never equated to the declared law probabilities.** This catches a joint state whose minutes conserve locally but whose DNP label is impossible under all compatible marginal laws.

The report's target zero-minute atom has no conserving allocation and is rejected even though the sampled rows all assign 48 minutes. The positive two-player 0/48 exchange remains accepted, including when every finite sample takes the same branch. An independent rational 5-by-5 exchange grid also checks probability compatibility, beyond support maxima or a mean-only check.

## F2: positive counts require possible positive exposure

The full `validate_forecast` entry point now retrieves the maximum participation and positive-exposure probability permitted by the compatible joint exposure laws. For an analytic unconditional or declared-roster forecast:

P(count > 0) <= sup P(minutes > 0).

For participation-conditional analytic forecasts, the bound is the declared played-conditional positive-minute mass, and the participation conditioning event must be possible. For unknown participation, the analytic count constraint is also put back into the coupling: reaching a probability upper bound must not silently make a positive-weight DNP witness impossible.

**Hard-zero exposure always requires exactly zero positive-count mass**, including tiny positive probabilities and empirical Monte Carlo distributions. The rule applies to points, rebounds, assists, made threes, PR, PA, RA and PRA. It also covers positive counterfactual support when conserved team minutes force the unknown participation probability to zero.

Interior empirical Monte Carlo frequencies can exceed theoretical probabilities through finite sampling, so no deterministic interior probability cap or exact frequency equality is imposed on empirical S_O/J marginals. Their support and hard endpoint constraints still apply. Tests explicitly protect both empirical S_O and J cases, and distinguish unconditional from participation-conditional bounds.

`validate_settlement` already invokes the full forecast validator before evaluating original quotes and corrections, so the repaired boundary protects C without duplicating a weaker rule. F2's quote-bound Over=.75 result is rejected as an invalid forecast; genuine zero-count distributions retain Over=0, Under=1, Push=0 at the synthetic original 1.5 quote.

## Numerical and computational certification limits

Declared G masses and discrete laws are normalized only after the existing validators establish their respective 1e-10 and 1e-12 normalization tolerances. Conservation uses the existing 1e-7 minute tolerance. The LP's returned primal equality and bound residuals must be <=1e-12. Solver failure or an uncertified residual is rejected explicitly. Numeric underflow is rejected rather than silently erasing known positive mass.

Structural checks do not rely on solver tolerances: a positive G state must have a conserving allocation, an unattainable positive atom with known positive participation is rejected, and an unattainable conditional atom with unknown participation forces q=0 through a unit-scale constraint, even when its declared mass is 1e-20.

Enumeration is bounded at 500,000 search nodes, 50,000 conserving allocations, 32 team variables, 64 overtime groups and 256 extra witness-support solves per team. These are **verification budgets**, not NBA eligibility rules or claims that larger laws are invalid. Exhaustion raises `O_COUPLING_VERIFICATION_BUDGET`; no unverified forecast passes. Larger real law families need an efficient independently validated feasibility certificate or algorithm under their G1 engineering gate. This G0 repair does not introduce a fitted law family, event-level rotation witness or production capability.

The pure numeric verifier cache is keyed by the complete laws, participation constraints, G probabilities, positive witnesses and any analytic count constraint. It does not trust object hashes or player names in place of verification.

## Verification packet and boundaries

- `invariants.json` version 1.2.0 extends the prior 24 groups with conserving-law coupling, exposure/count dominance and numerical certification. Prior registries remain unchanged.
- `check_inventory.json` records current expressions in the changed modules; `test_inventory.json` links old and new test cases.
- `failure_ledger.json` identifies the two independent HIGH findings and their exact reproducers, root causes, repair locations and positive counterparts.
- `exchange_golden.json` records a valid complete joint forecast whose finite draw frequencies differ from its feasible declared exposure laws.
- `mutation_checks.py` removes each repaired boundary in temporary copies. Both mutations must cause negative tests to fail. These expected mutant failures are sensitivity evidence, not failures in the repaired candidate.
- `reproduce.py` checks Draft 2020-12, all three legacy goldens, the earlier complete golden and the new exchange golden, every preexisting architecture document/test byte against the rejected SHA, registry references, full tests, raw hashes and environment versions.

WS1/P1 source authenticity, S/P2 and O/P3 fitted model quality, real producer adapters, event-level G/J/P4 chronology, C/P5 product interpretation and storage-wide uniqueness remain under their existing G1/G2 gates. The repaired O/full forecast/C contracts are synthetic engineering evidence only. No historical performance scoring, NUTS/training, Monte Carlo weight tuning, deployment, merge, collector, notebook, source archive or schedule changes occurred. The unchanged upstream v1 implementations are not re-certified as v2 adapters.

## Reproduce and hand off

Use the exact implementation/final PR SHA specified in the receipt and PR description. In an isolated checkout, install `v2/nba_architecture/requirements.txt`, then run:

```bash
python docs/nba_architecture/law_repair_20261116/reproduce.py --out /tmp/g0-law-independent
```

For targeted mutation sensitivity, use a disposable checkout and run:

```bash
python docs/nba_architecture/law_repair_20261116/mutation_checks.py
```

Independent reviewer prompt: Review the new repair PR at its exact frozen SHA. Independently reproduce both findings from the uploaded rejection, inspect the finite-law coupling proof and probability-to-exposure boundary, and run the complete old/new suites and preserved-byte checks. Construct different supports, marginal masses, participation patterns, overtime mixtures, conditional laws, tiny atoms and sampled witnesses. Verify that valid finite-sampling variation remains legal and that failed numerical certification is never accepted. Reject with a reproducer if any material G0 defect remains. Only a genuinely separate reviewer may issue technical G0 PASS. Do not merge or authorize G1/G2 work, training, scoring, optimization or production.

Rollback: close the new draft PR and use a separate detached checkout of e1983b2. That checkout is the rejected candidate, not an approved fallback. Preserve the rejection, all prior receipts and this repair packet. PR #156 remains marked rejected; G0 is not closed by this author's repairs.
