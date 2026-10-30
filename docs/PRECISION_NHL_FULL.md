# Precision 5490: NHL-only, full historical Bayesian fitting

## One-time compiler setup before restarting NHL training

The original native Windows job was accidentally deployed without the
PyTensor C++ compiler. Native MSYS2 UCRT64 GCC/G++ is required by the
current workflow. It is NOT Ubuntu, WSL2, Visual Studio Code or Cursor.

In regular PowerShell 7, install MSYS2 once:

    winget install --id MSYS2.MSYS2 --exact --source winget --accept-package-agreements --accept-source-agreements

From the Windows Start menu open **MSYS2 UCRT64** (not "MSYS").
Inside the MSYS2 UCRT64 terminal run:

    pacman -Syu

If the updater asks you to close the terminal, reopen MSYS2 UCRT64 and
repeat "pacman -Syu" until the upgrade finishes. Then run:

    pacman -S --needed mingw-w64-ucrt-x86_64-gcc

Return to ordinary Windows PowerShell 7 and verify:

    & "C:\msys64\ucrt64\bin\g++.exe" --version

If that reports a GCC version, the compiler is installed. The workflow
then automatically puts C:\msys64\ucrt64\bin on its step PATH and runs
a real PyTensor compiled-function test. It refuses to start a four-model
fit if C++ compilation fails instead of silently training without it.

The already-cancelled workflow cannot pick up the compiler retroactively.
Start a fresh run only after PowerShell shows the compiler version.
Note: Compiler availability improves the ability to compile optimized
kernels but does not guarantee a specific CPU speedup, convergence or
full CPU utilization.


This manually dispatched job trains FOUR independent NHL count models on your
Windows self-hosted runner, leaving NBA and NFL untouched:

- shots on goal
- hits
- blocked shots
- goalie saves

The source is the completed 2018-2026 NHL population in the private GitHub
data/bayesian-history branch, frozen at 2026-10-29 exclusive (Oct 28 included).
Every historical eligible player and up to twelve seasons may be used;
MAX_PER_POSITION=0 means NO 15-player research cohort limitation.

## Launch command (PowerShell 7)

In a second PowerShell window (leave .\run.cmd running in the first):

    gh workflow run precision-nhl-full.yml -R royalexx/pickem-auditor --ref main -f as_of=2026-10-29 -f max_parallel_models=4 -f min_free_ram_mb=8192

Monitor:

    gh run list -R royalexx/pickem-auditor --workflow precision-nhl-full.yml --limit 5

Or open:
https://github.com/royalexx/pickem-auditor/actions/workflows/precision-nhl-full.yml

Do not start a different precision Bayes workflow at the same time. This
single GitHub Actions job runs on ONE self-hosted Windows runner, but
starts up to four local PyMC fit subprocesses, which each run four CPU
sampling chains. Potentially SIXTEEN active sampling processes, leaving
some of the 22 logical CPU threads free for Windows, the sampler parent
processes, and background tasks.

All four market fits have independent outputs; every fit uses 2,000 kept
draws and 1,800 tuning iterations per chain, for eight thousand
retained draws per market if completed. This improves sampling precision
(Monte Carlo error) versus 1,000 draws, but does not guarantee that
forecast probability accuracy improves.

## Dynamic memory and CPU utilization

Jobs are staggered four minutes apart. A new model is launched only when
at least 10 GiB of physical RAM is available (8 GiB reserve, plus 2 GiB
startup cushion). This reduces OOM risk with full player-season models.
If available RAM stays below 4 GiB for 45 seconds, the newest running
model is killed to protect Windows and is marked as failed. The other
models continue. Thus 16 simultaneously working sampling chains are
a MAXIMUM, NOT a promised minimum or guaranteed utilization. CPU usage
may remain low if compilation or a single complex likelihood dominates.
The current environment does not use the RTX GPU or require Ubuntu.

## Where to see live progress

The GitHub Actions log will print messages approximately every 45 seconds:

    [shots on goal] NUTS_PROGRESS sport=NHL stat=shots on goal [########----------------] 33.3% stage=warmup chains={'0':1200,...} elapsed=...s status=running

Before any draw is recorded (e.g., PyTensor compilation), it prints a
heartbeat at 0.0% with stage=initializing_and_compiling rather than
pretending that the sampler is stalled.

The campaign also writes a single high-level status each minute:

    NHL_CAMPAIGN_PROGRESS finished=0/4 accepted=0 failed=0 started=2 queued=2 sampling=8.5% free_ram_mb=...

When the runner finishes, the GitHub Actions artifact includes:
- nhl_campaign.json: four model statuses, progress and memory telemetry;
- one folder per NHL stat containing progress.json, training.log,
  manifest.json, posterior.nc (when available), model_receipt.json;
- the manifest includes sample budget, full player population count,
  exact source digest and strict sampler diagnostics.

The GitHub artifact is kept for 90 days. No bets are ranked, no
production model weights are changed, and this does not deploy the new
model to live scoring.

## Scientific quality requirements

Four chains are used for every market. The **full player, opponent and
season effects**, not only global model hyperparameters, are checked for:

- R-hat <= 1.01
- minimum bulk ESS >= 400
- zero NUTS divergences
- minimum BFMI >= 0.30

If a fit violates any threshold, the model_receipt marks that
market as failed, while preserving diagnostics and posteriors. Training
a model on the entire data is NOT the same as demonstrating predictive
skill; chronological holdout benchmarks against the simple and existing
Bayesian models remain necessary before production deployment.

## Laptop and job limitations

You must leave the Windows laptop on AC power, awake, and the GitHub
runner Online (e.g. its PowerShell run.cmd window open).
The job's time budget is 48 hours; it could take much longer than one
night, or fail due to memory, compilation or non-convergence. No code
here can make a training run that has not happened count as converged.

The workflow requires and smoke-tests an existing MSYS2 UCRT64 G++.
If it is missing, PyMC sampling will not start. No automatic system
compiler installation is attempted within the self-hosted runner.
