# Cloud Bayesian sequential updates (Pick'em Auditor)

## Safety boundary

This system does NOT mutate or sample the frozen hierarchical PyMC/NUTS
posterior. It cannot update the existing NUTS player/team/season/opponent
latent distribution without a compatible posterior transition model and an
out-of-sample validation process. It also does NOT promote new models, alter
Engine A/B production rankings, invoke the Dell, use a self-hosted runner, or
modify any of the frozen 31-market campaign's manifests or source snapshots.

The implementation is an isolated sequential Bayesian *challenger*:
- Source-verified player-game count-rate Gamma-Poisson posterior with an
  exposed workload and a fixed weak prior; it is a reduced, not a joint
  hierarchical NUTS, model.
- Separate discrete Bayesian logit calibration posteriors for empirical
  Bayesian A and B source-verified pregame forecasts.
- A prospective monitoring process with Brier/log-loss and a date-cluster
  bootstrap. All inferential results remain research-only.

## One-time historical bootstrap

The first morning update loads the source-verifiable population warehouse
from a SHA-pinned Git commit on branch data/bayesian-history. It does NOT
recollect historic games or write into that branch. It uses at most the last
520 days strictly before the earliest new live game date to avoid future
information. Observations older than 120 days have likelihood power 0.15,
recent observations power 1.0, to reduce stale-player-role dominance.

The frozen historical source commit, archive digest, and source cutoff are
saved in the online state. Both rate and original bootstrap state are saved
so Monday's replay does not need to download the old warehouse again.

## Automatic morning update

After successful completed-game verification and immutable Git publication,
the notebook executes:

    python scripts/cloud_bayes_incremental.py update --as-of YYYY-MM-DD \
      --report reports/cloud_bayes_monitor.json

The as-of date is the CURRENT Toronto date. All game dates consumed are
strictly earlier. Updates consume only morning bundles on the append-only
data/live-observations branch. Missing or partially verified sources block
the update; no missing stats or workload is silently filled as zero.

The cloud state is itself a deterministic compressed Git file under
data/online_bayes/states/YYYY-MM-DD-SHA256.json.gz. Duplicate daily runs
are idempotent. A conflicting same-date state is an error, not an overwrite.

For rates:
  alpha_new = alpha_old + observed_count
  beta_new = beta_old + observed_minutes_or_snaps

For historical bootstrap days with a power prior, alpha/beta receive a
0.15 likelihood contribution from older source-verified observations.
Posterior predictive counts integrate the Gamma rate analytically into a
negative binomial probability, with separate push mass for integer lines.
No other player stat market is assumed from a missing source.

For probability calibration, each unique pregame player/event/stat is
represented at most once, regardless of multiple available lines or
over/under quotes. The likelihood is Bernoulli on non-push outcomes, with
proper normalization for push mass. A fixed grid approximates the posterior
over a log-odds shift:
  logit(p_corrected) = logit(p_frozen) + shift

The entire calendar date is evaluated using the prior day's posterior
BEFORE any observations from that date update its likelihood, eliminating
within-slate hindsight. Original pregame shadow forecasts remain immutable.

## Afternoon run

The notebook invokes:

    python scripts/cloud_bayes_incremental.py shadow \
      --date YYYY-MM-DD --root . \
      --out data/online_bayes_shadow/YYYY-MM-DD.jsonl

The latest verified online posterior must be strictly older than the game
date. The resulting sidecar includes online-updated Bayesian A, Bayesian B,
and an independent player-count Gamma-Poisson forecast when sufficient
source samples and a verified pregame workload exist. Otherwise it
abstains with a named reason. Historical and online input dates are
recorded in the sidecar. No base model weights, tiers or rankings change.

The afternoon Git evidence bundle also freezes this online sidecar so
tomorrow morning can score the ACTUAL online probabilities rather than
recompute them after the games.

## Periodic refitting / drift monitoring

Every Monday morning, the cloud runner replays all verified, immutable
daily evidence chronologically from the SHA-frozen bootstrap rates. It
requires the rebuilt posterior state to equal the incremental state.
This is a full replay/refit of the lightweight online Bayesian correction,
NOT a full NUTS refit.

The 30-day monitor uses paired, truly prospective Brier and log loss
versus the original empirical-Bayes forecasts. It date-cluster bootstraps
the paired Brier gain (400 draws). A challenger is only flagged
research-qualified when 200+ scored events spanning at least 20 dates
show a strictly positive 5th-percentile gain AND improved log loss.
This is NOT production authorization. No automatic Tier 1/2 promotions.

A fresh FULL hierarchical PyMC/NUTS fit is a separate, explicitly approved
periodic operation to perform on suitable non-Dell infrastructure using the
assembled historical + new live pool. The free Deepnote 2 vCPU/5 GiB
environment is reserved for collection and lightweight inference, not
assumed capable of training all 31 complex NUTS scopes. A new NUTS
posterior cannot be substituted until its convergence diagnostics,
compatible release artifact, and chronological out-of-sample validation
are available. Existing frozen Dell sampling remains untouched.

## Reproducibility and tests

Cloud notebook source is retained in the repository under
notebooks/deepnote_daily_cloud_inference.ipynb. The live Deepnote notebook
is in project 9cc31536-93be-44db-bdeb-06fba3f61410.

Run offline tests without credentials or a running Dell:

    python -m unittest discover -s tests -p test_cloud_bayes_incremental.py -v

The tests validate exact count-rate updates, normalized predictive
probabilities, historical no-future-data seeding, one observation per
player/event/stat, prospective day-level updates, immutable Git state,
weekly full replay, no production promotion, and frozen sidecars.

## Operational caveat

The private Deepnote GITHUB_TOKEN (Contents read/write) and
PROPLINE_API_KEY need to be installed via encrypted Environment variables.
Until that is done and the complete afternoon->morning integration has been
executed and its Git receipt inspected, no claim of live cloud posterior
updating is warranted. Daily ChatGPT schedules remain paused intentionally.
