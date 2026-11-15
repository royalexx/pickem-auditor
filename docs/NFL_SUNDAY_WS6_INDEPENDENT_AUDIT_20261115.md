# NFL Sunday 2026-11-15 — Workstream 6 independent audit packet

**Classification:** RESEARCH_ONLY / FAIL_CLOSED / NO_TIER / NO_MODEL_PROMOTION  
**Owner:** Workstream 6, independent audit and integration (NOT original source collection).  
**Repository base observed:** `912bc7010058092ea735dcda0aa941429194474b` (`main`, Nov 14 2026 night).  
**Branch:** `audit/nfl-sunday-ws6-20261115`.  
**Source owner:** Workstream 1 on `chatgpt/nfl-sunday-ws1-source-20261115`.  
**Deepnote project:** `9cc31536-93be-44db-bdeb-06fba3f61410`.

## 1. Exact originally observed WS1 evidence, not a forecast claim

The first genuine WS1 original raw-capture manifest was independently opened in Deepnote detached run `f3950cc0-fca8-4147-8bd7-9af33f427603` and its unchanged source bytes were rehashed:

- Original file: `reports/nfl_20261115_prospective/source_control/captures/20ed83fd40787cccc38a242a8698f0a4e09aaaa54f261b923c8a5f4aa232ed10.json`
- Size: **5,789,769 bytes**.
- Raw-file SHA-256: **`9a7752e70db7c1d56226847df56f7985c1dd4fba79ae6c3b49acc9e7aad6c150`**. Do not confuse the content-addressed *canonical-object filename* with the digest of the complete serialized file, which includes its terminal newline.
- WS1 schema: `nfl_20261115_source_control_v1`.
- WS1 code commit recorded **at capture:** `9c8dcea17365575337b0ab063c34e3f30e51baee`. This is *not* interchangeable with the latest WS1 branch HEAD.
- WS1 capture freeze: **`2026-11-15T04:33:16.852853Z`**, before the first listed event.
- Captured original **two-sided quote observations: 1,845**, **unique candidate IDs: 1,804** (difference 41 records; classify the colliding keys before interpreting them as distinct duplicate pairs).
- Verified scheduled games per WS1 evidence: **12 of 12**, ESPN event IDs present; rosters accessed for 24 teams.
- WS1 source-certified quotes: **0**. WS1 forecast-eligible contracts: **0**. No valid Workstreams 2–5 frozen forecast denominator can yet be claimed.
- WS1 first failure code: **`EVENT_IDENTITY_UNVERIFIABLE` on all 1,845**. All 1,845 candidate rows also carry `IDENTITY_UNVERIFIABLE` eligibility, and the source audit showed no accepted settled-stat/product semantics.
- WS1 recorded **50** original source receipts (ESPN schedule and roster/depth context plus PropLine original response), but **24** attempted ESPN injury feeds returned `ValueError`; no claim of injury-feed completeness.
- Workstream 1's `source_history_rows` is **0**, meaning there is no independent training-history cutoff evidence in this capture.

Original recorded market distribution (counts sum to 1,845):

| Market | Original observations |
|---|---:|
| Receptions | 568 |
| Receiving yards | 584 |
| Rushing yards | 249 |
| Rush attempts | 98 |
| Passing yards | 96 |
| Pass attempts | 69 |
| Completions | 67 |
| Tackles + assists | 114 |
| **Total** | **1,845** |

The original provider quote includes **American signed odds** (examples `-115/-115`, `-120`). Neither the WS1 source contract nor the Workstream 6 adapter may treat these as decimal-odds probabilities, executable pick'em prices, or valid no-vig comparators until quote format, pairing, product terms, timestamp, and price-vs-prop equivalence are independently accepted.

## 2. Defect attribution on the code version that actually captured the source

At exactly `9c8dcea17365575337b0ab063c34e3f30e51baee`, the WS1 `scripts/nfl_sunday_source_contract.py` `build_universe` function only resolved `opponent` from event teams if the provider quote already supplied a nonempty `team`. The live provider rows inspected had blank `team` and `opponent` but valid original `event_teams` pairs. Consequently, `event_by_pair.get(("", ""))` could not resolve a fixture, and the later roster lookup `roster.get(("", normalized_player))` could not resolve a unique player. This code path explains the observed simultaneous **1,845 event failures** and **1,845 unresolved player eligibilities**.

The current, later WS1 source-contract branch contains a narrower two-team roster-based identity resolution attempt. **It cannot repair the archived manifest retroactively.** It needs a *new* source-authentic pregame capture and independent acceptance. An earlier 1,845-row capture is retained for diagnosis, not relabeled valid. Do not silently deduct 41 collision records from the denominator.

