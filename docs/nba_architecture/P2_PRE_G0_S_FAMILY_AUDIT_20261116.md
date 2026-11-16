# NBA V2.5 P2 — pre-G0 S-family capability and gate audit

**Date:** 2026-11-16  
**Status:** `BLOCKED_BY_G0` — preparatory read-only audit, **not P2 implementation**, acceptance, G1, historical scoring, or production release.  
**Audit base:** `main@912bc7010058092ea735dcda0aa941429194474b`.  
**Latest unaccepted contract candidate:** `research/nba-g0-law-coupling-repair-20261116@59d28dc23be97de2a6a82d22be8338151e31f5b6`, draft PR #157.  
**Contract:** `nba-sojc-contract/2.0.0` (candidate, not independently signed G0 PASS).  
**Owner:** S statistical modeling, exclusive eventual ownership of outcome statistical distributions; P0 owns shared contract, P1 source, O opportunities, J game draws, C score/calibration.

## 0. Decision — mandatory prerequisite

`docs/nba_architecture/GATE_BOUNDARIES_V2.md` on the contract candidate explicitly prohibits beginning P1–P6 before independent G0 PASS. GitHub issue #149 is OPEN and requests a separate reviewer. PR #157 is OPEN/DRAFT/UNMERGED and states `NOT_APPROVED_PENDING_NEW_INDEPENDENT_REVIEW`. The prior G0 candidate PR #156 was independently rejected at `e1983b2d0b94742dfb1bf411694dc46c7cad1ac6` for incompatible conserved minute laws and positive count distributions despite zero possible exposure. PR #157 repairs these according to author tests, but reports **267/267 author tests, not an independent certificate**. Do not treat this as G0 PASS.

**Gate disposition:** No P2 executable family implementations, fit runs, trained artifacts, P2 synthetic test executions, G1 attestations, scenario adapters, historical accuracy studies, branch merge, external PR approval, NUTS training, or weight learning were undertaken by this audit. Do not claim P2 completion or create an approval-seeking P2 code PR before independent acceptance. This audit-only branch can be closed without affecting model code.

The separately named *NBA Parallel Architecture and Monte Carlo Execution Prompts* packet was not among source attachments available in this work session or the prior P0 inventory; the user provided P2 instructions directly. No packet-exact compliance can be claimed before the packet is located.

## 1. Inspected reusable statistical implementations

| Source (exact inspected blob SHA) | Actual reusable behavior | P2 limitation / ownership decision |
|---|---|---|
| `scripts/bayesian_engine.py` (`3dfe8a94dbd0ed07e7af396cef571e322692a480`) | Empirical cross-player prior; source/cutoff checks; Gamma–Poisson predictive recurrence; fixed-dispersion NB posterior grid; count and Normal paths; exact at-line O/U/P | **Mathematical/reference candidate only.** Output is an offered-line probability summary, not a certified complete PMF over support with explicit tail bound and v2 S identity/lineage; no O-scenario law. No direct frozen-v1 modification permitted. |
| `scripts/nba_prior_bridge.py` (`04079df2397d1ec9138e745194a0a1264c6f488b`) | Early-season historical prior with fractional-power observations, separate workload uncertainty and rate estimates; Poisson/Gamma and fixed-dispersion NB paths | **Extract/test statistical concepts only.** Owns its historical workload modeling internally; cannot substitute those modeled past workloads for O's point-in-time participation/minutes predictions. Its original outputs are line-specific shadow probabilities, not a v2 S adapter. No reuse of its source chronology assumptions without P1 verification. |
| `v2/nhl_nba_phase1.py` (`e500b72100e4864ee9ba8f0fa886ad522ec2b058`) | Read-only source-hash-checked historical record loading; Poisson count-rate counterfactual baseline; missingness and exact matchup handling | **Good simple control reference.** Replayer reports counterfactual shadow controls, not originally published pregame model predictions. Distinguish stat-agnostic Poisson count control from calibrated NBA likelihood. |
| `v2/nba_architecture/v2_contracts.py` (`920d10390553f1de5635b5efbc9437d45212db74`) | Candidate v2.0.0 versioned `validate_distribution`, `threshold_triplet`, shared source/identity/time joins, S-only/O/J lineage, strict nonnegative-integer PMF and tolerance checks | **Contract owned by P0.** No S-side edits; adapt after independent G0 PASS. Contract requires `tail_mass_upper_bound <= 1e-8` and `sum(pmf.mass)=1 ± 1e-10`; an uncontrolled partial CDF or silent tail renormalization is invalid. |
| `v2/nba_architecture/families_v2.py` (`6fc93fa4568523da534da082806e058d4309d967`) | Candidate O/G/J validation, exposure/count bound, integration check against actual G/O/J objects | **Not an S likelihood.** S must not resample O/J participation, alter shared minutes, or count S/O/J layers as independent forecasts. |

