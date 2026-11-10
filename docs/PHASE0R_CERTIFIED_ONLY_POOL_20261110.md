# Phase 0R — prospective certified-only forecast pool

Date: 2026-11-10. Applies to new production-afternoon collections under
`PICKEM_PRODUCTION_CONSENSUS=1`, and to explicit strict live runs under
`PICKEM_PHASE0_CERTIFIED_ONLY=1`. Historical testing and archived forecasts
are not rewritten.

## Intent and observed failure

The original 2026-11-10 live batch included 1,310 immutable forecasts:
702 passed independent strict pre-evaluation input certification, while
252 lacked original verifiable same-contract market evidence and 356 had
external `event_context` dependencies not pinned to the isolated model
input. The independently archived 3,296 source objects passed SHA-256 and
byte-length checks, but an intact archive cannot certify a dependency that
was not captured before model evaluation.

## Execution policy

1. Retain every prepared contract in the attempt ledger. Check event start
   before evaluation. Exclude any candidate with non-empty `event_context`
   while its external source and evaluation effects cannot be proven
   isolated. Never silently drop the context or pretend the player is
   healthy.
2. Exclude candidates without authentic two-sided original quotes, an
   approved same-line consensus, a fresh original quote clock, or uniquely
   matched book/time/event identities. Never fill a missing timestamp
   with the date of a later collection or a synthetic line.
3. Archive model inputs before evaluation and evaluate against isolated
   frozen history, original market bytes and production policy. If archival
   fails, abstain; never compute from mutable originals as a fallback.
4. After numerical evaluation, apply the same strict independent
   `phase0r_contract.strict_snapshot_status` used by `phase0_preflight`.
   A failed contract receives an `unavailable` receipt and is never
   appended to the forecast ledger, ranked, compared as an available model,
   or subsequently represented as certified.
5. Preserve all original input/rejection information in
   `reports/all_prepared_props_attempts.json`. The report distinguishes
   the attempted universe from the smaller certified prediction pool,
   including sport-level counts and rejection reasons. Don't interpret
   accuracy measured on this nonrandom subset as full-slate accuracy.
6. Never retroactively certify prior forecasts. A successful selected-pool
   strict report proves source-byte and model-input-binding integrity under
   the stated clock assumptions; it does **not** independently verify a
   provider's upstream publication clock or establish profitable betting
   performance.

## Release and safety boundaries

- Tier 1/Tier 2 publication and model promotion remain blocked.
- Research NUTS shadow failures cannot be silently replaced with legacy
  probabilities; missing sidecars remain explicitly unavailable.
- No heavy NUTS training, paid compute, new odds API purchases or GitHub
  agent execution are required for this gating change.
- Overall Phase 0R closure requires a genuinely prospective, independent
  review of the fresh selected batch, archive integrity, provenance
  limitations, rejection coverage and precommitted validation controls.
  The decision cannot be based solely on the fact that all retained rows
  were selected by a strict filter.
