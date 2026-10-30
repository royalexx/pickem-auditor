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


## 2026-10-30 runner availability fallback

The GitHub-hosted Ubuntu matrix attempt #41066586701 failed in all three
matrix jobs **before GitHub recorded even one execution step**. Offline
checks showed the same symptom. No sampler comparisons ran; this is not
evidence that Nutpie or NumPyro is incorrect or slow. An account billing,
runner allocation, organization policy or platform access issue must be
verified in the GitHub Actions run UI before hosted jobs can run.

A second workflow,
`.github/workflows/precision-nhl-sampler-windows.yml`, provides a
**self-hosted Windows fallback**, sequentially running PyMC, Nutpie and
NumPyro on the SAME Dell Precision laptop. It uses the exact same
`precision-windows-nhl-complete-history` concurrency group as the
original training workflow, with `cancel-in-progress: false`.
Its automatic `workflow_run` trigger is guarded by the exact original
run ID **40993538888**; it will not start on unrelated training campaigns.
The fallback begins **only after that full run completes**, preserving
the active hits and saves chains. It also supports explicit manual
dispatch for later repeat trials.

The benchmark records source digest, cohort size, compilation + sampling
wall time, strict diagnostic values, and ESS/sec. It never marks its
short pilot as an approved production backend even if diagnostics pass.
Production approval additionally requires a longer, representative
full-population and heldout predictive comparison.

## Read-only saves convergence check

When the full NHL saves fit completes, it writes
`reports/precision_training/40993538888/saves/manifest.json`,
`posterior.nc`, and `model_receipt.json`. The manifest already checks
all global, player, opponent and season effects; max R-hat <=1.01, min
bulk ESS >=400, zero divergences, min BFMI >=.30.

From the ORIGINAL runner checkout, a quick safe manifest inspection
without installing anything is:

```powershell
$folder = "$HOME\actions-runner\_work\pickem-auditor\pickem-auditor\reports\precision_training\40993538888\saves"
if (!(Test-Path "$folder\model_receipt.json")) {
  Write-Host 'Saves still fitting or finalizing. Do not infer convergence from progress.'
} else {
  $m = Get-Content "$folder\manifest.json" -Raw | ConvertFrom-Json
  $r = Get-Content "$folder\model_receipt.json" -Raw | ConvertFrom-Json
  [pscustomobject]@{
    Status=$r.status; AllEffects=$m.diagnosed_all_player_and_opponent_effects
    Rhat=$m.diagnostics.max_rhat; MinESS=$m.diagnostics.min_bulk_ess
    Divergences=$m.diagnostics.divergences; MinBFMI=$m.diagnostics.minimum_bfmi
    Passed=$m.diagnostics.posterior_sampling_ok
    PosteriorPresent=(Test-Path "$folder\posterior.nc")
  } | Format-List
}
```

The new read-only script `scripts/precision_nhl_convergence.py` also
enforces provenance, all-player effects, posterior existence, sampler
budget and the worker receipt. For a secondary, independent recomputation
of diagnostics from the saved NetCDF posterior use
`--independent` only when there is sufficient RAM and the proper
research environment; it may be expensive while hits is still sampling.


## Automatic second-opinion goalie convergence audit

After original run 40993538888 completes and uploads its artifact, the
deferred Windows benchmark tries to download
`precision-nhl-full-history-40993538888` using the job's read-only
GitHub Actions permissions. It then calls
`precision_nhl_convergence.py --market saves --independent`, which opens
the saved NetCDF posterior and recomputes the **entire** strict
all-player/all-opponent/all-season convergence diagnostic set. A
`reports/nhl_saved_fit_audit/saves.jsonl` receipt is uploaded even
when the model fails or its original artifact is unavailable. In those
cases the workflow must NOT report saves as converged.
