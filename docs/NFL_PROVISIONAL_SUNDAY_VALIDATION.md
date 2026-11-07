# Prospective NFL provisional NUTS validation — Sunday, November 8, 2026

**Production baseline is unchanged:** the 70% Engine A + 30% Engine B consensus in `config/production_consensus.json`. Strictly converged NUTS forecasts remain separate. **No provisional NUTS estimate may change ranking, tiers, stakes, or production probabilities.**

## Provisional challengers

The four **completed** four-chain NUTS runs are pinned in `config/provisional_nuts_artifacts.json`:
- NFL pass attempts (run 42316167923)
- NFL targets (run 42324673573)
- NFL rushing touchdowns (run 42376841453)
- NFL receiving touchdowns (run 42395673312)

Original strict diagnostics remain `posterior_sampling_ok=false`. Admission to research-only validation requires all of: max R-hat ≤1.02, min bulk ESS ≥300, zero divergences, min BFMI ≥0.30, an exact SHA256-matched completed artifact and matching frozen train/model provenance. No gate is silently relabeled as passed.

## Sunday inference and original source freeze

- `scripts/provisional_nuts_shadow.py` downloads only the four explicitly pinned GitHub Actions ZIP artifacts and checks their hashes, complete four-chain manifest and numerical criteria; no training is started. It separately integrates the frozen count-model likelihood (new season effects drawn from pre-cutoff hyperpriors), with source-verified player/opponent/home/away, exact side/line, event start and no post-kickoff inference. Each row records `provisional=true`, `ranking_allowed=false`, `publication_eligible=false`, `original_strict_convergence_failed=true`, run ID, sampler metrics and timestamps.
- A scheduled one-time Deepnote pregame run at **7:00 a.m. America/Toronto, Sunday Nov 8** exists. It invokes the usual `run_phase=afternoon` notebook before the 9:30 a.m. first NFL kickoff. The normal 4 p.m. run alone would not be sufficient for morning games.
- The Deepnote project's private GitHub Contents token lacks Actions artifacts permission (HTTP 403). The scheduled automation, using **the connected GitHub app**, retrieves four ephemeral authenticated artifact download links and immediately writes a private `private_provisional_signed_assets.json` to the Deepnote project. The very first notebook checkout block fetches all four artifacts in parallel **before the 5-minute signed links expire**, verifies ZIP SHA256/size, deletes the URL manifest, and exports `PICKEM_PROVISIONAL_PRESTAGED_DIR` for the optional research inference stage. The source ZIPs are deleted after each model is evaluated.
- If the signed handoff, artifact transfer, numerical environment, or a model fails, the ordinary Engine A/B consensus runs unchanged. Never claim that a missing provisional forecast exists.
- The original prospectively frozen output is `data/provisional_nuts_shadow/2026-11-08.jsonl`. `scripts/slate_model_report.py` displays `NUTS_provisional` separately from **strict** `NUTS`. `scripts/live_pool_exchange.py` archives sidecars with the original pregame run in the immutable live observations branch. Later post-kickoff reruns cannot replace the earliest canonical pregame cohort.

## Monday scoring

The Deepnote morning notebook reads the **earliest immutable Sunday afternoon archive** and verified settled source observations. It scores `provisional_nuts` only when the original forecast and provisional inference were both completed before the source event began and the actual player stat is resolved. Pushes/missing stats and invalid identities are excluded; evaluate Brier/log loss against consensus, Engine A, Engine B, Bayesian A/B and market using identical player/line/game cohorts. Do not substitute an older target-context release for any of these four provisional models. One Sunday is exploratory and cannot certify calibration.

## Verification so far (November 7)

- Artifact IDs, SHA256 digests and sizes checked live through the connected GitHub app; all four artifacts existed and were unexpired.
- Five offline `test_provisional_nuts_shadow.py` tests passed in Deepnote.
- Four modified Deepnote notebook code blocks passed Python syntax parsing.
- Direct Deepnote fetch of a short-lived signed artifact ZIP URL succeeded in a live range-request probe (HTTP 206, ZIP signature).
- A full four-artifact Deepnote inference run on actual Sunday NFL pregame rows **has not yet succeeded or been observed**. The scheduled run must report success/failure and eligible forecast counts; do not claim production validation before it finishes.

The frozen Dell campaign remains separate and untouched.
