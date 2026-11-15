# WS4 — 2026-11-15 genuine prospective original-contract NFL forecast execution

**Branch:** chatgpt/nfl-20261115-ws4-joint-shadow-20261114; existing draft PR #130 remains unmerged.
**Deepnote project:** 9cc31536-93be-44db-bdeb-06fba3f61410.
**Execution notebook:** 34fa673189714831acc72e880549a2f6.
**Status:** PROSPECTIVE RESEARCH SHADOW, UNCERTIFIED. No selection/publishing/production approval.

## Verified actual results

- Authoritative WS1 immutable source: 1,845 original source observations, 1,767 source-certified, 1,753 research-shadow eligible. Corrected source manifest SHA-256: 5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71.
- Retrieved authentic pregame nflverse player identity master; 288/288 shadow-eligible distinct ESPN player IDs uniquely mapped to GSIS (0 ambiguous/unknown).
- Fitted 2024 historical team pace/pass/sack estimates on 544 real team-game records. Observed plays–passes–rushes residual was nonnegative and bounded throughout; explicitly modeled as sack opportunity, with official no-play limitations.
- Fitted 2025 starter-QB passing share from 18,540 original completed-game weekly player rows, with 3 equivalent historical games of source-derived pooled QB-role shrinkage and 4 equivalent games of source-derived team-rate shrinkage. Source sample counts and rates are stored per event. LA (nflverse) to LAR (ESPN) was an explicit verified historical team-code alias, not a synthetic team.
- First successful genuinely original-contract smoke: CAR Bryce Young, BetMGM 36.5 attempts. J1 P(Over)=0.209716796875, J2 P(Over)=0.28076171875. 4,096 draws each. Created 2026-11-15T14:38:32.507537Z, kickoff 18:00Z. Deepnote run cc383d9a-27c0-4185-88c6-13d2039594ca. This first v0.3.0 frozen output is preserved separately.
- Extended original-contract subset through every still-upcoming kickoff window. **11 events, 58 distinct real QB pass-attempt quotes, 58 J1 + 58 J2 = 116 genuine model-specific original-contract forecasts**, 4,096 draws per model and event, zero errors. Created 2026-11-15T14:54:22.857760Z through 2026-11-15T14:55:06.282472Z, strictly before each kickoff. The already-started 9:30 ET game was not retrospectively predicted.
- No original J3 pregame favorite/underdog spread was present: **J3 zero forecasts; explicit abstention.** J4 remains a dependence diagnostic, never a marginal probability generator.

**Actual multi-game Deepnote run:** 33231250-59f2-4859-9e8f-94adaa06db4e.
**Actually independent numerical audit run:** 0d255b78-fcf9-4c0f-ac2d-60cd933b6c56.
**Final 67/67 passed regression/adversarial unit tests:** b55d19c9-fc2a-4850-b653-bab309daf318.

## New immutable originals

All below are exactly-once SHA-addressed immutable JSON, under the connected Deepnote project's folder:

reports/nfl_20261115_prospective/joint_models/real_original_qb_attempts_multievent_v031/

Each JSON includes original input packet, parameters with prior sample sizes, original quote and team/player/event source identities, historical source receipts, output PMFs/CDFs/quantiles, numerical health, 1,845-row original-denominator ledger, explicit abstentions, code SHA and immutable creation time.

| Matchup | ESPN event ID | Distinct quoted QB-attempt lines | J1 | J2 | SHA-256 filename |
|---|---|---:|---:|---:|---|
| CAR–NO | 401873055 | 6 | 6 | 6 | c64ebbadb1eb06ae187d268234012759774f6b90f2a6c37e061f869b788f8465 |
| BUF–NYJ | 401873054 | 6 | 6 | 6 | e2a1b48cc88bdaa789d645bef56907e481d7ccc561dec46aef1636f60006df12 |
| HOU–CLE | 401873056 | 6 | 6 | 6 | c736a6900f8a2503f5f37af106d8464f7340b8025d517042dc1f817f49ce4c3f |
| JAX–TEN | 401873057 | 4 | 4 | 4 | 61377e04e4e08b75383303b8463a21710fff2d5dac377f5b391f382502425a58 |
| MIN–GB | 401873060 | 4 | 4 | 4 | 6da040ddb84cfec6993df3360e0cd1ce1bae8aa7a2f6bb9e4e033429119590cd |
| KC–ATL | 401873058 | 5 | 5 | 5 | 86e87da1e2f690f3476bd162c5184ac45a9b3621a4e4d20c92326d1233704f15 |
| MIA–IND | 401873059 | 6 | 6 | 6 | 74c7cfe8393b4f46374bcea470ce13bda673eb2f83283cc552360bd8bd91ba9a |
| LAR–ARI | 401873061 | 6 | 6 | 6 | 66bf68544c3c3e7060b0bdd7e49728dd5d85a514956180ff9d2a1938275c4bbd |
| SEA–LV | 401873062 | 3 | 3 | 3 | cdb34f1e02c436eeddf2817cd982a509be4cee8e87af1ada0087c2d93cc85eaa |
| SF–DAL | 401873063 | 6 | 6 | 6 | 266e150058c4c810d30ce21864572a10cdfef3b180f1d5df48903ca9bb1781ce |
| PIT–CIN | 401873064 | 6 | 6 | 6 | d6ca302f8a12b540b07163f1f65b1688c6f31d1f1f4bbb55b147d625768d2946 |
| **TOTAL** | **11 games** | **58** | **58** | **58** | |

