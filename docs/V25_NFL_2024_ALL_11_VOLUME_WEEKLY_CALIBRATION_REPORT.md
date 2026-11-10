# NFL 2024 — all 11 volume markets, 18-week global/role calibration audit

**RESEARCH ONLY — NOT VERIFIED SPORTSBOOK PRICES OR PRODUCTION VALIDATION.**

Frozen research receipt: `d18906ee4fef21ca89572a3b30d55a0497d69cca2517967234c72465d81d2c65`. Independent audit receipt: `9f0be6a3047514ab993fad13c2a9e5244a3f341d7db5c7869f458f418fe5f9bb`.

The source is the archived 2024 multi-market model's fixed synthetic research lines and forecast probabilities, not the new Phase 2 target-only participation/snap simulator. Three probability columns are evaluated for each underlying source: **Raw** archived, **Global** Platt logistic fit on *previous 2024 weeks in the same market*, and **Role** (market-global plus shrunken QB/RB/WR/TE/DL/LB/DB intercepts). The new participation model has not been trained for these other 10 markets.

Initial market-level calibration is the **exact raw identity** until at least 80 prior settled labels are available; role adjustment needs at least 40 prior examples of that role. Week 1 has no 2024 history and all three methods coincide. A week is fully calibrated and frozen before revealing its outcomes. No 2024 current/future outcomes are supplied to the fit. Confidence ≥80% is calculated separately per model and method, so the cohorts differ.

**Sample:** 57,223 archive candidates across 18 weeks; 38,809 separately recorded graded outcomes. Missing outcomes are abstentions, not zeros.

## Full-season overview: same contracts, probability scores

| Volume market | Archived candidate n | Graded n | Raw Brier | Global Brier | Role Brier | Role − Global Brier |
|---|---:|---:|---:|---:|---:|---:|
| pass attempts | 868 | 547 | 0.3211 | 0.2568 | 0.2567 | -0.00009 |
| completions | 868 | 547 | 0.3068 | 0.2549 | 0.2549 | -0.00004 |
| passing yards | 868 | 547 | 0.2829 | 0.2520 | 0.2520 | -0.00002 |
| targets | 6,186 | 4,266 | 0.2489 | 0.2422 | 0.2412 | -0.00092 |
| receptions | 6,186 | 4,266 | 0.2454 | 0.2397 | 0.2395 | -0.00021 |
| receiving yards | 6,186 | 4,266 | 0.2456 | 0.2424 | 0.2409 | -0.00142 |
| carries | 2,570 | 1,769 | 0.2637 | 0.2463 | 0.2453 | -0.00101 |
| rushing yards | 2,570 | 1,769 | 0.2585 | 0.2480 | 0.2478 | -0.00018 |
| tackles + assists | 10,307 | 6,944 | 0.2449 | 0.2436 | 0.2421 | -0.00151 |
| solo tackles | 10,307 | 6,944 | 0.2407 | 0.2384 | 0.2368 | -0.00158 |
| tackle assists | 10,307 | 6,944 | 0.2485 | 0.2397 | 0.2392 | -0.00045 |

All three probability methods score the **same eligible player/game/line contracts** within each market; negative differences in Brier favor the calibrated method. Do not compare a different market's Brier as evidence of better forecasting of that stat.

## Full-season ≥80% hit-rate and selection-count comparison

| Market | Raw hit (n) | Global hit (n) | Role hit (n) | Raw Under share | Global Under share | Role Under share |
|---|---:|---:|---:|---:|---:|---:|
| pass attempts | 53.7% (216) | 58.3% (36) | 58.3% (36) | 90.7% | 80.6% | 80.6% |
| completions | 56.2% (178) | 50.0% (32) | 50.0% (32) | 89.3% | 75.0% | 75.0% |
| passing yards | 59.9% (167) | 66.7% (48) | 65.2% (46) | 88.6% | 87.5% | 87.0% |
| targets | 70.8% (295) | 75.4% (57) | 73.4% (64) | 94.9% | 91.2% | 92.2% |
| receptions | 66.1% (307) | 77.3% (44) | 73.5% (49) | 97.1% | 86.4% | 85.7% |
| receiving yards | 60.6% (94) | 64.3% (14) | 68.8% (16) | 97.9% | 92.9% | 87.5% |
| carries | 62.4% (388) | 54.2% (48) | 57.8% (45) | 90.2% | 89.6% | 88.9% |
| rushing yards | 61.1% (203) | 59.3% (27) | 60.0% (25) | 93.6% | 85.2% | 84.0% |
| tackles + assists | 72.6% (197) | 70.9% (55) | 72.9% (59) | 51.8% | 58.2% | 52.5% |
| solo tackles | 71.5% (575) | 63.7% (102) | 66.7% (108) | 93.7% | 84.3% | 83.3% |
| tackle assists | 67.5% (1202) | 56.5% (85) | 55.3% (85) | 96.7% | 97.6% | 96.5% |

## Week-by-week scores across all volume markets (sample-weighted pool)

The pooled weekly score weights contracts equally and is therefore disproportionately influenced by large defensive cohorts. Market-specific tables below remain the main decision tool. Each calibration method has the same graded n per week. Hit rates are **selective**: changes in n may explain higher percentages.

