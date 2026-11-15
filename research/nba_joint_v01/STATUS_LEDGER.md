# NBA WS5 status ledger

Governing `PA-V25-MASTER-2026-11-09 / v1.1`; bounded user-authorized WS5 research ticket. Base `912bc7010058092ea735dcda0aa941429194474b`; final simulator execution pin `ca41c79426a90a57e78ca9554a993db326461737`.

| Deliverable / gate | Status | Evidence |
|---|---|---|
| WS1 / WS2 / WS4 integration | Implemented and tested, unmerged | Exact source pins and unchanged-byte verification; WS4 late PR #139 integrated; WS3 baseline substitution documented |
| Shared state, rotations, events, combinations | Implemented and tested | `v2/nba_joint`; 179 local targeted tests, zero failures/skips; 113 Deepnote tests |
| Gate A engineering | PASSED | 2,688 synthetic stress scenarios; 14,848 constrained historical configuration scenarios; zero required arithmetic/minute/final-score violations; scientific replay hash match |
| Gate B source integrity | BLOCKED-BY-DATA | Source gates fail closed; fresh Nov15 canary rejected all 36 candidates; no certified new original-contract forecasts |
| Gate C marginal reliability | FAILED | J2 regresses against J0 on the matched 24-date cohort; no baseline replacement |
| Gate D joint reliability | FAILED | J2 Energy/Variogram regress against J0; dependence-only Energy benefit is INCONCLUSIVE; no joint model adoption |
| Gate E prospective readiness | BLOCKED-BY-DATA | Original source capture works; eligibility/participation/quotes and independent certification missing |
| Gate F production promotion | BLOCKED-BY-DATA | Outside this directive's authorization; genuine prospective evidence and explicit approval remain required |
| Independent WS4 structural/count checks | Tested through actual WS4 code | 3,712 scenario boundaries / 4,496 count-distribution checks; exact count CRPS agreement |
| External independent joint approval | INCONCLUSIVE / pending | Neither author tests nor separate-runtime execution constitute external scientific approval |

Largest measured limitation: the prior-appearance-union conditional roster overpopulates candidate teams, and projection materially shifts player-minute marginals downward. Next: a small authenticated roster/availability diagnostic, preserving unknown appearance probabilities. No neural model, copula, NUTS refit, scheduler or promotion work is proposed.

Rollback: stop invoking this isolated package and close the draft PR. If later merged, revert that research PR while retaining source and experiment receipts. No production migration exists.
