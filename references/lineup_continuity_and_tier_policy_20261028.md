# Lineup continuity and high-conviction tier definitions — October 28, 2026

## Why "not confirmed" need not mean "no research"

Team-specific past appearances are useful evidence about the **likelihood of availability**, but not official confirmation of a current starting assignment. The afternoon research workflow now performs bounded, verified five-game roster collection for shortlisted sports/stat/team scopes. Source-backed results are stored under `data/verification/YYYY-MM-DD/tendencies` and carried in each conditional research candidate's `lineup_tendency` field. The original forecast, old 60-game shared-context history and official game-day statuses remain unchanged.

- **High continuity**: The athlete appears on all five *completed team* game-active rosters, with complete official collection for the relevant team games and a same-day source timestamp. Shows `historically_likely`, but `confirmed_active=false`.
- **Moderate**: Four of five with the most recent three all present. Needs additional reporting.
- **Low/unknown**: Any relevant recent absence, incomplete collection, older data or unmatched identity. Do not silently treat missing injury feeds as a clean bill of health.
- **NHL goalies**: Recent game roster participation cannot verify tonight's start. Explicit starter confirmation remains required.
- **NBA**: An active roster can include a coach's DNP. This signal describes active-roster continuity, not guaranteed minutes or being one of the starting five.
- **NFL**: A source-verified GSIS player ID and complete prior game-specific rosters are required; a numeric ESPN ID is not interchangeable. Active/dressed does not prove the player starts or participates at a given snap count.

A confirmed current out/doubtful or an unresolved source conflict overrides a high tendency. A questionable status remains uncertain. Current injuries not yet reported remain unknown, not affirmatively ruled out.

## Tier labels no longer mean 56-58%

Legacy numerical bands of 58/57/56% are retained only inside engine-internal diagnostics, to avoid corrupting historical comparisons. **Publishing** an approved Tier now has additional modeled quality floors:

| Tier | Minimum conservative model win probability | Intended interpretation |
| --- | ---: | --- |
| Tier 1 | 90% | Unicorn, exceptionally rare; requires validated blend and full causal evidence |
| Tier 2 | 81% | Elite candidate targeting **over 80% empirical realized hit rate** when actually available |
| Tier 3 | 70% | Remarkable, strongly supported, uncommon pick |
| Screened candidate | Below approved tier floors | Model screening only; not a Tier |

These are provisional **prediction floors**, not demonstrated realized hit rates. The Tier 2 >80% empirical goal can only be certified by prospective settled game-level results (wins / settled opportunities with verified participation), adequate sample sizes, and calibrated holdout evidence. No 81% model estimate *guarantees* 81% actual wins.

`research_ranked_board.json` now labels the lower-probability shortlisted forecasts **Screened Research Candidate** rather than false Tier 2 picks. Stronger inputs may receive clearly labeled `Tier 3 Research Prospect`, `Tier 2 Research Prospect` or `Unicorn Research Prospect` **without any approval**. Prospect never means verified.

`verified_board.json` double-checks the stricter thresholds on top of actual game-day status, same-line quotes, independent source-quality mechanisms, and reliable engines; historical tendency cannot satisfy that game-day status gate.

## Why ranked approved picks may remain rare

The pre-existing absolute model-market gap cap of 8 percentage points can block an 81% model forecast at a near-even market price. This is a genuine structural tradeoff: relaxing this cap should require independent market and causal corroboration, not treating a very large disagreement as proof of value. No artificial probabilities or threshold overrides were applied here.

All new continuity evidence is machine-readable and date/source/roster-linked. No betting transactions, odds quotas, original history or ensemble weights were changed.