| Wk | N graded | Raw Brier | Global Brier | Role Brier | Raw ≥80% hit (n) | Global ≥80% hit (n) | Role ≥80% hit (n) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1,735 | 0.2436 | 0.2436 | 0.2436 | 64.4% (208) | 64.4% (208) | 64.4% (208) |
| 2 | 1,530 | 0.2674 | 0.2587 | 0.2571 | 61.1% (283) | 63.0% (184) | 64.2% (187) |
| 3 | 1,664 | 0.2446 | 0.2392 | 0.2401 | 66.3% (255) | 66.7% (18) | 64.0% (25) |
| 4 | 2,148 | 0.2498 | 0.2428 | 0.2415 | 63.9% (233) | 53.3% (30) | 54.8% (31) |
| 5 | 1,960 | 0.2454 | 0.2435 | 0.2435 | 73.6% (144) | 77.8% (9) | 66.7% (12) |
| 6 | 1,999 | 0.2446 | 0.2403 | 0.2393 | 68.5% (168) | 66.7% (18) | 66.7% (18) |
| 7 | 2,160 | 0.2374 | 0.2358 | 0.2354 | 77.2% (167) | 71.4% (7) | 60.0% (10) |
| 8 | 2,443 | 0.2568 | 0.2477 | 0.2470 | 59.3% (226) | 47.6% (21) | 47.1% (17) |
| 9 | 2,270 | 0.2482 | 0.2416 | 0.2403 | 68.8% (202) | 53.8% (13) | 61.5% (13) |
| 10 | 2,131 | 0.2440 | 0.2385 | 0.2365 | 70.8% (185) | 80.0% (10) | 80.0% (10) |
| 11 | 2,203 | 0.2540 | 0.2433 | 0.2415 | 65.9% (211) | 57.1% (7) | 62.5% (8) |
| 12 | 1,998 | 0.2512 | 0.2408 | 0.2393 | 63.1% (198) | 66.7% (3) | 66.7% (3) |
| 13 | 2,460 | 0.2530 | 0.2424 | 0.2412 | 64.6% (209) | 80.0% (5) | 83.3% (6) |
| 14 | 1,971 | 0.2450 | 0.2387 | 0.2380 | 66.9% (175) | 66.7% (3) | 80.0% (5) |
| 15 | 2,547 | 0.2403 | 0.2358 | 0.2349 | 71.3% (244) | 100.0% (1) | 100.0% (1) |
| 16 | 2,530 | 0.2527 | 0.2410 | 0.2415 | 65.4% (231) | 100.0% (4) | 100.0% (4) |
| 17 | 2,604 | 0.2550 | 0.2426 | 0.2398 | 62.3% (260) | 80.0% (5) | 75.0% (4) |
| 18 | 2,456 | 0.2549 | 0.2442 | 0.2434 | 60.1% (223) | 50.0% (2) | 100.0% (3) |

## Individual market results: complete 18-week tables

### Pass Attempts

Original candidates 868; graded 547; missing 321. Lower Brier is better. Values at ≥80% show actual accuracy and number selected.

| Wk | Graded | Raw Brier | Global Brier | Role Brier | Raw ≥80% hit (n) | Global ≥80% hit (n) | Role ≥80% hit (n) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 25 | 0.3091 | 0.3091 | 0.3091 | 61.5% (13) | 61.5% (13) | 61.5% (13) |
| 2 | 23 | 0.2267 | 0.2267 | 0.2267 | 100.0% (2) | 100.0% (2) | 100.0% (2) |
| 3 | 24 | 0.3204 | 0.3204 | 0.3204 | 40.0% (5) | 40.0% (5) | 40.0% (5) |
| 4 | 32 | 0.2744 | 0.2744 | 0.2744 | 44.4% (9) | 44.4% (9) | 44.4% (9) |
| 5 | 29 | 0.2133 | 0.2138 | 0.2137 | 66.7% (9) | 100.0% (2) | 100.0% (2) |
| 6 | 28 | 0.2677 | 0.2397 | 0.2401 | 75.0% (8) | 100.0% (1) | 100.0% (1) |
| 7 | 30 | 0.2931 | 0.2524 | 0.2532 | 60.0% (10) | — (0) | — (0) |
| 8 | 33 | 0.3369 | 0.2757 | 0.2756 | 45.5% (11) | 33.3% (3) | 33.3% (3) |
| 9 | 31 | 0.2285 | 0.2231 | 0.2233 | 75.0% (12) | — (0) | — (0) |
| 10 | 28 | 0.2907 | 0.2326 | 0.2324 | 85.7% (7) | 100.0% (1) | 100.0% (1) |
| 11 | 31 | 0.3953 | 0.2786 | 0.2779 | 27.3% (11) | — (0) | — (0) |
| 12 | 26 | 0.3856 | 0.2498 | 0.2489 | 53.3% (15) | — (0) | — (0) |
| 13 | 34 | 0.4336 | 0.2711 | 0.2701 | 26.7% (15) | — (0) | — (0) |
| 14 | 29 | 0.4019 | 0.2734 | 0.2732 | 23.1% (13) | — (0) | — (0) |
| 15 | 39 | 0.3076 | 0.2437 | 0.2443 | 61.9% (21) | — (0) | — (0) |
| 16 | 34 | 0.3874 | 0.2459 | 0.2453 | 50.0% (20) | — (0) | — (0) |
| 17 | 38 | 0.3577 | 0.2535 | 0.2536 | 59.1% (22) | — (0) | — (0) |
| 18 | 33 | 0.3024 | 0.2508 | 0.2508 | 61.5% (13) | — (0) | — (0) |

**Season-wide threshold detail** (sample-size changes are material):

| Confidence threshold | Raw hit (n) | Global hit (n) | Role hit (n) |
|---|---:|---:|---:|
| ≥70% | 52.6% (304) | 60.0% (75) | 60.0% (75) |
| ≥80% | 53.7% (216) | 58.3% (36) | 58.3% (36) |
| ≥90% | 55.2% (145) | 50.0% (14) | 50.0% (14) |
| ≥95% | 58.2% (110) | 55.6% (9) | 55.6% (9) |

**Source-model controls:**
Archived hurdle raw Brier 0.3202; hurdle-global 0.2561; hurdle-role 0.2560.
Archived no-refit control raw Brier 0.3171; no-refit-global 0.2558; no-refit-role 0.2558.

Role calibration minus global Brier: -0.00009; clustered descriptive interval [-0.00033, 0.00013].

### Completions

Original candidates 868; graded 547; missing 321. Lower Brier is better. Values at ≥80% show actual accuracy and number selected.

