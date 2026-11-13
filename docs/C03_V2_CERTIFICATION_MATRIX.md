# C03 v2 implementation / integration certification matrix

**Status:** IMPLEMENTED AS OPT-IN RESEARCH, NOT END-TO-END CERTIFIED.
**Base:** foundation integration candidate PR #120, commit
\`5c649e3edb5916ac051314aea451435f6a26c68f\`.
**Current branch:** \`work/v25-c03-context-cohorts\`; independent review pending.
**Feature flag:** \`PICKEM_C03_V2_SHADOW=1\`, default off. Do not set in a live
publishing or scheduled process without a separate owner/independent approval.

## Cohort and estimand matrix

| Cohort | Evidence | Forecast output | Publication |
|---|---|---|---|
| A | No relevant event_context; legacy exact history, original quote, source and model cutoffs verified | Neutral baseline conditional on play; strict legacy v1 authoritative | No new Tier or release |
| B | Verified player/team/event/source-backed active or teammate OUT, no subject OUT/Q/D/conflict; independent original+neutral byte binding; valid pregame clocks | Exact unadjusted baseline, no role uplift | RESEARCH ONLY until independently certified |
| C | Separate context adjustment with source AND training-manifest receipt; forecast separately versioned | Adjusted distribution is a research hypothesis only | Forbidden |
| D | Missing/tampered/late raw source; wrong identity; Q/D/OUT/conflict; unknown starter; unverified lineup; source or model mismatch | Abstention/uncertified; all attempted rows remain in denominator | Forbidden |

Subject status \`unknown\` is not implicitly active. A conditional-on-play baseline
is not marginal over participation, not conditional on a verified lineup, and
not the payout probability conditional on no void. The latter requires the
individual book/contract's void terms. An active player who leaves early
retains scored actual production if the product did not void. A played 0
is a genuine 0, NOT a DNP.

## Code status and strict-source boundary

- \`scripts/c03_context_cohorts.py\`: content-addressed original HTTP response
  **body** bytes and exact JSON-pointer claim verification, source IDs, player/
  team/event identity, UTC possession/freeze checks, A/B/C/D classifier, neutral
  input transform, separate strict v1+v2 validator, official NHL roster
  revalidation and bookmaker-conditional settlement disposition.
- \`scripts/jobs.py\`: opt-in research gate, original candidate archived before
  numerical freeze, independently rechecked at actual pinned evaluation
  timestamp, then dual strict-source status check. No default behavior changed.
- \`tests/test_c03_context_cohorts.py\`: OUT teammate, active/out/Q/D, conflicting,
  tampered, late, wrong team, QB started/backup, goalie membership/starter,
  immutable SHA, actual legacy A/B/blend invariance and void/early-exit cases.
- Existing \`scripts/phase0_pre_eval.py\` and \`scripts/phase0r_contract.py\`
  remain unchanged by C03. V2 is a separate sidecar above old v1 strict
  source and numeric-input certification; old Nov 10–12 receipts untouched.

**Current hard blocker:** The existing \`context_feeds.py\` /
\`research_resolver.py\` fetch functions return parsed dictionaries rather
than signed, pregame, raw HTTP availability bytes with exact claim pointers.
The new \`capture_live_http_body()\` transport primitive is not yet connected
to their actual pregame producers. Therefore source-bound B forecast
certification is NOT demonstrated by these fixtures; do not claim this repair
has increased legitimate certified live coverage.

**Additional hard blocker:** An independently archived original *pre-research*
prepared-candidate record and verified raw→neutral numeric dependency graph
must be bound before calling any B strict certification complete. The current
sidecar retains the original *postmerge* candidate as well, but that
serialized state is not proof of the collector-owned premerge source. Do
not substitute it. Status remains research implementation pending this proof.

**Clock distinction:** Collector possession is first-known information time;
it is not authenticated upstream publication time. A response carrying an
\`effective_at\` game date does NOT prove when the report was published.

**QB identity caveat:** NFL pass-attempt/completion/passing-yard contracts
need a verified named pregame starter. Rushing stats apply that rule only to a
verified position QB. Verified RB rush props must not be excluded as backup-QB
props. Unknown rusher position is an abstention in the C03 opt-in path.

**NHL caveat:** Official both-team roster membership verifies identity,
not goalie named starter, game activation, or participation. Separate starter
claim is needed for goalies.

## Integration / migration / rollback

1. Keep old v1 schema and old v1 hashes unchanged. Read v1 historic snapshots
   only with the existing validator and original semantics. Never backfill
   source clocks or retro-certify Nov 10–12.
2. Merge/review PR #120 foundations only following owner + independent review.
   For C03 sidecar, independently audit every new source read and numeric
   transform before any B acceptance. Require strict source possession
   evidence and a valid underlying v1 certificate.
3. Run fail-closed prospective canaries for teammate OUT and active, source
   tampering, post-freeze report, correct NHL trade and named goalie, QB
   rushing role, and full attempt-ledger denominator reconciliation.
4. Test exact equality of neutral A/B input hashes AND actual legacy Engine A/B
   and blend probability objects, with fixed source/model/quote bytes.
5. For rollback, leave \`PICKEM_C03_V2_SHADOW\` unset, preserve all new
   source bytes, snapshots, rejects and audits, and do not modify old records.

## Review signoff

CI success demonstrates executable tests only. Raw-source transport lineage,
premerge input provenance, true source-authoritative injury status,
product-specific DNP/void treatment, and genuinely prospective score
denominators remain unverified. Independent engineering + mathematical
review/owner approval are required for branch merge and for any later source
certification release. This document grants no model promotion or Tier.
