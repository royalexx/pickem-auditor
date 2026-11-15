# Pick'em Auditor V2.5 — Sunday WS6 independently matched real S2 × C2

**Date:** 2026-11-15 (America/Toronto). **Draft PR #135 only. No production release, model promotion, betting tiers or scoring.**

## Immutable source-linked original-contract ledger

**Canonical source:** `reports/nfl_20261115_prospective/source_control/HANDOFF_PIN.json`  
**Canonical WS1 source manifest file SHA-256:** `5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71`  
**WS1 feature-pin SHA-256:** `35a1bf7fe16acca1e115c7be7bcad2c2464ec27cdf7e799df4f2b31adba24c2a`

**Full 1,845-original-contract, immutable WS6 joined ledger (Deepnote):**

- Project: `9cc31536-93be-44db-bdeb-06fba3f61410`
- Directory: `reports/nfl_20261115_ws6_real_comparison/canonical_s2_c2_first_original_forecast_comparison_v1/`
- `comparison_ledger_1845.jsonl` **SHA-256** `2fff057f2f3ed136136844bd61533fa68d20f41eb836b154bb95732dad77e101`
- `freeze_index.json` **SHA-256** `682e9c7f341959b6c9fd913358de44e1f4f358df9b39e0d10c8959a7e5e8610f`.
- `independent_join_audit_report.json` has per-market and per-kickoff counts and is mirrored in this GitHub directory, as is the freeze index.
- The Deepnote full ledger is deliberately **not** copied into the GitHub repository, to avoid unnecessarily committing a large private research-data payload. Its exact path and SHA-256 are committed in the freeze index.
- Deepnote source-only 1,845-row archive remains separately immutable in `reports/nfl_20261115_ws6_real_comparison/canonical_5e17ff057f528a1e_fullsource_audit_v1/`. The old superseded 0/1,845 capture is preserved, not rewritten.

## Exact matched model coverage

| Set | Original-contract observations |
|---|---:|
| Original denominator | 1,845 |
| SOURCE_VERIFIED | 1,767 |
| Research eligible, conditional-on-playing | 1,753 |
| Genuine S2 player forecasts independently validated | **1,672** |
| C2 market-only nonpush references independently validated | **1,767** |
| **Exact S2 × C2 intersection** | **1,672** |
| C2-only rows | 95 |
| S2-only rows | 0 |
| Neither | 78 |
| FULLY_CERTIFIED | 0 |

C2-only rows consist of **81 research-eligible S2 abstentions and 14 source-verified backup QB exclusions**. The 78 neither rows are WS1 source-identity rejections. Every original quote and row is retained, with no deduplication.

S2 abstentions: 78 cross-team identity; 14 research/backup exclusion; 12 independent player name/ID mismatch; 55 insufficient recent verified history; 14 insufficient player appearances. These sum to 173.

### Per-market original matching

| Original market | Original | S2 statistical | C2 market reference | Exact matched |
|---|---:|---:|---:|---:|
| Completions | 67 | 54 | 65 | 54 |
| Pass attempts | 69 | 55 | 67 | 55 |
| Passing yards | 96 | 78 | 94 | 78 |
| Receiving yards | 584 | 547 | 564 | 547 |
| Receptions | 568 | 532 | 549 | 532 |
| Rush attempts | 98 | 88 | 91 | 88 |
| Rushing yards | 249 | 216 | 233 | 216 |
| Tackles + assists | 114 | 102 | 104 | 102 |
| **Total** | **1,845** | **1,672** | **1,767** | **1,672** |

### Original kickoff deadline windows

| America/Toronto ET | Original | S2 valid pregame | C2 valid pregame | Matched |
|---|---:|---:|---:|---:|
| 9:30 AM | 126 | 126 | 126 | 126 |
| 1:00 PM | 1,076 | 978 | 1,019 | 978 |
| 4:05 PM | 335 | 270 | 324 | 270 |
| 4:25 PM | 152 | 144 | 144 | 144 |
| 8:20 PM | 156 | 154 | 154 | 154 |

