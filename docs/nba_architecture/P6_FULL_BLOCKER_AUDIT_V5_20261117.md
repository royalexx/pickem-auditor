# Fresh independent NBA G1 full audit v5 — NO-GO

Authority: **PA-V25-MASTER-2026-11-09 / v1.1**. Accepted G0 remains
`59d28dc23be97de2a6a82d22be8338151e31f5b6` only. Reviewer:
`/root/p6_independent`, separate from the implementation owners. This task is
an audit and remediation-prompt pass; the reviewer changed no owner code.

**36 criteria: 26 PASS, 2 FAIL, 8 BLOCKED.** The fresh audit reopens
**F-P2-07** and **F-P5-05** with new concrete counterexamples at unchanged
owner heads. Their aliases F-P2-07-R1/F-P5-05-R1 are not additional criteria.
The previous 28-PASS/8-BLOCKED review at PR172/e748 remains immutable history.
Standard suites remain green, which does not close these new failures.

The complete per-criterion owner SHA, runnable command, result, classification,
minimum remaining requirement and independent disposition are in
[criterion_ledger.json](p6_full_blocker_audit_20261117/criterion_ledger.json).

## Fresh source population and execution

GitHub PR metadata was freshly fetched at **2026-11-17 13:39:48 UTC**,
followed by Git fetches of all submitted objects and disposable checkouts.

| Owner | PR | Exact current tested head |
|---|---:|---|
| P1 |167|`50d2b3874c7c14c9b73bdf13e441957986b88acd`|
| P2 |165|`fe46965394ea0f48ef5e9da501ec8ca9e441ce47`|
| P3 |166|`eb0882b5011f2004c5eaf27cccfdc6297704f261`|
| P4 |164|`865bdb8f4770ac28262e49c3b4901cf1d72a22fb`|
| P5 |163|`cb3ff8279bc7f4cc7b86a519a1e386ddbe37ae93`|
| P0 discovery |171|`c14b5584c30f8fbca3eb2e51acfaea24c40eff29`|

Coordination PR170 was `39fd26c509722bb46dc3ad6b5df22e73902e68bc`;
previous independent PR172 was `e7484523b2e9a5e8a79d636bb862957e88dd2b37`.
The exact assembly is `6dee6e09fa786479dc2e163a33e14257f207b35e`,
with all 653 owner files/modes and 24 inherited G0 files independently
reverified. Fresh end-of-audit drift checks are retained in the packet.

The full execution harness was committed before execution at
**`32243941a92559ff11b2640582e4fa6cd0f4ef1e`**. New adversaries were
separately committed before their executions: c70b4fd (P2), d1ca72f (matrix),
821aafb (public P5), 64aa822 (status aliases). Full SHAs and raw source hashes
are in `source_execution_provenance.json`. All executable bytes remain
unchanged in the later documentation/evidence publication.

The fresh standard run reexecuted:

- **24 current-owner commands**, including architecture suites
  377/267/319/351/267, five separate 83-control P6 runs, P1 preflight9,
  S61/C76, immutable original probes and separate repaired regressions.
- **32 historical expected command outcomes**, including original red exits
  and exact case names; original upstream WS1/WS2/WS4/WS5 pins pass
  25/25/33/63 controls.
- **Five latest-owner native boundary cases** and **eleven independent
  adversarial/numerical sections**, including full-count proper scores,
  active-face synthetic W2/W3 references, scalar/clock/identity/immutability,
  weighted ESS/game counts, same-draw combinations and process-hash replay.
- **17 shared checks**: clean root discovery with PYTHONPATH unset,
  513 architecture, S61/C76, ten inspected offline suites/56 methods,
  compilation and two Bash syntax checks. Unrelated root test bodies were not
  executed; repository-wide CI is not certified green.
- The actual **256-seed P4 study**, all96 PMFs, independent pooling and
  reference-conditioning checks, plus an opaque 99-shard archive hash check.

All 26 standard top-level executions meet their declared expectations.
Dedicated suites overlap; their counts are not independent observations.
The new counterexample programs then fail as specified below. All fits and
optimization fixtures are synthetic. No historical/holdout warehouse shard
was decompressed, no historical predictive evaluation/training was performed,
and no source/forecast/correction record was replaced.

