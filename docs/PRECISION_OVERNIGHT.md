# Overnight 31-market full-player Bayesian fitting on native Windows

The Precision 5490 runs one research-only historical player-stat Bayesian model
at a time, not 31 simultaneous fits. Upon completion or controlled failure,
the workflow uploads that single market's result and dispatches the next
market. This avoids single large-run timeouts and GitHub queues that may expire.
It uses the already registered self-hosted Windows x64 runner labeled
pickem-trainer, which must remain online and awake.

The source and code are pinned by GitHub SHAs in per-market
cloud_provenance.json. No changes to production grades or pick rankings occur.

## Start from PowerShell

Ensure gh auth status shows your account. Cancel the older small-player
pilot **only if you want to replace it**, then start a full-player run:

    gh run cancel 40986667852 -R royalexx/pickem-auditor
    gh workflow run precision-full-markets.yml -R royalexx/pickem-auditor --ref main -f index=0 -f max_per_position=0 -f as_of=2026-10-29

Do not launch 31 separate invocations. The new one queues the next automatically.
On Windows 11, disable sleep while plugged in and keep your first runner
PowerShell terminal (run.cmd) open; the screen itself may turn off.

To inspect the current campaign's most recently created run:

    gh run list -R royalexx/pickem-auditor --workflow precision-full-markets.yml --limit 5

Manual recovery after a failure to dispatch the next market: choose the index
from the last market's catalog receipt and run the same command with
-f index=N. Never restart with index 0 without checking whether a previous
campaign is still active.

## Research coverage

There are 31 distinct sport/statistical model families:
- NHL 4: shots on goal, hits, blocked shots, saves; 2018-10-01 onward;
- NBA 11: points, rebounds, assists, threes, steals, blocks, turnovers,
  PRA, PR, PA, RA; contiguous 2023-10-01 onward;
- NFL 16: 13 count and three yardage families; completed 2018–2025 seasons.

The old NBA 2018–2023 source warehouse remains incomplete. Those partial,
non-contiguous early-season games are deliberately not mixed into the
recent complete NBA population. NFL 2026 games also are not presumed
collected. Training cutoff 2026-10-29 excludes October 29 games.

The default -f max_per_position=0 selects **all eligible players** instead
of the 15-player-per-position exploratory cohort. Four PyMC chains run in
two concurrent CPU jobs. Each model is separately bounded to 600 minutes
and retains a failure/success receipt, but the 31-market campaign may
take many hours or days; it is NOT guaranteed to finish in one night.

A model is accepted for research evaluation only when the independent
sampler diagnostics pass: R-hat <=1.01, bulk ESS >=400, zero divergences,
and BFMI >=.30. The full-data posterior is not automatically calibrated,
holdout-tested, or production eligible. Use separate chronological holdout
runs to compare with the simple and existing Bayesian baselines.

Each market's GitHub Actions artifact lasts 90 days by workflow policy.
If a full population fit exhausts memory on the 32GB laptop, its failure
is recorded and the campaign advances. Smaller cohorts do NOT qualify as
full-population fits.

## Safety and controls

GitHub Actions workload stays research-only and runs on the already
registered local laptop. The per-market runner is granted read access to
repository data and actions:write only to self-dispatch the next market.
It must execute trusted code only. Disabling the runner or cancelling
the current campaign prevents further local computation, provided no
separate continuation has already been queued. If a run is cancelled,
the continuation step is skipped. Monitor GitHub for a queued successor.
