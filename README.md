# Pick'em Auditor — GitHub is the authoritative project

Code, original research, immutable history, collection jobs, diagnostics, and design decisions live in this repository. Before interpreting any dated status or launching work, verify the current repository, schedules, source receipts, and training state.

## Start here — V2.5 governing documents (approved November 10, 2026)

**New engineering/research agents and ChatGPT Work sessions: read these documents first, in order.** Do not substitute an older chat answer or an out-of-date README section for the approved V2.5 specification.

| Read order | Document | Authority |
|---|---|---|
| 1 | **[README.md](README.md)** | Orientation, repository entrypoints, and legacy operational context |
| 2 | **[V2.5 Master Implementation Plan v1.1](docs/Pickem_Auditor_V2_5_Master_Implementation_Plan_v1_1_2026-11-10.md)** | **Governing architecture, scientific contracts, dependencies, experiment design, investment/release gates, and rollback** |
| 3 | **[V2.5 Next Workflow Launch Brief v1.1](docs/Pickem_Auditor_V2_5_Next_Workflow_Launch_Brief_v1_1_2026-11-10.md)** | Bounded immediate task, verified-at-the-time checkpoints, evidence recovery, and execution guardrails |
| 4 | **[AGENTS.md](AGENTS.md)** | Mandatory project agent startup order, instruction precedence, and engineering restrictions |

**Authority and updates:** The master plan is the authoritative reference for project design and permitted promotion. The launch brief determines the next working session's focus but must be reconciled against current GitHub/Deepnote/runtime evidence. `AGENTS.md` operationalizes this startup hierarchy. The [November 8 directional-accuracy baseline](docs/research/DIRECTIONAL_ACCURACY_RESEARCH_BASELINE_20261108.md) and earlier phase documents remain preserved research references. If a historical instruction conflicts with an explicitly approved V2.5 v1.1 amendment, follow V2.5, record the difference, and do not silently rewrite prior results. Material revisions require an ADR and versioned review.

**Current v1.1 engineering priorities (dated plan, not independently live-verified):** diagnose Phase 0R forecast-certification failures and quote rejections, capture immutable genuine pregame evidence in parallel, independently validate Phase 1.5 directional/error/power diagnostics, and maintain Phase 1 chronological baselines. Choose Phase 2/3 modeling only from the evidence-priority decision; advanced simulation is conditional. Frozen legacy 60/40/engines, NUTS artifacts, all-original receipts, morning settlement, and the comparison chart are retained. No automatic Tier 1/2 release, costly NUTS restart, or afternoon schedule activation.

**Historical material below:** The remainder of this README records previous implementations, methods, and operational behaviors. It is valuable for orientation but may describe earlier phases or statuses. Check the live code and current governed gates before treating a historical claim as production authority.

---

## User-approved directional research baseline (November 8, 2026)

For work involving forecasting, source feeds, Bayesian training, opportunity,
consensus weighting, calibration, ranking or settlement, consult
[the original directional-accuracy research contract](docs/research/DIRECTIONAL_ACCURACY_RESEARCH_BASELINE_20261108.md)
**after** the governing V2.5 master plan. This November 8 research remains a frozen
supporting baseline; V2.5 v1.1 controls when an approved amendment changes the roadmap.
The existing 60/40 model is the frozen validation control, not a calibrated
champion. [Phase 1](docs/PHASE1_DIRECTIONAL_VALIDATION.md) implements a
read-only, source-time and leak-aware scorecard; no model/Tier/deployment
change is authorized by it. The full original Deep Research report remains
in the November 8 research conversation. Future pull requests must use
[the research compliance checklist](.github/PULL_REQUEST_TEMPLATE.md).

## Architecture

