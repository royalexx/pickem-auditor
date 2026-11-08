# Pick'em Auditor operating instructions

## User-approved directional-accuracy research baseline (mandatory)

**Before making ANY future forecasting, data, lineup, Bayesian training, ranking,
probability, calibration, settlement, or validation changes, read and apply
docs/research/DIRECTIONAL_ACCURACY_RESEARCH_BASELINE_20261108.md and its
frozen source manifest config/directional_research_baseline_20261108.json.**
These encode the November 8, 2026 user-approved Deep Research study comparing
Pick'em Auditor against relevant statistical papers and LosingLoonies.
Treat the report as the design and acceptance baseline, not optional advice.

Implement in sequence: (1) immutable 60/40 baseline and strict timestamp/
leakage/source receipts; (2) independently modeled exposure/opportunity and
current role/lineups/injuries; (3) role/position/season-specific hierarchical
priors; (4) temporally cross-fitted correlation-aware stacking; (5) separate
held-out calibration; (6) adversarial chronological validation, shuffled-feature
controls and independent game/slate cluster uncertainty. At every phase,
compare on EXACT pregame contracts against the frozen 60/40 and timestamped
market baseline, with separate directional accuracy, Brier/log-loss, side bias,
coverage, missingness and abstentions. Never present a single slate as proof.
**No production promotion or Tier changes without a separate decision.**
Retain the full source report in the research conversation; the repository
methodology document is its implementable research contract. Deviations require
explicit reasoning and new authorization, not a silent implementation shortcut.

The Phase 1 read-only validator is scripts/directional_phase1_validation.py.
It must not overwrite historical rows, change the trained model or dispatch
Dell jobs. Consult docs/PHASE1_DIRECTIONAL_VALIDATION.md for use and limits.


The production slate policy is `config/production_consensus.json`:
60% consensus of available, same-contract, pregame historical engines
(Engine A, Bayesian A, Bayesian B and strictly eligible NUTS) plus 40%
source-verified opportunity/situational Engine B. Missing historical models
are individually reported; the historical pool requires Engine A plus at least
one other valid family. Market and provisional NUTS are NEVER included in the
blend. Final production probabilities are computed after Bayesian/NUTS sidecars;
preliminary A/B-only snapshots are unranked and not publication-authorized.
Preserve existing research, availability, market and Tier 1 validation gates.
Do not interpret production authorization as demonstrated probability calibration.

For every requested slate, report each pick's player/stat/side/line plus Engine A,
Engine B, production Consensus, Bayesian A, Bayesian B, normalized Market and
trained NUTS probabilities. Use `scripts/slate_model_report.py`; retain unavailable
values and reasons, exact model builds and original timestamps. Never substitute
another model into a missing column. Bayesian/NUTS comparisons do not enter the
production blend.

Before a slate, inspect completed model availability. Deepnote's current token
has Contents access but lacks Actions-artifact access. Approved cached NUTS fits
remain usable. Use connected GitHub capabilities to stage newly completed,
strictly converged artifacts when needed, validating artifact/manifest/posterior
hashes. Do not ask the user to manually collect files that connections can read.

Never interrupt, restart, overwrite or modify active training to run a slate.
Never relax convergence gates or promote a failed model. Preserve original
predictions and outcomes; settle archived forecasts without rebuilding them.
Do not invoke GitHub Copilot or GitHub-hosted AI agents. See
`docs/PRODUCTION_VALIDATION.md` for the validation/reporting contract.


For nightly slate requests, also report the evidence-based research top ten
for each sport from slate_top10_evidence.json and slate_top10_evidence.md.
Every worthwhile candidate must have its exact line and all available model
probabilities plus concrete evidence: verified same-line current-season hits
and observed workload trends when available, or explicit "unavailable" and
required source checks. Never infer lineup status from prior appearances.
Use the transparent priority score for research ORDER ONLY, not as a win
probability, Tier certificate or permission to bet. Preserve the separate
fully verified board.

For every slate, evaluate EVERY source-supported, archived NFL/NBA/NHL player/stat/side
contract before narrowing the display to ten per sport. Read
`slate_full_universe_research.json` and `slate_forecast_scope_audit.json`:
report the player trend and the opponent tendency or explicitly name missing
context. Verify current lineup, snaps/usage, opponent scheme, opportunity,
game script, injuries, rest and stadium-specific weather before claiming that
the matchup favors a candidate. No unsourced trend, venue assumption or weather
multiplier can substitute for actual opponent evidence. Retain the existing
all-model comparison chart. In NFL research prioritize credible volume overs
(targets, pass attempts, rush attempts) and outcome-dependent unders as a
screening preference, NOT a probability bonus or a reason to ignore other
stronger opportunities. Never skip an available market solely due to type.