## Eight original sportsbook market denominators

| Market | Original quotes | Modeled J1 | Modeled J2 | Not modeled |
|---|---:|---:|---:|---:|
| Completions | 67 | 0 | 0 | 67 |
| Pass attempts | 69 | 58 | 58 | 11 |
| Passing yards | 96 | 0 | 0 | 96 |
| Receiving yards | 584 | 0 | 0 | 584 |
| Receptions | 568 | 0 | 0 | 568 |
| Rush attempts | 98 | 0 | 0 | 98 |
| Rushing yards | 249 | 0 | 0 | 249 |
| Tackles + assists | 114 | 0 | 0 | 114 |
| **TOTAL** | **1,845** | **58** | **58** | **1,787** |

## Source/feature provenance and independent QA

- WS1 original canonical SHA-256: 5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71.
- 2024 team-game archive SHA-256: 4a70391b28826053b45979c15c18fa23590e994e701fb0c2eab98cc182436066.
- 2025 player-game archive SHA-256: ba1169df7f3a41b486f33b839cc0870f65f30ffac2e29978ea031d7350b3a1bb.
- NFLverse ESPN ↔ GSIS master SHA-256: a8a86df9be83cdf88d0dadb47f09fb4a3c5db326e19b46cf20bdade38e3e024d.
- Immutable all-event independent audit SHA-256: 8076017e5012af8d4a51e367bd0ce3ea85a83d619ee574bbab695c36a97d1449. The matching JSON is in independent_validation/ws4_real_original_multievent_audit_v031/.

An independent executable auditor, not importing the simulator, tested 11/11 files and 116/116 model rows: original contract, source identity, quote time, model cutoff, forecast-before-kickoff, hash integrity, numeric probability and PMF identity, quantile ordering and MC standard error. Eight cloned source/identity/time/probability/release tamper cases were correctly rejected. Final historical parameter and legacy simulator regression: **67/67 pass**.

The corrected v0.3.1 simulator uses original sportsbook full-game period (without claiming settlement equivalence), source-backed expected-QB passing shares, source-certified but **UNCERTIFIED_SHADOW** classification, explicit kickoff checks, and leaves unmodeled receiver/rusher/defensive categories as residuals rather than fabricating observed conversion rates. Both old synthetic artifacts and the original v0.3.0 canary remain unchanged.

## Fail-closed blockers; no release authority

1. Only QB pass attempts have a defensible presently wired rate/role-input path. For 1,787 other original quotes, the contract remains unmodeled, with explicit original denominator preservation. There is no retrospective construction using Sunday outcomes.
2. Historical team season 2024 and QB season 2025 are not recent 2026 form. No game-day inactive or QB-start **confirmation** was independently certified: depth chart provides an **expected** starter only, so probabilities are role-conditional research estimates rather than certified unconditional probabilities.
3. J2's frozen extra variance assumptions are not independently learned/calibrated; 4,096-draw Monte Carlo precision is not empirical forecast reliability.
4. No certified original pregame spread/favorite for J3. Do not infer a spread from a prop line or future score.
5. No official full-game sportsbook settlement, overtime, DNP, substitution or NFL no-play certification; no market-implied probabilities or payouts invented.
6. J4 dependence diagnostics remain available but are not standalone forecasts and are underpowered for non-QB pathways.
7. Keep existing draft PR #130, frozen V1 baselines, full source/settlement archive, paused NUTS training and all output hashes unchanged. No production promotion, betting recommendations or Tier certification.

**Final state:** IMPLEMENTED; TESTED (67/67); PROSPECTIVE SHADOW (58 original contracts, 116 model rows); INDEPENDENT NUMERICAL PASS; ACTIVE-ROLE CERTIFICATION BLOCKED; OTHER MARKETS BLOCKED BY VERIFIED PARAMETERS; J3 BLOCKED BY ORIGINAL GAME SPREAD; NO RELEASE.