The P0 capability inventory also reports that no dedicated accepted NBA WS3 fitted outcome family was found; this audit did not discover a later accepted WS3 via GitHub pull-request search. Archived WS5 tests validate joint physical mechanics, not substitute for a fitted S conditional likelihood. Deepnote's NBA WS1, WS2, WS5 and G0 notebooks remain existing separate research evidence; no new Deepnote execution was made.

## 2. Candidate S-family design, **not implemented**

After G0, implement four primitive, full-game-including-OT supports: `points`, `rebounds`, `assists`, `threes`. All distributions have nonnegative integer counts; `PR/PA/RA/PRA` are J same-scenario sums, never independent S votes.

**S0 control:** History-only per-exposure count rate with bounded, declared shrinkage and Gamma–Poisson predictive law; compare both direct historical per-game Poisson and exposure-conditional Poisson where valid. Do not reassign original historical Engine A probabilities. Cases without defensible exposure use S_ONLY and an explicit limitation, rather than secretly substituting realized target minutes.

**S1 hierarchical conditional-rate:** Player-specific exposure-normalized rate with peer/position/team shrinkage using time-valid historical observations only. Freeze posterior/hyperparameters at `model_training_cutoff_at`. Integrate epistemic uncertainty and O-provided pregame opportunity mixture, never realized target-game minutes. Avoid unproven exchangeability of completely different roles.

**S2 count dispersion challenger:** Negative-binomial (NB2, variance `mu + mu²/k`) when count dispersion justifies a challenger; zero-altered/hurdle candidates only if a *structural* zero mechanism survives after O's participation model. Do not count DNP zeros as evidence of shooting inefficiency. Underdispersion requires an appropriate capped/binomial or other justified model rather than forcing NB.

**S3 efficiency/compound challenger:** For points, explicit shot/FT attempt opportunities and conditional conversions from the same scenario. If no legitimate pregame shots and FT opportunities are available, leave this challenger **BLOCKED_BY_O_DATA**, not falsely replaced by made-shot independence. For threes, binomial made-threes conditional on scenario 3PA with `0 <= 3PM <= 3PA`. For rebounds and assists, prefer cap-aware opportunity-based conversions if the O/J scenario exposes defensible rebound/assist opportunities; otherwise use labeled exposure-conditional count laws with tail/support diagnostics. Never allow independent S sampling to violate J's team constraints.

**S4 expensive optional:** Existing NUTS/hierarchical artifacts and nonlinear distributional approaches remain **DEFERRED_RESEARCH** until convergence, posterior predictive checks, time provenance, compute budget and later matched out-of-sample evidence justify them. No automatic restart.

### Proposed deterministic interface

`fit(history_rows, *, asof_cutoff_utc, source_manifest, hyperparameters, seed) -> FittedSArtifact` must fail on missing/naive/source-late timestamps, duplicate player/game/stat keys, source digest mismatch, unseen target outcome, target realized minutes, stat mismatch, or non-monotone training chronology. The artifact stores exact training observation cutoff, model/feature versions, verified source hashes, parameter posterior summary, config hash and seed.

`predict(fitted, *, frozen_pregame, target_player_id, statistic, opportunities=None, scenario_ids=None, seed=...) -> Distribution` emits **one complete PMF** and the registered v2.0.0 envelope after G0. For S_ONLY, `O/G/J` lineage and hashes are null. For S_O, bind the exact O output and consume its pregame scenario/exposure law; report whether unconditional versus conditioned on participation. For S_O_J, J owns same-draw conversion and marginal extraction, while S only supplies conditional likelihood parameters/callable distributions, not a separately seeded player-level mixture.