| Wk | Graded | Raw Brier | Global Brier | Role Brier | Raw ≥80% hit (n) | Global ≥80% hit (n) | Role ≥80% hit (n) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 25 | 0.3414 | 0.3414 | 0.3414 | 53.8% (13) | 53.8% (13) | 53.8% (13) |
| 2 | 23 | 0.1958 | 0.1958 | 0.1958 | 100.0% (1) | 100.0% (1) | 100.0% (1) |
| 3 | 24 | 0.2613 | 0.2613 | 0.2613 | 50.0% (4) | 50.0% (4) | 50.0% (4) |
| 4 | 32 | 0.2902 | 0.2902 | 0.2902 | 44.4% (9) | 44.4% (9) | 44.4% (9) |
| 5 | 29 | 0.1952 | 0.2128 | 0.2129 | 77.8% (9) | — (0) | — (0) |
| 6 | 28 | 0.3365 | 0.2674 | 0.2674 | 57.1% (7) | 100.0% (1) | 100.0% (1) |
| 7 | 30 | 0.2225 | 0.2210 | 0.2207 | 87.5% (8) | — (0) | — (0) |
| 8 | 33 | 0.2742 | 0.2571 | 0.2581 | 66.7% (9) | 0.0% (1) | 0.0% (1) |
| 9 | 31 | 0.2505 | 0.2359 | 0.2359 | 72.7% (11) | 0.0% (1) | 0.0% (1) |
| 10 | 28 | 0.2719 | 0.2332 | 0.2332 | 75.0% (8) | 100.0% (1) | 100.0% (1) |
| 11 | 31 | 0.3345 | 0.2766 | 0.2766 | 50.0% (8) | 0.0% (1) | 0.0% (1) |
| 12 | 26 | 0.3976 | 0.2655 | 0.2648 | 45.5% (11) | — (0) | — (0) |
| 13 | 34 | 0.4341 | 0.2924 | 0.2920 | 20.0% (10) | — (0) | — (0) |
| 14 | 29 | 0.3246 | 0.2563 | 0.2562 | 33.3% (9) | — (0) | — (0) |
| 15 | 39 | 0.3190 | 0.2459 | 0.2460 | 56.2% (16) | — (0) | — (0) |
| 16 | 34 | 0.3555 | 0.2424 | 0.2419 | 50.0% (16) | — (0) | — (0) |
| 17 | 38 | 0.3544 | 0.2478 | 0.2480 | 61.1% (18) | — (0) | — (0) |
| 18 | 33 | 0.3072 | 0.2464 | 0.2463 | 54.5% (11) | — (0) | — (0) |

**Season-wide threshold detail** (sample-size changes are material):

| Confidence threshold | Raw hit (n) | Global hit (n) | Role hit (n) |
|---|---:|---:|---:|
| ≥70% | 53.4% (262) | 64.9% (74) | 64.4% (73) |
| ≥80% | 56.2% (178) | 50.0% (32) | 50.0% (32) |
| ≥90% | 59.7% (119) | 50.0% (16) | 50.0% (16) |
| ≥95% | 60.7% (84) | 36.4% (11) | 36.4% (11) |

**Source-model controls:**
Archived hurdle raw Brier 0.3065; hurdle-global 0.2547; hurdle-role 0.2547.
Archived no-refit control raw Brier 0.3061; no-refit-global 0.2548; no-refit-role 0.2548.

Role calibration minus global Brier: -0.00004; clustered descriptive interval [-0.00020, 0.00013].

### Passing Yards

Original candidates 868; graded 547; missing 321. Lower Brier is better. Values at ≥80% show actual accuracy and number selected.

| Wk | Graded | Raw Brier | Global Brier | Role Brier | Raw ≥80% hit (n) | Global ≥80% hit (n) | Role ≥80% hit (n) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 25 | 0.2543 | 0.2543 | 0.2543 | 69.2% (13) | 69.2% (13) | 69.2% (13) |
| 2 | 23 | 0.2616 | 0.2616 | 0.2616 | 100.0% (1) | 100.0% (1) | 100.0% (1) |
| 3 | 24 | 0.2490 | 0.2490 | 0.2490 | 100.0% (2) | 100.0% (2) | 100.0% (2) |
| 4 | 32 | 0.2688 | 0.2688 | 0.2688 | 40.0% (5) | 40.0% (5) | 40.0% (5) |
| 5 | 29 | 0.1944 | 0.2038 | 0.2044 | 85.7% (7) | 100.0% (3) | 100.0% (3) |
| 6 | 28 | 0.2769 | 0.2584 | 0.2583 | 75.0% (4) | 50.0% (2) | 50.0% (2) |
| 7 | 30 | 0.1700 | 0.1941 | 0.1952 | 100.0% (7) | 100.0% (4) | 100.0% (2) |
| 8 | 33 | 0.2543 | 0.2425 | 0.2425 | 70.0% (10) | 60.0% (5) | 60.0% (5) |
| 9 | 31 | 0.2641 | 0.2470 | 0.2463 | 66.7% (6) | 33.3% (3) | 33.3% (3) |
| 10 | 28 | 0.3100 | 0.2753 | 0.2752 | 50.0% (8) | 75.0% (4) | 75.0% (4) |
| 11 | 31 | 0.3826 | 0.3165 | 0.3157 | 22.2% (9) | 33.3% (3) | 33.3% (3) |
| 12 | 26 | 0.4089 | 0.2838 | 0.2821 | 41.7% (12) | 0.0% (1) | 0.0% (1) |
| 13 | 34 | 0.3464 | 0.2685 | 0.2684 | 46.2% (13) | — (0) | — (0) |
| 14 | 29 | 0.2446 | 0.2278 | 0.2275 | 70.0% (10) | 100.0% (1) | 100.0% (1) |
| 15 | 39 | 0.2663 | 0.2491 | 0.2505 | 70.6% (17) | — (0) | — (0) |
| 16 | 34 | 0.3213 | 0.2352 | 0.2344 | 56.2% (16) | 100.0% (1) | 100.0% (1) |
| 17 | 38 | 0.3413 | 0.2650 | 0.2652 | 47.1% (17) | — (0) | — (0) |
| 18 | 33 | 0.2537 | 0.2381 | 0.2384 | 60.0% (10) | — (0) | — (0) |

**Season-wide threshold detail** (sample-size changes are material):

| Confidence threshold | Raw hit (n) | Global hit (n) | Role hit (n) |
|---|---:|---:|---:|
| ≥70% | 57.3% (248) | 62.6% (99) | 62.6% (99) |
| ≥80% | 59.9% (167) | 66.7% (48) | 65.2% (46) |
| ≥90% | 64.6% (82) | 71.4% (14) | 71.4% (14) |
| ≥95% | 71.1% (38) | 100.0% (5) | 100.0% (5) |

