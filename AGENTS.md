# Pick'em Auditor operating instructions

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
