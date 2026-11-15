# Pick'em Auditor V2.5 — WS6 corrected Sunday source-only audit

**2026-11-15, America/Toronto. RESEARCH-ONLY. NOT a validated pregame model-forecast cohort or production release.**

## Exact source authority

- WS1: `reports/nfl_20261115_prospective/source_control/HANDOFF_PIN.json`
- Canonical source manifest: `reports/nfl_20261115_prospective/source_control/captures/ab2eebf29ea0dfcf9b2cc4ff5287b898e6b7b15238ea059a11df3ac399ccc6c8.json`
- Manifest bytes SHA-256: `5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71`
- Independent WS1 coverage SHA-256: `2bec43d5dfad53ddb9b662643776db8291b53442a8c42f6f022f9a9d521516a5`
- Original superseded manifest SHA-256: `9a7752e70db7c1d56226847df56f7985c1dd4fba79ae6c3b49acc9e7aad6c150`
- Correct archive root: `reports/nfl_20261115_prospective`.

The canonical manifest and independent coverage report were independently rehashed in WS6 on free Deepnote Basic CPU; all 50 source-referenced raw receipts were rehashed independently, and all 1,845 candidate original-quote fields, source archive hashes, certified event identity and chronology were checked. Rejected records with unresolved ESPN event/start IDs were preserved as rejected, never given an invented identity or promoted.

## Canonical denominator and state ladder

| State | Observations | Interpretation |
|---|---:|---|
| Original observations | 1,845 | Entire original-source universe; no deduplication |
| SOURCE_VERIFIED | 1,767 | Matched roster/game/source identities, NOT production eligibility |
| REJECTED | 78 | Cross-team source identity cannot be certified |
| ABSTAIN | 14 | Source-verified backup QBs, excluded from research predictions |
| CONDITIONAL_ON_PLAYING | 1,753 | Source-bound research shadow cohort; role/injury and terms unresolved |
| FEATURES_VERIFIED | 0 | No independently accepted Sunday model-input historical feature manifest |
| PROSPECTIVE_RESEARCH_FORECAST | 0 | No authentic recorded model probabilities received |
| FULLY_CERTIFIED | 0 | Not reached |

The 1,753 conditional cohort is not certified as participating, does not guarantee injury/inactive status, and is not a model-ready forecast denominator. The source manifest has zero historical source rows, no authenticated model training-cutoff receipts and no captured legacy probabilities. Provider publication truth and product-specific settlement terms remain unverified. This does not prohibit a valid future conditional-on-playing *research* forecast when the actual model inputs and attested pregame time are supplied. It does prohibit inventing such a forecast.

## Kickoff windows and genuine model coverage

| ET kickoff (UTC) | Original | Source-verified | Conditional research | Genuine model predictions |
|---|---:|---:|---:|---:|
| 09:30 (14:30Z) | 126 | 126 | 126 | 0 |
| 13:00 (18:00Z) | 1,076 | 1,019 | 1,019 | 0 |
| 16:05 (21:05Z) | 335 | 324 | 310 | 0 |
| 16:25 (21:25Z) | 152 | 144 | 144 | 0 |
| 20:20 (Nov 16 01:20Z) | 156 | 154 | 154 | 0 |
| **Total** | **1,845** | **1,767** | **1,753** | **0** |

No forecaster may create new prospective snapshots after each event's actual kickoff. The immutable source-only audit was created at **2026-11-15T14:28:16.894727Z**, before the 14:30Z first kickoff; that is the *audit* time, **not** a model forecast timestamp. First and last genuine forecast timestamp: `null`.

## The historical 41 excess candidate IDs

The superseded first capture had 1,804 unique candidate IDs for 1,845 rows. Independent verification classified **41 excess observations as collisions of different original contract keys** (41 two-row collision groups), rather than identical repeated quote observations or a justified deduplication. For example, distinct FanDuel player quotes for Devaughn Vele and Darren Waller shared a first-capture candidate ID and quote ID despite being different players. The final canonical manifest has **1,845 unique candidate IDs and 1,845 unique quote IDs**. All 41 original collisions remain archived with their original quotes and observation indices in the Deepnote collision ledger (SHA below).

## Independent execution