## Reopened F-P2-07: raw zero can pass through a positive caller display

At [P2 p1_native.py:127](https://github.com/royalexx/pickem-auditor/blob/fe46965394ea0f48ef5e9da501ec8ca9e441ce47/v2/nba_s_family/p1_native.py#L127),
the played branch converts exact raw minutes, checks a half-minute display
tolerance, then applies the zero-credit guard only when the caller display
equals zero. A positive display such as **0.25 or0.5** bypasses that guard.

The raw source has `PT0M0S`, played1 and positive credits. Actual P1 rejects
`ZERO_MINUTE_CREDIT_UNRESOLVED`; P2 instead returns `structurally_checked=1`
and preserves `OFFICIAL_BOX_RECONCILED`. Tiny positive displays also bypass it.
Admission still remains BLOCKED and `training_rows=[]`; this is a narrow
structural-accounting defect, not demonstrated real certification or leakage.

The five-case standalone reproducer retains two valid controls (raw15 seconds,
display0 or0.25), the already-correct raw0/display0 rejection and two new red
positive-display controls. A separate **224-case** raw/display/subset matrix
finds **ten P2 disagreements** with actual P1, all in this same zero-clock seam.

Source raw SHA256:
`372af3be16c33437272d9ee63bf37b18c581962c7566c4f64827961259e5bcc1`.
Baseline native fixture raw SHA256:
`c89948eb44e0ca926a2bd5929effa098fb3988c6a26cb9be321316af2ec410b5`.
One exact failing input SHA256 is
`825e9e03a87a7d32dc79782e2ba290ae0b87de047efaeedc0ec1e8ad837a3c12`.
Full inputs/source-before/raw outputs are preserved in
`red_F_P2_07_R1/`, initially committed at
`4faa8cbe370e55fc0940a5b87f45b492a6ef70f0`.

Minimum owner repair: compare **exact raw rational zero** against **all raw
normalized credits** before display/status reconciliation. Do not use the
possibly underflowed serialized float as the zero test. Preserve genuine tiny
positive/subminute cases, omitted-stat subsets, true-zero/all-zero, DNP/unknown,
source/ancestor/cutoff/identity checks and exact duration caps. Add separate
green owner regressions and re-pin downstream runtime inventories. The old
adversary remains the immutable red baseline, not a repaired-head provenance
record.

## Reopened F-P5-05: hidden raw credits change the rounding rule and status

At [P5 native_adapters.py:196](https://github.com/royalexx/pickem-auditor/blob/cb3ff8279bc7f4cc7b86a519a1e386ddbe37ae93/v2/nba_c/native_adapters.py#L196),
the strict subminute rule depends on retained `record.stats`; at
[line432](https://github.com/royalexx/pickem-auditor/blob/cb3ff8279bc7f4cc7b86a519a1e386ddbe37ae93/v2/nba_c/native_adapters.py#L432),
the prior accounting status is also derived from the retained subset.
Both must use the complete normalized raw-credit population.

Three public-path failures are independently reproduced:

1. **False rejection:** actual P1 exports raw15 seconds/display0/rawPTS11 with
   retained `stats={'threes':0}` and correct `ADJUDICATED_ROUNDED_SUBMINUTE`.
   Actual P2 accepts that structural case. Public `NativeForecastArchive.put_s`
   rejects `NATIVE_PRIOR_ACCOUNTING_STATUS_JOIN`. The same problem occurs
   strictly below30 seconds and at a positive rational duration that underflows
   the serialized float to zero.
2. **False outcome acceptance:** rawexact30 seconds/display0 with those hidden
   raw positive credits fails actual P1/P2, but both public
   `validate_p1_export(..., outcome=True)` and `NativeOutcomeArchive.put_p1`
   accept it when the retained subset is zero.
3. **Caller-label bypass:** the same invalid30-second prior source is accepted
   by public `NativeForecastArchive.put_s` when its caller label is
   `OFFICIAL_BOX_RECONCILED`; the correct raw-derived status is not being
   enforced. Even the legal15-second source is accepted with that false label
   and rejected with its correct ADJUDICATED label.

The standalone test invokes **actual P1 export, actual P2 synthetic fitting
and public P5 forecast/outcome APIs**. These are not private-helper-only
observations or replacement models. Source admission and scoring remain
BLOCKED; the accepted invalid outcome has `scored=False`. P5's existing exact
raw-zero guard is correct and must be preserved.

The matrix reports three false prior rejections and one false outcome
acceptance. Public ten-case and four-case status follow-ups overlap these
counterexamples; they are not extra independent defects or games.

P5 source raw SHA256:
`a875ca2d819879ce0ace1083599780d42db7942a3aca4dd88bc08fb2eabed5e8`.
Outcome fixture raw SHA256:
`d73730d0a5c923c41555e85722c35e318545f16e6c591d396b1e1caaf4630fdb`.
The false outcome input hashes to
`d37302fc1848843a2dfec31a18431d8ed22101bee701e25696131b22592ca224`;
the invalid prior accepted under the false label hashes to
`d74b6876b2ee6557ef4ffcc4533cc4a3b7ebbcd91bad4a105e919d5c6914cb92`.
All inputs, synthetic fitted artifact bytes, code-before and raw outputs are
retained in `red_F_P5_05_R1/`.

Minimum repair: derive the strict `0 < exact_raw_minutes < 1/2` rounded-credit
rule and matching accounting status from raw normalized credits consistently
across prior attachment and outcome validation. Validate caller labels against
that derived classification. Do not merely widen accepted strings, reject all
display-zero rows, infer missing requested stats, erase raw credits or relabel
them as DNP. Reexecute the full matrix and public-path controls, C76/native21,
owner/G0/P6 and affected latest native consumers, then obtain separate P6 review.

## The eight substantive blockers remain open

The authentic strict builder again stops at P1:
`OFFICIAL_SOURCE_EVIDENCE_REQUIRED`, **26 attempted entries**, no snapshot and
no G/O/S/J/C continuation. Synthetic compatibility cases are separate.
Opaque archive integrity again matches **99 compressed shards /39,916,715bytes**;
that proves neither first availability nor roster/DNP/correction completeness.

| Criterion | Responsible owners | Concrete remaining work |
|---|---|---|
| B-P1-01 |P1/P0| Obtain and independently admit original roster/availability, dated membership/trades, complete schedule/result/participation populations and corrections with honest clocks and raw byte domains. Document bounded searches and exact missing populations. |
| B-P1-02 |P1| Obtain authentic specific prior-game duration/OT/stat/correction and minute-display exception evidence. The retained official request is HTTP403, not duration proof. |
| B-P2-01 |P2/P1/P0| Repair F-P2-07; independently approve an authentic-source/fit admission protocol; implement a new admitted native reader; supply admissible existing fitted artifacts at lawful cutoffs. Do not fit historical replacements. |
| B-P3-01 |P3/P1/P0| Independently admitted original roster/context, dated membership/home/role and participation/minute priors, followed by an explicitly versioned admitted consumer. Preserve null genuine participation. |
| B-P4-01 |P4/P2/P3/P0| Actual latest synthetic native consumer already works. Add authentic source/fitted-byte admission only after independently reviewed trust contracts; do not relax fixture/code hashes or real-mode guards. |
| B-P4-02 |P4/P0/P2/P3| Produce and independently review a new constrained physical-law contract, justified predeclared distortion/tail limits and event-time possession/FT/rebound/assist/co-presence/OT/early-exit/participation semantics. Implement/prove the approved version; current proposal remains unaccepted. |
| B-P4-03 |P0/P3/P4| Implement a mathematically verified scalable full-law coupling/max-q/support strategy or precisely characterized accepted range. Preserve the old n32 budget red and old G0. A candidate bound-attainment proof is described below, not accepted. |
| B-P5-01 |P5/upstream/P0| Repair F-P5-05, then adopt independently accepted admitted source/fit/J contracts and genuine separate outcome/event/end/release/correction evidence. Actual synthetic intake/all96 law handoff already works. |

Current v1 transport readers deliberately accept only BLOCKED or synthetic
profiles: P2 admits no rows, P3 does not sample, P4 real mode rejects and P5
real admission is closed. **Acquisition alone cannot activate these APIs.**
An independently reviewed admission protocol and coordinated new reader
versions are required, while old blocked/synthetic objects remain unchanged.
Hashes, caller flags, source labels or a nominal reviewer signature cannot
substitute for actual source/clock/identity/coverage authentication.

A bounded supplementary coordinator inspection found an existing WS2
conditional-minute artifact in the original Deepnote project. Its recorded
cutoff is 2024-04-15; its experiment uses positive observed-minute rows and
explicitly blocks participation metrics without complete eligible rosters.
It is not a genuine fitted-participation artifact, is after the old2018
targets, and is not independently source-admitted here. The retained text
receipt has domain `TOOL_RETURNED_UTF8_PROJECT_FILE_TEXT_NOT_PROVIDER_HTTP_BYTES`.
No notebook, historical dataset or predictive result was executed/read by
this audit to establish its admission. Do not describe the artifact as absent;
describe its precise current limitations and review prerequisites.

## P4 numerical and coupling review

The fresh actual study again retains all **256 J seeds ×4 fixed O2 scenarios
=1,024 weighted paths**, zero observed games, no O resampling/scenario discard,
12,288 rate attempts and 1,037 event attempts including13 retained ties.
Independent pooling reconstructs all96 normalized PMFs and semantic SHA256
`5de46126c5158d061d9f327f3e78c1faa123970ccf1a7fba80cb61cbed28b262`.
New compressed/uncompressed raw output hashes are separately recorded.
Maximum absolute mean distortion remains **11.3679975911**; maximum empirical
TV **0.4767262428**. All48 public unconditional P2 calls abstain. Played-
conditional comparisons match the fixed-O reference to3.7402e-12; no q=1
authentication follows from sampled PLAYED states.

The fresh70-digit reference still proves an actual P2 marginal incompatibility:
Pr(3PM≥20)4.7690783256717101e-10 exceeds Pr(PTS≥60)2.7588729050486701e-10,
contrary to any coherent PTS≥3×3PM law. This does not accept the proposed
constrained kernel or its distortion. The physical/conditioning/possession
semantics and acceptable approximation remain a material contract requirement;
`NBA-J-CONSTRAINED-LATENT-RATE/0.1.0-PROPOSAL` is not accepted for G1.

The actual O2 n32 budget failure is again reproduced. A **candidate** scalable
proof is mathematically sound in principle: if a verified nonnegative primal
measure on conserving allocations satisfies **all** declared minute atoms,
known-q and OT marginals and witness-support constraints, and attains each
unknown existential q_i=1, universal q_i≤1 certifies the full-support maxima.
No enumeration of other columns is needed for that bound-attainment argument.

It is not a general sparse-primal shortcut. A new P0-owned version must
independently derive/check the complete atom population, including tiny
positive masses, exact weight/identity bindings, DNP versus played-zero,
eligibility, duration caps, conservation, required-positive queries and
positive mass for observed witnesses. Uniform1/32 inputs may permit exact
rational checking. Genuine q must remain null; positive-exposure bound remains
q_max×P(minutes>0|played), not automatically1. Mixed/nonattaining cases need
complete LP/certified pricing or another independently accepted full bound;
different objective maxima need not share one optimizer. Unsupported cases
stay explicitly unresolved. No implementation, selection, semantic-equivalence
review or acceptance of this candidate occurred here, and it does not solve
event-time physics or source authentication.

## Formal independent recommendations

| Family | Recommendation |
|---|---|
| P1 | **BLOCKED** |
| P2 | **FAIL — F-P2-07 reopened; B-P2-01 also remains BLOCKED** |
| P3 | **BLOCKED** |
| P4 | **BLOCKED** |
| P5 | **FAIL — F-P5-05 reopened; B-P5-01 also remains BLOCKED** |
| P6 | **PASS — finite independent QA exposing the failures** |

**Overall G1: NO-GO.** The two repairable defects are intentionally unrepaired
in this audit-only task and must be the first owner tickets in the remediation
master prompt, followed by separate independent review. The eight substantive
criteria require the concrete evidence, admitted readers and engineering proof
above. All original reports and red/green receipts remain append-only. No G2,
historical predictive fitting/validation, historical weights, NUTS restart,
merge, deployment, schedule change or Tier promotion is authorized or performed.

See [REPRODUCE.md](p6_full_blocker_audit_20261117/REPRODUCE.md), raw red packets,
fresh execution receipts and SHA256SUMS. The coordinator authors the master
prompt; this reviewer supplies the independent findings and prerequisites.