A second blocking category is unchanged even after valid identities: WS1 explicitly has `availability_certified=false`, `forecast_eligible=false`, unverified product settlement rules, `model_training_cutoff_at=null`, `forecast_at=null`, and all frozen legacy comparison model probabilities `null`. These are not valid inputs for certified prospective forecast comparisons or economic claims.

## 3. The independent receipt-audit root correction

The first WS6 adapter test of real data in Deepnote produced a **false 0/50 archived-source hash count** because the tool invocation supplied the Deepnote *project root* rather than WS1's dedicated **capture out-root** to resolve relative `source_control/raw/...` paths. This is an independent **auditor path bug**, not evidence that any WS1 raw bytes were corrupted. The original manifest SHA remained `9a7752e...` before and after that run.

The WS6 adapter now **fails explicitly** with `WS1_ARCHIVE_ROOT_MISMATCH_USE_CAPTURE_OUT_ROOT` if a canonical WS1 capture is opened with an incorrect archive root. The proper value of `--root` for this capture is:

`reports/nfl_20261115_prospective`

The first (false-negative) review was preserved under `reports/nfl_20261115_ws6_audit/ws1_9a7752e70db7c1d56226/`, classified **INVALID_AUDITOR_ROOT_NOT_CERTIFICATION**. A corrected-root detached Deepnote run **`7883fd70-afa3-4b42-9374-8781b75717d5`** independently rehashed **50/50 raw source receipts successfully**. The valid immutable review is at `reports/nfl_20261115_ws6_audit/ws1_9a7752e70db7c1d56226_rootverified/`. The corrected derived manifest SHA-256 is **`e0deabc878de9d5211f3d019584122c6e9b5a87344802ce78851aae0da6d1ff2`** and the independent derived original-quote ledger SHA-256 is **`9d1d1d2061ab92ae043bf55644d71e942a1f0144f6841be92fcf09933939a861`**. Raw-byte verification does **not** validate provider publication clocks, unlinked player identities or exact product settlement rules.

## 4. Implemented Workstream 6 infrastructure

All WS6 changes are additive research-only paths and cannot trigger source collection or production publishing.

| File | Purpose |
|---|---|
| `research/nfl_sunday_ws6_audit.py` | Original-quote/source SHA checks, event/player/stat/line/period identity, timeline/model freeze, probability/support validation, append-only research comparison ledger; separate official-only settlement and proper scores. |
| `research/nfl_sunday_ws6_ws1_adapter.py` | Independently checks exact WS1 source schema, 12-game schedule, original file SHA, raw receipt paths, rejected/abstained candidate population, and creates **new** derived source/quote/identity ledgers. Does **not** upgrade a WS1 source-rejected record. |
| `research/test_nfl_sunday_ws6_audit.py` | 23 adversarial unit tests: source hashes, corruption, post-kickoff, duplicate, selected side, discrete push, CRPS, market-only benchmark semantics, game-completion gate. |
| `research/test_nfl_sunday_ws6_ws1_adapter.py` | 6 adversarial unit tests: genuine native field mapping, refusal to upgrade bad archive, schedule mismatch, immutable original, and source-rejection retention. |
| `research/nfl_sunday_ws6_pending_universe.py` | Generates a create-once 1,845-observation immutable attempted-quote comparison with null model probabilities and explicit rejection states; never misrepresents rejected rows as certified contracts. |

**Executed tests:** **29/29 PASS**, final Deepnote detached **read-only** run `66791a40-0629-4702-a8cb-2c22445f65c5` (23 scorer/provenance + 6 WS1 adapter); both test modules passed on synthetic *test fixtures only*. Earlier exploratory test failed due a mistaken expected Brier value in the test assertion (the correct three-way half-Brier for (0.4,0.4,0.2) when a push occurs is 0.48), corrected before the 26-test run. This is software verification, **not** actual Sunday forecast certification or predictive validation. The corrected archive-root guard, common log-loss epsilon, and official result chronology have been re-tested. This validates isolated fixtures and does not constitute an independently certified Sunday forecast.

**Actual full-slate attempted-universe archive created (before kickoff):** Deepnote detached run `ea72a0e7-93c5-47ce-9c4a-e40739e24602` produced `reports/nfl_20261115_ws6_audit/original_attempted_universe_9a7752e70db7c1d56226/attempted_universe_comparison.jsonl` with **1,845 unfiltered original quote observations, 1,804 distinct candidate IDs and 41 duplicate-excess observations**. All original source quote references and rejection reasons remain row-level and all model/market/outcome fields are null; this is **not** a certified, scored or forecast-complete model universe. The verified ledger SHA-256 is **`0faa133410964e674f7bc4a6e4d4c74583a078d230a165af618123966e0e225c`**. The separate `attempted_universe_index.json` preserves the complete denominator and source-manifest SHA.

