# One full NFL read-aware training run

This configuration trains **one targets model** on all eligible 2024 and 2025
regular-season training games, with 2026 held out until 2026-10-30 12:00 UTC.
There is no 80-game limit, preliminary baseline fit or three-model comparison.
The model retains separate player, own-team, opponent and season effects and
now includes both offensive and defensive read covariates.

Run in the existing VS Code PowerShell terminal:

```powershell
git pull --ff-only origin codex/nfl-context-local-pilot
python scripts/nfl_context_campaign.py run --config config/nfl_context_reads_full.json --run-dir reports/nfl_reads_full_v1
```

Use the existing numerical environment that completed NHL training. No new
dependency is required beyond `requirements-nfl-context.txt`. UTF-8 and quiet
sampling are automatic. Four chains run with two workers and one BLAS thread
per process. Collection uses public nflverse data, not an odds API or Actions.
Full training can be much slower than the small NHL/synthetic pilots; heartbeat
logs report each running stage. Repeating the same command verifies and resumes
completed stages. Keep the earlier pilot directories intact.

## Retry after the v1 workload convergence failure

The first real fit completed but failed the unchanged R-hat/bulk-ESS gates only
for position-level workload means (max R-hat 1.01494, min bulk ESS 317.45).
The full diagnostic packet shows all read coefficients passing; duplicate
observed-mask columns are retained to preserve the original regression prior.

Model v3 changes sampling coordinates, not the probability model. For players
with at least five training observations, sample the total workload intercept
as Normal(position mean, player workload SD). Recover its standardized workload
coordinate and combine it with the independent production coordinate through the
same LKJ Cholesky factor. Sparse players retain the original noncentered form.
This preserves the joint correlated player prior, position priors, likelihood,
all read features and forecasting equations. The training-only threshold affects
computation, not the prior distribution. It reduces the dependency between the
workload position mean and well-observed player deviations.

A four-chain check on the exact 10,082-row/637-player frozen design used 500
tuning and 500 retained draws per chain. Workload position means improved to
max R-hat 1.00432 and min bulk ESS 1,439.53, versus 1.01494/317.45 in the original
1,500-draw fit. However, the shorter fit **does not pass overall diagnostics**:
max R-hat 1.01877 (team scale), min bulk ESS 330.30, zero divergences/depth hits,
min BFMI 0.8469. It is evidence for the targeted workload change, not a fully
converged replacement posterior. The full-budget v3 run still needs verification.
The receipt is `validation/nfl_workload_reparameterization_2026-10-31.json`.

Use a new run identity and reuse verified frozen inputs; do not delete v1:

```powershell
git pull --ff-only origin codex/nfl-context-local-pilot
python scripts/nfl_context_campaign.py run --config config/nfl_context_reads_full.json --run-dir reports/nfl_reads_full_v2 --reuse-frozen-from reports/nfl_reads_full_v1
```

This requires the same configuration, verifies every original frozen input,
copies and rechecks those files, and records their origin. It does not recollect
data or copy the failed posterior/status. A new fit and holdout scoring run under
the new code identity. The original 1,500 tuning/1,500 retained draws, four chains,
two workers and strict diagnostics remain in force. Convergence is still checked
on the actual new fit. An existing project-local PyTensor cache environment
setting can remain in the terminal.

ASCII `NUTS_PROGRESS` lines identify each chain's warmup/posterior phase every
250 iterations and on completion, in `fit_context.log`. In another terminal:

```powershell
Get-Content reports/nfl_reads_full_v2/fit_context.log -Tail 15 -Wait
```

## Reused read workflow

The implementation imports `READ_MAP`, `BUCKETS`, `bucket()` and
`build_profiles()` from `nfl_season_store.py` rather than creating a different
classification. The existing mapping is:

| FTN code | Bucket |
| --- | --- |
| 0 | First read |
| 1 | Second read |
| 2 | Later read |
| CHK | Checkdown |
| DES | Designed |
| SD | Scramble drill |
| Missing/unrecognized | Unknown |

Designed plays remain separate from first reads. Labels describe the read
actually targeted, not the intended receiver on every route or a complete QB
progression. Sacks do not count as throws; nullified plays and two-point attempts
are excluded. Game/play IDs join FTN observations exactly. Conflicting duplicate
charting fails validation. FTN snapshots are archived separately with hashes and
attribution; no synthetic charting fills a source gap.

Offense covariates include QB bucket distributions, receiver shares within each
bucket and targetable share per throw. The upcoming defense is removed from
these offensive baselines. Defense covariates reuse the existing comparison of
each QB's throws against that defense with the same QB's other opponents, using
matching comparison populations. Unknown read mass is preserved in the matched
mixture. Opponent-adjusted ratios and the resulting receiver opportunity share
enter the fitted regression as covariates. No extra read multiplier is applied
to the posterior forecast or elsewhere in production.

Historical starter announcements were not archived, so the batch model does not
fabricate confirmed-QB facts or call a live scenario with false confirmations.
It uses a disclosed mixture of passers from the offense's three preceding
available games. Tonight's actual QB is never looked up to construct a historical
pregame feature. This is a pregame proxy, not a proven starter projection. Live
integration still needs verified passer/lineup evidence and a consistent feature
contract. Passer changes, feature measurement uncertainty and role shifts remain
important model risks; feature values are not sampled as a full causal scenario.

## Historical availability and missingness

