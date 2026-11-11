# V2.5 Phase 1.5 — Sequential Gates B → C → D → E (NBA/NHL, 10–11 November 2026)

**Execution outcome:** All four diagnostic workflows were executed in strict order, independently checked where outcomes permit, and their code failures repaired. **No scientific/performance release:** only 47 of 356 frozen player-line contracts had source-verified final results at the settlement cut; all 47 are NHL SOG from **three games on one slate date**. **Zero NBA contracts** were final in this capture. Partial diagnostic execution is **not** full prospective validation.

**Scope/inputs:** original certified Phase0R NHL/NBA pregame batch `20261110T180409Z`, original SHA `76f8cabc512977ce33017e73c72b7708d452e5f5ec962b33d3ee7f91c75285e6`; Phase 1 merged-source report `reports/phase1_nhl_nba_certified_20261110_original_batch_939024a347d6.json` in connected Deepnote project `9cc31536-93be-44db-bdeb-06fba3f61410`. Total **1,314 prepared forecast sides**, 712 retained sides (356 unique player/stat/line contracts: 250 NBA and 106 NHL), 602 excluded sides kept in original denominators.

## Gate B — Verified actuals, directional scoring and repair

A free official-source, append-only final-only collector is now implemented:

- `scripts/capture_nba_nhl_official.py` and `v2/official_nba_nhl_capture.py`; state `FINAL` required for NHL and `STATUS_FINAL + completed=true` for NBA. Never settle in-progress counts.
- Match original opaque PropLine event IDs to official event IDs only through a **unique sport/teams/time-window** match, then independently verify final boxscore source, original player ID, sport, team, market stat and game identity.
- NHL skaters use the original numeric NHL player ID and official `sog`; NBA official ESPN summary player ID, `PTS`, `REB`, `AST`, and *made* `3PT`, with physically consistent PA/PR/RA/PRA sums. DNP/missing roster are unresolved rather than invented zero.
- Archive exact official source bytes, SHA256, captured-at clock and source URL in NEW records; original frozen forecasts/market lines are never altered. The settlement clock means *first collector-observed final*; it is **not** a manufactured final-whistle timestamp.

**Real result:** 47/356 official contracts settled (NHL 47, NBA 0), 309 pending/unverified. Official SOG observations: **15 Overs, 32 Unders**; one player-team conflict quarantined. All 1,314 originally attempted sides remain in the source-denominator. The old behavior blocked the **entire** NJD–WPG game's 14 contracts when one player-team mismatch occurred; patched behavior rejects only that player and independently settles the other 13.

**Stale-source issue:** Dawson Mercer, NHL ID `8482110`, was originally labeled **NJD** by both the frozen candidate and *the underlying bookmaker aggregator quotes* but appears under **WPG** on the verified postgame game roster. That is **not** a mere joining bug. A truly independent, timestamped official-roster check is a prerequisite for preventing this upstream problem on future slates. The affected original contract remains unverifiable; it was not retrocorrected or silently selected as a winner.

| NHL result, 47 contracts / 3 games | Recent-rate Poisson | Peer-shrunk Poisson | Original no-vig bookmaker |
| --- | ---: | ---: | ---: |
| Brier, lower better | **0.296334** | **0.254484** | **0.245472** |
| Log loss | 0.797491 | 0.702964 | 0.684178 |
| Mean predicted P(Over) minus observed Over fraction | **+18.94 pp** | **+17.63 pp** | **+17.35 pp** |
| Chosen-side hit rate | 42.55% | 51.06% | 56.52% |
| Confidence ≥80% selected contracts | 3 | 0 | 0 |

**Observed Over frequency:** 15/47 = **31.91%**, compared with approximately 49–51% pregame Over probability across the references. This is a descriptive three-game signal, not a stable side-bias estimate or a transferable NBA/NHL recalibration. Both simple rate controls were computed as **counterfactuals** from pregame-frozen histories during Phase 1 replay, not issued as original 2026-11-10 forecasts; original finalized legacy 60/40 remains unavailable. Do not claim the market has proven superiority from three games.