| Location | Purpose |
|---|---|
| `main` | Engine A (statistical), Engine B (scouting), shared context, research gates, collectors, tests and workflows |
| `data/history-archive` | **Immutable, lossless copy** of the original 2026-10-26 ChatGPT Library history (7,905 files, 1,492 original pregame forecasts, original timings and source packets) |
| `data/shadow-calibration` | Authoritative evolving forecasts, verified settlement outcomes, cached usage and season records. Initialized from the immutable archive on the first run. |
| `data/nhl/games` on `main` | Verified NHL completed-game boxscores |
| `data/history_slate` on `main` | Daily timestamped, validated NBA/NHL/NFL source-observation snapshots, per sport and collection window |
| Actions artifacts | Per-run source coverage and execution receipts (temporary logs, **not** sole history storage) |

## Intended daily schedule (America/Toronto; cron currently paused)

**6:00 a.m. — Morning history and settlement.** Collect yesterday's completed-game evidence; refresh the source observations; restore the authoritative prior forecasts; settle past pregame forecasts using verified actual stats; persist updated history. **Do not automatically modify engine weights, distributions, coefficients, blend-fit files or tier thresholds.**

**4:00 p.m. — Pregame shadow evaluation.** Refresh the current pregame sports slate and public sportsbook quotes; run the existing engines and research checks where evidence permits; retain immutable forecast timestamps and append current projections. Incomplete lineups, scouting research or market data remain unranked and cannot be promoted to official Tier 1/2/3.

Manual collection entrypoint: `.github/workflows/pickem-daily.yml`. Automatic GitHub Actions cron is currently disabled. Choose Actions > Pickem morning and afternoon > Run workflow and select morning or afternoon. Pregame rechecks are separately manually dispatched in `.github/workflows/pregame-verification.yml`.

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


### Joint NHL model evaluation — first honest retrospective result

The source-verified 2018-10-20 historical cutoff benchmark scored **401**
post-cutoff appearances from the train-only NHL pilot subset at the **fixed,
non-sportsbook** 2.5-shots threshold. After correcting a single-season
identifiability problem and verifying four-chain convergence, the fully joint
Bayesian model scored Brier **0.190892** and log loss **0.566364**, versus a
same-record Gamma–Poisson control of Brier **0.189522** and log loss **0.560094**.
Both paired challenger-minus-control differences were slightly positive and
exploratory calendar-day bootstrap intervals straddled zero. **Do not promote**
the new model or change any Tier/weight based on eight holdout dates.

The accepted fit now requires not only zero divergent transitions and
population R-hat/ESS thresholds, but also convergence of the inferred
workload–shot-rate correlation and acceptable NUTS energy BFMI. Historical
source backfill remains independent and ongoing. See the
[complete dated evaluation and troubleshooting log](references/nhl_joint_evaluation_2018.md).

### October 28, 2026 independent empirical audit

[Real nine-market joint Bayesian versus Gamma–Poisson/Student-t holdouts](references/multisport_joint_audit_20261028.md)
found that the elaborate model now samples and scores correctly but is **not**
consistently better than the simple baseline. NHL goalie saves and NBA 3PM
were also trained and evaluated after historical collection/replay. All
research scores remain shadow-only; no tier or production model promotion.

## Multi-sport joint Bayesian shadow research

The NHL fully joint workload/scoring Bayesian pilot has been generalized into
[NHL/NBA/NFL independently sourced stat-specific population training](references/multisport_joint_population.md).
The new daily historical collector adds verified NHL hits, blocks and goalie saves,
NBA points/rebounds/assists/three-pointers/defensive stats/combos, and eligible
NFL passing, rushing and receiving volume plus signed yardage from actual
game snap exposure. Histories are immutable and isolated on
`data/bayesian-history`. A manual four-chain NUTS workflow compares each stat
on dated later completed player-games against a simpler pooled control.

**Experimental only:** no production picks, prices, rankings, engine weights,
quota consumption or Tier authorization are altered. Confirm live fetch receipts
and model holdouts before making any accuracy claims.

### Recent-season population acceleration