Every profile is rebuilt from earlier, available games in that season. No
current/future play, outcome or chart label is eligible. Historical FTN publication
times are not available in these snapshots: the declared retrospective assumption
is each game's statistical availability (kickoff +18h), plus a configurable
seven-day charting delay. This conservative delay does **not** certify publication
time or eliminate annotation revision bias. Actual retrieval times are recorded.

Missing read covariates remain explicit `None` with per-feature observed masks.
Only training observations determine imputation centers and scales. A missing
read is never interpreted as zero first reads, zero checkdowns or an average
defense. The configured preflight requires offensive and defensive read history
for at least 50% of training and holdout observations; it stops before sampling
if this coverage is unavailable rather than silently fitting the old model.
Rows with partial history remain in the cohort, with masks and reliability flags.

The previous descriptive reliability flags are retained: thin independent
passer/receiver history, fewer than three passer games, read coverage below 80%,
thin defensive comparisons and sparse bucket counts. These are disclosed research
limitations, not an automatic live Tier or an unsupported defensive quality grade.

## Outputs

- `frozen/preflight.json`: full cohort sizes, offensive/defensive read coverage,
  joined-source diagnostics and the single model selected for fitting.
- `context/posterior.nc` and `context/manifest.json`: one fitted model and strict
  four-chain, all-effect R-hat/ESS/energy/divergence/tree-depth diagnostics.
- `context/holdout_predictions.json` and `comparison.json`: holdout scores for
  this one model. The name `comparison.json` is retained for packet compatibility;
  this configuration fits no comparison model.
- `review_packet.zip`: designs, frozen team/player/read data, training/holdout
  rows, coverage, code/source receipts, diagnostics and predictions. Large raw
  sources/posteriors stay local with hashes.

The 5.5-target threshold is for research; historical sportsbook quotes are not
included. Source joins, unseen entities and excluded records are reported.
Convergence does not establish calibration, predictive superiority or a market
edge, and this run does not change rankings or Engine A/B weights. The stored
posterior is frozen before the holdout; earlier completed holdout games may
update later pregame features without retraining it.

## Delivery verification

Live source collection and exact FTN/PBP joins were checked for 2024, 2025 and
2026. The full preflight produced 10,082 training observations, 544 games, 637
players and 32 teams. Both offensive and defensive read history were available
for 89.2% of training rows and 70.8% of scored holdout rows under the declared
seven-day lag. It scheduled only `context` for fitting. No real full-history fit
was run in the workspace; that is the local job above.

A synthetic single-model end-to-end check used 512 training observations over
two seasons and 256 held-out observations. Four chains with 1,000 warmup and
1,000 retained draws passed all stochastic/derived-effect gates: maximum R-hat
1.00481, minimum bulk ESS 1,388.66, minimum tail ESS 1,755.10, no divergences or
max-depth hits, and minimum BFMI 0.8819. The count intervals over-covered in that
small simulation; it is execution/convergence evidence, not real NFL calibration.
The machine-readable receipt is
`validation/nfl_reads_full_verification_2026-10-30.json`.

If a completed fit fails strict diagnostics, retain the saved posterior and run
the read-only audit before spending another full fit:

```powershell
python scripts/nfl_context_diagnostics.py --run-dir reports/nfl_reads_full_v1
```

This rechecks the existing posterior and identifies worst features/player effects,
chain differences, energy behavior and design redundancy. It writes
`convergence_audit.json` and `convergence_diagnostics.zip` beside the saved fit;
it does not sample, modify the model/status, waive a gate or change frozen inputs.
The ZIP includes the design and receipts, not the large posterior. It can be
uploaded for diagnosis. No campaign restart or data recollection is required.

## Completed full posterior verification

The full v2 run's uploaded posterior was independently verified, including its
SHA-256, four chains/6,000 retained draws, and every strict sampling diagnostic.
Maximum R-hat is 1.00549, minimum bulk/tail ESS 631.23/771.41, BFMI 0.7568,
with zero divergences or maximum-depth hits. All 1,738 stored holdout forecasts
replay to floating-point precision and all predictive intervals match.
The receipt is `validation/nfl_targets_posterior_acceptance_2026-10-31.json`.

Pregame inference now accepts a missing or null `target`. It returns `target`
and `log_predictive_density` as null until an outcome is observed. Probabilities,
expected counts/snaps and predictive intervals are independent of that outcome.
Invalid observed counts are rejected. The training graph, fitted priors,
likelihood, cache and model version are unchanged; the existing posterior works
without retraining. Historical scoring with observed counts is unchanged.

On the same 1,738 rows/107 games at 5.5 targets, Brier scores are 0.12939 for
the context model, 0.13980 for a frozen player-mean Poisson control and 0.13599
for a frozen position-shrunk Gamma-Poisson control. Paired game-bootstrap 95%
intervals for the context-minus-control Brier differences are
[-0.01396, -0.00694] and [-0.00966, -0.00361], respectively. These are simple
training-only controls, not the previous hierarchical model or a read ablation.
The controls retain their frozen training histories; the context model's pregame
covariates can use earlier available holdout games. This comparison does not
separate read effects from the value of updated recent-game context.

The verified posterior is ready for prospective adapter testing. Live feature,
identity, roster and QB checks remain required; this acceptance does not activate
live rankings or modify the A/B blend. The fixed research threshold does not
establish accuracy at actual market lines, and the historical charting lag
assumption remains a limitation.
