# P1 exact partial-integer accounting v5

Authority: PA-V25-MASTER-2026-11-09 / v1.1. Contract `nba-p1-partial-integer-accounting/1.0.0`, implementation `v2.nba_architecture.p1_integer_accounting.partial_counts_feasible`. This is an exact source-count validator, not a forecasting model, fit, source-authentication system or permission to reveal outcomes. Absent source values remain absent. Existential internal witnesses are never exported as observed or pregame data. Accepted G0 remains unchanged.

## Preserved failure and scope

The orchestrator's exact pre-P6 red witness at `d5cafda47a2f881a88974bfb7bcbb90372fe69c2` is retained in `p1_integer_accounting_20261117_v5/orchestrator_red_d5cafda.json`. The earlier F-P1-NATIVE-04 necessary lower/upper bounds were insufficient: `points=1, fga=1, fg3a=0, ftm=0` is inside loose bounds but only zero/two points are possible; `pr=pa=ra=3` requires fractional primitive counts. Earlier receipts remain preserved as finite owner checks, not rewritten as complete acceptance.

Fix `542d91a7d6c134441ce8cb9bb54312095b186833` extends F-P1-NATIVE-04 to exact relevant nonnegative integer feasibility. Existing direct inequalities and their error codes remain; the exact feasibility hook adds `INTEGER_STAT_ACCOUNTING`. The validator applies to source-normalized counts, native exposure, historical builder and isolated vault through the shared P1 `_stats` path. Boolean, negative and noninteger values reject before physical feasibility. It neither requires all fields nor fills missing ones.

## Exact algorithm and proof basis

The unknown primitive nonnegative integers are points P, rebounds R, assists A, two-point makes X, three-point makes T, free throws F, corresponding attempts/misses, offensive rebounds and defensive rebounds. They must satisfy P=2X+3T+F, FGM=X+T, makes no greater than matching attempts, R=OREB+DREB, and same-player PR/PA/RA/PRA sums. The algorithm uses a fixed number of exact integer operations regardless of observed count magnitude; there are no floating tolerances, optimizer limits or count-size search caps.

First project rebound/assist/combination constraints onto P. R and A have affine lower/upper bounds from known primitives and PR/PA; RA/PRA give affine exact sums. Pairwise lower-versus-upper and sum inequalities yield the exact integer interval for P. For fixed integer P, the remaining R/A matrix has rows (1,0), (0,1), (1,1), which is totally unimodular. Real interval feasibility therefore supplies integer R/A feasibility. Half-integer all-pair contradictions become an empty integer P interval.

Next represent exact field-goal point support Q=2X+3T. Known FGM makes Q a consecutive interval over feasible T. Known T makes Q a step-two progression over feasible X. With both unknown, write X=x+3i, T=t+2j for x in 0..2 and t in 0..1: Q=2x+3t+6(i+j). Under rectangular attempt bounds, i+j spans a complete integer interval. Under the triangle X+T<=FGA, a fixed i+j=s has a feasible realization exactly when x+t+2s<=FGA, choosing i=0. Thus no more than six step-six progressions describe the exact support, including all holes and finite endpoints.

Known FTM fixes F; otherwise F spans the integer interval from zero to known FTA or infinity. Adding that interval to a step-d progression fills all gaps when its width is at least d-1; narrower intervals require at most six offsets. Intersect this finite exact union with the P interval. Any intersection supplies a valid integer completion; no intersection means the supplied counts are physically incompatible. No such completion is returned as source evidence.

## Independent synthetic references and QA correction

At `c48dc5cb9127e3e98f5a749208ca6c12574139b7`, **456,386** exact synthetic reference checks passed:

- 16,384 exhaustive seven-field shooting partial assignments, including every absent/0/1/2 field state.
- 262,144 exhaustive nine-field rebound/assist/combination partial assignments.
- 16,384 exhaustive seven-field cross-shooting/combination partial assignments.
- 93,312 projections covering every subset of complete small shooting primitive vectors (six primitives each 0..2), including point totals above two.
- 37,500 individual integer-point checks under small rectangular attempt caps.
- 30,662 individual integer-point checks under small triangular attempt caps.

These references enumerate primitive count constructions independently of the production affine/residue algorithm. Separate sparse valid controls and counts of 10**100 pass. P2's distinct MILP-plus-exact-witness implementation additionally agreed over 5,000 seeded sparse/mutated cases, with zero disagreements; its raw case/result digest is `a2e54fa448d0bbac4993292393db01edee4caa3edde9d9dc2c0128809b3e4b86`. That cross-owner exercise is supporting mathematical QC, not independent P6 gate acceptance.

One provisional new QA positive fixture incorrectly labeled `points=1,fga=1,ftm=0` as legal. The exact helper and brute references correctly rejected it. Its initial test source and failed execution remain in `qa_initial_fixture_source.py.txt` and `before_hook_and_oracle.log`. The corrected QA keeps that input as a negative and adds the legal three-point positive. No historical fixture or accepted assertion was changed. The same preserved log also demonstrates the two genuine old `_stats` bypasses before the hook.

## Exact execution and gates

Exact `c48dc5cb9127e3e98f5a749208ca6c12574139b7` execution: **377 architecture, 9 preflight, 83 unchanged P6 controls PASS**, plus immutable original negative probe, v3 P1 adversarial controls and separate green wrapper, all exit zero. Commands, logs and hashes are retained in `p1_integer_accounting_20261117_v5/exact_c48dc5c/receipt.json`. Final documentation-only successors receive another exact-head run and PR receipt. These owner executions do not award independent acceptance.

Portable reproduction: `python scripts/nba_p1_native_handoff_check_20261117.py --output work/p1-integer-fresh`, using a fresh output directory. The v5 SHA256SUMS binds current source/tests and the versioned raw evidence; older v1/v2/v3/v4 receipts remain bound to their own exact source versions. B-P1-01/B-P1-02 remain BLOCKED for authentic pregame availability/roster, dated identities/trades, official denominators/corrections, admitted fitted priors and authentic duration/exception evidence. No G2, historical fitting/evaluation/weight fitting, NUTS, deployment, schedule change, Tier promotion or merge is authorized.