**Actual source/model forecast creation clocks, not compilation clocks:**

- WS5 C2 original reference: `2026-11-15T14:18:48.776849Z` (9:18:48 AM ET), all applicable events pregame.
- WS2 S2 first-model forecast: `2026-11-15T14:29:18.370098Z` (9:29:18 AM ET), first cohort before 9:30 kickoff.
- WS2 S2 last first-forecast version: `2026-11-15T14:32:41.529073Z` (9:32:41 AM ET), applied **only to later-starting events**.
- Final WS1 feature pin was **published** at `14:30:05.331698Z`, after the first kickoff. Original early S2 run was independently checked against its separately archived received-before-kickoff history files; it was **not retroactively linked** to a later feature-pin publication.

## Source inputs and model code

- S2 first-population SHA-256: `766245a051b4b3247009040a0c28df82fde285fb237ab40087d510bcfd4efd5d`; first index SHA-256 `cc8049b9335b09d578b9ecae8982616e88c8f0208f06114ab720291413ec85a4`.
- Original C2 WS5 ledger SHA-256: `4bde5ffe88aabfbfe563b57835889dce88e1df56fff703faa6c3b56a132a927e`.
- S2 first-model code commits: `cdf2e8c9029217ee26fb28d21f7ecd6e8aaeeb81` (1,635 rows); `d926113b63e0207693aed70774844299b467a8dc` (37 later-event rows).
- C2 original code commit: `81049c04359f609986c6e76813daee81a0295954`, independent model/version identity `C2:32f05d479a99021680f7d9467910c34af4ced553c76a065b42944a5e1df8eedc` / `nfl-ws5-calibration/1.0.0`.

## Independent WS6 verification

- **29/29** existing WS6 regressions PASS, Deepnote `3601640b-bd69-4064-8367-b7e44d4fd65a`.
- Canonical source manifest and independent WS1 coverage SHA exact, **50/50** original source receipt bytes verified, **1,845** original offers checked, Deepnote `0d8a28fe-1a9d-4b2f-be80-d02f2393fa32`.
- Archived ESPN roster and depth source validated independently for **24 teams, 1,767 accepted player/team identities, 317 QB starters and 14 backup-QB exclusions**, with no discrepancies, Deepnote `9f2f591b-f8ea-41fa-a683-e27bfc856677`.
- **1,672 S2** empirical mass normalization, exact line threshold (including integer push), conditional nonpush and first/second moment checks; original quote matching, historical availability and individual kickoff chronology, Deepnote `69ce1c64-38ef-404b-bc8b-7e915724c1d3` (**PASS**).
- **1,767 C2** two-sided original American-odds devig probability checks, exact source and original-contract identity, and separate C2 kickoff/source lineages, Deepnote first C2 integration evidence in `reports/nfl_20261115_ws6_real_comparison/c2_market_benchmark_4bde5ffe88aa_v1/`; subsequent **full exact S2/C2 original-contract match** and SHA seal, Deepnote `dcdae75c-c62f-442c-86e0-5f5cdf0663eb` (**PASS, zero identity/numerical errors**).
- No GitHub Actions, paid machine, source recollection, model rewrite, backdating or postgame scoring.

## Interpretation and remaining uncertified constraints

S2 is a genuine player-appearance-conditioned empirical **statistical forecast** with three-way Over/Under/Push probabilities and a mean. C2 is **not** an independent player-statistical model: it is the archived book's two-sided price-derived `P(Over | no push)`; all C2 unconditional three-way probabilities, mean and push mass remain **null**. Preserve that distinction when later scoring, ranking, or plotting.

The models are **not FULLY_CERTIFIED**: player final inactives, DNP settlement terms, actual upstream publication-time truth and older historical original pregame availability were not independently established. No comparison performance or edge claim follows from this pregame matching audit, and one Sunday is insufficient for automatic promotion. Production ensemble and existing tiers are untouched. **Draft PR #135 remains unmerged.**
