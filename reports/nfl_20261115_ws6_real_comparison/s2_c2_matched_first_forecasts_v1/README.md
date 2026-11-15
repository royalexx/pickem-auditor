# Pick'em Auditor V2.5 — 2026-11-15 independent real S2 × C2 Sunday comparison

**Immutable research comparison V1, not a betting release, player-availability certification, or predictive-performance result.**

## Result

The independent Deepnote WS6 audit **succeeded** in run `df7db56c-9b90-4b88-b530-0ab6dab33978`, using code SHA-256 `ad8825344d956606adc1a5802309fa1068f0a9b291644eb730f84407a091cffb`. The source-original 1,845-contract denominator was retained in a new **create-once** comparison ledger, without overwriting any WS2 or WS5 bytes.

| Final disjoint cohort | Original quote contracts |
|---|---:|
| S2 original conditional-on-appearance player-stat forecast **and** C2 original conditional-on-nonpush market benchmark | **1,672** |
| C2 market benchmark only; S2 abstained | **95** |
| S2 only; C2 missing | **0** |
| Neither model; WS1/C2 source-identity rejection | **78** |
| **Total** | **1,845** |

Of the 95 C2-only records, 81 are in WS1's 1,753 research-shadow player universe but lack valid S2 forecasts; 14 are source-certified backup QB quotes excluded from player predictions. S2 has 173 abstentions: 78 cross-team identity rejections, 14 player research exclusions, 12 independent name-ID mismatches, 55 insufficient recent verified history, and 14 insufficient appearances. C2 has 1,767 authentic frozen market reference probabilities and 78 rejects (54 roster identity failures plus 24 exact-contract conflicts). WS6 independently compared exact contract-ID rejection sets and found them equal to WS1's 78 rejected candidate IDs.

## Source inputs and original-run chronology

| Immutable artifact | SHA-256 |
|---|---|
| WS1 final source manifest | `5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71` |
| WS2 first forecast population index | `cc8049b9335b09d578b9ecae8982616e88c8f0208f06114ab720291413ec85a4` |
| WS2 first forecast population (1,845 rows) | `766245a051b4b3247009040a0c28df82fde285fb237ab40087d510bcfd4efd5d` |
| WS5 original C2 ledger (unchanged) | `4bde5ffe88aabfbfe563b57835889dce88e1df56fff703faa6c3b56a132a927e` |
| WS6 prior C2 conditional-nonpush ledger | `2f6229f126ac8b110798401d491920233fc9ea7525e341ae70f79a35d1a3404b` |
| **WS6 new combined S2/C2 ledger** | **`acb22acc34f2d4ef7241c86e18c31b8140db315e11c37739c51f6e80d0f02019`** |
| **WS6 new combined freeze index** | **`76cd376617e5cdecafcc3237032a17dc8a59356b160a83f417edc123a6982bb6`** |

WS5 C2 was captured at **2026-11-15T14:18:48.776849Z** (09:18:48 ET), strictly before each official Sunday kickoff. Its original independent source run: `11d1d944-1fcc-4192-925a-aeed8c89802e`; subsequent WS6 C2 audit: `f0c4fbd3-d065-480f-b265-5a8bb075a347`.

WS2 S2 has **1,635** valid first forecasts from its original **2026-11-15T14:29:18.370098Z** run, and **37** later newly-forecast contracts from the **2026-11-15T14:32:41.529073Z** run. The later run correctly excludes 126 09:30 kickoff contracts. The immutable first-population assembly was created at 14:36:18Z and is **not** substituted for actual original forecast timestamps. Original source WS2 audit run: `280461f8-acb5-4893-8d72-565614cfad9b`.

