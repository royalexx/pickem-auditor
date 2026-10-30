# Train the joint Bayesian research model natively on Windows 11

No Ubuntu and no WSL2. The Dell Precision 5490 serves as a **Windows x64
self-hosted GitHub Actions runner**. GitHub holds code and historical records;
the laptop downloads them, trains PyMC locally, and uploads diagnostic reports
and the sampled posterior to a private GitHub Actions artifact.

ChatGPT can use the connected GitHub repository to inspect runs, fix source
code and evaluate output artifacts, but cannot directly access your Windows
desktop or files. The historical warehouse remains on the independent
data/bayesian-history branch. The training workflow only reads it.

## Step 1 — Prepare Windows

- Windows 11, AC power, stable internet, enough free SSD space for the history
  checkout and large NumPy/PyMC temporary files.
- Install Git for Windows from https://git-scm.com/downloads/win if needed.
  In PowerShell: git --version
- Windows PowerShell/PowerShell 7 is used by the workflow (GitHub runner ships
  compatible PowerShell support). actions/setup-python@v5 installs Python 3.12
  for each training job, then the workflow creates an isolated venv.
  You do not need Miniforge, Anaconda, Ubuntu or WSL2 to start.
- During long runs set Windows Power & Battery > Screen, sleep & hibernate
  timeouts to never sleep while plugged in (screen may turn off). The laptop
  must stay on, plugged in and connected to GitHub.

## Step 2 — Install GitHub self-hosted runner (Windows x64)

Visit:
https://github.com/royalexx/pickem-auditor/settings/actions/runners/new

Select Windows and x64. Open **Administrator PowerShell** if installing
as a Windows service. GitHub recommends the runner folder C:\actions-runner.
Run its CURRENT PowerShell download and unzip commands exactly; runner package
versions change. The GitHub registration token is time limited and must not
be sent to ChatGPT or stored in the repository.

During configuration use a custom label: pickem-trainer.
The command shape is:

    .\config.cmd --url https://github.com/royalexx/pickem-auditor --token YOUR_EXPIRING_GITHUB_TOKEN --labels pickem-trainer

Follow the runner's interactive prompts. If you choose to install it as a
**Windows service** when configuration asks, it can run without keeping the
PowerShell window open. For the very first test, it is also fine to NOT use
a service and start the runner manually:

    .\run.cmd

GitHub > Settings > Actions > Runners must show the laptop as Online, Idle,
with self-hosted, Windows, X64, pickem-trainer labels. Only assign trusted,
reviewed repo workflows to it; the runner executes commands on your laptop.

## Step 3 — Launch the model through GitHub

Open:
https://github.com/royalexx/pickem-auditor/actions/workflows/precision-local-bayes.yml

Select **Run workflow**. The workflow is manual-only and explicitly targets
[self-hosted, Windows, X64, pickem-trainer]. It will remain queued until the
laptop runner is Online.

Suggested first **NHL shots on goal, chronological holdout** pilot:

    sport: NHL
    stat: shots on goal
    mode: holdout
    train_from: 2023-10-01
    cutoff: 2026-09-01
    holdout_until: 2026-10-29
    line: 2.5
    max_per_position: 15

For a similar NBA test, use sport NBA, stat rebounds, line 9.5; the same
time windows. NFL contains 2018–2025 completed seasons and can use
sport NFL, stat tackles + assists, train_from 2022-09-01, cutoff
2025-09-01, holdout_until 2026-03-01, line 5.5.

The research-only fixed line is NOT a sportsbook line; it is only used
to compare the Bayesian posterior to a transparent baseline on identical
heldout player-games.

The initial max_per_position=15 cohort is deliberately limited and is
NOT a full-population fit. Use 0 to attempt all eligible historical players
only when testing confirms the 32GB laptop has adequate RAM. The model
currently uses 4 independent chains, 1,000 retained draws and 1,200
tuning iterations per chain, with 2 concurrent CPU chains. Its native
PyMC implementation does not use the RTX GPU. To test GPU acceleration
in future requires a separately validated JAX/NumPyro or other sampler
setup; it is not enabled by changing a workflow label.

Once a holdout fit has passed diagnostics and validation, switch
mode=pregame_fit and cutoff=2026-10-29 to build a posterior trained through
October 28. This is still RESEARCH ONLY and cannot rank or forecast tonight's
slate until a live scorer and calibration evidence are added.

## Step 4 — Inspect results from the cloud

The GitHub Actions job shows execution logs and a 90-day artifact named
precision-windows-bayes-<SPORT>-<RUN_ID> with, when completed successfully:

- posterior.nc: the trained joint posterior, sampled on the laptop;
- manifest.json: model version, training source hash, Rhat, ESS, divergences
  and BFMI; fit is NOT publication-eligible by default;
- stat_holdout.json: date-frozen Bayesian vs simple control comparison
  for mode=holdout;
- window_preflight.json: input window and historical-source continuity;
- cloud_provenance.json: exact training Git code SHA, history branch commit
  SHA, runner type and user-supplied training parameters.

GitHub repository storage and artifact retention limits still apply. Large
posterior files should ultimately be copied into versioned cloud object
storage with SHA256 hashes if they need to persist indefinitely; do not add
large binary .nc files to the Git history.

## Troubleshooting

- **Queued**: Runner Offline, Windows asleep, service stopped, or missing
  the pickem-trainer label. Open GitHub runner list and check its status.
- **Failure before any step**: GitHub Actions account/billing, runner
  permissions, platform or repo settings. Training scripts did not run.
- **Source fetch permission error**: The workflow uses checkout's read-only
  GitHub job token to fetch data/bayesian-history. Check actions permissions.
- **PyMC pip error**: Inspect the log. A Windows/NumPy dependency may need
  a Windows-specific pinned requirements revision or Miniforge environment;
  do not silently substitute incompatible versions.
- **Out of memory**: Use a smaller training-only cohort, do not lower
  convergence requirements. Running two chains simultaneously already caps
  CPU concurrency in the current model.
- **Sampling diagnostics fail**: A result with Rhat > 1.01, bulk ESS < 400,
  divergences > 0, or BFMI < .30 must remain experimental.
- **Posterior cannot score a live prop**: Current joint training only
  produces a posterior and holdout. A separate production-safe scoring
  adapter, identities and calibrated evaluation remain to be implemented.

Security: Use a dedicated Windows account for the runner if practical. Do
not store personal credentials or sensitive files in its working directory.
Keep the repo private and avoid invoking self-hosted runner code from
untrusted pull requests. Do not share registration tokens or personal
access tokens in chats.
