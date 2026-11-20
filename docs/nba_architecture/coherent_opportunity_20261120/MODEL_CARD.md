# Coherent opportunity S4/J — bounded research family

Authority: PA-V25-MASTER-2026-11-09 / v1.1. The user approved changing the
statistical construction while retaining strict physical accounting. This is
a new shadow family, not a replacement or retroactive repair of S1 forecasts.
The original protocol and its pre-fit addendum are immutable inputs.

## Statistical construction

For each supported player, fit working Gamma-Poisson components for two-point
attempts, three-point attempts, free-throw attempts and turnovers. The Gamma
parameters use shape/rate units. Own-player updates add observed counts and
reported minutes. Leave-player-out same-role peer rates supply a fixed
180-minute empirical-Bayes prior, with shape `.5 + 180 * peer_rate` and rate
`181`. Residual groups use Gamma(.5,1) plus their observed counts/minutes.
Observed zero attempts remain zero observations; they are not missing records
or structural impossibility. Proper priors remain explicit.

Two-point, three-point and free-throw conversions use Beta priors with
`.5 + 40 * peer_make_proportion` and `.5 + 40 * peer_miss_proportion`, updated
with own makes and misses. Residual conversions use Beta(.5,.5) plus pooled
makes/misses. Peer conversion denominators must be observed and positive.
Priors are plug-in role summaries, not a posterior over uncertain role-level
hyperparameters. All 698 original rows remain accounted for; the same 456
ordinary records supply updates. No new source population is substituted.

Draw these opportunity rates and probabilities once per scenario. Let
`a2,a3,f,t` be attempt/turnover rates and `p2,p3,pf` conversion probabilities:

```
made_three_intensity = a3 * p3
non_three_point_intensity = 2*a2*p2 + f*pf
point_intensity = 3*made_three_intensity + non_three_point_intensity
free_throw_point_share = f*pf / non_three_point_intensity
```

These derived quantities adapt to the unchanged audited event path. Its shot
selector recovers weights `a3`, `a2`, `f/(2+q)` and `t`, where `q` is the
inherited observed two/three-free-throw-series-length proxy. A relative
roundtrip error above 1e-10 rejects execution with the numeric draw retained.
No floor, clipping, independent points/threes draw or rate-vector rejection
is used to repair a contradiction.

The posterior identities are exact for the stated conditional aggregate
working likelihoods. In the chronological game kernel these intensities become
relative opportunity weights. They are **not** unconstrained expected J counts
per minute, and this modular fit is **not** a posterior under the full clock,
rotation, foul and overtime-conditioned event-process likelihood.

## Shared predictive law

G and O are drawn once; all named statistics and combos use the same event
path. Points arise only from made shots/free throws, threes from made threes,
assists from eligible made field goals and rebounds from eligible misses.
The original hard event auditor, lineup construction and physical tolerances
are unchanged. Score, actor, clock, missed-shot, FT-series and team-minute
constraints remain strict.

S4 is the marginal projection of this J law. It is not an independent vote or
an S1 marginal forced into a different joint distribution. Public S4 and J
queries use the same immutable scenario bank. Exact same-bank equality is a
software/measure identity, not evidence of predictive accuracy or convergence.

Operational estimates use the preregistered 64 scenarios and seed20261120.
Every event-path proposal is retained as deterministic gzip JSON, with
compressed and uncompressed hashes and byte-domain sizes. All G/O/parameters
stay fixed across OT rejections. Event/path/byte-cap exhaustion fails the
whole batch and prevents successful-subset forecasts. Partial fixed draws,
failed event paths and missing raw bytes on resource rejection are explicitly
identified. No favorable seed or successful rerun is selected.

PMF/CDF/OUP results are Monte Carlo estimates. Their pointwise binomial
intervals assume iid ideal-kernel draws; finite execution and selection of
completed runs do not establish that coverage. OUP cell intervals use a
three-cell multiplicity adjustment; they are not simultaneous across players,
statistics or arbitrary queried lines. Zero hits do not establish population
zero probability. The population law is not truncated or renormalized to the
largest observed count.

## Conditioning, limits and gates

The new law conditions on **all 14 supported named players participating**.
It does not identify those participation probabilities or legal eligibility.
The same 35 candidates, 140 primitive requests and 280 primitive/combo requests
remain; unsupported players abstain. Exact older abstention reasons are
retained. Anonymous residual actors are model slots, not invented identities
or proof of a complete later roster. A future evaluation must verify the
matching conditioning event and retain DNP/conditioning mismatches unscored.

The unupdated Beta(.5,49.5) zero-state prior, homogeneous extrapolation below
30 seconds, rate/minute factorization, pace proxy, circular minute copula,
restricted foul mechanisms and instant reported-clock rebound approximation
remain hypotheses. New-family zero-weight sensitivity is **pending**; the
earlier S1 grid is not validation of this different family.

The old S1 controls and their mathematical incompatibility witnesses remain
unchanged. Their comparison with S4 reports mean, CDF and partition-TV drift
with MC and numerical-reference limits; it is not an exact-matching gate for
this new family. No existing legacy gate is relabeled PASS. Predictive
accuracy, valid historical replay, proper target scoring, scientific G1/G2
acceptance and release remain separate requirements. No historical replacement
fit, holdout scoring/decompression, ensemble-weight optimization, NUTS restart,
schedule change, merge, deployment or Tier promotion is performed here.

Rollback is to stop the new explicit research CLI; all previous source,
forecast, posterior, engine and accounting implementations remain untouched.