**Independent Gate B check:** Deepnote `ecf8452c-2dec-47a4-8360-bac1b3e92a33`. Independently read source-provider JSON bytes, recalculate all 47 official skater SOG outcomes and teams, verify each digest and stale-team quarantine, and reproduce all Brier/log-loss, side and game-cell calculations. Evidence `reports/phase15_gate_B_20261110_independent_official_audit.json`. Original partial settlement input archive `reports/phase15_Nov10_gate_B_official_capture_83198f51e6d5/`, Phase 1 scored receipt `reports/phase15_gate_B_phase1_scored_20261110_83198f51e6d5.json`, and Phase 1.5 output `reports/phase15_gate_B_matched_diagnostics_20261110_83198f51e6d5.json`.

## Gate C — Retrospective ice-time diagnosis, safe future factor capture

`v2/phase15_exposure_oracle.py` independently re-reads official final raw boxscore bytes and verifies player identity, SOG and actual time on ice. It substitutes *actual postgame TOI* into the rate × exposure calculation in an **isolated retrospective oracle** only. Actual TOI never becomes a pregame feature or a certifiable published forecast.

| NHL 47 contracts | Value |
| --- | ---: |
| Average historical-median projected TOI | 18.75 minutes |
| Actual TOI | 18.89 minutes |
| Mean absolute TOI error | **1.56 minutes** |
| Observed SOG | 1.89 |
| Naive Poisson mean count | 2.44 |
| Pooled Poisson mean count | 2.33 |
| Naive original vs actual-TOI oracle **count MSE** | 3.5683 → **3.4489** |
| Pooled original vs actual-TOI oracle **count MSE** | 2.7973 → **2.5954** |
| Naive original vs actual-TOI oracle **Brier** | 0.2963 → **0.2890** |
| Pooled original vs actual-TOI oracle **Brier** | 0.2545 → **0.2460** |

The oracle correction is modest. The early overforecast is **not explained solely by average TOI underestimation**; conditional shot rates, on-target conversion, count dispersion, opponent context and selection remain plausible hypotheses. No causal factor was isolated, and postgame-oracle scores are **not deployable improvements**. There are still **0/356** genuinely originally frozen four-factor team/participation/share/efficiency vectors, so the full four-factor Shapley attribution is explicitly **BLOCKED**.

**Implemented future-only instrumentation:** `v2/phase15_pregame_factors.py`, `scripts/capture_phase15_pregame_factors.py`, and adversarial tests. The logger must receive actual producer-supplied pre-event factors, source-file hashes and original retrieval clocks, writes a new SHA-bound shadow receipt using the runtime clock, and rejects missing/stale/untrusted factor data. NHL shot-on-goal product is explicitly defined; NBA composite stats are **not** treated as physically valid four-term products. This CLI is **opt-in only**, not automatically wired into the live daily production path. It cannot retrocertify Nov 10.

Gate C receipt: Deepnote `reports/phase15_gate_C_NHL_time_oracle_20261110_5dda576d25d8.json`; test run `f85c6fc1-b006-4bfd-999c-d15134beb385`.

## Gate D — Market-relative proper scores and economic gate

Real frozen pregame two-sided bookmaker reference prices were preserved for all 356 accepted contracts. On the 47 actual settled NHL player/stat/line outcomes:

- Naive-versus-market Brier difference **+0.050862** (worse).
- Pooled-versus-market Brier difference **+0.009012** (worse).
- A *retrospectively analyzed, not preregistered* positive-model-implied-ROI selection heuristic yielded 41 settled naive selections, with hypothetical average one-unit bookmaker return **−19.18%**, and 25 pooled selections at **−24.36%**. It is **not** real betting profit/loss, a prospective strategy, or a release-grade test. Unsettled or unmatched contracts remain in the full ledger.
- The actual pick'em operator's leg payout, parlay payout and eligible selection restrictions were not supplied or certified. Even an ex-post sportsbook quote cannot stand in for an original pick'em execution receipt.

