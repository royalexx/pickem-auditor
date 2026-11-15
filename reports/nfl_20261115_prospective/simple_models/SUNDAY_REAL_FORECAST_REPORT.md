# WS2 Sunday real forecast delivery

Status: **prospective research-only partial execution**, with genuine numerical forecasts. No outcomes inspected, no performance claim and no promotion.

The first-forecast population contains all **1,845** original contracts: **1,672 S2 forecasts and 173 S2 abstentions**. S1/S3/S4/S5 each have zero forecasts because source-bound role peers were not supplied; S6 and both S7 variants each have zero because original frozen production controls were not supplied. All model-specific failures and null probability/moment fields remain in the complete population.

| Market | Original contracts | S2 forecasts | S2 abstentions |
|---|---:|---:|---:|
| completions | 67 | 54 | 13 |
| pass attempts | 69 | 55 | 14 |
| passing yards | 96 | 78 | 18 |
| receiving yards | 584 | 547 | 37 |
| receptions | 568 | 532 | 36 |
| rush attempts | 98 | 88 | 10 |
| rushing yards | 249 | 216 | 33 |
| tackles + assists | 114 | 102 | 12 |

Every other model has **0 forecasts in each market** above. These are original book/stat/line contracts, not independent events or players.

The first numerical run created 1,635 forecasts at **14:29:18 UTC** and completed at **14:29:25 UTC**, before 14:30 kickoff, including 126 for that earliest game. It used only already archived WS1 raw CSVs, exact ESPN–GSIS crosswalks and an actual WS2 feature freeze at 14:29:15 UTC; it explicitly did not claim a WS1 feature pin. WS1's canonical pin then became available at 14:29:58 UTC. A second run consumed that pin at 14:32:41 UTC, correctly rejected the started game, and froze 1,546 later-game forecasts. There are 1,509 later versions of earlier predictions and 37 additional contracts. No earlier forecast was overwritten.

Primary window coverage (UTC): 14:30 **126**; 18:00 **978**; 21:05 **270**; 21:25 **144**; November 16 01:20 (Sunday Toronto) **154**. All remaining Sunday windows are frozen; the index assembled at 14:36 is explicitly an assembly, not a new forecast time.

Smoke contract: Amon-Ra St. Brown, BetMGM receiving yards **82.5**, Over **0.43714456036542126**, Under **0.5628554396345787**, Push **0**. Original line/provider and original quote identity are preserved. Mean **82.62960554168716**, variance **1655.0783227372945**, eight observed appearances, four-appearance half-life. Empirical laws retain finite observed support; there is no unseen-tail extrapolation.

## Immutable artifacts

The complete 1,845-row selected population is in the supplied Deepnote project at:

`reports/nfl_20261115_prospective/simple_models/sunday_first_forecasts_v1/first_forecast_population.jsonl`

The original complete version populations remain under `simple_models/live/<timestamp>/forecast_rows.json`. The corresponding first-forecast index is committed alongside this report and remains byte-identical to Deepnote:

- Final index SHA-256: `cc8049b9335b09d578b9ecae8982616e88c8f0208f06114ab720291413ec85a4`
- Complete population SHA-256: `766245a051b4b3247009040a0c28df82fde285fb237ab40087d510bcfd4efd5d`
- Original source-manifest SHA-256: `5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71`
- Canonical WS1 feature-pin SHA-256: `35a1bf7fe16acca1e115c7be7bcad2c2464ec27cdf7e799df4f2b31adba24c2a`
- Independent audit run: `280461f8-acb5-4893-8d72-565614cfad9b`

## Checks and limits

**61 targeted tests** and **22 additional discrete-contract tests** passed. Deepnote numerical runs repeated their pinned targeted suite before inference. The independent post-freeze audit verified **3,181 forecast version rows** for probability sums, exact Over/Under/Push masses, legal empirical support, predictive means/variances and actual pre-kickoff creation. It verified **24 raw feature-source hashes**, the immutable WS1 feature pin, version output hashes, original contract equality across runs, and zero nonfinite raw cells in the early-source numeric fields. Quote source hashes were checked before and after inference. The frozen mathematical library and production policy have no diff against the starting branch.

The input histories lack source-bound role peers; unknown/DNP are excluded, not imputed as zero. A nonzero official stat proves an appearance even when the target stat is zero. All-zero rows without authenticated snaps remain unknown. Exact historical game-final clocks remain null; completed pre-today game identity and actual current source receipt times establish today's admissibility. Historical pregame availability is not retro-certified. Final inactives and product-specific void/payout terms remain unverified, so every prediction is appearance-conditional and uncertified/shadow.

No 60/40 modification, calibrator promotion, Tier release or accuracy/edge claim. Source records and prior forecasts remain unchanged. Code and evidence stay on `research/nfl-nov15-ws2-marginal-models`, draft PR #132.