**Source-model controls:**
Archived hurdle raw Brier 0.2820; hurdle-global 0.2512; hurdle-role 0.2512.
Archived no-refit control raw Brier 0.2830; no-refit-global 0.2525; no-refit-role 0.2526.

Role calibration minus global Brier: -0.00002; clustered descriptive interval [-0.00035, 0.00034].

### Targets

Original candidates 6,186; graded 4,266; missing 1,920. Lower Brier is better. Values at ≥80% show actual accuracy and number selected.

| Wk | Graded | Raw Brier | Global Brier | Role Brier | Raw ≥80% hit (n) | Global ≥80% hit (n) | Role ≥80% hit (n) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 187 | 0.2161 | 0.2161 | 0.2161 | 76.9% (26) | 76.9% (26) | 76.9% (26) |
| 2 | 158 | 0.2511 | 0.2460 | 0.2429 | 72.7% (22) | 71.4% (14) | 80.0% (15) |
| 3 | 181 | 0.2338 | 0.2310 | 0.2337 | 73.1% (26) | 75.0% (4) | 62.5% (8) |
| 4 | 233 | 0.2353 | 0.2337 | 0.2326 | 77.8% (9) | 100.0% (4) | 100.0% (3) |
| 5 | 215 | 0.2510 | 0.2544 | 0.2545 | 88.9% (9) | 100.0% (1) | 100.0% (1) |
| 6 | 222 | 0.2338 | 0.2334 | 0.2338 | 87.5% (8) | 100.0% (3) | 75.0% (4) |
| 7 | 242 | 0.2278 | 0.2282 | 0.2294 | 75.0% (8) | 0.0% (1) | 0.0% (2) |
| 8 | 279 | 0.2666 | 0.2569 | 0.2551 | 66.7% (15) | 0.0% (1) | 0.0% (1) |
| 9 | 253 | 0.2567 | 0.2483 | 0.2457 | 81.8% (11) | — (0) | — (0) |
| 10 | 232 | 0.2461 | 0.2398 | 0.2345 | 58.8% (17) | — (0) | — (0) |
| 11 | 248 | 0.2509 | 0.2429 | 0.2397 | 75.0% (16) | 100.0% (1) | 100.0% (1) |
| 12 | 229 | 0.2540 | 0.2434 | 0.2441 | 62.5% (16) | 100.0% (1) | 100.0% (1) |
| 13 | 276 | 0.2629 | 0.2507 | 0.2494 | 70.0% (20) | 0.0% (1) | 0.0% (1) |
| 14 | 217 | 0.2504 | 0.2424 | 0.2412 | 72.7% (11) | — (0) | 100.0% (1) |
| 15 | 273 | 0.2536 | 0.2424 | 0.2411 | 69.6% (23) | — (0) | — (0) |
| 16 | 271 | 0.2554 | 0.2444 | 0.2456 | 66.7% (18) | — (0) | — (0) |
| 17 | 279 | 0.2425 | 0.2372 | 0.2329 | 66.7% (21) | — (0) | — (0) |
| 18 | 271 | 0.2725 | 0.2558 | 0.2586 | 57.9% (19) | — (0) | — (0) |

**Season-wide threshold detail** (sample-size changes are material):

| Confidence threshold | Raw hit (n) | Global hit (n) | Role hit (n) |
|---|---:|---:|---:|
| ≥70% | 63.6% (1354) | 70.9% (368) | 70.8% (390) |
| ≥80% | 70.8% (295) | 75.4% (57) | 73.4% (64) |
| ≥90% | 77.8% (27) | 80.0% (5) | 75.0% (4) |
| ≥95% | 100.0% (2) | 100.0% (2) | 100.0% (2) |

**Source-model controls:**
Archived hurdle raw Brier 0.2475; hurdle-global 0.2415; hurdle-role 0.2407.
Archived no-refit control raw Brier 0.2465; no-refit-global 0.2413; no-refit-role 0.2406.

Role calibration minus global Brier: -0.00092; clustered descriptive interval [-0.00189, 0.00010].

### Receptions

Original candidates 6,186; graded 4,266; missing 1,920. Lower Brier is better. Values at ≥80% show actual accuracy and number selected.

| Wk | Graded | Raw Brier | Global Brier | Role Brier | Raw ≥80% hit (n) | Global ≥80% hit (n) | Role ≥80% hit (n) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 187 | 0.2230 | 0.2230 | 0.2230 | 77.8% (27) | 77.8% (27) | 77.8% (27) |
| 2 | 158 | 0.2609 | 0.2606 | 0.2597 | 64.7% (17) | 63.6% (11) | 58.3% (12) |
| 3 | 181 | 0.2349 | 0.2336 | 0.2342 | 62.5% (16) | 100.0% (1) | 100.0% (1) |
| 4 | 233 | 0.2403 | 0.2388 | 0.2413 | 75.0% (8) | 100.0% (1) | 100.0% (2) |
| 5 | 215 | 0.2552 | 0.2484 | 0.2504 | 80.0% (5) | — (0) | 100.0% (1) |
| 6 | 222 | 0.2417 | 0.2380 | 0.2375 | 77.8% (9) | 100.0% (3) | 75.0% (4) |
| 7 | 242 | 0.2267 | 0.2287 | 0.2284 | 72.7% (11) | — (0) | 0.0% (1) |
| 8 | 279 | 0.2551 | 0.2478 | 0.2476 | 55.6% (18) | 100.0% (1) | 100.0% (1) |
| 9 | 253 | 0.2442 | 0.2387 | 0.2384 | 64.7% (17) | — (0) | — (0) |
| 10 | 232 | 0.2310 | 0.2297 | 0.2284 | 77.8% (18) | — (0) | — (0) |
| 11 | 248 | 0.2492 | 0.2411 | 0.2386 | 61.1% (18) | — (0) | — (0) |
| 12 | 229 | 0.2566 | 0.2455 | 0.2435 | 54.2% (24) | — (0) | — (0) |
| 13 | 276 | 0.2478 | 0.2402 | 0.2392 | 63.6% (22) | — (0) | — (0) |
| 14 | 217 | 0.2322 | 0.2304 | 0.2323 | 70.0% (20) | — (0) | — (0) |
| 15 | 273 | 0.2307 | 0.2293 | 0.2295 | 66.7% (18) | — (0) | — (0) |
| 16 | 271 | 0.2494 | 0.2398 | 0.2405 | 68.2% (22) | — (0) | — (0) |
| 17 | 279 | 0.2569 | 0.2452 | 0.2427 | 66.7% (24) | — (0) | — (0) |
| 18 | 271 | 0.2733 | 0.2546 | 0.2553 | 46.2% (13) | — (0) | — (0) |