The law must represent `p0`, the right tail and a quantifiable lost-mass upper bound. For analytic Poisson/NB, use stable log PMFs/recurrences and controlled tail truncation, retaining enough precision to satisfy v2 tolerances. For controlled MC, record scenario count, weight-based ESS, random seed, same-draw dependencies and finite-M uncertainty, not false independent-game replication. Provide explicit abstention reason codes for no lawful training pool, missing opportunity evidence, uncertain participation, source receipt failure, likelihood numerical instability or unsupported physical constraints.

## 3. Mandatory red/green test plan — **planned, not executed**

| Test family | Test and independent reference |
|---|---|
| Analytic counts | Independent Poisson PMF and tail-CDF values; Gamma–Poisson = NB with gamma shape/rate; NB2 mean and variance; log-gamma numerical stability; limiting dispersion cases |
| Distribution integrity | Integer/nonnegative unique support, probability in [0,1], exact mass normalization within candidate contract tolerance, certified right-tail bound <= 1e-8, zero mass present, no NaN or overflow, valid push on integer lines |
| Fit chronology | Duplicate game, wrong player/team, source hash tamper, future game, same-game cross-player target outcome, missing first-available timestamp, post-freeze revision, naïve timestamps, realized target-minute input |
| O conditioning | DNP/PLAYED_ZERO/PLAYED remain distinct; excluded player gives zero positive-count mass; uncertain P(played) retained; O/G hash and scenario IDs exactly match inputs; no re-generation of minutes |
| Statistic physics | 3PM <= 3PA for scenario-conditioned efficiency; 0 <= FTM <= FTA; points = 2×2PM+3×3PM+FTM in J; no unsupported independent points/combo construction |
| Simulation | Fixed seed + sorted canonical source yields byte-identical output; changing seed changes stochastic draws but not source manifest; no state-dependent random global calls |
| Abstention | Missing source, unsupported likelihood/opportunity, tail bound breach, unverified roster and unaccepted contract all return explicit blocked/abstain reason, not silent NaN/zero |
| Performance | Per-player throughput, large-roster batch runtime, numeric stability at high means/tails, memory and CPU recorded with exact environment and SHA; no retrospective forecast skill assertions |

**G1 readiness requirement:** Each enabled S family must have executable fit/predict, four-stat examples, independent mathematical references, v2 contract tests, zero/tail/temporal adversarial tests, actual callable O fixture conformance and hash-bound runtime receipts. Synthetic tests are *engineering* evidence only; P8/P9 historical scoring and P10 forward validation are later independent gates.

## 4. Gate and next bounded actions

1. **Release custodian / independent G0 reviewer:** challenge PR #157 at exact SHA `59d28dc23be97de2a6a82d22be8338151e31f5b6` and issue a genuinely independent pass/fail receipt, not an author assertion. Keep issue #149 open until the independent record is accepted.
2. **P0 contract owner:** record the immutable accepted G0 SHA/schema or reject and repair with another review. Do not silently rebase P2 against a moving G0.
3. **P1/O/J owners:** provide accepted frozen synthetic fixtures with proven timestamps, participation/minutes exposure law and shared scenario IDs, explicitly distinguishing original prospective from retrospectively reconstructed features.
4. **S owner, only after G0 PASS:** create an isolated `research/nba-p2-s-family-...` implementation branch from the *accepted* G0 source; write tests before code, adapt validated mathematical kernels without editing legacy engines, publish code/fixture SHA receipts, and prepare a genuine draft P2 PR.
5. **Independent P6:** adversarially audit exact P2 source/receipt before G1 acceptance. No retrospective predictive validation, Monte Carlo weight optimization, or production approval under P2.

### Current statuses

| Deliverable | Status |
|---|---|
| Frozen G0 contract inventory | inspected; current acceptance **BLOCKED** |
| Existing S-related code and reuse candidates | **AUDITED_READ_ONLY** |
| Mathematical S0/S1/S2/S3 research specifications | **DESIGN_ONLY** |
| S-family callable implementation | **NOT_STARTED_BY_GATE** |
| Mathematical/adversarial P2 executed tests | **NOT_STARTED_BY_GATE** |
| Isolated P2 implementation branch and actual draft P2 PR | **NOT_CREATED_BY_GATE** |
| Historical predictive validation or production release | **OUT_OF_SCOPE** |

**Rollback:** Close this audit-only draft/branch. No model, source collector, historical archive, P0 contracts, training pause, scheduler or production file was edited. This document is a prospective work inventory, not release-grade engineering evidence.
