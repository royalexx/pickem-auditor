# Pick'em Auditor — GitHub is the authoritative project

Private code, original research and history, collection jobs and diagnostics live in this repository. The historical ChatGPT Tasks were disabled; GitHub Actions owns the daily schedules.

## Architecture

| Location | Purpose |
|---|---|
| `main` | Engine A (statistical), Engine B (scouting), shared context, research gates, collectors, tests and workflows |
| `data/history-archive` | **Immutable, lossless copy** of the original 2026-10-26 ChatGPT Library history (7,905 files, 1,492 original pregame forecasts, original timings and source packets) |
| `data/shadow-calibration` | Authoritative evolving forecasts, verified settlement outcomes, cached usage and season records. Initialized from the immutable archive on the first run. |
| `data/nhl/games` on `main` | Verified NHL completed-game boxscores |
| `data/history_slate` on `main` | Daily timestamped, validated NBA/NHL/NFL source-observation snapshots, per sport and collection window |
| Actions artifacts | Per-run source coverage and execution receipts (temporary logs, **not** sole history storage) |

## Daily schedule (America/Toronto)

**6:00 a.m. — Morning history and settlement.** Collect yesterday's completed-game evidence; refresh the source observations; restore the authoritative prior forecasts; settle past pregame forecasts using verified actual stats; persist updated history. **Do not automatically modify engine weights, distributions, coefficients, blend-fit files or tier thresholds.**

**4:00 p.m. — Pregame shadow evaluation.** Refresh the current pregame sports slate and public sportsbook quotes; run the existing engines and research checks where evidence permits; retain immutable forecast timestamps and append current projections. Incomplete lineups, scouting research or market data remain unranked and cannot be promoted to official Tier 1/2/3.

GitHub schedule: `.github/workflows/pickem-daily.yml`. The four UTC cron expressions are de-duplicated using local Toronto time across DST. For diagnostics, choose Actions > Pickem morning and afternoon > Run workflow and select morning or afternoon.

## Original history integrity

The original history was compressed losslessly and stored on `data/history-archive` as 90 binary Git blobs with an SHA-256 manifest (`archive/2026-10-26/manifest.json`). It is not regenerated, graded, or relabeled. `scripts/history_bootstrap.py` validates every segment and the full payload, then restores original `data/prop_snapshots.jsonl`, `data/usage`, `data/season` and archive metadata **only when destination files do not already exist**. `scripts/shadow_store.sh` subsequently loads/saves ongoing authoritative state through `data/shadow-calibration`.

The complete older replays and research packets remain available in the immutable archive, not in each ephemeral Actions workspace. Missing/unsupported actual outcomes must remain unresolved—no retrospective creation of pregame predictions.

## PropLine market data

The afternoon collector uses the bulk PropLine player-odds endpoint at `api.prop-line.com` (one request per NBA, NHL, or NFL sport rather than one per game). Authentication uses the `X-API-Key` header; keys are never embedded in stored source URLs. The automatic quota guard reads `X-Daily-Remaining` from the authenticated `/v1/sports` probe, then requires sufficient allowance to collect the three sports. The preflight's public `/v1/freshness` probe does not authenticate or fetch sportsbook prices. Only approved two-sided sportsbook markets are retained. PropLine currently documents NBA PRA but not separate PA, PR and RA; these combinations remain unpriced unless independently evidenced.

## Credential setup

PropLine key is **not stored in Git commits**. Add it to repository **Settings > Secrets and variables > Actions** as `PROPLINE_API_KEY`. Only GitHub's encrypted secret mechanism should supply the key to the 4 p.m. job. A private repository alone does not make plaintext API keys in commits safe.

The GitHub connector currently cannot administer Actions secrets; the repository owner must save this one secret through GitHub. Without it, a full priced pregame ranking is blocked and the workflow reports `PROPLINE_API_KEY_SECRET_MISSING`.

## Validation and grading

- Live historical NHL, NBA and NFL source fetches have run successfully from GitHub.
- Offline CI includes source-connectivity classification, engine A/B contracts, source receipts, archive checksum and bootstrap/idempotence tests.
- A green step alone does **not** certify an operational cycle: inspect the job conclusion **and the run receipt** for feeds, forecasts, settlement and persistence. Failed steps are explicit.
- All adjustments to weights/calibration remain manual and evidence-gated.
- No Underdog access, payouts, entry slips, or bets.

Older instructions referencing only the original NHL-only bootstrap are superseded by this document; that workflow is now manual-only.


## Verified source research and pregame decisions

The afternoon workflow now produces source research, a capped verification
queue, reviewer-ready task templates, separate forecast-linked decision
receipts and a verified-only board. A second GitHub Action checks approaching
games 25–55 minutes before kickoff. Strict, current, identity-matched
evidence and reliable statistical/scouting engines are required; qualifying
subjects may now be examined by a **live, deterministic primary-source
reviewer** (clearly labeled as machine review) or a human source reviewer.
No original forecasts or calibration weights are rewritten.
PropLine credits are conserved until a due candidate passes either review.

See [Evidence-gated pick verification](references/pick_verification.md) for
the exact review submission format, workflow stages and failure policy.


### Autonomous source investigation

A machine-readable investigator now independently checks live official
league game logs against collector history, preserves both supporting
and contrary observations, and discovers named ESPN reporting for source
review. It runs automatically after the afternoon priority queue and
during due-game pregame checks. It never calls PropLine or invents
research attestation. See
[autonomous investigator sources and limitations](references/autonomous_investigator.md).