**Season-wide threshold detail** (sample-size changes are material):

| Confidence threshold | Raw hit (n) | Global hit (n) | Role hit (n) |
|---|---:|---:|---:|
| ≥70% | 65.3% (1511) | 66.9% (372) | 69.8% (427) |
| ≥80% | 66.1% (307) | 77.3% (44) | 73.5% (49) |
| ≥90% | 100.0% (11) | 100.0% (3) | 100.0% (3) |
| ≥95% | 100.0% (1) | 100.0% (1) | 100.0% (1) |

**Source-model controls:**
Archived hurdle raw Brier 0.2442; hurdle-global 0.2386; hurdle-role 0.2385.
Archived no-refit control raw Brier 0.2429; no-refit-global 0.2384; no-refit-role 0.2383.

Role calibration minus global Brier: -0.00021; clustered descriptive interval [-0.00082, 0.00044].

### Receiving Yards

Original candidates 6,186; graded 4,266; missing 1,920. Lower Brier is better. Values at ≥80% show actual accuracy and number selected.

| Wk | Graded | Raw Brier | Global Brier | Role Brier | Raw ≥80% hit (n) | Global ≥80% hit (n) | Role ≥80% hit (n) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 187 | 0.2209 | 0.2209 | 0.2209 | 80.0% (5) | 80.0% (5) | 80.0% (5) |
| 2 | 158 | 0.2524 | 0.2523 | 0.2513 | 66.7% (6) | 60.0% (5) | 66.7% (6) |
| 3 | 181 | 0.2320 | 0.2337 | 0.2328 | 57.1% (7) | — (0) | 0.0% (1) |
| 4 | 233 | 0.2456 | 0.2456 | 0.2431 | 100.0% (2) | — (0) | — (0) |
| 5 | 215 | 0.2637 | 0.2585 | 0.2603 | 100.0% (1) | 100.0% (1) | 100.0% (1) |
| 6 | 222 | 0.2493 | 0.2451 | 0.2442 | 66.7% (6) | 50.0% (2) | 50.0% (2) |
| 7 | 242 | 0.2306 | 0.2325 | 0.2344 | 100.0% (3) | — (0) | — (0) |
| 8 | 279 | 0.2651 | 0.2582 | 0.2567 | 14.3% (7) | 0.0% (1) | — (0) |
| 9 | 253 | 0.2505 | 0.2454 | 0.2431 | 66.7% (3) | — (0) | — (0) |
| 10 | 232 | 0.2388 | 0.2375 | 0.2343 | 66.7% (9) | — (0) | — (0) |
| 11 | 248 | 0.2454 | 0.2410 | 0.2359 | 66.7% (9) | — (0) | — (0) |
| 12 | 229 | 0.2436 | 0.2400 | 0.2363 | 57.1% (7) | — (0) | — (0) |
| 13 | 276 | 0.2437 | 0.2403 | 0.2365 | 71.4% (7) | — (0) | — (0) |
| 14 | 217 | 0.2494 | 0.2438 | 0.2453 | 75.0% (4) | — (0) | 100.0% (1) |
| 15 | 273 | 0.2371 | 0.2364 | 0.2384 | 40.0% (5) | — (0) | — (0) |
| 16 | 271 | 0.2412 | 0.2381 | 0.2385 | 60.0% (5) | — (0) | — (0) |
| 17 | 279 | 0.2578 | 0.2487 | 0.2451 | 25.0% (4) | — (0) | — (0) |
| 18 | 271 | 0.2460 | 0.2412 | 0.2379 | 50.0% (4) | — (0) | — (0) |

**Season-wide threshold detail** (sample-size changes are material):

| Confidence threshold | Raw hit (n) | Global hit (n) | Role hit (n) |
|---|---:|---:|---:|
| ≥70% | 65.0% (829) | 66.0% (191) | 67.3% (217) |
| ≥80% | 60.6% (94) | 64.3% (14) | 68.8% (16) |
| ≥90% | 100.0% (2) | 100.0% (1) | 100.0% (1) |
| ≥95% | — (0) | — (0) | — (0) |

**Source-model controls:**
Archived hurdle raw Brier 0.2443; hurdle-global 0.2417; hurdle-role 0.2405.
Archived no-refit control raw Brier 0.2439; no-refit-global 0.2417; no-refit-role 0.2406.

Role calibration minus global Brier: -0.00142; clustered descriptive interval [-0.00244, -0.00039].

### Carries

Original candidates 2,570; graded 1,769; missing 801. Lower Brier is better. Values at ≥80% show actual accuracy and number selected.

