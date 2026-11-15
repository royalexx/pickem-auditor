# WS3 emergency historical activation

Governing authority: PA-V25-MASTER-2026-11-09 / v1.1, with the user's November 15 bounded O-family activation instruction. Research only. No ranking, betting recommendation, production promotion, NUTS training or merge.

## Adapter contract

`ws1_feature_adapter.py` authenticates the immutable WS1 original manifest, feature pin, archived history manifest, handoff pin, every feature table, all twenty archived historical files, four new raw receipts and native source archives. The native source archive paths are relative to `reports/nfl_20261115_prospective`, rather than the project root. No original source is rewritten or collected again.

Source manifest SHA-256: `5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71`.
Feature pin SHA-256: `35a1bf7fe16acca1e115c7be7bcad2c2464ec27cdf7e799df4f2b31adba24c2a`.

| WS1 source | Existing O input | Binding / missingness |
|---|---|---|
| events + raw 2026 schedule | event | ESPN event -> schedule ESPN field; home/away and week verified; LAR -> LA explicit alias |
| raw 2026 weekly player stats + completed schedule | team_history | Sum observed attempts, carries and sacks_suffered across complete team-game rows; accounting plays = these three counts; no missing-cell zero fill |
| last10_by_contract | player_history | Deduplicate GSIS player/game; preserve actual historical team; 2026 histories with complete team exposures; positive recorded stats establish appearance; all-zero rows alone do not |
| raw players crosswalk | identities | ESPN player ID -> unique GSIS ID; PFR namespace is distinct |
| roster/availability | roster | Source-backed expected QB1 only; no claim of confirmed active status |
| original contracts | contracts | Preserve candidate/quote/book/line/period/event/ESPN player; internal player key GSIS; original records retained |
| source tables / raw receipts | provenance | Exact SHA-256 and actual forecaster availability clocks; no historical pregame publication claim |

The team-history JSONL alone cannot supply sacks. The adapter uses the already archived 2026 raw source containing actual sacks suffered. It does not add zero sacks to the reduced 2016–2025 table. The authenticated 2025 QB file is retained in provenance but excluded from model fitting when its complete team accounting cannot be reconstructed. All excluded historical rows are counted, and all 1,845 original contracts remain in the expanded ledger.

## Conditional participation and product terms

Roster `participation_probability=1` is an explicitly conditional scenario: all modeled roster members appear and the source-backed expected QB1 starts. It is not an estimated unconditional participation probability or confirmed active claim. The frozen model's conditional distributions are retained; unconditional stat probabilities and DNP probabilities are unavailable in the published research handoff. Product-specific settlement/void rules remain unverified. The model's internal void convention does not certify sportsbook terms.

O2 uses the existing route-free targets-per-attempt path. No routes are inferred. The existing residual bucket retains opportunities for omitted players and throwaways. O5 retains its .2/.6/.2 scenario weights and .6/1/1.25 multipliers as uncalibrated sensitivity assumptions. O1 outputs team distributions only, never player prop probabilities.

The sole change to the existing `models.py` is the event-day validation in America/Toronto instead of UTC. Exact UTC kickoff chronology remains enforced. A failing regression test was recorded before the fix. No generative equations, seeds, model identifiers or frozen O5 weights changed. The original mathematical implementation is retained at branch ancestor `8e635c6a94645d985ca9fc18de7a0eef537fd7a0`, SHA-256 `54175541f90ac68b36afd9d0766b790dbacb0a6e01903627e5fafb404ff157cb`; the validator-corrected file SHA-256 is `2d7c5cb16ae8164cb9fa8fc6fa6ca768fb1a9af9cf3798eb52fafd3281befdd0`.

The final adapter uses exact PFR-to-GSIS, game and team joins for `defense_snaps`, never offensive or special-team snaps. Recorded zero-stat appearances require observed positive defensive snaps. Rows whose snaps exceed the model’s opponent accounting exposure remain missing; the original O4 gate abstains whenever any required played history remains incomplete. All three official tackle components retain their distinct meanings.

The authenticated 2024 archive contains actual team plays, passes and rushes, but its historical availability fields are retrospective start-plus-18-hour assumptions. It was inspected and hash-verified, rather than using those times as authenticated source publication clocks. The successful activation uses genuine 2026 raw counts with actual WS1 acquisition receipts.

Current-week completed Thursday rows are excluded and counted because the original model requires prior-week training. Historical end timestamps use the conservative end-of-calendar-day bound, not an invented precise final whistle. No target-date score or outcome is passed to a model.

`ws1_feature_adapter_frozen_v1.py` preserves the exact first-activation adapter bytes (SHA-256 `6f274bedd1d52c57288c5eeaa0cb861ed37fbe9a5f75ec26ee01220f53468f20`); the final adapter adds the defensive join and Toronto date handling. Early forecasts remain immutable.

## Reproducibility and audit

Each run writes an exclusive, content-addressed `report.json`, original receipt and exact `adapter_packet.json` under `reports/nfl_20261115_prospective/opportunity_models/activation_v1/<report SHA>/`. Code hashes, input source hashes, packet hash, start and completion clocks are retained. The completion clock must precede every modeled event kickoff.

`verify_activation.py` independently sums empirical masses to reconstruct Over/Under/Push, mean and variance; replays frozen packets twice; and corrupts required sacks, team accounting, player/game namespace, historical cutoff, kickoff and roster uniqueness. This is a separate numerical pass by the same agent, not independent human or external review.

`ws6_handoff.py` creates 9,225 model-contract rows using canonical original WS1 candidate records, with explicit abstentions and per-game/per-market coverage in `WS6_INDEX.json`. Existing WS6 comparison files and S2/J1/J2/C2 outputs are not modified. No accuracy, superiority, calibration or market-edge claim is made before future independently sourced settlement.

## Rollback

Stop invoking this research adapter and retain its immutable outputs. No production rollback or baseline restoration is needed: this change creates isolated research code and artifacts only.
