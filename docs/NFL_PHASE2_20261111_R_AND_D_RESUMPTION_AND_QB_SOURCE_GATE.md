# NFL Phase 2 R&D resumption — frozen 2024 replay, QB eligibility and remaining Phase 2 gates

**Recovery date:** 2026-11-11. **Source:** existing archived Deepnote and GitHub research. The ChatGPT share-link transcript itself was not retrievable in this environment; the work below is a recovery from verifiable artifacts, not a claim to have read the Work chat.

**Scientific status:** RESEARCH ONLY; no original 60/40 or NUTS production mutation; no Tier 1/2, pick, model promotion or declaration that 2024 is a fresh holdout. The 2024 outcomes and models are repeatedly development-exposed. No authentic sportsbook or pick'em payout lines exist for the 2024 frozen hybrid replay.

## A. Recovered interrupted run — completed already, do not refit

Original frozen 2024 run `pickem_runs/2024_hybrid_activezero_pre2024_numpy2_clean_v3` generated **66,793 forecasts in 18 weeks** using historical data with model fit cutoff strictly before **2024-01-01**. Original `FROZEN_MANIFEST.json` SHA256: `e416676f803022dda60d715a45e4a3206b2fb771f5631fd8859aee57b87e6b41`.

The first Deepnote clean subprocess run `5da237b2-b691-4a60-98bd-72e216b5099e` successfully completed the expensive fit and lock, then its evaluator crashed because it treated `MODELS/active_zero_platt_calibration.json` as an XGBoost `.ubj` model. That is a **serialization-type bug**, not a forecast accuracy failure. The research code subsequently corrected the filename dispatch; **separate no-retraining recovery** succeeded: Deepnote run `7747bfe3-65b7-4a7a-b04f-5b92a93344e4`, 2026-11-09T18:25Z. It compared frozen model/file SHA, verified 18 week hashes, and first read 2024 settlement after the forecast lock. No need to refit; original immutable files remain unchanged.

| Model | Same scored original contracts | Brier (lower better) | Directional hit | Predicted Under share |
| --- | ---: | ---: | ---: | ---: |
| Simple pre-2024 historical player prior | 26,952 | **0.247801** | 56.46% | 69.55% |
| XGBoost team + hierarchical Monte Carlo | 26,952 | 0.255488 | 56.58% | 82.90% |
| Same hybrid plus active-zero hurdle | 26,952 | 0.254041 | **56.98%** | 82.12% |

Independent game-cluster audit run `34a661ba-ce3e-42b1-92b2-6b8abffc9b99`: 272 game clusters, matched active-zero minus historical prior Brier **+0.006240** (95% game-cluster descriptive interval **[+0.004056,+0.007916]**, positive is worse). The active-zero hurdle improves the unmodified hybrid by Brier **−0.001447** on the same contracts, but the simple historical player prior remains better than both more complex models.

**NO-GO for automatic Phase 2 hybrid promotion.** The current winner for this particular synthetic-line 2024 proper-score comparison is the **simple player prior**, but even this prior has not been certified against original pregame sportsbook markets.

## B. Structural selection defect quantified from exact archived bytes

Independent Deepnote notebook `e94479564fc14fe1a7162864a272395b`, read-only runs `67ab8a18-c8a5-45a7-9447-431ee3ccfe6f` and `04b47b6b-66d1-4f6a-97ab-2139c5c0d765`. Frozen `all_props.json` 66,793 rows, evaluation summary SHA `f73f02b4c4f9c0f0f477ff041ef6e79b906e40ab4d6d0088d9b5192cb6a9902a`.

