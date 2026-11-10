# Phase 0R scoped acceptance correction — November 10, 2026

**Decision:** NHL/NBA pregame input-contract and provenance infrastructure **ACCEPTED** for the genuine November 10 prospective run. This corrects the over-strict P0R-05 gate in [the earlier November 10 decision](phase0r_nov10_prospective_independent_audit_decision.md), without altering the original frozen forecasts, receipt bytes, confidence thresholds, or historical records.

**Scope:** 500 NBA and 212 NHL original forecast contracts. The November 10 run did **not** prove a complete NFL prospective certification. Tier 1/2 publication, production model promotion, and NUTS sidecar model approval **remain separately blocked**. The 60/40 baseline stays frozen.

## Finding: the missing URL was in the wrapper, not in the original quote

The frozen aggregate `Market/original_book_quotes` source receipt intentionally does not contain a single upstream URL: the original quote file contains **both** NBA and NHL records, originating from two different PropLine bulk API paths. Its `source_url_status=upstream_url_unknown` described only that *aggregate wrapper*. It did **not** mean the individual original quote rows lacked original-source references.

Independent read-only examination of the original immutable source bytes proved:

- **1,817** original two-sided bookmaker quote records, with **1,817/1,817** HTTPS `source_url` values on `api.prop-line.com`, and **1,817/1,817** retrieval timestamps.
- **1,421 NBA** quotes from `/v1/sports/basketball_nba/odds` and **396 NHL** quotes from `/v1/sports/icehockey_nhl/odds`.
- **1,998/1,998** retained market book-receipt references match the original frozen quotes by sport, event ID, normalized player (including Jr/Sr suffix resolution), market/stat, bookmaker, line, both Over/Under prices and retrieval timestamp. Every linked quote has the expected API URL, PropLine event namespace, correct event start, and a retrieval timestamp before the model's input freeze.
- **712/712** original retained forecasts independently pass the patched strict pre-evaluation source validator when the complete original archive is reconstructed in an isolated temporary directory and rechecked. No new or revised forecast was generated.
- Original immutable bundle SHA-256: `76f8cabc512977ce33017e73c72b7708d452e5f5ec962b33d3ee7f91c75285e6`.

**Explicitly retired extra gate:** The PropLine API cannot supply a direct originating *bookmaker* URL or trustworthy bookmaker *publication* timestamp for every aggregated offer. Their absence is not a reason to reject an otherwise authentic, archived, pregame provider quote. Claims are limited to API collection evidence and pre-evaluation availability; no independent sportsbook publication/price truth is asserted.

The Engine B `original_research` source receipt identifies a **collector-derived research artifact**, not necessarily a third-party page. It is stored and hashed as an immutable input; externally sourced facts remain prohibited if unpinned, and the production gate continues to reject such `event_context` candidates.

## Scope and actual original collection

| Audit control | Outcome |
| --- | ---: |
| Original prospective collection | Deepnote `ccd5d53d-6583-4380-97ed-9fda64e90559`, success |
| Code commit used to generate actual forecasts | `e5635d8fd8444a3144174cf019924d2010cdbca8` |
| Prepared slate candidate universe | 1,314 |
| Certified retained forecasts | 712 (500 NBA, 212 NHL) |
| Rejected pre-evaluation | 602 (438 unresolved context; 164 market unavailable/unverified) |
| Source objects independently hashed | 1,783 |
| Source hashes/length errors, duplicate contracts, leaked rejected contracts | 0 / 0 / 0 |
| Original market-book references independently matched | 1,998 / 1,998 |
| Tampering fixtures rejected | 10 of 10 plus altered archive bytes |
| New API-origin adversarial unit tests | 11 of 11 |
| Full focused source/collector test suite | 49 of 49 |
| Patched strict checker against ORIGINAL frozen batch | 712 of 712 accepted |

## Patch and regression protection

The new `scripts/phase0_quote_origin.py` verifies API quote lineage **directly against existing archived original quote bytes**, not the wrapper receipt, for PropLine-namespace contracts. `scripts/phase0r_contract.py` applies it during strict pregame certification. It rejects missing/wrong API URL, wrong event, wrong player, wrong stat, wrong book, wrong line, changed odds, changed retrieval clock, inconsistent normalized identity, and ambiguous duplicates. It does not request any new API data or reconstruct bookmaker publication times.

Adversarial tests: `tests/test_phase0_quote_origin.py`. Branch QA (source commit `7f6040e6cc9faf8dd7b89b8f7f0ffe7a23e68ec1`): Deepnote run `38106522-e762-4f1e-aebf-a76c2dd1c610`. Full actual original archive strict replay: `113cf255-1cf4-429f-9176-7439d8d267cc`. Original quote-level provider audit: `0305f780-884e-4a60-a5c0-9ea599971411`.

All detailed independent artifacts are in Deepnote project `9cc31536-93be-44db-bdeb-06fba3f61410`, under:

- `reports/phase0r_20261110T180409Z_independent_final_audit.json`
- `reports/phase0r_20261110T180409Z_original_api_quote_linkage.json`
- `reports/phase0r_20261110T180409Z_adversarial_fixtures.json`
- `reports/phase0r_20261110T180409Z_scoped_acceptance_v2.json`

## Remaining boundaries

1. **NHL/NBA Phase 0R operational infrastructure:** ACCEPTED for the prospective Nov 10 frozen contract universe. Unverifiable candidates continue to be rejected; full attempted-universe denominators are preserved.
2. **NFL Phase 0R operational infrastructure:** NOT certified by this Nov 10 NHL/NBA run. Requires its own genuine prospective NFL acceptance when an eligible slate exists.
3. **Tier 1/2 confidence publication, model promotion and Tier power:** BLOCKED. Passing this infrastructure gate does **not** validate forecast directional accuracy, calibration, edge, or economic profitability.
4. **Bayesian/NUTS outputs:** separately shadow/research only unless their own frozen artifact and model-convergence promotion gates pass.
5. **Earlier Nov 9 forecasts:** remain uncertified, unmodified, and never backfilled with the Nov 10 quote evidence.

**Acceptance classification:** `PHASE0R_SCOPED_ACCEPTED_NHL_NBA`; this is **not** `PRODUCTION_MODEL_APPROVED`.
