# Recent multi-season Bayesian training and source catch-up

**Purpose:** collect historical NHL/NBA seasons from 2023 onward promptly, while retaining the source-owned 2018-forward archive; advance verified completed NFL seasons in bounded batches. Improve historical training selection and strict chronological validation. Everything here is **research only**, with zero production tier, betting line, weight or paid API changes.

## Status and independent streams

- Existing checkpoint `data/bayesian_warehouse/states/{nhl,nba}.json` continues chronologically from October 2018, never rewritten or reset.
- New independent checkpoints `data/bayesian_warehouse/states/{nhl,nba}_recent.json` start October 1, 2023. Their records go into the SAME immutable sport/stat/season shards so the warehouse has a single deduplicated source of truth. A verified matching game is idempotent; a different source payload raises a conflict instead of silently changing stored records.
- `NFL` continues its verified `data/bayesian_warehouse/states/nfl.json` from the next uncollected **fully completed** season. It can process up to three complete seasons each run. It never seals an ongoing NFL season: the following March must have begun before the season advances.
- The daily GitHub Action runs at 06:43 and 18:43 UTC, serialized with the existing NHL historical collector. Each run retains the old archive collection at up to 25 calendar days/sport and independently advances the newer stream at up to 100 calendar days/sport, max 700 completed games/sport. Per-API request pacing, finite retries and early fail-closed receipts remain in place. The near-year backfill is a bounded ongoing process, not instantaneous.
- Completed day/season data is checkpointed and pushed to `data/bayesian-history` even if a different sport blocks. Any individual step failure still marks the workflow unsuccessful, never a fake success. No PropLine or Odds API usage.

## Real 2023 source verification

The one-off validation against original live completed-game sources passed for NHL October 11, 2023 (six games, 650 player-market rows: hits 212, blocked shots 212, SOG 212 and goalie saves 14) and NBA October 25, 2023 (twelve games, 2,992 player-market rows, including 272 made three-point records). Both emitted independent recent-source receipts, date checkpoints, and left their 2018 archive checkpoints unchanged. This was an isolated `/tmp` source test and **not an assertion** that all 2023–2026 seasons have been copied to the persistent history branch.

Live evidence: https://github.com/royalexx/pickem-auditor/actions/runs/40760456769

## Manual training and paired evaluation once the recent checkpoint covers the holdout

The existing manual workflow `.github/workflows/multisport-joint-evaluation.yml` now exposes matching date-bounded inputs: `train_from`, `as_of`, `until`, `max_seasons`, `min_training_seasons`, fixed `research_line`, `min_rows` and an optional strictly pre-cutoff `max_per_position` compute cap. It sends the same `train_from` and `max_seasons` to both training and the independently reconstructed heldout. A strict preflight confirms the archive or recent chronological source checkpoint covers the entire heldout, at least two training seasons exist by default, training seasons are contiguous (no misleading jump from 2018 to 2023), and enough verified player-games exist for training. If missing, it fails BEFORE expensive NUTS fitting and writes a documented receipt.

Suggested NHL or NBA later validation after **actual coverage** extends far enough: `train_from=2023-10-01`, `as_of=2025-10-01`, `until=2026-05-01`, `max_seasons=4`, `min_training_seasons=2`. This uses the 2023-24 and 2024-25 seasons for training and the 2025-26 season as untouched holdout. Choose a relevant stat and fixed noninteger threshold, and a compute-bounded train-only cohort if full-population NUTS is prohibitively expensive. Cutoff is exclusive, so no 2025-26 outcome enters that fit. NHL 2026 playoffs are not eligible, only completed regular-season player-games.

Suggested NFL after 2025 is fully collected: `train_from=2023-09-01`, `as_of=2025-09-01`, `until=2026-03-01`, `max_seasons=4`, `min_training_seasons=2`. This fits the completed 2023 and 2024 seasons and uses the 2025 regular season for an independent holdout. As above, the 2025 games cannot influence the earlier fit.

**Old 2018 research remains reproducible:** direct command-line fitting without a lower bound still supports legacy windows; when testing 2018 explicitly change the new workflow's `train_from`, `min_training_seasons` and dates. Its default recent `train_from=2023-10-01` is intentionally not valid for the old 2018 case. The historical `max_seasons` cap is a *selection limit*, not a request to fabricate seasons that have not been collected.

## What this does NOT prove

- The joint model has NOT been promoted. Last benchmark mixed: Gamma–Poisson was better on several 2018 single-season markets; the joint model won some point estimates. Evidence remains underpowered and potentially date-/stat-dependent.
- More historical rows do not guarantee a lower Brier or log loss. Regularization, player career changes and season effects must be assessed on independent future games.
- Until the new stream reaches 2025/2026 and the source preflight passes, no results should be reported as a full recent-season backtest.

## Source and code references

- Collector: `scripts/population_backfill.py` (`--stream archive|recent`, `--max-days`, `--max-games`, `--max-nfl-seasons`)
- Coverage: `scripts/population_window_check.py`, strict date/season and source-stream checks
- Training: `scripts/joint_population_bayes.py` (`--train-from`, `--max-seasons`, `--as-of`)
- Holdout: `scripts/joint_population_holdout.py` (`--train-from`, `--max-seasons`), verifies frozen manifest and SHA256 training provenance
- Regressions: `tests/test_recent_population_window.py`