- **Full 2024 frozen universe:** 66,793 archived predictions; **26,952** matched to official graded rows; **39,841 unmatched (59.65%)**. Missing is never recoded as an Under hit, a loss or confirmed inactive player.
- **QB pass-attempt market:** **1,105** originally forecast QB-player props over **544 team-games**, averaging **2.031 QB identities per team-game**. **378** matched actual player pass-attempt statistics; **727 (65.79%) did not**. Among 544 team-games, **189** had zero graded forecast QB IDs, **332** had one and **23** had two. **408 of 544 team-games** had more than one QB forecast (289 had two, 85 had three and 34 had four); only 136 had one.
- **All 1,105 QB forecasts had `roster_2024_verified=false`.** Therefore none is source-qualified for pregame confirmed-starter selection, even though many appeared in historical diagnostic candidate sets.
- **Spurious-looking confidence among proposed QB opportunities:** active-zero challenger made **685 ≥80%-confidence QB pass-attempt predictions**, **648 Under**, **496 unmatched (72.41% of high-confidence forecasts)**. On the 2024 exposed dataset alone, a high-confidence probability for a player absent from the settlement source is not a verified profitable Under and should not be graded as such.
- **Major structural selection issue:** candidate roster derives partly from historical 2023 player identity rather than genuine game-time starting QB assignment. A 2023 roster carryover player may be traded, inactive, backup, missing from coverage or a player whose team identity changed. An observed stat in the final box score does not retro-prove starter status. The full pool needs pregame participation and offer eligibility authority, not postgame filtering.

This selection problem affects rushing, receiving and defensive markets too; 2024 historical observed rates 34%–42% depending on market. No model should claim release-grade proper scoring on an unverified, selection-biased 40.4% subset.

## C. New source-gated **future** starter eligibility harness

`scripts/nfl_phase2_starter_gate.py` provides a strictly research-only interface: exact same game/team/pregame starting QB named by an explicit original league-source record, HTTPS league-domain verification, raw archive content SHA, original capture clock at/before forecast freeze and before kickoff, ≤6h age, rejection of postgame/depth-chart/projection status and mismatched QB identity. It preserves every candidate and records an explicit **abstention** for backups or missing/stale evidence. Supports QB pass attempts, completions, passing yards, QB rushing attempts and QB rushing yards. Existing frozen forecasts are never deleted, renamed, regraded or relabeled as source-certified.

**Important evidence limitation:** A SHA proves local raw-byte integrity, not the upstream publication time or whether the feed genuinely reports the starter. This module **does not** provide a production-approved source parser; its source document contract still needs a live vendor-specific adapter and independent original authority verification. All outputs explicitly say `production_eligible=false`, `tier1_tier2_authorized=false`, `pre_game_source_truth_independently_verified=false`. Historical 2024 has no original starter receipts and must yield **zero source-qualified** starter props under this research gate, without calling that a win-rate statistic.

Red-team tests: `tests/test_nfl_phase2_starter_gate.py` covers explicit starter vs backup, missing data, projected depth chart, postgame claim, future/stale timestamps, spoofed domain, hash alteration, contradictory ID, duplicate forecast, invalid line and output immutability.

## D. Next research execution sequence

1. **No more 2024 model training on inspected outcomes.** Keep frozen source bytes, original output identity, and the same full eligible/attempted ledger. Record all 39,841 unmatched contracts with reasons only when supported by independent sources; no inferred DNP.
2. **Pregame opportunity and QB-starter instrumentation.** Acquire original current-date roster, injury, independent starting-QB and official schedule receipts, with actual retrieval clocks and original bytes. Absence or backup status must be independently sourced. Do not mistake depth-chart QB1 or final box-score high attempts for confirmed pregame starter.
3. **Small, preregistered source-certified NFL shadow.** For QB pass/rush, player targets, carries and defensive tackles, identify original executable lines, original starter/role status and correct stat semantics before simulating. Freeze all attempts plus abstentions before kickoff; score next morning on single complementary contracts.
4. **Model-factor fault isolation.** The 2024 active-zero hurdle slightly repaired the hybrid but did not beat the simpler player prior. Diagnose team attempt mean, participation/active-zero, player share, yard/target conversion and defensive zero/hit distributions on exact game/team/player cohorts. Introduce one mechanism at a time, compare proper count CRPS and binary Brier/log loss against the frozen prior.
5. **Prequential 2023–24:** historical repeat runs are **regression/diagnostics only**; neither year is untouched. Use frozen feature-history gates, original team/player identity and all attempted candidates, not postgame oracle participation as a pregame feature. No certified real market comparison without authentic archived offers.
6. **Promotion blocks remain:** NFL Phase 0R certification not independent from NHL/NBA, Phase 1.5 predictive power and genuine source availability not met, Tier 1/2 and full Phase 2 deployment disallowed; paused NUTS untouched.

This document is for an *isolated research draft branch* stacked on the original hurdle work, not a request to merge the unvalidated Phase 2 architecture into `main`.
