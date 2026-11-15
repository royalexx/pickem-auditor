# WS6 — Sunday November 15, 2026 — immutable S2 / C2 / J1 / J2 reconciliation

**Research-only, independently verified. No production approval, outcome scoring, model calibration claims, betting recommendations or Tier promotion.** PR #135 remains draft.

## Authoritative source and immutable comparison lineage

- WS1 corrected canonical original source manifest SHA-256: `5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71`.
- Previous WS6 S2/C2 original-contract ledger SHA-256: `2fff057f2f3ed136136844bd61533fa68d20f41eb836b154bb95732dad77e101`.
- Previous WS6 S2/C2 freeze index SHA-256: `682e9c7f341959b6c9fd913358de44e1f4f358df9b39e0d10c8959a7e5e8610f`.
- WS4 independent original-model 11-event audit SHA-256: `8076017e5012af8d4a51e367bd0ce3ea85a83d619ee574bbab695c36a97d1449`.
- Original WS2 first-population SHA-256: `766245a051b4b3247009040a0c28df82fde285fb237ab40087d510bcfd4efd5d`.
- Original WS5 C2 ledger SHA-256: `4bde5ffe88aabfbfe563b57835889dce88e1df56fff703faa6c3b56a132a927e`.
- Original complete 1,845-observation denominator is unchanged; original quotes, rejections and per-model abstentions are preserved.

### New canonical comparison (Deepnote, immutable, **not committed as a large repository blob**)

Project `9cc31536-93be-44db-bdeb-06fba3f61410`.

`reports/nfl_20261115_ws6_real_comparison/canonical_s2_c2_j1_j2_original_forecast_comparison_v1/`

- **`comparison_ledger_1845.jsonl` SHA-256: `242c4404a6b1505844528ee7096f86060f459df6517f0420f618deef8888fbba`**.
- **`freeze_index.json` SHA-256: `30fa5583a3583e2c01427bcd3bdbf4460be50a1ff664e84b3fd5594c1a5a119d`**.
- `independent_join_audit_report.json` SHA-256: `efc012e0ae6e322b04798e8557704bdcf7ecac55b810017fc7200d0a895ccfc9`.
- `ws4_individual_event_file_receipts.json` SHA-256: `519631bab6de9a9c685ba12652316a2e134667a797f5e9f7aa2f35ce8c7dae34`.

All three small evidence files are mirrored here in GitHub. Independent reproducer: `research/ws6_nfl_sunday_20261115/integrate_ws4_j1_j2_into_s2_c2_v1.py`.

## Independently validated forecasts and exact intersections

| Category | Original contract count |
|---|---:|
| Canonical original observations | 1,845 |
| Source-certified | 1,767 |
| Research-shadow eligible | 1,753 |
| S2 statistical player forecasts | **1,672** |
| C2 market price-derived nonpush reference | **1,767** |
| J1 joint-game player forecasts | **58** |
| J2 joint-game player forecasts | **58** |
| J3 conditional game-script forecasts | **0** |
| Exact S2 + C2 + J1 + J2 matched contracts | **49** |
| J1 + J2 + C2, **without S2** | **9** |
| S2 + C2, **without J1/J2** | **1,623** |
| C2-only, without S2/J1/J2 | **86** |
| Neither S2/C2/J1/J2 (source rejected) | **78** |

All 58 J1/J2 contracts have their exact C2 original-contract reference. The 49 four-way matches all occur in the "pass attempts" market. There are no J1-only or J2-only inconsistencies.

**Why 9 J1/J2 contracts lack S2:** all nine carry the original, immutable S2 abstention reason `WS1_FEATURE_ABSTAIN:INSUFFICIENT_RECENT_VERIFIED_PLAYER_HISTORY` — three sportsbook quotes for Kyle McCord (1:00 p.m.), three for Carson Beck (4:05 p.m.) and three for Fernando Mendoza (4:05 p.m.). These are legitimately different model coverage gates, not identifier collisions.

**Why six pass-attempt S2 contracts have no J1/J2:** six original Jared Goff / Drake Maye quotes belong to the already-started 9:30 a.m. game. WS4 correctly declined to backdate a joint-game simulation.