Code: `v2/phase15_market_research.py`; receipt `reports/phase15_gate_D_NHL_source_book_research_20261110_f2cae97a4032.json` in Deepnote. **Economic edge gate BLOCKED** by payout data and independent sample power.

## Gate E — Evidence-ranked go/no-go

Signed source-bound Gate E decision `reports/phase15_gate_E_NHL_NBA_Nov10_signed_investment.json`, Deepnote run `6763844e-5ea8-41a7-96fb-a92e4cd76c6c`; SHA-256 of memo bytes: `73f116f7d9c931bc0432c83305a243e9d4b91d4da11b92efb73087502265b80a`.

| Ticket | Result | Allowed next action |
| --- | --- | --- |
| **B** directional, calibration | **Measured descriptively for 47 NHL; NBA and reliable clustering blocked** | Continue final-only source-hashed settlement, compare on multiple independent dates |
| **C** role / opportunity | **Partial real TOI-only oracle; four-factor unavailable** | Capture proper original pregame factors prospectively (shadow-only) |
| **D** payout / market | **Matched bookmaker Brier measured; actual pick'em payout edge blocked** | Keep two-sided book receipts and obtain exact eligible operator payout terms if testing economics |
| **E** model investment | **DEFER expensive Phase 2/NUTS** | Fix identity robustness first; precommit a *small NHL SOG rate/dispersion challenger* for a future, genuinely unseen cohort |

**Ranked problem hypotheses:** (1) proven independent-player/team identity drift; (2) plausible NHL SOG shot-rate/conditional conversion or count-distribution miscalibration; (3) more modest TOI projection effect; (4) NBA points/combo error unknown without finalized NBA outcomes. A future NHL simple Poisson/NB/shrunk-rate shadow comparison is cheaper and more appropriate than building a full joint game simulator now. No result authorizes changing current production weights, Tier confidence thresholds or Bayesian posterior acceptance.

**Proposed preregistration:** `config/experiment_specs/EXP_NHL_SOG_P15_RATE_DISPERSION_NEXT_PROSPECTIVE.json` is a research plan, not an approved live model. Train cutoff strict and before each future event; all future source quotes and role identity captured before evaluation; matched Brier/log-loss primary, game/date clustered intervals, and no holdout reuse. Change only a single named mechanism; a failed challenger remains shadow-only.

## Reproduce and preserve history

From a checkout with original Deepnote source files mounted:

```bash
python -m unittest discover -s tests -p 'test_v25_official_capture.py' -v
python -m unittest discover -s tests -p 'test_phase15_exposure_oracle.py' -v
python -m unittest discover -s tests -p 'test_phase15_pregame_factors.py' -v
python -m unittest discover -s tests -p 'test_phase15_market_research.py' -v

python scripts/capture_nba_nhl_official.py \
    --phase1 reports/phase1_nhl_nba_certified_20261110_original_batch_939024a347d6.json \
    --date 2026-11-10 \
    --output-dir reports/NEW_APPEND_ONLY_OFFICIAL_CAPTURE
```

Then replay `scripts/v25_phase1_nhl_nba.py` with `--official-settlements NEW_APPEND_ONLY_OFFICIAL_CAPTURE/official_settlements.json` and `--settlement-source-root NEW_APPEND_ONLY_OFFICIAL_CAPTURE/official_source_raw`; feed the newly scored receipt to `scripts/phase15_nhl_nba.py`. Output names must be unique and all originals preserved.

**Critical limits:** This is one partially final NBA/NHL slate, 47 labeled NHL contracts in three games and one date. The sample does not provide meaningful game/date-clustered intervals, reliable calibration/Tier validation, or a proof of positive or negative market edge. Each new official capture is a new version; do not rewrite older capture statuses retrospectively. Do not interpret an apparent market improvement as proof a particular statistical family is correct.

**Production/Tier/automation policy:** unchanged. No model training or promotional mutation executed. Future NHL player-team roster checks require independent source receipts at original pregame time; postgame roster observations here identify the bug, not retrospectively repair the original forecast.
