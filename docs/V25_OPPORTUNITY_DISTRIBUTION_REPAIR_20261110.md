# Opportunity distribution repair — November 10, 2026

This replaces the earlier recommendation to proceed directly to a more elaborate allocator. The forensic audit found incorrect QB opportunity sharing, receiver exposure/residual mistakes, defensive component mean distortion and unsupported tail confidence. The implementation follows rules 1, 4, 7–9 and 11–16 of `docs/research/DIRECTIONAL_ACCURACY_RESEARCH_BASELINE_20261108.md`.

## Research default and challenger

**Default:** appearance-matched, role-shrunk marginal distributions for eight count markets (`simple_control` in the immutable replay, retained under that name to avoid rewriting evidence). `research_default_draws` exposes only these counts. Means and predictive variance use actual observed player-game rows, including observed zeros; missing records do not become zero or proof of inactivity. Predictive game variance does not disappear as the number of historical games grows. These are individual marginal forecasts, not a valid joint parlay simulator or an availability forecast.

**Yards:** retain existing yard models. The three proposed yard replacements are explicitly abstained by the default interface. Empirical yard candidates and conditional donor challengers remain available for comparisons, but receiving and rushing yard Brier scores worsened. Integer yard lines are rejected by this replay's continuous yard approximation rather than inventing a push probability.

**Challenger:** a physically conserved joint opportunity simulator. QB attempts follow a most-recent-primary proxy / switch / unknown-QB mixture fitted from past primary transitions, rather than splitting workload among stale QB historical averages. Passes with no target, targets to unseen recipients and attempts for unknown QBs remain separate. Receiver weights use the player's matched appearance-game attempt exposures. Unseen-receiver mass is learned by predicting recipient coverage at earlier historical origins; it is not the historical targets of departed players. Rushing attempts similarly separate modeled RBs, unseen RBs and non-RB carries. Defensive solo, assist and with-assist categories have directly fitted means and sum to the source-compatible total.

The first complete 2024 comparison rejected the joint receiver model as a count-skill replacement. It underpredicted target means and lost CRPS to the simpler marginal control. The default therefore retains the simpler model, rather than silently selecting the most elaborate architecture. The joint QB/receiver/RB and defensive component code remains a separately labeled challenger. Its physical checks must not be presented as demonstrated predictive improvement.

The original 2024 data is development-exposed. Nothing here promotes probabilities, tiers, schedules, NUTS fits or the production 60/40 model. Current player eligibility and availability still require genuine point-in-time source evidence. The replay uses past appearances as an explicitly uncertified research candidate proxy, not a verified current roster. New/unknown players abstain rather than becoming fabricated zero-target Unders.

## Runnable entrypoints

An immutable as-of snapshot has exactly `schema`, `week`, `history`, and `schedule`. The schema is `v25-opportunity-asof-v1`. Historical team-game records contain `event_id`, `team`, `opponent`, `season`, `week`, `pass_attempts`, `rush_attempts` and observed `players`. Current schedule records contain only event/team/opponent/week. The forecaster rejects current/future historical rows and extra schedule/outcome fields.

```bash
python scripts/v25_phase2_nfl_research.py \
  --mode opportunity-repair --input examples/v25_opportunity_repair_synthetic_asof.json --output reports/opportunity_repair_synthetic_receipt.json \
  --code-commit "$(git rev-parse HEAD)" --n-scenarios 512
```

For a sealed 18-week replay against original archived forecasts:

```bash
python scripts/v25_opportunity_repair_replay.py run \
  --source player_stats_2021_2024.json.gz \
  --root pickem_runs --output-dir NEW_IMMUTABLE_RUN_DIRECTORY --samples 512
```

Alternatively, replace `--root` with `--audit-export archival_export.json` to use the verified forensic export's exact original contracts and strict outcomes. That route records the original file hashes as **references** and separately hashes the evaluated contract table. It never fabricates replacement original files or claims reconstructed bytes have the original hash.

The forecast child process sees only one past-only snapshot. Model source bytes are frozen before the run and each child executes that frozen code copy, preventing a mixed-code campaign if development continues. Each week saves compressed as-of inputs, all sample arrays, complete calibration parameter preimages and offered probabilities before looking up current results. Settlements use exact event/team/player/stat identity. Full line identity is retained in scoring keys. Unmatched and push states remain explicit. Existing files cannot be overwritten.

The independent audit reads only saved files and performs no fitting:

```bash
python scripts/v25_opportunity_repair_receipt_audit.py \
  --folder NEW_IMMUTABLE_RUN_DIRECTORY --audit-export archival_export.json \
  --output NEW_IMMUTABLE_RUN_DIRECTORY/INDEPENDENT_FROZEN_AUDIT.json
```

## Other audit repairs

- Target calibrator `raw` and insufficient-history paths now preserve 0, 0.5 and 1 exactly. `calibration_active` and `exact_raw_identity` distinguish warmup from a learned map.
- All-volume calibration receipts retain full parameter preimages and NumPy version, rather than only unreconstructable fit hashes.
- `nfl_contract_settlement.py` rejects duplicate or nonfinite outcomes and binds team identity. It does not relabel missing rows as zero.
- The route-aware experimental allocator retains empirical between-game logit SD rather than dividing it by sqrt(n). This fixes a predictive-variance/standard-error confusion; the actual route-aware model still lacks an independent historical acceptance test.
- Empty unidentified zero-only provider placeholder rows are explicitly quarantined. A nonzero unidentified record is a hard rejection, not a discarded observation.

## Acceptance boundary

The completed 18-week, 512-scenario v2 replay has receipt `e7d06fd789c8f7012e79c2800372c6310ca82bf55014eada67dc7108bfc9e6db`. The independent audit passed 214,563 frozen probability scores, 71,521 raw distribution scores and 278,528 team scenarios. Full inputs, sample arrays, fitted calibration maps and rejected experiments are retained in the accompanying evidence packet. No current-source certification is claimed.

On identical settled contracts, the simple count control reduced pass-attempt mean error from -5.029 to -1.352 (501 rows; Brier 0.3172 to 0.2515), targets from -0.485 to -0.116 (4,065; 0.2497 to 0.2391), receptions from -0.345 to -0.086 (4,065; 0.2465 to 0.2359), and carries from -1.879 to -0.202 (1,171; 0.2751 to 0.2458). These are development comparisons against raw archived probabilities, not a prospective edge certificate. Tackles plus assists still has negative mean error (-0.191 versus original +0.072); the count repair is not uniformly superior on every metric.

Joint-minus-simple count CRPS was +0.0820 for targets (week-cluster descriptive 95% interval +0.0685 to +0.0944) and +0.2835 for carries (+0.2204 to +0.3477); lower CRPS is better. The physically conserved joint model therefore failed the predictive acceptance comparison. Raw 80%+ target forecasts from the simple control still hit only 71.4% (84 rows). Do not restore high-confidence tiers or force a particular Over/Under mix.

Keep model identities, full candidate coverage, matched contracts, signed mean error, count CRPS, interval coverage, Brier/log loss, side concentration and selective hit/claimed-confidence discrepancies separate. Calibration changes event probabilities, not underlying count samples. Compare the joint challenger with the simpler default using identical contracts; preserve failures. An originally collected future data window and source-certified availability are required for promotion. No minimum number of 80% selections is an acceptance target.
