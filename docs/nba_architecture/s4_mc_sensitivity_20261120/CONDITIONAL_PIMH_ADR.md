# S4/J Step 1 numerical remediation: period-bridge particle MH

**Scope:** research-only, original PR193 and PR195 fully preserved.
Branch `research/nba-s4-conditional-pimh-20261120` is a versioned
candidate to repair the deterministic finite-4096-tries rejection failure.
The earlier `s4_mc_sensitivity_20261120/PROTOCOL.md` and its 64/256/1024
receipts are not overwritten. This is a *new versioned protocol*, not a
retroactive modification to the failed trial.

## What probability measure is intended?

For a fixed S4/J draw `F=(G,O,rates,pace,event parameters)`, let
`X=(X_0,...,X_K)` be the complete path of regulation and K overtime
segments under the original chronological `residual_events_v1` law.
The original pipeline samples `K` in F and generates event paths until

```
A_0 = {score is tied at the end of regulation}       if K>0
    = {score is not tied at regulation}               if K=0
A_j = {score is tied at OT j}                        if 1<=j<K
A_K = {score is not tied at OT K}                    if K>=1
```

holds. The desired event law is **P(X | F, A_0,...,A_K)**, not a forced
endgame score, a cut-and-paste possession repair, a point-mass tie, a
source-backed assertion of player participation, or a new fitted forecast.
The old single whole-path rejection routine is mathematically correct
when it terminates, but its workload grows roughly like the inverse
probability of simultaneous tie constraints, and failed runs cannot
discard difficult scenarios.

## Unmodified transition and checkpoint equivalence

`conditional_periods_v1.py` implements period checkpoints by copying
the original kernel's minute clock, Gamma possession waiting time,
shot selection, shooting probabilities, scoring, rebounds, fouls,
on-court roster, post-miss 14-second reset and period-opening possession
entitlement. The only new boundaries are the original quarter/OT ends.

For each fixed scenario and original `event-path:i` RNG, the
unconditional period-transition simulator must match **the original
path ledger byte-for-byte on all accepted paths and up to the original
early-rejection prefix on rejected paths**. This is tested before
any inference. Every final path is independently processed by the
original `residual_audit_v1.audit_path`.

## Bootstrap particle filter, unbiased normalizer

At stage 0 generate N independent regulation transitions. Their
indicator weights are `w_i=1[A_0]`. At subsequent stages first
multinomially resample from survivors, then generate **unmodified**
one-period OT transitions, and set `w_i=1[A_j]`. If a stage has zero
survivors, the proposal has zero evidence. Otherwise the bootstrap
particle filter supplies a complete original-law chronological path
and the nonnegative estimate

`Zhat = product_(j=0)^K [ (1/N) sum_(i=1)^N w_(j,i) ]`.

The standard Feynman–Kac particle filter identity gives
`E[Zhat | F] = P(A_0,...,A_K | F)`. The normalizer estimate and
ancestral path must stay on the same proposal receipt. Retrying a
zero-particle filter and ignoring its failed `Zhat=0` is prohibited.

A raw finite-N bootstrap particle trajectory is **NOT EXACTLY** a
draw from `P(X|F,A)`; finite-N particle genealogies and resampling
change it. Do not make that false equivalence.

## Particle independent Metropolis–Hastings

Independently propose a complete bootstrap filter and its `Zhat`.
When the current retained filter has `Zhat>0`, accept the new
filter with probability `min(1,Zhat_new/Zhat_current)` and otherwise
retain the old filter and its path. The extended-space target
`pi(du) proportional to q(du)*Zhat(u)` has event-path marginal
exactly `P(X|F,A)`. Thus the PIMH kernel is **exact-invariant**
for the ORIGINAL conditional chronological event law.

**Exact invariant distribution is not exact finite-chain stationarity.**
A finite PIMH run has burn-in/autocorrelation risk. Scientific
certification requires independent chains, predeclared warm-up,
between-chain rank/split-Rhat, effective sample size, evidence
log-weight stability, zero-particle frequency, high-score tail
stability and conservative numerical error accounting. A chain
with a few accepted proposals is an engineering smoke test, not
proof of convergence.

The fallback for 0/1 OT remains the untouched original full-path
rejection algorithm and is conditionally exact under its
4096-path execution budget. Higher OT uses the new PIMH proposal.
A multi-OT sample is never advertised as iid; empirical
count PMFs and DKW iid bounds may not be certified while finite
MCMC convergence remains unresolved. The original source-listed
population, fixed G/O/rates, 14 named players, identities and
source hashes are unchanged.

## Required independent gates

1. Exact transition parity and genuine zero-minute/five-on-court
   conservation without final-minute leakage.
2. Unbiased normalizer tests against enumerated toy models,
   distinguishing plain sequential conditioning from full-event
   conditioning.
3. End-to-end acceptance of former failure scenario 297 and 4OT
   scenario 6711 with full audit.
4. Independent replicated PIMH chain diagnostics and no
   cherry-picked random seed or silently omitted scenario.
5. Numerical convergence/tail precision at 64/256/1024/5000/20000
   with create-only SHA receipts, strictly increasing stage counts
   and no mislabeled DKW bands for non-iid samples.
6. Independent P6 review and explicit authorization. None of this
   changes G1/G2, P8, C outcomes or release gates.

**Stop conditions:** an unrecognized original-kernel drift, failed
physical ledger audit, degenerate PIMH weight, burn-in/mixing
uncertainty, missing source SHA, run time/resource budget, or
an unverified participation condition must produce a blocked
or research-only result, not a certified probability.