| Wk | Graded | Raw Brier | Global Brier | Role Brier | Raw ≥80% hit (n) | Global ≥80% hit (n) | Role ≥80% hit (n) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 74 | 0.2901 | 0.2901 | 0.2901 | 50.0% (24) | 50.0% (24) | 50.0% (24) |
| 2 | 66 | 0.2437 | 0.2437 | 0.2437 | 80.0% (15) | 80.0% (15) | 80.0% (15) |
| 3 | 73 | 0.2224 | 0.2340 | 0.2361 | 80.0% (10) | 100.0% (1) | 100.0% (1) |
| 4 | 102 | 0.2540 | 0.2418 | 0.2392 | 64.7% (17) | — (0) | — (0) |
| 5 | 92 | 0.2539 | 0.2457 | 0.2423 | 60.0% (5) | 0.0% (1) | 0.0% (1) |
| 6 | 89 | 0.2485 | 0.2435 | 0.2426 | 75.0% (12) | — (0) | — (0) |
| 7 | 96 | 0.2438 | 0.2366 | 0.2318 | 75.0% (12) | — (0) | — (0) |
| 8 | 113 | 0.2852 | 0.2590 | 0.2625 | 45.8% (24) | 0.0% (3) | 0.0% (2) |
| 9 | 106 | 0.2671 | 0.2471 | 0.2462 | 64.0% (25) | 0.0% (2) | — (0) |
| 10 | 98 | 0.2929 | 0.2539 | 0.2485 | 59.1% (22) | — (0) | — (0) |
| 11 | 107 | 0.2511 | 0.2329 | 0.2403 | 65.6% (32) | 100.0% (1) | 100.0% (1) |
| 12 | 90 | 0.2583 | 0.2385 | 0.2398 | 68.0% (25) | — (0) | — (0) |
| 13 | 114 | 0.2536 | 0.2367 | 0.2375 | 60.6% (33) | — (0) | — (0) |
| 14 | 87 | 0.2812 | 0.2512 | 0.2482 | 50.0% (20) | — (0) | — (0) |
| 15 | 117 | 0.2411 | 0.2333 | 0.2303 | 66.7% (30) | — (0) | — (0) |
| 16 | 116 | 0.2701 | 0.2441 | 0.2440 | 76.9% (26) | — (0) | — (0) |
| 17 | 120 | 0.2938 | 0.2579 | 0.2565 | 56.2% (32) | 0.0% (1) | 0.0% (1) |
| 18 | 109 | 0.2783 | 0.2504 | 0.2433 | 50.0% (24) | — (0) | — (0) |

**Season-wide threshold detail** (sample-size changes are material):

| Confidence threshold | Raw hit (n) | Global hit (n) | Role hit (n) |
|---|---:|---:|---:|
| ≥70% | 61.0% (764) | 65.2% (135) | 64.1% (117) |
| ≥80% | 62.4% (388) | 54.2% (48) | 57.8% (45) |
| ≥90% | 64.8% (108) | 68.8% (16) | 68.8% (16) |
| ≥95% | 60.0% (35) | 57.1% (7) | 57.1% (7) |

**Source-model controls:**
Archived hurdle raw Brier 0.2610; hurdle-global 0.2459; hurdle-role 0.2448.
Archived no-refit control raw Brier 0.2627; no-refit-global 0.2463; no-refit-role 0.2452.

Role calibration minus global Brier: -0.00101; clustered descriptive interval [-0.00255, 0.00065].

### Rushing Yards

Original candidates 2,570; graded 1,769; missing 801. Lower Brier is better. Values at ≥80% show actual accuracy and number selected.

| Wk | Graded | Raw Brier | Global Brier | Role Brier | Raw ≥80% hit (n) | Global ≥80% hit (n) | Role ≥80% hit (n) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 74 | 0.2720 | 0.2720 | 0.2720 | 57.1% (14) | 57.1% (14) | 57.1% (14) |
| 2 | 66 | 0.2705 | 0.2705 | 0.2705 | 55.6% (9) | 55.6% (9) | 55.6% (9) |
| 3 | 73 | 0.2677 | 0.2749 | 0.2778 | 100.0% (3) | 100.0% (1) | 100.0% (1) |
| 4 | 102 | 0.2553 | 0.2448 | 0.2444 | 66.7% (9) | — (0) | — (0) |
| 5 | 92 | 0.2431 | 0.2418 | 0.2429 | 75.0% (4) | — (0) | — (0) |
| 6 | 89 | 0.2400 | 0.2402 | 0.2385 | 66.7% (3) | — (0) | — (0) |
| 7 | 96 | 0.2676 | 0.2528 | 0.2504 | 44.4% (9) | 0.0% (1) | — (0) |
| 8 | 113 | 0.2620 | 0.2475 | 0.2504 | 41.7% (12) | — (0) | — (0) |
| 9 | 106 | 0.2512 | 0.2412 | 0.2395 | 64.3% (14) | — (0) | — (0) |
| 10 | 98 | 0.2354 | 0.2333 | 0.2312 | 73.3% (15) | — (0) | — (0) |
| 11 | 107 | 0.2354 | 0.2314 | 0.2363 | 81.0% (21) | 100.0% (1) | 100.0% (1) |
| 12 | 90 | 0.2510 | 0.2392 | 0.2398 | 40.0% (10) | — (0) | — (0) |
| 13 | 114 | 0.2667 | 0.2476 | 0.2458 | 66.7% (12) | — (0) | — (0) |
| 14 | 87 | 0.2319 | 0.2325 | 0.2313 | 80.0% (10) | — (0) | — (0) |
| 15 | 117 | 0.2527 | 0.2413 | 0.2400 | 75.0% (12) | — (0) | — (0) |
| 16 | 116 | 0.2876 | 0.2590 | 0.2615 | 53.3% (15) | — (0) | — (0) |
| 17 | 120 | 0.2816 | 0.2559 | 0.2541 | 40.0% (20) | 100.0% (1) | — (0) |
| 18 | 109 | 0.2751 | 0.2539 | 0.2507 | 54.5% (11) | — (0) | — (0) |

**Season-wide threshold detail** (sample-size changes are material):

| Confidence threshold | Raw hit (n) | Global hit (n) | Role hit (n) |
|---|---:|---:|---:|
| ≥70% | 57.9% (558) | 59.1% (110) | 58.1% (93) |
| ≥80% | 61.1% (203) | 59.3% (27) | 60.0% (25) |
| ≥90% | 69.0% (42) | 83.3% (6) | 83.3% (6) |
| ≥95% | 81.8% (11) | 100.0% (2) | 100.0% (2) |

**Source-model controls:**
Archived hurdle raw Brier 0.2562; hurdle-global 0.2471; hurdle-role 0.2468.
Archived no-refit control raw Brier 0.2581; no-refit-global 0.2476; no-refit-role 0.2474.

Role calibration minus global Brier: -0.00018; clustered descriptive interval [-0.00117, 0.00094].

