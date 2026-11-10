# Phase 0R — Nov 10 prospective certified-only source-origin acceptance decision

**Decision: NOT CLOSED.** Internal archived pre-evaluation data integrity passed. The upstream source-origin / quote provenance release gate remains unresolved. This report does **not** retrocertify data or authorize Tier 1/2 publication, production model promotion, or new NUTS training.

## Source and immutable evidence

- Daily Deepnote run: `ccd5d53d-6583-4380-97ed-9fda64e90559`; **success**, completed 2026-11-10T18:11:00.233Z.
- Frozen source code: `e5635d8fd8444a3144174cf019924d2010cdbca8`, merged PR #99.
- Run stamp: `20261110T180409Z`.
- Immutable published bundle SHA-256: `76f8cabc512977ce33017e73c72b7708d452e5f5ec962b33d3ee7f91c75285e6`.
- Independent audit notebook: `818a10801dc34193b3a366659069137f`.
- Independent strict archive run: `7617e496-7e06-486d-b0a3-389d004d3ee9`; original archive full-universe, source receipt, and tampered-fixture tests.
- Independent source-origin assessment run: `ff98c686-a32e-4244-8dad-17ad882ed692`.

## Independent acceptance results

| Control | Verified result |
| --- | --- |
| Total prepared / attempted forecast contracts | **1,314** |
| Retained immutable forecast contracts | **712** (NBA 500, NHL 212) |
| Rejected before forecast | **602** (NBA 558, NHL 44) |
| Rejected: unresolved external context | **438** |
| Rejected: missing/unverified market | **164** |
| Source blobs independently SHA-256 checked | **1,783** |
| Archive SHA mismatch / byte-length mismatch | **0 / 0** |
| Duplicate forecast contract identities | **0** |
| All frozen pre-evaluation, market, model-cutoff, receipt, and input-binding checks | **712 / 712 passed** |
| Retained forecast erroneously listed among rejected attempts | **0** |
| Missing retained forecasts from original attempted universe | **0** |
| Deliberately altered forecast fixtures rejected | **10 / 10** |
| Corrupted archive byte detected | **Yes** |

Deepnote audit evidence is in `reports/phase0r_20261110T180409Z_independent_final_audit.json`, `reports/phase0r_20261110T180409Z_adversarial_fixtures.json`, and `reports/phase0r_20261110T180409Z_closure_decision.json` in project `9cc31536-93be-44db-bdeb-06fba3f61410`.

## Remaining P0R-05 source-origin gap (closure blocker)

All **712** archived `Market/original_book_quotes` receipt records have `source_url_status=upstream_url_unknown`, empty `source_url`, no third-party `published_at`, and `clock_semantics=collector_captured_no_publication_claim`. All **712** `Engine_B/original_research` receipt records similarly lack an upstream URL and publication claim; distinguish legitimately internal research from external sources. `Engine_A/historical_usage` references do carry a sanitized ESPN source URL on all 712 receipts.

The market quotes have immutable collector retrieval and observation timestamps and passed internal market-line/book-contract consistency checks. **This does not imply the quotes were late or forged.** However, a source digest and collector timestamp cannot independently establish original upstream provider identity or upstream publication chronology. The Phase 0R P0R-05 original-source provenance requirement cannot be signed off as fully independently verified merely because the 712 rows pass the internal strict-binding validator.

## Required fix and next audit

1. Capture authentic upstream provider/offer reference (provider identity, book offer ID and/or original URL) with a verifiable first-seen/retrieved-at capture **before** any model evaluation; explicitly tag genuine internally generated research as internally sourced rather than `upstream_url_unknown`.
2. Make the strict certification gate reject unknown or unverifiable *required* quote origins; retain original complete candidate/reject denominators.
3. Validate using fresh property/time-travel tests and **another genuinely prospective** NHL/NBA freeze with no retrofit of the November 10 records.
4. Independently reconcile the new archived quote receipts, full rejected universe, source digests, pregame cutoffs, and provenance; then write a versioned release sign-off. Keep Tier 1/2 publication and model promotion blocked regardless of Phase 0R infrastructure success until separate statistical release gates pass.

**Formal Phase 0R release status: BLOCKED_P0R05_ORIGINAL_SOURCE_ORIGIN_NOT_INDEPENDENTLY_VERIFIABLE.**