The [multi-season population workflow](references/recent_multiseason_bayesian_training.md) now independently collects NHL and NBA 2023-forward completed regular-season games while preserving the old 2018-forward source archive, and advances up to three fully completed nflverse seasons per execution. Manual research evaluation accepts a fixed source-verified training start, a recent-season lookback cap and a strict holdout end; uncollected or discontinuous historical periods block sampling. This does **not** change production rankings or assume the joint model is better.

### Verified pick ranking and research recovery

[October 28 ranking-repair audit](references/evidence_ranking_repair_20261028.md): source verification prioritizes numerically Tier-capable candidates ahead of model–market disagreements that cannot exceed Watchlist, early-season scouting can corroborate game history from the **official prior season**, and final pregame verification rechecks official status reports in the last eight minutes before puck drop. No numerical Tier is published without fresh, game-specific active identity, validated research and independent market/evidence gates; original forecasts remain immutable.


## Research-ranked candidates versus verified picks

Each afternoon and applicable pregame recheck now builds a separate `reports/research_ranked_board.json`. Its **Research Tier 2 / Research Tier 3** entries are source-forecast-linked numeric rankings **pending availability, causal research and refreshed market verification**. They are not approved picks, are not actionable without those checks, and cannot replace or silently populate `reports/verified_board.json`. The verified board remains the sole final Tier 1–3 publication source. See [research ranking recovery and verification options](references/research_ranked_recovery_20261028.md).

## Daily odds history and calibration (no PuckAPI)

The new `scripts/market_odds_archive.py` archives **only already-fetched**,
approved two-sided player-prop prices. It does not scrape websites or make
additional sportsbook/API requests. It stores immutable per-run market snapshots
on the private `data/shadow-calibration` branch alongside forecast history.

| Stage | Trigger | Output |
|---|---|---|
| Morning | Manual `pickem-daily.yml` / `morning` | Initial source receipt, optionally real odds |
| Afternoon | Manual `pickem-daily.yml` / `afternoon` | Exact bookmaker prices observed before forecasts, plus model-vs-market comparisons |
| Pregame | Manual `pregame-verification.yml` | Refreshed due-candidate prices and later line movement; reuse in Conditional Tier 3 |
| Next morning | Morning settlement | Read-only Brier calibration against settled player results |

**Morning costs:** the morning collector keeps `PICKEM_DISABLE_ODDS=1` by
default. An explicit `morning_odds=true` manual-dispatch input requests new
quota-guarded morning player-prop prices. Without that opt-in, morning writes
a `no_eligible_market_quotes` receipt, never fabricated lines.

**Evening limitations:** pregame observations are captured only for candidates
actually selected by the existing verification workflow, not necessarily every
player on the slate. The second pregame model check reuses the verified
refreshed quote batch rather than consuming another provider request.

**Immutability:** each capture uses
`data/market_odds_history/YYYY-MM-DD/{morning,afternoon,pregame}/<run-id>-<attempt>.json`.
An existing capture with different content is rejected. Full source metadata,
event/player identity, bookmaker, line, paired prices, quote-update time,
collector-observation time, and a SHA-256 digest are preserved. No snapshot
after a prediction can be used as that prediction's original market price.
Later pregame line movements are reported separately from model calibration.

Run an offline audit (requires restored forecast and market history):

```bash
python scripts/market_odds_archive.py evaluate --archive-root data/market_odds_history --forecasts data/prop_snapshots.jsonl --out reports/market_odds_evaluation.json
python -m unittest discover -s tests -p 'test_market_odds_archive.py' -v
```

The output is **research-only**: no automatic model weighting, tier assignment
or posterior promotion. Historical prices from unrecorded games cannot be
reconstructed. Missing/unpriced markets remain explicit. GitHub Actions cron
remains paused due to usage limits; these workflows currently require manual
dispatch (or an independently configured authorized runner).