### Tackles + Assists

Original candidates 10,307; graded 6,944; missing 3,363. Lower Brier is better. Values at ≥80% show actual accuracy and number selected.

| Wk | Graded | Raw Brier | Global Brier | Role Brier | Raw ≥80% hit (n) | Global ≥80% hit (n) | Role ≥80% hit (n) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 317 | 0.2458 | 0.2458 | 0.2458 | 75.0% (4) | 75.0% (4) | 75.0% (4) |
| 2 | 285 | 0.2708 | 0.2633 | 0.2623 | 61.1% (54) | 71.8% (39) | 70.3% (37) |
| 3 | 301 | 0.2337 | 0.2339 | 0.2344 | 78.9% (38) | — (0) | 100.0% (1) |
| 4 | 383 | 0.2514 | 0.2447 | 0.2426 | 68.4% (19) | 0.0% (1) | 0.0% (1) |
| 5 | 348 | 0.2430 | 0.2437 | 0.2426 | 80.0% (10) | 0.0% (1) | 0.0% (1) |
| 6 | 357 | 0.2332 | 0.2390 | 0.2375 | 75.0% (12) | 50.0% (2) | 50.0% (2) |
| 7 | 384 | 0.2479 | 0.2448 | 0.2436 | 91.7% (12) | 100.0% (1) | 100.0% (3) |
| 8 | 427 | 0.2503 | 0.2476 | 0.2462 | 41.7% (12) | 50.0% (2) | 50.0% (2) |
| 9 | 402 | 0.2379 | 0.2406 | 0.2400 | 85.7% (7) | 100.0% (1) | 100.0% (1) |
| 10 | 385 | 0.2370 | 0.2394 | 0.2378 | 100.0% (3) | 100.0% (1) | 100.0% (1) |
| 11 | 384 | 0.2482 | 0.2456 | 0.2425 | 100.0% (4) | — (0) | 100.0% (1) |
| 12 | 351 | 0.2443 | 0.2436 | 0.2409 | 66.7% (3) | — (0) | — (0) |
| 13 | 434 | 0.2483 | 0.2449 | 0.2439 | 100.0% (3) | 100.0% (1) | 100.0% (1) |
| 14 | 353 | 0.2474 | 0.2448 | 0.2416 | 100.0% (4) | — (0) | — (0) |
| 15 | 459 | 0.2341 | 0.2365 | 0.2339 | 100.0% (2) | — (0) | 100.0% (1) |
| 16 | 461 | 0.2501 | 0.2451 | 0.2447 | 100.0% (1) | 100.0% (1) | 100.0% (1) |
| 17 | 471 | 0.2445 | 0.2413 | 0.2366 | 50.0% (4) | 100.0% (1) | 100.0% (1) |
| 18 | 442 | 0.2445 | 0.2438 | 0.2452 | 80.0% (5) | — (0) | 100.0% (1) |

**Season-wide threshold detail** (sample-size changes are material):

| Confidence threshold | Raw hit (n) | Global hit (n) | Role hit (n) |
|---|---:|---:|---:|
| ≥70% | 66.4% (754) | 67.8% (183) | 70.0% (207) |
| ≥80% | 72.6% (197) | 70.9% (55) | 72.9% (59) |
| ≥90% | 74.2% (62) | 33.3% (12) | 38.5% (13) |
| ≥95% | 61.9% (21) | 50.0% (4) | 60.0% (5) |

**Source-model controls:**
Archived hurdle raw Brier 0.2451; hurdle-global 0.2436; hurdle-role 0.2421.
Archived no-refit control raw Brier 0.2449; no-refit-global 0.2435; no-refit-role 0.2420.

Role calibration minus global Brier: -0.00151; clustered descriptive interval [-0.00224, -0.00083].

### Solo Tackles

Original candidates 10,307; graded 6,944; missing 3,363. Lower Brier is better. Values at ≥80% show actual accuracy and number selected.

| Wk | Graded | Raw Brier | Global Brier | Role Brier | Raw ≥80% hit (n) | Global ≥80% hit (n) | Role ≥80% hit (n) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 317 | 0.2329 | 0.2329 | 0.2329 | 81.8% (22) | 81.8% (22) | 81.8% (22) |
| 2 | 285 | 0.2843 | 0.2796 | 0.2764 | 52.5% (61) | 52.5% (61) | 55.6% (63) |
| 3 | 301 | 0.2486 | 0.2379 | 0.2391 | 64.9% (57) | — (0) | 100.0% (1) |
| 4 | 383 | 0.2516 | 0.2412 | 0.2388 | 68.3% (60) | — (0) | 100.0% (1) |
| 5 | 348 | 0.2415 | 0.2394 | 0.2407 | 63.6% (22) | — (0) | 0.0% (2) |
| 6 | 357 | 0.2397 | 0.2390 | 0.2395 | 72.4% (29) | 0.0% (2) | 0.0% (1) |
| 7 | 384 | 0.2365 | 0.2371 | 0.2364 | 87.0% (23) | — (0) | 100.0% (1) |
| 8 | 427 | 0.2345 | 0.2348 | 0.2340 | 85.7% (28) | 100.0% (2) | 100.0% (1) |
| 9 | 402 | 0.2434 | 0.2385 | 0.2350 | 71.4% (35) | 80.0% (5) | 83.3% (6) |
| 10 | 385 | 0.2422 | 0.2393 | 0.2387 | 65.2% (23) | 100.0% (2) | 100.0% (2) |
| 11 | 384 | 0.2445 | 0.2403 | 0.2383 | 72.7% (22) | — (0) | — (0) |
| 12 | 351 | 0.2262 | 0.2300 | 0.2263 | 90.9% (22) | — (0) | — (0) |
| 13 | 434 | 0.2389 | 0.2372 | 0.2344 | 90.0% (20) | 100.0% (1) | 100.0% (1) |
| 14 | 353 | 0.2326 | 0.2337 | 0.2329 | 72.0% (25) | 100.0% (1) | 100.0% (1) |
| 15 | 459 | 0.2350 | 0.2345 | 0.2328 | 83.3% (30) | — (0) | — (0) |
| 16 | 461 | 0.2403 | 0.2379 | 0.2375 | 62.1% (29) | 100.0% (2) | 100.0% (2) |
| 17 | 471 | 0.2415 | 0.2371 | 0.2330 | 72.7% (33) | 100.0% (2) | 100.0% (2) |
| 18 | 442 | 0.2317 | 0.2318 | 0.2285 | 73.5% (34) | 50.0% (2) | 100.0% (2) |

