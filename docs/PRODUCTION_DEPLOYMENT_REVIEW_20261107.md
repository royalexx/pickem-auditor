# Independent deployment review

**Disposition: no remaining deployment blocker identified in the reviewed changes.** The three material findings below were reproduced or established from execution order, reported before deployment, and corrected. This accepts the implementation within the stated scope; it does not certify calibration, profitable picks, or a live hosted deployment.

Scope: new production 70/30 policy, per-pick comparison reporting, completed-fit NUTS adapter, notebook/workflow integration, and persistence against local audit HEAD. Read AGENTS.md and the recorded production authorization. The user already authorized deployment; no further approval is needed. This reviewer made no production source edits, remote writes, training changes, or historical-record modifications.

## Resolved findings

1. **P1 — normal NFL targets retries aborted the entire report.** An unavailable attempt followed by a valid forecast for the same parent raised `conflicting_model_sidecar_identity`. The reporter now separates failed attempts, deterministically selects the earliest successful inference, and still rejects conflicting successful probability masses. The regression reproduces both the successful retry and conflicting-success rejection.
2. **P2 — NFL January/February predictions used the wrong season.** Generic NUTS context used calendar year. January/February now map to the previous NFL season; the January2027→2026 regression passes.
3. **P1 — reused NUTS adapters stamped batch start as completion.** Future NHL saves and NFL targets outputs now stamp actual inference completion, identify that timestamp's semantics, and reject completion at or after event start. Production CLI calls use a live clock. Historical rows remain unchanged. Independently exercised the NFL targets run with completion exactly at kickoff: unavailable, `model_not_completed_before_event`, and no probability. The equivalent NHL regression passes. This finding established a timing-proof weakness, not actual historical leakage.
4. **Persistence hardening:** the new immutable-sidecar guard uses canonical JSON multisets instead of Python value equality. Independently executed the exact embedded guard: numeric1→booleantrue substitution and duplicate-row deletion fail; reordered preservation plus append succeeds. Offline NUTS discovery now passes through the same receipt/hash checks as online cached discovery.

## Verified behavior

- Six production policy tests passed: full win/push/loss mixture, missing or unreliable component abstention, null serialized production probabilities, opt-in isolation, policy-dependent run IDs, and retained Tier1 gate.
- Latest focused verification: slate/NUTS comparison tests10/10; NHL saves tests9/9; NFL context tests13/13. These supplement the parent's full-suite run rather than replace it.
- Reviewed jobs/verification production opt-ins, source revision pinning, comparison bundling, and post-inference persistence. Bayesian/NUTS values remain comparisons only. No failed convergence fit is admitted and no threshold is relaxed. Missing B never becomes an A-only production consensus.
- Displayed probability columns use the exact original player/side/line and conditional-on-nonpush scale. Paired-price normalized Market is distinct from the historical policy-adjusted market score. Context adjustments remain identified. Fixed NUTS family priority does not select the largest probability.
- Completed successful model artifacts only; normal cached discovery verifies manifest/posterior hashes and remains usable with an Actions403/Contents-only token. Generic NUTS support is limited to count markets; unsupported adapters produce explicit unavailable values. No training or active job mutation occurs in this path.

## Remaining operational limits

- Generic population NUTS deliberately freezes the first result for each parent snapshot, including unavailable. Recovering availability after cache staging requires a new source run. Frozen comparison rows remain unchanged. A rerun can refresh an output file while preserving the original archived comparison; consumers must distinguish the refreshed view from the frozen evaluation cohort.
- The report preserves legacy adapter timestamp fallback for older records. Only new outputs with `generation_semantics=inference_completed` carry the stronger completion evidence added here; this patch does not retrospectively establish older forecasts as prospective.
- A strict manifest and hash-verified posterior establish artifact identity and the configured sampler gate, not universal predictive convergence or calibration. The earlier independent review of all nine actual posteriors and the rejection of eight failed fits remain applicable. IID numerical integration error, posterior uncertainty, and chain-aware posterior MCSE must not be conflated.
- Hosted rollout, actual new slate collection, and live artifact persistence are the parent's deployment verification responsibility. This local review does not claim those operations succeeded. Existing broader atomic-write, concurrency, historical evaluation, and calibration limitations remain documented in the prior audit and were not silently expanded into this deployment patch.
