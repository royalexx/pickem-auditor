# NBA V2.5 P6 — Owner-routed G1 conformance blockers (NOT observed fresh bugs)

**Tested QA source:** `5ce05bf31b6efc3b70114be56a496fb74c00d649` against G0 candidate `59d28dc23be97de2a6a82d22be8338151e31f5b6`. **G0 status:** independently unaccepted; **G1:** NO-GO. Complete P6 report: [P6_G1_INDEPENDENT_QA_REPORT_20261116.md](P6_G1_INDEPENDENT_QA_REPORT_20261116.md). 327/327 suite passing under pinned deps. Do **not** read PASS as accepted family engineering.

| Assigned owner | Required submitted evidence | Independent acceptance test | Current status |
|---|---|---|---|
| P0 architecture / release custodian | Separate G0 exact candidate SHA reviewer and signed handoff; future G0 changes use append-only accepted contract version | Reproduce 327 at candidate, stress zero-probability exposures and correlated minute laws; external independent gate signoff | BLOCKED |
| P1 canonical source engineer | Original raw-byte receipts and full revision chains, first defensible availability UTC clock, canonical IDs, global duplicate game/forecast map and immutable outcome-vault separation | Hash raw source, tamper correction, late timestamps, traded player ID join, duplicate game partitions and target-result feature | BLOCKED |
| P2 statistical S owner | Executable PTS/REB/AST/3PM full PMFs or controlled scenarios, frozen feature/model cutoffs, provenance and abstention | Exact support/mass/tail/zero, Poisson/NB analytic cross-check and absence of target-game actual minutes or post-event availability | BLOCKED |
| P3 opportunity O owner | Eligibility/participation/DNP and conditional minutes joint laws with original G IDs, complete minute-allocation witness and proof five on floor over full clock (including OT) | Marginal-law coupling feasibility, 240/265 per-team conservation, impossibility of OUT played, interval-level five-on-court check | BLOCKED |
| P4 G/J simulator owner | Actual S/O/G bridge, original scenario/joint weight ledger, substitutions/shot/FT/rebound opportunity events and primitive vectors | Every combo from one draw, exact marginal-from-J equality, shot and rebound ledger, seed/hash repeatability, identity and OT | BLOCKED |
| P5 C scoring/optimization owner | Standalone scoring module and immutable predictive distribution warehouse, chronological CV and legitimate complete-pipeline simplex regularization | Compare C CRPS/NLPD/point MAE/RMSE/PIT/ES/VS to oracles, bootstrap game/date not paths, never treat S/O/J upstream stages as independent votes, 5k/20k finite-M precision test | BLOCKED |

**Important specificity:** The previously reported four contract bugs were reproduced as **closed regression checks** on this G0 repair candidate. No new critical defect is asserted on that candidate by the executed finite suite. G1 blockers are **evidence not yet presented**, not proof that an unavailable implementation is defective.

**Owner fix policy:** QA will not alter P1/P2/P3/P4/P5 source or mathematics. Create new owner branches and submit implementation SHAs, original receipts and targeted reproducer outputs. QA reopens red tests only when a concrete counterexample appears; no green retrospective fabrication.

**Prohibited:** historical predictive model scoring, training/weight-fitting, market-edge claims, Tier/production release, treating thousands of simulated draws as thousands of observed games, and a self-signed G0 approval. No other notebook, live automation or production artifact was changed by this QA handoff.