**Season-wide threshold detail** (sample-size changes are material):

| Confidence threshold | Raw hit (n) | Global hit (n) | Role hit (n) |
|---|---:|---:|---:|
| ≥70% | 67.2% (2152) | 66.9% (341) | 72.6% (529) |
| ≥80% | 71.5% (575) | 63.7% (102) | 66.7% (108) |
| ≥90% | 68.3% (120) | 59.5% (42) | 62.8% (43) |
| ≥95% | 71.6% (74) | 73.3% (15) | 65.0% (20) |

**Source-model controls:**
Archived hurdle raw Brier 0.2396; hurdle-global 0.2377; hurdle-role 0.2360.
Archived no-refit control raw Brier 0.2393; no-refit-global 0.2376; no-refit-role 0.2360.

Role calibration minus global Brier: -0.00158; clustered descriptive interval [-0.00231, -0.00075].

### Tackle Assists

Original candidates 10,307; graded 6,944; missing 3,363. Lower Brier is better. Values at ≥80% show actual accuracy and number selected.

| Wk | Graded | Raw Brier | Global Brier | Role Brier | Raw ≥80% hit (n) | Global ≥80% hit (n) | Role ≥80% hit (n) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 317 | 0.2624 | 0.2624 | 0.2624 | 51.1% (47) | 51.1% (47) | 51.1% (47) |
| 2 | 285 | 0.2826 | 0.2506 | 0.2490 | 58.9% (95) | 57.7% (26) | 57.7% (26) |
| 3 | 301 | 0.2634 | 0.2410 | 0.2417 | 59.8% (87) | — (0) | — (0) |
| 4 | 383 | 0.2543 | 0.2397 | 0.2386 | 61.6% (86) | 100.0% (1) | 100.0% (1) |
| 5 | 348 | 0.2401 | 0.2365 | 0.2348 | 73.0% (63) | — (0) | — (0) |
| 6 | 357 | 0.2551 | 0.2417 | 0.2380 | 61.4% (70) | 50.0% (2) | 100.0% (1) |
| 7 | 384 | 0.2377 | 0.2356 | 0.2350 | 75.0% (64) | — (0) | 0.0% (1) |
| 8 | 427 | 0.2587 | 0.2426 | 0.2412 | 62.5% (80) | 100.0% (2) | 100.0% (1) |
| 9 | 402 | 0.2532 | 0.2412 | 0.2416 | 65.6% (61) | 100.0% (1) | 50.0% (2) |
| 10 | 385 | 0.2420 | 0.2375 | 0.2366 | 78.2% (55) | 0.0% (1) | 0.0% (1) |
| 11 | 384 | 0.2576 | 0.2418 | 0.2402 | 70.5% (61) | — (0) | — (0) |
| 12 | 351 | 0.2482 | 0.2402 | 0.2405 | 69.8% (53) | 100.0% (1) | 100.0% (1) |
| 13 | 434 | 0.2352 | 0.2344 | 0.2356 | 75.9% (54) | 100.0% (2) | 100.0% (3) |
| 14 | 353 | 0.2317 | 0.2322 | 0.2320 | 79.6% (49) | 0.0% (1) | 0.0% (1) |
| 15 | 459 | 0.2338 | 0.2328 | 0.2323 | 77.1% (70) | 100.0% (1) | — (0) |
| 16 | 461 | 0.2390 | 0.2354 | 0.2366 | 74.6% (63) | — (0) | — (0) |
| 17 | 471 | 0.2435 | 0.2370 | 0.2374 | 72.3% (65) | — (0) | — (0) |
| 18 | 442 | 0.2537 | 0.2411 | 0.2411 | 60.8% (79) | — (0) | — (0) |

**Season-wide threshold detail** (sample-size changes are material):

| Confidence threshold | Raw hit (n) | Global hit (n) | Role hit (n) |
|---|---:|---:|---:|
| ≥70% | 66.3% (2704) | 67.5% (252) | 68.3% (312) |
| ≥80% | 67.5% (1202) | 56.5% (85) | 55.3% (85) |
| ≥90% | 71.5% (137) | 100.0% (2) | 100.0% (3) |
| ≥95% | 69.8% (63) | — (0) | — (0) |

**Source-model controls:**
Archived hurdle raw Brier 0.2467; hurdle-global 0.2388; hurdle-role 0.2384.
Archived no-refit control raw Brier 0.2464; no-refit-global 0.2389; no-refit-role 0.2384.

Role calibration minus global Brier: -0.00045; clustered descriptive interval [-0.00106, 0.00007].

## Independent integrity and limitations

Receipts matched 18 original frozen 2024 SHA-256 files and 594 individual market-model-week as-of calibration counts. 396 independently weighted season-score checks and 396 selected hit-rate/count checks passed. No current or future week's outcome labels appeared in calibration history. Week 1 control equals exact raw probabilities, including original zero/one predictions.

Market lines and roster statuses are **retrospective synthetic research artifacts**, not originally captured sportsbook prices or verified in-game participation states. Selection hit percentages are **not profitability claims**. A significant fraction of source forecast candidates lack matched outcome rows and were not silently treated as zeros. The 2024 season has been repeatedly used in model selection. Historical tackle credit conventions and team/injury upstream timestamps require separate verification before a Phase 0R acceptance gate.

Role Platt corrections use shrunken position-group intercepts within each market, not re-estimation of the underlying count/yard distributions; a better Brier score cannot prove that target, yard or tackle means became more accurate. The archived model's frozen no-refit and hurdle variants are shown as independent source-model controls. Neither the new target-specific participation model nor any other new Phase 2 count distribution has been claimed to cover all 11 markets.

**Release:** Research-only shadow report; no production model, probabilities, tier definitions, daily jobs or ranking pipeline are promoted.
