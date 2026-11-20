# Coherent S4/J implementation and actual execution

The statistical construction changed. Physical accounting did not.
Governing authority: **PA-V25-MASTER-2026-11-09 / v1.1**. This is bounded,
user-authorized shadow research on an isolated branch, based on PR192
publication `d029747c106c8b825d13f13c0d107d45b36d6ec3`. Main was freshly
verified as `912bc7010058092ea735dcda0aa941429194474b`; it was not substituted
for the accepted implementation. All existing tracked paths remain unchanged.

## Implemented behavior

The new model fits opportunity components: two-point attempts, three-point
attempts, free-throw attempts, turnovers and shot conversions. Points and made
threes are derived together. It never draws independent points/threes rates
and rejects or projects them until they look physically compatible.

The old, independently tested event path, O coupling and physics auditor are
reused byte for byte. Every named statistic and combo comes from the same
game path. S4 is the marginal of this same J measure and scenario bank, not
an independent vote. See `MODEL_CARD.md` for exact priors, likelihood units,
branch-weight identities, conditioning, numerical guards and restrictions.

This is a new versioned family. All S1/S3 forecasts, prior posteriors, old J
outputs, original budget reds and mathematical incompatibility witnesses
remain immutable comparators. No old gate is silently relaxed or relabeled.

## Actual source-backed results

| Item | Recorded result |
|---|---|
| Frozen target |MEM–MIN, ESPN401910026,2026-11-22T01:00UTC / November21 at20:00 Toronto. |
| Population |Same35 listed players;14 supported,21 abstained. Same20 training games,698 source records,456 included ordinary rows,242 excluded rows retained. |
| New prospective fit |One fit;64 Gamma opportunity components and48 Beta conversion components. Old32 assist/rebound allocation components remain source-bound working auxiliaries. |
| Fit actual clocks |2026-11-20T13:00:57.538825UTC start;13:00:57.551179 completion;13:00:57.551289 persisted-byte verification. |
| Independent artifact checks |Entire model reproduced exactly without calling the writer again;112 independent posterior updates and1,440 posterior-predictive identity checks. Genuine ownFTA0 and own3PA0 retained. |
| Model admission |2026-11-20T13:07:09.021326UTC, for separate shared-kernel engineering execution only. |
| New actual freeze |2026-11-20T13:07:59.046901UTC; generation began13:07:59.063142 and completed13:09:03.026510. |
| Declared execution |Seed20261120,64 scenarios.64 completed,0 failed,0 dropped. |
| Paths |131 proposed paths;64 accepted,67 OT-pattern rejections. Scenario11 has oneOT and58 proposals; scenario36 has oneOT and11 proposals. FixedG/O/parameters never change across those proposals. |
| Raw traces |All131 deterministic gzip JSON files retained:14,390,781 JSON bytes and1,538,588 gzip bytes, with both byte-domain hashes. |
| Accounting |26,480 accepted-path event rows; unchanged auditor reports0 violations. |
| Marginal coverage |280 primitive/combo requests:112 supported,168 abstained. Primitive coverage remains140/56/84. Every older abstention reason remains attached. |
| S4/J identity |336 paired PMF/CDF/OUP public queries agree exactly on the same bank. This is software/measure identity, not predictive validation. |
| Old-reference disclosure |Largest observed CDF difference0.1706257776 versus simultaneous56-marginal DKW MC allowance0.2454942582. All56 mean/CDF/partitionTV comparisons and84 abstentions are saved. No closeness or improvement claim follows. |
| Target scoring |280 pending outcomes,0 actual scores. No offered quote or publication/end clock was invented. |

`FORECASTS.csv` contains all280 requests. `ARTIFACT_LEDGER.json` binds the exact
model, bank, receipts, comparison and replay outputs. `execution/` preserves
actual commands and stdout/stderr. The fit implementation is
`5a39abb8ab006319d5554e74d49c7e49b48dc04e`; the actual prediction implementation
is `8d8df996a44b00ba9af3f9e58325539b75641802`. The separately reviewed root
activation is `4b464906`; full SHAs are in the Git history and review ledgers.

## Independent review and preserved failures

Separate reviewers authored no implementation repairs. Protocol, closed-fitter
and actual-artifact reviews are in `independent_protocol/`,
`independent_prefit/` and `independent_artifact/`. Runtime review includes its
own synthetic controls, actual64-source replay, immutable-reader tests and
exact record/source/code/clock checks in `independent_runtime/`.

The wrong-team cohort counterexample and false aggregate trace-byte receipt
counterexample are preserved, with their repairs. Source-code/identity/clock/
readback/reuse mutations remain rejected. The reviewer's initial assumption
that every own-player attempt count must be positive is also retained as a
reviewer red; source zeros were preserved instead of manufactured away.

## Remaining scientific requirements

The Gamma-Poisson and Beta-binomial posterior identities apply to conditional
aggregate working likelihoods and fixed empirical peer priors. Their modular
use as relative event-opportunity weights is not a posterior under the full
clock/foul/rotation/OT-conditioned process. Neither its actual count marginals
nor an endogenous-attempt conversion law is asserted to be unchanged Poisson
or beta-binomial.

The all14-participate conditioning, unknown genuine participation and legal
eligibility, unupdated zero-state prior, below30-second extrapolation,
rate/minute factorization, residual-group exchangeability, pace proxy and
restricted NBA mechanisms remain explicit assumptions. New-family zero-weight
sensitivity is **pending**. The older S1 grid cannot validate this family.

MC intervals assume iid ideal-kernel samples. Finite path/event/storage caps
can fail as a function of latent state; completed-run selection does not prove
population error coverage. Intervals are pointwise per query, with a three-cell
OUP adjustment; not simultaneous across arbitrary players/lines. Zero hits
remain an estimate, never a certified population zero or an epsilon-clipped
log score. Whole-bank failure retains every requested population and exposes
no successful-subset forecast.

Target outcomes and correctly matched conditioning are still needed for real
scoring. Historical predictive validation remains required before release;
the supplied20 training games contain no matching pregame S4 model/forecast
receipts. No historical replacement fitting, holdout scoring/decompression,
ensemble-weight optimization, NUTS restart, schedule change, merge, deployment
or Tier promotion was performed. **Release remains NO-GO.**