Research freeze output (only after strict eligible-source proof): `comparison_ledger.jsonl`, `source_receipt_ledger.jsonl`, `quote_rejections.jsonl`, `forecast_rejections.jsonl`, `model_registry.json`, `integrity_report.json`, `freeze_index.json`. Original control names are never filled by calculated challengers. Missing models are represented as null with explicit coverage denominators. A new source/news event creates a new version, never overwrites frozen values.

Settlement output (only after original freezes and **12 official final game receipts**): `settlement_ledger.jsonl`, `invalid_official_outcomes.jsonl`, `score_report.json`, `score_index.json`. No score is created before game-final/source checks. Pushes remain a third category rather than binary misses. DNP, void, unmatched, missing outcomes are retained separately.

## 5. Scoring contract and statistical limitations

Define `q_over=P(Y>L)`, `q_under=P(Y<L)`, `q_push=P(Y=L)`. Require each in [0,1] and total = 1. When official `Y` exists, one contract has one three-way outcome. Full three-class Brier is `sum_k(q_k - 1[k=outcome])^2`; **half-Brier is explicitly distinguished**. Three-class log loss is negative log probability of the realized category. For nonpush binary outcome, compare **conditional `q_over/(q_over+q_under)`** and report pushed contracts separately. A genuinely compatible two-way sportsbook market reference is **conditional on nonpush**; do not fabricate the market push mass or include it as an unconditional three-way forecast.

For complete discrete distributions, CRPS uses `sum_i p_i|x_i-y| - sum_{i<j} p_i p_j |x_i-x_j|`. For missing or unsupported distributional evidence, CRPS is null, not zero. Distinct models are compared only on *exact common contract IDs* and official outcomes, with game-cluster paired confidence intervals (and one-date dependence caution). Report original candidate coverage, all abstentions and failed/missing challenger forecasts, selected-vs-unselected, side skew, confidence-vs-frequency and per-market results.

**One Sunday is not a model selection dataset.** No model tuning, Tier release, multiple-comparison winner declaration, retroactive threshold change, or production promotion is permitted from these results, whether favorable or not.

## 6. Integration handoff and current decision

**Blocking issues, ordered:**

1. **WS1 identity repair:** deliver a *new* original source manifest from its existing sole-source collector, with player and ESPN event mapping independently verified; preserve the first 1,845-row attempt for audit. Do not reproduce source retrieval in WS6.
2. **Source/archive/offer gate:** raw receipt content SHA-256 has passed **50/50** corrected-root checks; separately accept original quote and terms, payout/source semantics and pregame availability, and fully classify 41 duplicated candidate-ID excess rows without silent dropping. Original signed odds need explicit interpretation/format and compatibility before computing no-vig.
3. **Forecast handoff:** WS2–5 must provide truly frozen original contract ID, quote ID, same source manifest raw SHA, model name/version/commit, model artifact hash, real training cutoff, forecast-input freeze, external pregame attestation, distribution and calibrated probabilities (or explicit per-model abstention) before matching; legacy 60/40 remains unchanged.
4. **Official outcome handoff:** independently observe final game/source evidence after all games, map player statistics to exact period/stat policy, preserve void/push/zero/DNP and missing cases. No scoring before final verification.
5. **PR gate:** review code/overlap vs main and WS1 separately, execute full regression suite and correct-root audit, and obtain independent signoff. Merge **research infrastructure only** if accepted; no production model changes or automatic execution.

**Exact classifications as of this packet:** WS6 code = **IMPLEMENTED / TARGETED TESTED / RESEARCH_ONLY**. Original WS1 capture = **PRESERVED / INTEGRITY_CANDIDATE / NOT CERTIFIED**. WS1 quote/model universe = **0 certified, 0 forecast-eligible from first capture**; 50/50 raw receipts SHA-verified, provider publication and product/offer semantics not certified. Full-slate model ledger = **BLOCKED BY SOURCE IDENTITY + MISSING ORIGINAL FORECASTS**. Sunday settlement = **NOT STARTED, FUTURE EVENT**. Model selection = **PROHIBITED**.

No workstream should merge source collector changes into this branch or use research-branch test successes to authorize betting selection. A paper trail of all failure states and original SHA is more valuable than a fabricated early 60/40 or Tier score.
