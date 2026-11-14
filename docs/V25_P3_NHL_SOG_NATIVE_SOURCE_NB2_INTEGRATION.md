# V2.5 Priority 3 — NHL SOG original-source reliability and native NB2 shadow

Date: 2026-11-14. Release status: **RESEARCH-ONLY, NOT PRODUCTION CERTIFIED**.

## Diagnosis (verified original workflow)

The legacy \`NHL SOG shadow capture\` Deepnote notebook (notebook \`3fb28f20bc154fa7990c29e195530dd2\`) looks for:

\`pickem_runs/YYYY-MM-DD/*/live_pool_YYYY-MM-DD_afternoon_*.json.gz\`

and the sibling \`all_prepared_props_attempts.json\`. Its script \`scripts/v25_phase1_nhl_nba.py\` expects to compute the **original frozen Phase1 pooled-peer Poisson mean** from that exact source bundle, followed by official current rosters and \`scripts/p15_nhl_sog_nb2_shadow.py\`.

The separate real-source NHL SOG Gamma–Poisson daily collector creates:

\`reports/v25_sog_source_cert_sprint/YYYY-MM-DD/daily_original_gamma_poisson_research_*/daily_research_generation_manifest.json\`

and per-player:

- a canonical original provider HTTP body with the real two-sided offer;
- structured original quote rows with SHA-256;
- a signed official NHL event and two current-team rosters;
- a manifest of independently signed official player-history observations;
- an immutable original quote/identity source receipt;
- immutable Gamma model and forecast snapshot at the original offered line.

**These are not the original Phase1 pooled-peer mean or its attempts ledger.**
Copying or synthesizing an old \`live_pool\` bundle would falsely certify a different source.

## Correct intervention

Keep the legacy Phase1 NB2 experiment and preexisting notebook historical records intact. Add a new, independently versioned study:

\`EXP-V25-NHL-SOG-NB2-NATIVE-PLUGIN-MEAN-20261114\`

For each *genuinely new* source-native Gamma shadow **while its game has not yet started**, verify the entire source graph again, then calculate a fixed-shape NB2 (\`r=4.0\`) using exactly the original shadow's **frozen plugin-Poisson control mean**:

\`\`\`
mu_native = original_model.plugin_rate * original_model.plugin_exposure
variance_nb2 = mu_native + mu_native^2 / 4
P_NB2(Y=k) = Gamma(k+4) / (Gamma(4) k!) *
               (4/(4+mu_native))^4 * (mu_native/(4+mu_native))^k
\`\`\`

This is a **new paired same-mean dispersion sensitivity study**, not a rerun of \`EXP_NHL_SOG_P15_RATE_DISPERSION_NEXT_PROSPECTIVE\` and not a new opportunity-volume model. Poisson control must match the exact original frozen probabilities at the original offered line, including pushes.

### Independent fail-closed gates

1. Exact first frozen real Gamma research attempt + append-only snapshot/shape/rate artifact hashes.
2. Correct original day, real model/quote identity, code revision, official player and crosswalk, input freeze and pregame chronological order.
3. Original provider HTTPS response bytes SHA; exact real book, full-game SOG, native NHL player ID, line, two American prices; separate original pre-resolution structured quote row.
4. C03 signed HMAC official NHL scoreboard original body and two team rosters. HMAC authenticates collector possession; no independent publisher-publication claim. Original NHL scoreboard game ID, two teams, and UTC event start must match. Rosters must be no more than six hours old at native capture; no starter/DNP assumption.
5. All 220 original played-history observations in the illustrated November 13 forecast (or the actual model's count on another day) independently matched and reverified against C03-signed NHL player profile, game log, and official final-game bodies. Preserve the original mandatory 20 peers/200 games; do not lower thresholds or call unsigned sources certified.
6. At least three minutes before the actual game start, **using current system time**; never inject an earlier capture time, backfill or recover a missed forecast.
7. First valid native frozen contract wins. A rerun cannot overwrite/change the original snapshot or create a second shadow under a different capture time.

An absent source emits an append-only abstention/coverage report; never synthesizes an original Phase1 input or forecast.

## Why historical coverage is still constrained

The original November 13 source generator's signed history is a fixed 51-player population. Real recorded failures include repeated insufficient subject history, missing/short peer history, no provider-native NHL player ID and occasional official NHL score/roster HTTP errors. The counts are occurrences, **not unique players or distinct bets**; new audit records retain both occurrences and distinct subjects.

Additional signed history should be collected through a **new, separate, actually live NHL HTTPS capture**, not by signing archived unsigned JSON, reversing settlement results into pregame factors, lowering the peer floor, or silently changing a preregistered study's training population. Any new history cohort must be explicitly versioned and its source collection time recorded. Official team rosters and player identity require original NHL source evidence at the true freeze. The old corpus ages; there is no automatic fresh training claim.

## Deployment protocol

- Pre-register \`config/experiment_specs/EXP_V25_NHL_SOG_NB2_NATIVE_PLUGIN_MEAN_20261114.json\`.
- Run the repository suite; separately verify archived *past* signed source bytes in read-only audit mode **without forecasting them**.
- Deploy the source-native code at an immutable reviewed Git SHA. The Deepnote native fallback may run **after** the existing 16:45 ET Gamma collector, so it can inspect only that same-day original source; the 17:30 ET legacy NB2 collector must not change old input semantics.
- Freeze each new native research record under \`reports/v25_sog_nb2_source_native/YYYY-MM-DD/frozen/<sha256>.json\`. Append a same-day attempt/coverage audit even if no authentic eligible source exists.
- Do not merge research-only validation conclusions with the old Phase1 NB2 cohort. Exclude all outcomes already known before the protocol was frozen.
- Keep scheduled morning settlement, production consensus, Engine A/B, Tier rules, and NUTS pause intact.
- Independently score paired three-way Brier/log-loss and count CRPS on official NHL finals; date-equal and game/date-clustered uncertainty must be precommitted. Review no sooner than 40 genuinely prospective distinct dates; this is not by itself sufficient evidence of power or practical edge.

## Rollback

Remove/disable only the new **research-only native fallback**; preserve signed source archives, frozen forecasts and attempts. Revert its GitHub code commit by reviewed PR after CI. Never rewrite original Phase1 bundles, source possession clocks or settlement history.