### Per kickoff window

| ET kickoff | Original | S2 | C2 | J1 | J2 | Four-way intersection |
|---|---:|---:|---:|---:|---:|---:|
| 9:30 a.m. | 126 | 126 | 126 | 0 | 0 | 0 |
| 1:00 p.m. | 1,076 | 978 | 1,019 | 37 | 37 | 34 |
| 4:05 p.m. | 335 | 270 | 324 | 9 | 9 | 3 |
| 4:25 p.m. | 152 | 144 | 144 | 6 | 6 | 6 |
| 8:20 p.m. | 156 | 154 | 154 | 6 | 6 | 6 |
| **Total** | **1,845** | **1,672** | **1,767** | **58** | **58** | **49** |

### Per original market

| Market | Original | S2 | C2 | J1 | J2 |
|---|---:|---:|---:|---:|---:|
| Completions | 67 | 54 | 65 | 0 | 0 |
| Pass attempts | 69 | 55 | 67 | 58 | 58 |
| Passing yards | 96 | 78 | 94 | 0 | 0 |
| Receptions | 568 | 532 | 549 | 0 | 0 |
| Receiving yards | 584 | 547 | 564 | 0 | 0 |
| Rush attempts | 98 | 88 | 91 | 0 | 0 |
| Rushing yards | 249 | 216 | 233 | 0 | 0 |
| Tackles + assists | 114 | 102 | 104 | 0 | 0 |
| **Total** | **1,845** | **1,672** | **1,767** | **58** | **58** |

## Independent execution and numerical gates

- **WS6 newly executed integration:** Deepnote notebook `248ce578511e4e78b2c0e54eb28a6f8e`, successful run `27267e1d-377c-40a8-a566-47a297fb4eeb`; 11 event files, **116/116** original J1/J2 model forecast rows validated with independent calculations.
- WS4 source model run `33231250-59f2-4859-9e8f-94adaa06db4e`; independent WS4 original numerical auditor `0d255b78-fcf9-4c0f-ac2d-60cd933b6c56`; **67/67 regression tests** `b55d19c9-fc2a-4850-b653-bab309daf318`.
- Independent WS6 checked *each event file* against its SHA filename; verified all 11 source-input SHA, output SHA, original quote source receipt/quote ID/event/player/book/stat/line/period identities; all 1,845 original denominator entries in each 11 original event files; each training cutoff and event-specific pregame deadline; and every 4,096-draw model's reconstructed exact PMF over/under/push, mean, variance, selected quantiles, deterministic seed and Monte Carlo SE.
- WS4 first genuine event-model timestamp: **2026-11-15T14:54:22.857760Z**; last: **2026-11-15T14:55:06.282472Z**. The original 9:30 game is not included. This ledger's later assembly time is **not** treated as a prediction timestamp.
- Independent raw history byte SHA matches: 2024 team-game history `4a70391b28826053b45979c15c18fa23590e994e701fb0c2eab98cc182436066`; 2025 QB history `ba1169df7f3a41b486f33b839cc0870f65f30ffac2e29978ea031d7350b3a1bb`; nflverse original identity crosswalk `a8a86df9be83cdf88d0dadb47f09fb4a3c5db326e19b46cf20bdade38e3e024d`.
- No source-history publication-date certainty beyond documented possession; no game-day inactive confirmation; no verified product-specific settlement semantics; model distributions conditional on expected player participation.
- WS4 J3 stays `null` because an authentic frozen pregame game spread was absent. J4 diagnostics do not produce probability columns. Missing models WS3 O1–O5, legacy Engine A/B, Bayesian A/B, strict NUTS and frozen 60/40 remain null.
- WS5 C2 remains a **conditional-on-nonpush sportsbook-price benchmark** only, not a three-way unconditional player-stat model. Never infer `P(Push)` from C2.
- **FULLY_CERTIFIED = 0**. No calibration, performance comparison, postgame settlement, or production merge was carried out. Historical 2024/2025 parameters may be stale; J2 additional variance assumptions remain uncalibrated.

## Merge guard

Draft PR #135 (WS6) and #130 (WS4) remain unmerged. New work is additive to original-source and research artifacts. Independent review is required before production use.
