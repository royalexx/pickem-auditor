# Pick'em Auditor

Private repository for the Pick'em Auditor workflow.

## Phase 1: verified NHL-history collection

The initial GitHub runner **does not yet contain Engine A, Engine B or the full local skill package**. It establishes a reproducible, network-enabled NHL data pipeline before importing the full research and ranking system.

- Workflow: \`.github/workflows/nhl-history.yml\`
- Collector: \`scripts/nhl_collect.py\`, using only Python's standard library.
- Inputs: official NHL scoreboards and completed-game boxscores.
- Outputs: \`data/nhl/games/YYYY-MM-DD/GAME_ID.json\` plus an execution receipt uploaded as a workflow artifact.
- Scheduled at 6 a.m. and 4 p.m. Toronto time (including daylight-saving alternatives), with manual runs supported.

The workflow fails visibly if NHL APIs cannot be reached or if the response schema changes. Completed game files are deterministic and are not rewritten when unchanged.

### Verify the first run

Open **Actions → NHL history collection → Run workflow**, then inspect the job, the collection receipt artifact, and committed \`data/nhl/games\` files. A successful trigger is **not** proof that data was collected.

### Future phases

Import the repaired skill code (excluding credentials and preexisting private archives), restore prior history, add NBA/NFL feeds, verify Odds API secrets, and add the A/B probabilistic ranking/settlement pipelines.

Do not commit API credentials, local secrets, raw private archives, or picks to the repository. No Odds API key is required for this first NHL historical collector.
