# P3/P0 coupling verification proposal v1 — pending independent acceptance

Authority: PA-V25-MASTER-2026-11-09 / v1.1. Accepted G0 remains
`59d28dc23be97de2a6a82d22be8338151e31f5b6`; its source, tests, tolerances,
search limits and mathematical semantics are unchanged. This proposal grants
no operating approval and does not close B-P4-03.

The actual latest P3 O2 producer is exercised with the exact immutable P4
synthetic input bytes (raw SHA-256
`92fc3063445502623d7810421b4de484a743e91ca1a903ad2bd3e4bc8ec61f00`).
P4's original fixture predates P3's required team/source/home fields. The first
attempt therefore stopped correctly at `O_PRIOR_FIELDS_OR_POSTGAME_LEAK`;
its program, all attempted inputs, outputs and raw errors are retained in
`p3_remediation_v4_20261116/coupling_before/` and the adjacent first-attempt
program/log. A separate explicitly enabled synthetic interface adaptation adds
only roster team/source/home bindings, updates hashes, and preserves the actual
minute model, draws, seed, per-scenario weights and all retained scenarios.
It is not an authentic-source case and is not a continuation of an admitted one.

For that latest-owner case, O2 n=4 and n=8 pass finite engineering validation;
O2 n=32 reproduces `O_COUPLING_VERIFICATION_BUDGET`. The inputs are saved before
execution. These finite successes establish no generally safe bound of n<=8:
the Cartesian support and number of conserving allocations also depend on the
roster, atom support and overtime groups. Runtime rejection remains mandatory
whenever the unchanged G0 verifier exhausts its budget. O0 benchmarks establish
no O2 scaling claim.

The G0 verifier forms an exact finite coupling LP over every physically legal
Cartesian allocation. For unknown participation, it existentially quantifies
q_i, then computes its maximum compatible positive-exposure probability. It
also requires every observed positive-weight state to have positive probability
under a compatible coupling. A P3 scenario ensemble already supplies a sparse
candidate measure: give each exact shared G/O draw its original weight, and
recompute every played-conditional marginal and participation frequency. If
those recomputed marginals equal the declared laws and G's overtime-group
weights, that measure proves feasibility and supports all supplied draws.

That sparse measure alone does **not** establish the G0 maximum over *all*
compatible couplings. Unknown q cannot be replaced by the sampled frequency,
by one, or by a posterior participation claim. Nor may a verifier restrict the
LP to only sampled allocations and describe the resulting smaller maximum as
the accepted full-support law. Doing so changes forecast support and downstream
positive-count acceptance.

A separately versioned P0 proposal can add a witness-assisted algorithm while
retaining the accepted meaning only if it proves all of the following:

1. Every raw witness state is source/G/O joined, physically conserving and
   consistent with DNP, played-zero, played and overtime semantics.
2. All declared law atoms and masses, including arbitrarily small positive
   mass, and every fixed G group weight are represented and reconciled.
3. The supplied nonnegative witness weights sum to one and satisfy every LP
   equality within the accepted residual threshold; no discarded states or
   post-hoc projection supplies feasibility.
4. Every required positive-count constraint and maximum unknown participation
   bound is solved over the complete legal allocation set. A sparse primal
   witness requires an independently verified dual upper certificate, or exact
   column generation with a certified complete separation oracle. A local
   optimum or failed pricing search is insufficient.
5. Small enumeratable examples agree with the accepted exhaustive implementation
   for feasible/infeasible laws, upper bounds, zero/tiny atoms, overtime groups
   and witness-support queries. Larger adversarial examples demonstrate the
   certificate independently and quantify compute limits.
6. Any unsupported or numerically uncertified case fails closed with its full
   attempted denominator and immutable receipt. The original bounded failure
   remains a regression and its historical red report is never rewritten.

Alternatively, P0/P3/P4 may submit an explicitly bounded operating contract
whose admissible inputs are mechanically characterized by verified support and
coupling complexity. A scenario-count-only limit is insufficient. Independent
P6 must accept that contract and its numerical/physical evidence before it can
close the engineering requirement. Until then B-P4-03 remains BLOCKED.

Reproduce the separate latest-owner engineering probe:

```bash
git show cf5483a16279b8af606caef415e9abacc8c41aab:research/nba_p4_integration/fixtures/inputs.json > work/p4-original-inputs.json
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 python scripts/nba_p3_coupling_probe_v4_20261116.py --fixture work/p4-original-inputs.json --latest-interface-adapter --output work/p3-coupling-fresh
```

Required external prerequisite: P0 mathematical/contract custody plus independent
P6 review of an exact semantics-preserving scalable certificate, or independently
accepted mechanically bounded operating contract. No G2, historical fitting,
holdout outcome access, historical predictive scoring or deployment is authorized.
