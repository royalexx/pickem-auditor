# Verified NFL targets model in the daily pipeline

The afternoon pipeline runs `nfl_context_daily.py run --download` after collection.
It reuses the NFL schedule, weekly production, snap counts, PBP and FTN downloads
already made by `fetch_slate.py`. No additional odds request is required.

The current slate exposes receiving yards/receptions rather than targets. Those
receiver identities now produce **target-opportunity projections**, with expected
targets and 90% predictive intervals. Over/under probabilities at 5.5 are explicitly
labelled `line_origin=research_threshold`; reception/yardage lines are never
treated as target lines. Genuine target snapshots, when available, use their
actual target reference line and are labelled `line_origin=market`.

Outputs:

- `data/nfl_context/YYYY-MM-DD.jsonl`: append-only forecasts and unavailable reasons.
- `reports/nfl_context_daily.json`: coverage, source/release issues and counts.
- `reports/nfl_context_settled.json`: morning Brier/log-loss audit, split by line origin.

The new joint forecast already includes offensive and defensive reads, so no
additional Engine B/read multiplier or 70/30 blend is applied to it. Original
Engine A/B predictions and tier decisions retain their own identities. The new
forecasts are conditional on appearance; they do not assert game-active status
or a confirmed QB. Recent-three-game passer mixtures and missing-read flags are
carried with every forecast. Prospective actual-market calibration remains
necessary before promoting these probabilities into production tiers.

## Source and model validation

The collector writes a hashed `data/season/nfl_context_2026.json.gz` snapshot.
Forecasting requires a source no more than one hour old, exact GSIS identity,
matching current-source team/position, and an unambiguous official schedule
match. Model coverage gaps are reported instead of assigning another player's
effects. Core and read features use the same functions as training, with history
cut off at forecast time rather than at the later kickoff. Seven-day charting
lag, observation masks and training-only imputation remain in force. The lag is
a conservative assumption, not verified historical publication timing.

The 2024/2025 seed retains enough prior history for early-season features.
All 1,738 held-out feature vectors reproduced using the compact history seed,
shared live feature builder and exported parameters. The exported arrays retain
all 6,000 posterior draws. Original posterior SHA, design, seed and every array
are pinned in `config/nfl_targets_release.json`; NPZ loading forbids pickle.
The production inference environment needs NumPy/SciPy, not PyMC or a sampler.

## Automatic model publication

`Publish verified NFL targets model from Precision` runs on the existing
`[self-hosted, Windows, X64, pickem-trainer]` runner. It reads the existing run at
`C:\Users\alexi\Music\pickem-auditor\reports\nfl_reads_full_v2` using its existing
`.venv`, verifies convergence and source hashes, and exports the inference assets.
It performs no training and uses no hosted Actions minutes. The source run is
outside the runner checkout and is not changed by checkout cleanup.

The job publishes `model.json` and `parameters.npz` to the private prerelease
`research-nfl-targets-20261031-v3`. Repeated publication verifies an existing
release instead of overwriting it. Afternoon jobs download and verify these
assets on demand. If the Precision runner is offline, publication remains queued
and the daily receipt reports missing assets until it completes. Hosted daily
jobs still require available Actions capacity; this does not change their billing.

For local use after a normal slate collection:

```powershell
python -m pip install -r requirements-nfl-inference.txt
python scripts/nfl_context_daily.py run --download
python scripts/nfl_context_daily.py audit
```

Morning scoring uses settled original target snapshots or subsequent observed
NFL target counts. Reception/yardage outcomes cannot settle target projections.
For past predictions, the morning audit refreshes public weekly target counts
and schedules, including on days without NFL games. Those two bulk calls use no
odds credits. Exact GSIS/game joins and the conservative 18-hour availability
boundary prevent a current/future game from being scored prematurely.
Unavailable results remain pending until verified target observations arrive.
Forecasts are preserved by `shadow_store.sh`; reruns cannot rewrite past rows.