### Mechanism quality rather than event counts

Verified picks now use [source-quality mechanism grading](references/mechanism_quality.md) instead of legacy event counts for Tier eligibility. A machine-corroborated workload change remains embedded in Engine B and is capped at Tier 3; higher evidence ceilings require genuinely independent, quantified and counterchecked causal research. The original statistical probabilities and thresholds are unchanged.

### Morning schedule recovery

Morning settlement now has backup Toronto-local cron slots and an immutable
completion marker stored in the authoritative data branch. This handles
missed scheduled events without repeating a successfully settled day.
See [morning recovery and verification](references/morning_scheduler.md).


## Phase 1: Bayesian Engine A shadow evaluation

A historical-only, hierarchical **empirical-Bayes** model (`history-bayes-v1`) now runs in shadow after a successful afternoon snapshot. It learns conservative sport/stat peer priors from *other* verified player histories, uses Gamma–Poisson, negative-binomial quadrature and Student-t predictive distributions, and stores separate append-only pregame predictions in `data/bayesian_shadow/` on `data/shadow-calibration`.

**Production remains history-v5.** No Bayesian output alters Engine A/B blending, Tier ranks, current research verification, historical forecasts or weights. Missing data are marked unavailable, not filled. Source timestamps, own source checksums and distinct peer identities are required. This is empirical Bayes conditional on fitted group hyperparameters, not full joint Bayesian inference and not an accuracy claim.

See [the Bayesian Engine A design and validation boundary](references/bayesian_engine_a.md).


## Phase 2: Bayesian workload and conversion shadow model

Phase 2 adds `usage-bayes-v1`, an **empirical-Bayes** Engine B challenger that
models positive-game workload (NBA minutes, NHL ice minutes, NFL snaps) with a
log-workload Student-t predictive distribution and conditions observed
production on workload with Bayesian rate/conversion posteriors. The model
integrates workload uncertainty deterministically, preserves paired historical
observations, and separates over/under/push. Results append to
`data/bayesian_b_shadow/YYYY-MM-DD.jsonl` on the persistent calibration branch.

It **does not replace** production `scouting-v7` or alter ranking, context,
market retrieval, the 70/30 diagnostic or calibrated blend configurations.
Missing source histories or small peer cohorts remain unavailable. Read
[Phase 2 model notes](references/bayesian_engine_b.md) for approximations and
validation requirements.


## Phase 3: posterior predictive Monte Carlo (shadow-only)

`posterior-mc-v1` adds reproducible, adaptive posterior predictive
simulation **of** the two Bayesian challenger engines. Simulations draw
posterior latent rates, workload and variances, while integrating next-game
observation noise analytically to reduce numerical error. This produces
separate Over/Under/Push probabilities, Monte Carlo precision intervals and
comparisons to the original analytic Bayesian forecasts. It does **not**
produce a third independent vote or authorize Tier ranking.

The afternoon workflow stores immutable sidecars under
`data/posterior_mc/` in the `data/shadow-calibration` branch, and the
morning workflow generates `reports/posterior_mc_audit.json` from
settled outcomes. This audit summarizes three-outcome log loss and
multiclass Brier for legacy, Bayesian analytic and Monte Carlo predictions.
No automatic calibration weights or model promotion are performed.

See [the Phase 3 methodology, safeguards and testing instructions](references/posterior_mc.md).


## Phase 4: predictive validation, not production promotion

Phase 4 introduces `scripts/phase4_validation.py`, a **read-only** audit
comparing original `history-v5`/ `scouting-v7` forecasts, Bayesian
analytic shadow forecasts, posterior Monte Carlo shadow forecasts and
a separately identified **diagnostic-only** 70/30 combination.

The morning workflow runs the audit only after successful verified result
settlement, and writes `reports/phase4_validation.json` to the GitHub
Actions artifacts. It evaluates chronologically separated pregame holdouts,
proper three-way Brier and log loss, matched-cohort date-cluster uncertainty,
walk-forward *non-deployed* temperature calibration, confidence reliability,
sport/stat/tier/side slices and same-line closing-market diagnostics.
Original historical archive snapshots are scored as originally recorded;
missing Bayesian/MC pregame forecasts are never backfilled from later games.

This feature **does not** update any deployed probability weights, ranking,
research gate, or Tier rule. Numerical sample size / predictive validity
are surfaced honestly; underpowered results do not authorize changes.
See [Phase 4 statistical guardrails](references/phase4_validation.md).

 
## Next generation: fully joint NHL Bayesian pilot (isolated shadow)
 
The new `data/bayesian-history` branch stores source-verified, compressed official
NHL game histories with complete player shots and ice-time observations,
resumable by calendar day. A separate GitHub Actions backfill starts when
the `nhl-bayesian-history.yml` workflow is merged and continues twice daily.
It uses **zero PropLine/odds credits** and never replaces existing collector
snapshots.
 
The experimental `nhl-joint-bayes-v1` model jointly samples unknown population
means, player-level correlated workload and shot-rate effects, season/opponent
effects and negative-binomial dispersion. A manual offline four-chain NUTS
workflow produces a posterior artifact, diagnostic manifest and strictly
**post-cutoff** historical test against a Gamma–Poisson baseline using the
fixed research line of **2.5 shots** (not a fabricated sportsbook line).
No results are publication-eligible or permitted to enter Tier ranking.
 
[Source, sampling, training and guardrails](references/joint_nhl_bayes.md).
