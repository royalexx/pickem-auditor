# Run joint Bayesian fits on your Precision 5490, audited through GitHub

Compute runs on your Windows laptop INSIDE Ubuntu WSL2 as a GitHub
self-hosted runner. Historical source data and code remain in the private
GitHub repository, and each run uploads a posterior NetCDF, manifest,
convergence diagnostics, and optional same-cohort holdout report to GitHub
Actions. No incoming network port or remote desktop access is required.
The ChatGPT GitHub integration can inspect runs, logs, code, and artifacts;
it cannot directly see or operate files on your laptop.

## 1. Set up Ubuntu on Windows

Run in Administrator PowerShell:

    wsl --install -d Ubuntu-24.04

Reboot if prompted, and launch Ubuntu to choose a Linux username/password.

Optionally edit the Windows file %UserProfile%\.wslconfig to allow more
RAM than the default WSL allocation, while retaining headroom for Windows:

    [wsl2]
    memory=22GB
    processors=12
    swap=16GB

Run wsl --shutdown in PowerShell, then reopen Ubuntu.

Inside Ubuntu:

    sudo apt update
    sudo apt install -y git curl ca-certificates python3 python3-venv python3-pip build-essential
    python3 --version
    free -h

Keep runner and working files under /home/... (Linux filesystem), not /mnt/c.

## 2. Register your GitHub runner

Visit:
https://github.com/royalexx/pickem-auditor/settings/actions/runners/new

Choose Linux / x64. Follow GitHub's CURRENT download, extraction and runner
registration commands inside Ubuntu. For registration, add the custom label
pickem-trainer. Example shape:

    ./config.sh --url https://github.com/royalexx/pickem-auditor --token YOUR_TEMPORARY_TOKEN --labels pickem-trainer

Copy the token from the actual GitHub runner setup screen. Do NOT paste it
into chats, tickets or files. This registration token expires.

From the runner directory:

    ./run.sh

The GitHub Actions runner list should show Online, Idle, Linux, X64,
and pickem-trainer.

To make the runner a service, enable systemd in /etc/wsl.conf if needed:

    [boot]
    systemd=true

Restart the distribution (wsl --shutdown in PowerShell), then:

    sudo ./svc.sh install
    sudo ./svc.sh start
    sudo ./svc.sh status

Ubuntu WSL must actually be running. Windows can launch it at sign-in with
Task Scheduler using: wsl.exe -d Ubuntu-24.04 --exec /bin/true
Keep the laptop plugged in and disable Windows sleep while on AC power.
Locking the Windows screen does not interrupt computation.

## 3. Launch training from GitHub

https://github.com/royalexx/pickem-auditor/actions/workflows/precision-local-bayes.yml

Click Run workflow. It is MANUAL only and will wait for the custom-labeled
self-hosted runner; no GitHub-hosted runner will run the NUTS job.

Recommended initial NHL diagnostic/holdout pilot:

    sport: NHL
    stat: shots on goal
    mode: holdout
    train_from: 2023-10-01
    cutoff: 2026-09-01
    holdout_until: 2026-10-29
    line: 2.5
    max_per_position: 15

NBA example: sport NBA, stat rebounds, same 2023-10-01 / 2026-09-01 /
2026-10-29 windows, line 9.5 (fixed research threshold, NOT an odds line).

NFL 2025 season holdout example: sport NFL, stat tackles + assists,
train_from 2022-09-01, cutoff 2025-09-01, holdout_until 2026-03-01,
line 5.5. The independent NFL source contains completed seasons to 2025.

After a converged heldout fit, run mode=pregame_fit with cutoff=2026-10-29
to freeze a fit using games through October 28, without same-run holdout.
This remains shadow research: scoring real live slate props requires a
separate identity/context bridge and calibration validation.

The max_per_position=15 default is a TRAINING-ONLY COHORT, NOT the full
population. Try 15 first; raise it only after inspecting RAM, run time,
diagnostics and heldout scores. Set 0 for the full population only when
the laptop can safely handle the model size.

Current sampling settings: four chains, 1000 kept draws per chain, 1200
tuning steps per chain, and two CPU chains running concurrently. Your
Core Ultra 7 165H is used. The current PyMC model does NOT use the GPU.
Your exact NVIDIA card can be confirmed using nvidia-smi. Any WSL2 CUDA
or JAX/NumPyro acceleration requires a separately benchmarked setup.

## 4. What appears in the cloud?

The Actions run logs are streamed to GitHub. Its artifact includes:

- posterior.nc: actual sampled posterior (when fitting reaches output stage)
- manifest.json: fit window, model version, player cohort, source digest,
  R-hat, ESS, divergences, BFMI, shadow-only status
- stat_holdout.json: paired Bayesian versus simple control on historical
  unseen games, if mode=holdout and fit passes diagnostics
- window_preflight.json: historical source continuity for holdout mode
- cloud_provenance.json: frozen code SHA, data-branch SHA, run ID, inputs

The data warehouse remains in the cloud on data/bayesian-history, with
immutable historical records. The training job never overwrites it.

Artifacts are retained for 90 days in this workflow, subject to repository
storage limits. For truly permanent large posteriors, add immutable cloud
object storage or versioned release assets with SHA256 digests. Do NOT
commit .nc binaries to the Git repository.

## 5. Security and limitations

- The private repo is already verified, but use a dedicated unprivileged
  Ubuntu account and limit runner access to this repository.
- The runner executes arbitrary workflow commands: never run unreviewed
  PR code or third-party workflows on it, and avoid storing personal
  tokens, SSH keys or betting API secrets inside the runner environment.
- This workflow triggers ONLY manually, requests contents:read access,
  and never changes the production ranking/weights.
- Read-only authenticated Git checkout temporarily keeps its job token
  until post-job cleanup so the private history branch can be fetched.
- A source-coverage checkpoint does not establish a converged model.
  Current fit code requires R-hat <=1.01, bulk ESS >=400, zero divergences,
  and BFMI >=.30. No diagnostics should be waived to finish faster.
- If GitHub Actions fails before assigning a runner, the laptop runner
  alone cannot resolve account billing, permissions, or platform failures.
