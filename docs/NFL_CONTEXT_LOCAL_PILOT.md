# NFL separated context pilot

This research campaign separates player, own-team, opponent and season effects.
It trains locally, produces comparable forecasts and never changes production
weights, rankings or approved picks. The initial market is receiver **targets**.

## What is separated

| Component | Data | Learned role |
| --- | --- | --- |
| Player | Official weekly targets and independently joined offensive snaps | Workload and target rate, with correlated player effects |
| Own team | PBP offensive plays, passes, rushes, targeted passes | Separate team production effect and recent opportunity environment |
| Opponent | Independently aggregated opposing offense/defense PBP history | Separate allowance effect and recent matchup environment |
| Season | Historical player/game season | Workload and production shifts |
| Matchup | Scheduled kickoff, home/away, prior observed rest | Pregame predictors, conditional on appearing |

PFR snap identities are not conflated with GSIS player identities. The existing
game/team/name join requires a unique match and records omissions. Team play
counts come from PBP, **not a sum of player snaps**. Targets, receptions, carries
and pass attempts reconcile to PBP player IDs; discrepancies are explicitly
excluded. Tackle totals use the existing weekly credit definition and defensive
snaps, without claiming a verified opportunity denominator or alignment data.

The likelihood models bounded player snaps followed by an NB count rate. It is
not a fully generative team-volume/roster-allocation model: team effects enter
the player rate while team play counts are historical predictors. It does not
infer routes, target competition from projected lineups, passer-specific chemistry,
formations, measured schemes, injuries, weather or a target-to-reception conversion
stage. The current count likelihood does not strictly bound outcomes by simulated
snaps. Those limitations must be assessed in holdout checks. Signed yardage
requires a different outcome model and is not included.

## First run in the existing VS Code PowerShell terminal

```powershell
git fetch origin
git switch --track origin/codex/nfl-context-local-pilot
python -m pip install -r requirements-nfl-context.txt
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
python scripts/nfl_context_campaign.py run
```

If that branch already exists locally, use `git switch codex/nfl-context-local-pilot`
and `git pull --ff-only` instead of creating it again. Preserve unrelated local
changes before switching. The source branch includes the earlier NHL fixes.

The same Python/PyMC/G++ environment that completed the NHL pilot is suitable.
Dependencies are checked before any campaign identity is pinned. Rich sampling
progress is disabled; UTF-8 is set for child processes. Four chains run through
two workers, one BLAS thread per process, with sequential model processes and
30-second stage heartbeats. No GitHub Actions training is dispatched.

Default configuration: `config/nfl_context_targets_pilot.json`.

- Sources: 2024, 2025 and completed 2026 regular-season observations.
- Training: 80 recent games, with a prior-season anchor, before 2026-09-01.
  Selection uses dates and identities, not target magnitudes or holdout results.
- Holdout: from that cutoff until 2026-10-30 12:00 UTC, exclusive.
- Target line: 5.5, a fixed research threshold, not an archived sportsbook quote.
- Each fit: 1,500 warmup plus 1,500 retained draws per chain; four chains.

Unlike NHL's game-by-game collector, this uses bulk season datasets from
nflverse via pinned nflreadpy 0.1.5. Initial download time depends on network
and cache size. Source snapshots are compressed and hashed per season under
the run's `source_cache`. Original fetched evidence remains available if
normalization fails. No odds API credits are used.

## Three models and a fair comparison

The command freezes normalized team/player bundles, design matrices, training
rows and holdout rows. It fits:

1. `context`: separate player/team/season effects plus recent team and opponent
   play/opportunity covariates, home, observed rest and prior player workload.
2. `base`: the same new architecture and same cohort, with only home, observed
   rest and prior player workload. It retains team effects, isolating the added
   rolling team context rather than changing the architecture at the same time.
3. `incumbent`: a refit of the existing workload/production model on the same
   observed training rows. No future-trained posterior is reused.

All three must pass four-chain, all-stochastic-effect diagnostics: R-hat <=1.01,
bulk and tail ESS >=400, zero divergences, BFMI >=0.30 and no depth-12 hits.
Evaluation recomputes those diagnostics from each saved posterior. Comparisons
require exactly matching identities, lines, outcomes and training cutoffs.
Outputs include Brier, log loss, predictive coverage where available and
game-cluster bootstrap intervals. Unseen players/teams and position changes are
explicit exclusions; individual effects are never guessed from another player.

All rolling features exclude the current/future game and any unavailable record.
Kickoff is schedule Eastern time converted to UTC. Historical availability is
approximated as kickoff plus 18 hours; this is explicitly retrospective and does
not certify historical publication times or eliminate revision bias. Earlier
completed holdout games may update later rolling features without refitting.
Same-day source handling is conservative. Missing source fields never become
invented zero-valued player appearances.

## Resume and inspect

```powershell
python scripts/nfl_context_campaign.py status
Get-Content reports/nfl_context_targets_pilot_v1/fit_context.log -Tail 25
python scripts/nfl_context_campaign.py run
```

Unchanged completed stages are hash-verified and reused. An interrupted sampler
does not checkpoint chains. A saved posterior that fails diagnostics is retained;
change the budget in a new configuration/run directory rather than deleting the
failure. Configuration, code and runtime changes also require a new run directory.
An OS lock prevents duplicate campaigns. The parent releases model memory
between fits. Fit logs are included in subprocess failure messages.

The final file is `reports/nfl_context_targets_pilot_v1/review_packet.zip`.
It includes normalized frozen bundles, training/holdout rows, all design matrices,
source coverage, code/runtime receipts, manifest diagnostics and paired predictions.
Bulky raw source snapshots and posteriors remain local with identifying hashes;
they are necessary for an independent raw-source/convergence recheck.

After this pilot, use a new configuration and directory for the implemented count
markets `receptions`, `carries`, `pass attempts`, or `tackles + assists`. All five
graphs share the same separated structure with stat-specific opportunity inputs.
Separate ready-to-run configs are named `nfl_context_receptions_pilot.json`,
`nfl_context_carries_pilot.json`, `nfl_context_pass_attempts_pilot.json` and
`nfl_context_tackles_assists_pilot.json`. Pass attempts uses 160 pilot games to
provide enough QB observations. Supply both a new `--config` and a distinct
`--run-dir` when changing market; the default output path is for targets only.
Do not claim those markets have been validated merely because targets converged.
Any holdout examined during development must not be relabeled untouched validation.

## Checks performed before delivery

Source-shaped synthetic tests cover player/team separation, PBP reconciliation,
missing-game and duplicate checks, cache integrity, pregame-only features, paired
cohorts, frozen-input hashes and explicit unseen-player exclusions. Numerical
smoke uses synthetic data only. No real NFL fit or predictive advantage is claimed
by the implementation; the first real campaign runs on the local machine.

The three-model end-to-end synthetic trial used 256 training observations from
32 games over two seasons and 256 held-out observations from 32 games. All
three four-chain fits (1,000 warmup and 1,000 retained draws per chain) passed
the same strict convergence gates before paired evaluation. The source-shaped
simulation does not establish real NFL calibration or predictive advantage.
Its count intervals over-covered in this small simulation; no promotion or
real-data claim follows. The receipt is in
`validation/nfl_context_synthetic_2026-10-30.json`.