**Crucial early-pin correction:** WS2's earliest actual feature freeze at `2026-11-15T14:29:15.089813Z` **precedes** the canonical WS1 feature pin frozen 14:29:58Z. WS6 independently rehashed the 2026 NFL player, games and stats source CSVs used by the early WS2 version (available at 14:26:44Z, 14:26:51Z, and 14:26:49Z respectively). We **did not** retroactively attribute that early run to the later WS1 pin. Older 2024–2025 game histories used by later versions were independently source-receipt checked and are allowed only in pin-backed post-freeze versions. Genuine historical pregame publication chronology is not retroactively certified.

WS6 compared every S2 probability with its **unchanged original run** rather than only with WS2's assembled population; verified each original quote/event/player/book/stat/line/period/source identity; rederived sum-to-one, exact integer push mass, mean and variance from the original empirical PMF; verified stat support, appearance conditioning, training cutoff ≤ feature freeze ≤ forecast creation < affected kickoff. Each C2 probability retains its original no-vig conditional-on-nonpush meaning, with **unconditional over/under/push null**. No C2 value is treated as a player-model probability.

## Match coverage by kickoff window (Eastern Time)

| Kickoff | Matched S2 + C2 | C2-only | Neither |
|---|---:|---:|---:|
| 09:30 | 126 | 0 | 0 |
| 13:00 | 978 | 41 | 57 |
| 16:05 | 270 | 54 | 11 |
| 16:25 | 144 | 0 | 8 |
| 20:20 | 154 | 0 | 2 |
| **Total** | **1,672** | **95** | **78** |

## Match coverage by original market

| Market | S2 + C2 | C2 only | Neither |
|---|---:|---:|---:|
| Completions | 54 | 11 | 2 |
| Pass attempts | 55 | 12 | 2 |
| Passing yards | 78 | 16 | 2 |
| Receiving yards | 547 | 17 | 20 |
| Receptions | 532 | 17 | 19 |
| Rush attempts | 88 | 3 | 7 |
| Rushing yards | 216 | 17 | 16 |
| Tackles + assists | 102 | 2 | 10 |

## Immutable files in the connected Deepnote project

Directory: `reports/nfl_20261115_ws6_real_comparison/s2_c2_matched_first_forecasts_v1/`

- `comparison_ledger.jsonl` — SHA `acb22acc34f2d4ef7241c86e18c31b8140db315e11c37739c51f6e80d0f02019` — 1,845 original contracts, all S2 and C2 numeric fields or explicit nulls
- `matched_original_contracts.jsonl` — SHA `24c98cae4c8ceed92e470190d6ee0c7967c835f1f63ed382f7a04c1a579b7fd3` — 1,672 exact matched original contracts
- `c2_only_original_contracts.jsonl` — SHA `02df380c72cceeea63e84d6b0b34857dfe03e2bf9e4f23f554878ac2d89a632e` — 95 original contracts with model-specific S2 abstention reasons
- `neither_source_original_contracts.jsonl` — SHA `6c52ff1600019bdd39e2cfdcdd90ee48b02e93fdef76dcef5d4d831178a231ab` — all 78 rejected original contracts and rejected source quotes
- `independent_integrity_report.json` — SHA `e160e9e736c09b29155937dd507078d15693cb344b678fc4ce2e023577caf5fc`
- `freeze_index.json` — SHA `76cd376617e5cdecafcc3237032a17dc8a59356b160a83f417edc123a6982bb6`

The smaller index, report, C2-only inventory, and audit code have also been committed to WS6's draft GitHub branch. The full 1,845-row and 1,672-row datasets remain available in connected Deepnote; the GitHub summary does **not** replace the hashed original ledgers.

**No official outcomes were scored.** Full player availability, product settlement rules and original historical pregame publication truth remain uncertified. All statistical forecasts are conditional-on-appearance research-only snapshots. Neither production promotion nor claims of betting edge are allowed. Legacy Engine A/B, Bayesian A/B, strict NUTS, frozen 60/40 and pending independent WS3/WS4 statistics are not imputed from S2 or C2.

**PR #135 must remain draft and unmerged pending independent review.**
