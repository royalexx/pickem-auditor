# Frozen NHL saves posterior in afternoon slates (research sidecar)

## Status and scope

Private GitHub prerelease tag:
`research-nhl-saves-20261029-run40993538888`

The frozen full-history NHL goalie saves model was fitted with an exclusive
2026-10-29 training cutoff and strict all-effect diagnostics. Its uploaded
posterior has four chains and 2000 retained samples per chain. Its SHA-256
digests are pinned in `scripts/nhl_saves_posterior_shadow.py` **and**
`.github/workflows/pickem-daily.yml`, so tag replacement cannot silently
replace the model.

The afternoon GitHub-hosted daily workflow now:

1. Runs all existing collection, model A/B forecasts, verification, ranking,
   and critical historical snapshot persistence unchanged.
2. Downloads the three exact release assets with its scoped GitHub token.
3. Verifies the release SHA-256 digests and strict saved convergence flags.
4. For every *official prospective NHL saves shadow snapshot* only, checks
   pre-event timing, exact model player ID, opponent identity, verified home/
   away orientation, valid market side/line, and a nonoverlapping model cutoff.
5. Calculates `q_over`, `q_under`, `q_push`, and side-specific `q_win`
   directly from the frozen posterior using the existing joint model's
   `forecast()` implementation (1500 Monte Carlo draws).
6. Saves immutable-by-run research results to
   `data/nhl_joint_saves_shadow/YYYY-MM-DD.jsonl` and a receipt at
   `reports/nhl_joint_saves_shadow_receipt.json`. Both are uploaded inside
   the existing `pickem-daily-receipt` workflow artifact.

This is **shadow-only**. No production A/B blend, historical snapshot,
market probabilities, ranking tiers, approved picks or settlement calculations
are changed. The frozen posterior is **not** an independent scouting model B.
A converged fit does **not** prove out-of-sample calibration or market edge.

## Important abstentions

The runner records an *unavailable* sidecar row (rather than guessing) when:
- goalie player_id is absent or not included in the manifest;
- opponent is not one of the fitted NHL opponent identifiers;
- event start time or verified home/away mapping is absent or ambiguous;
- forecast was not originally created before the start, or the newly generated
  forecast would be retrospective;
- the model's last training game is on/after the slate game date;
- the slate is in a later hockey season than this frozen 2026 posterior;
- line or side cannot be parsed without guessing.

No fallback from an absent NHL ID to player name matching is permitted.

If the release cannot be downloaded, its SHA-256 digest changes, or numeric
dependencies cannot be installed, the original daily slate continues
unmodified and the research step reports failure/unavailability. This
optional path is intentionally excluded from the critical daily ranking gate.

## Retrieving the shadow forecasts

Open the afternoon run in GitHub Actions `pickem-daily.yml`; open the
`pickem-daily-receipt` artifact. Inside look for:

- `reports/nhl_joint_saves_shadow_receipt.json` (counts and blocker reasons)
- `data/nhl_joint_saves_shadow/YYYY-MM-DD.jsonl` (one record per saves
  market/side/goalie, with `q_win` when reliably available)

**The posterior is only 2026-season-valid:** retrain and validate a
new posterior before using the next NHL season. It should first undergo
chronologically honest heldout comparisons against the existing A/B
baseline and bookmaker reference probabilities. Convergence is not
predictive validation. Production ranking stays unchanged until then.

## Operational limits

GitHub-hosted runner provisioning/billing has caused prior workflows to
fail *before* their first step. This code cannot repair account-level
runner access. If the daily workflow cannot start, no forecast sidecar
will appear; fix Actions access before treating that as a model problem.

The ongoing full-history NHL hits fit on the self-hosted Windows runner
is entirely separate and remains untouched.
