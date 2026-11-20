# NBA V2.5 S4/J Step 1 — P6 adversarial review: preliminary

## Immutable source and tests
- Review branch: `audit/nba-s4-ot-conditional-p6-20261120`
- Under review: `research/nba-s4-conditional-pimh-20261120`, frozen head
  `1f0dc864c51856127fcebb436b23b5ddea7b8d28`.
- Control S4/J event source remains as frozen in PR193, SHA receipts
  in PR195/PR196. This QA branch adds tests/documents only.
- Strictly no collector/source mutation, new fitted data, actual
  outcomes, weights, production edits or scheduled job changes.

## Mathematical scope independent of author test suite
1. Reproduce regulation and one-overtime original accepted path
   hashes under unchanged random seeds, including rejected-path ancestry.
2. Compare source-copied unconditional period trajectories against
   original accepted/rejected-prefix raw ledgers. Any mismatch = FAIL.
3. For rare K>=2, audit full NBA ledger and explicitly **refuse**
   to call sequential Q the exact globally conditioned law.
   Finite two-stage counterexample shows P(X=1|A0)=0.2 versus
   P(X=1|A0,A1)=9/13 ≈0.6923; future conditioning matters.
4. Check independently frozen K prior:
   P(K>=2) = p q = 0.00634719136781974, so replacing *any*
   conditional path law only for K>=2 can change an unconditional
   probability indicator or CDF by at most 0.635 percentage points.
   This result does NOT control conditional rare-OT accuracy,
   unbounded means, or relative rare-tail errors.
5. Verify positive/zero particle-filter evidence and finite-chain PIMH
   flags; exact-invariant PIMH is not called finite-iid or converged.
6. Check fixed G/O/P parameter sharing across all six zero-mixture
   assumptions, full 14 named identities and complete game clocks.

## Exact stage receipts available
- Original failed n1024 whole-path sampler PR195:
  6,143/6,144 accepted, one failure at original Beta index297;
  strictly fails whole stage.
- Research corrected PIMH n1024 with 96 particles and 16 iterations:
  5,292/6,144 paths completed before the 1,000-second budget,
  **FAILED_INCOMPLETE** (no analysis admitted).
- Bounded Q n1024: 6,144/6,144; receipt SHA256
  `134668a4d9f75571e650dfe4873e5eb127152e4e06e1638742a6a1534f119f93`;
  nominal 95% simultaneous CDF DKW + worst-case rare OT allowance 7.69pp.
- Bounded Q n5000: **30,000/30,000** across five global shards;
  independent identity/SHA aggregator checked 420,000 player
  stat rows; receipt SHA256
  `9bc43371cd1f7356896dd66950d58137624d081a402df64b5b2449fe7822cbce`;
  bound 3.828pp. Original zero-state forecast not replaced.
- Read-only cross-source first256: 1,530/1,530 K<=1
  player-stat vectors identical across original/new, six K>=2
  cases identified separately.

## QA disposition pending the independent test CI and full volume receipts
- Original unmodified event-law fidelity: engineering PASS if independent suite succeeds.
- Conditional mathematical mechanism: exact-invariant PIMH and
  bounded Q with explicit upper envelope **not interchangeable**.
- Finite PIMH chain convergence for K>=2: **NOT ESTABLISHED**.
- Full n20,000 bounded-Q sample and n5000-to-n20000 numerical precision
  stability: **PENDING until receipts audited**.
- Participation/roster/source-certified historical validation,
  future outcomes, CRPS, calibration, G1/G2, P8/P9/P10/P11 and
  production: **OUTSIDE STEP1 / NOT APPROVED**.
- This programmatic review is an evidence suite authored in the
  same conversation. It must not be portrayed as a separate
  organizational P6 approver signing the final gate.

The numerical and source no-leakage gates remain independent.