- Fresh 29/29 WS6 regression tests **PASS** in Deepnote run `3601640b-bd69-4064-8367-b7e44d4fd65a`, notebook `dab08b2b2db84f579602cda2e1b9e732`.
- Full 50-receipt, 1,845-observation source-only audit **PASS** in Deepnote run `0d8a28fe-1a9d-4b2f-be80-d02f2393fa32`, notebook `187f5a80507b41e79277ad3d3fa6274c`. Failed earlier exploratory runs were not erased and do not count as passes.
- Canonical source control PIN `cb93979c-0fd3-460f-b3b3-ab5bf0de0706`; corrected WS1 replay `cabc6de4-3ce3-41e2-8bbd-016d65ef7ee4`; WS4 synthetic-only `66d3e578-15ef-4cd4-92bc-6d654aaf361e`.
- The 29 WS6 fixture regressions validate arithmetic, contract matching, mutation rejection, kickoff, integer push, conditional-market semantics and preliminary scorer behavior. They are **not** matched real-forecast validation tests because zero authentic real predictions were available.
- No paid compute, no source collector rerun, no GitHub Actions, no posterior restart.

## Immutably archived comparison and source evidence

The authoritative **source-only** 1,845-row original-contract/nullable-model ledger resides in connected Deepnote project `9cc31536-93be-44db-bdeb-06fba3f61410`:

`reports/nfl_20261115_ws6_real_comparison/canonical_5e17ff057f528a1e_fullsource_audit_v1/`

Exact Deepnote filenames and content SHA-256:
- `original_contract_source_only_ledger.jsonl`: `f13b81b167054d38118b22d1bbb5b45fba8cd266ff3d79030e9beda3a2615c89` (1,845 rows, 3,922,429 bytes).
- `independent_raw_receipts.jsonl`: `16357e59d714cff667b7918d84797fd65b5fe19387165086da77f4885dfca090` (50).
- `old_capture_candidate_id_collisions.jsonl`: `6148080c9c846bd36ca7a5cd0f10a82b5d74d38a8c4f2d0e5c4c7161ed611d89` (41 groups).
- `independent_audit_summary.json`: `6e5f0dc758c79952992289b0b56b6aa1bfbc6b06a6bff2c5657d8f41a99ad8ba`.
- `freeze_index.json`: `507b9d9787b3931774330271b809f8713254f32d22ff6494de89c35d7e68cb86`.

The Deepnote `freeze_index.json` **explicitly says no actual model forecast was frozen**. It is an immutable *source evidence index*, not a completed real-forecast comparison. The first GitHub `freeze_index.json` in this directory is a separate, earlier preflight gate; do not mistake it for the full Deepnote source-only index.

All models S1–S7, O1–O5, J1–J3, C1–C7 and separately versioned sensitivity variants remain **null** on original Sunday contracts without actual input/forecast evidence. J4 is diagnostic, not a standalone forecast. Legacy Engine A, Engine B, Bayesian A/B, strict NUTS, frozen 60/40 and market comparator likewise remain null. No model's probability is substituted for another; no push mass is inferred from a market conditional-nonpush comparator.

## Remaining independently verified blockers

1. WS1's source identity does **not** contain a point-in-time, authenticated player-stat/opportunity **feature manifest and historical receipts** or per-model training cutoff. The corrected source archive explicitly records zero historical input rows. This is the primary forecast generation gate.
2. WS2, WS3 and WS5 have not delivered genuine Sunday source-bound model probabilities; WS4 delivered authentic quote **abstentions**, not forecasts. Report **zero verified forecasts**, not fabricated per-model numerical rejection statistics.
3. Missing verified player availability, source publication clocks and product-specific settlement terms block **FULLY_CERTIFIED** but do **not**, by themselves, bar appropriately conditioned, sourced and chronologically valid research forecasts.
4. Existing WS6 audit code's fully certified quote gate (`availability_certified` and verified product terms) must **not** be used to miscount the research-shadow denominator as zero. The separate source-only ledger retains all 1,753 conditional candidates without upgrading any of them to forecast or production status.
5. Any later authentic forecasts for later games require new immutable model-specific records, verified history/code/feature SHA and attested timestamps before each affected kickoff. Started games remain missing. Do not change earlier snapshots or backdate.
6. After official final outcomes and authorized settlement terms, score *only* matched original contracts using three-way Brier/log loss, nonpush binary comparisons when defined, CRPS for full distributions, calibration, side skew, coverage and paired game-clustered uncertainty. **No game was scored by this audit; one Sunday cannot promote a model.**

**Status: source independently verified, research cohort inventoried, real forecast comparison BLOCKED BY ABSENT AUTHENTIC FORECAST INPUTS/OUTPUTS. PR #135 remains draft and unmerged.**
