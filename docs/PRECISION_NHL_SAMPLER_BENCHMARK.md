# NHL sampler acceleration: isolated, scientific benchmarks

## What this does

The workflow `.github/workflows/precision-nhl-sampler-benchmark.yml`
runs on **GitHub-hosted Ubuntu workers**, never the self-hosted Windows
`pickem-trainer`. It benchmarks standard PyMC NUTS, Rust/Numba Nutpie, and
NumPyro/JAX CPU on the **same** selected NHL player cohort using the **same**
historical cutoff, model, seed, four chains, target acceptance, 400 tune
iterations and 400 posterior draws per chain.

This is a short **research feasibility pilot**. It is intentionally **NOT**
full-history all-player training and must **NOT** be used to publish forecasts,
approve picks, or replace the production sampler. Reports include full
population source digests and strict all-effects convergence statistics (R-hat,
minimum bulk ESS, divergences and BFMI). Timing alone never qualifies a backend.

A GitHub pull request changing the benchmark automatically triggers the three
hosted test jobs. You can also manually dispatch it from Actions using the
same date and cohort settings.

## Why not test on the laptop while fitting?

Your existing Windows NHL process has up to four active hierarchical fits.
A local benchmark would compete for scarce RAM, CPU bandwidth and cooling,
possibly delaying or crashing the original. Hosted CPU timing is **comparative
within one machine class** but cannot be used to predict wall-clock duration
on the Precision 5490 without a later matched local pilot.

## What happens after the pilot?

1. Check all three JSON receipts. The `source_digest`, rows, number of
   players, tune/draw counts, chains and target acceptance must match.
2. Reject missing diagnostics, broken samplers, bad R-hat or ESS, divergences,
   BFMI below 0.3, or differences in the target distribution.
3. For viable samplers, compare minimum bulk ESS/second, not raw iterations/sec.
4. Run a longer reproducibility and holdout predictive test before changing
   the production model; the 400-draw pilot alone cannot reliably qualify
   the complete posterior.
5. Once laptop capacity is free, benchmark Windows-native Nutpie on that
   machine. JAX CPU can be evaluated there separately.
6. CUDA feasibility requires a separate, explicit **opt-in** Windows WSL2
   workflow, because official JAX CUDA is not available on native Windows.
   Your RTX 2000 Ada has 8 GB VRAM. First test memory required by the **full
   population** model and resulting ESS/second; the hosted CPU comparison
   cannot establish GPU performance. No CUDA jobs are dispatched by this PR.
7. Pilot target_accept values separately only if convergence checks hold.
   Reducing acceptance merely for speed can increase divergent transitions.

## Safety for the active 2026-10-30 training

Run 40993538888 uses its **already checked out frozen source**. This PR does
not change or terminate its processes or modify its GitHub Actions workflow.

The existing campaign has all four markets running, so there are no queued
models left to launch. It will mark a deliberately terminated market as failed,
continue the other active markets, and eventually exit with a nonzero status,
which still triggers its final artifact-upload step (`if: always()`).

**Never cancel the whole GitHub run** if you intend to preserve hits/saves:
cancelling the workflow kills every model and can prevent results from being
uploaded. Terminating an individual Python worker on the user's local Windows
machine requires a *verified PID* read from the campaign's
`NHL_MODEL_STARTED stat=... pid=...` log line. Because multiple workers
share the same Python executable and command line, guessing PIDs is unsafe.

The existing workflow has no exact mid-NUTS resume/checkpoint support. Logs
and progress JSON can be archived but unfinished NUTS trajectories cannot
continue from the last displayed percentage. Completed posteriors should be
preserved intact for later comparisons.
