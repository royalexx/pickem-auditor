# Phase 0R — November 9 archived-slate adversarial replay

**Audit date:** November 10, 2026 (UTC).  
**Result:** SOURCE BYTES INTERNALLY VERIFIED; **STRICT PRE-EVALUATION CERTIFICATION NOT POSSIBLE FOR THESE HISTORICAL FORECASTS.**  
**Production release:** BLOCKED. **Tier 1/2:** BLOCKED. **Heavy NUTS training:** PAUSED.

## Work performed

The November 9 Deepnote snapshots were reopened **read-only** from their saved `live_pool_*.json.gz` bundles. Every `phase0_source_input_archive` entry was Base64-decoded and independently verified against both its declared SHA-256 and byte length. Each original forecast's `source_receipts` was cross-checked against that archive; every frozen `inputs` candidate was independently serialized and compared against its original candidate receipt digest. The six flagged NHL goalie-saves NUTS Over/Under pairs were independently identified. No markets were fetched, model predictions rewritten, historical timestamps inferred or archived files overwritten.

Evidence: Deepnote notebook `f8f91501571440dcae11a9ef8810bf32`; final detached read-only run `0c424fa0-dbb7-49b6-a25a-bfedaf3dcbdb`. Machine-readable results: [historical slate replay JSON](phase0r_historical_slate_replay_20261109.json).

## Verified historical results

| Metric | 2026-11-09 23:47 UTC run | 2026-11-10 00:10 UTC run |
|---|---:|---:|
| Original forecast rows | 1,568 | 1,056 |
| Rows passing **old metadata receipt** checks | 1,220 | 860 |
| Old metadata exclusions | 348 | 196 |
| Source archive byte objects independently checked | 3,894 | 2,634 |
| SHA-256 mismatches | **0** | **0** |
| Byte-length mismatches | **0** | **0** |
| Missing/unmapped source receipts | **0** | **0** |
| Original candidate digest mismatches | **0** | **0** |
| Rows with authentic pre-evaluation binding | **0** | **0** |
| Eligible for retrospective Phase 0R certification | **0** | **0** |
| NUTS Over/Under pair failures | 6 of 784 | 6 of 528 |
| Phase 0R publication eligible | **No** | **No** |

The six paired NUTS failures were all goalie-saves contracts. The older 23:47 UTC market capture rejected **948 of 2,122** input quotes as unverified or future; the later capture accepted **1,248 of 2,165**, excluding **699** associated with games already started and **218** with unverified or future market updates.

**Interpretation:** The archived bytes are tamper-evident and internally consistent. However, the old job computed its forecast **before** archiving the source input. No digest comparison can retroactively prove which bytes the numerical model actually read at the earlier instant. A strong Phase 0R proof for these original predictions is unavailable. The corrected verifier explicitly denies them strict status.

## Actual strict-validator negative-control replay

Both entire archived forecast batches were also replayed against the **new** `scripts/phase0_preflight.py` using the original 6,528 archived source byte objects materialized into isolated temporary archive roots. This is not merely an inference from missing fields: it is the actual Phase 0R release validator applied to the old source-backed forecasts.

- Run `20261109T234719Z`: **0/1,568 strict certifications**. All 1,568 rows failed `missing_or_imprecise_timestamp:input_freeze_at`. The older code's historical 1,220 metadata passes do not satisfy today's stronger contract.
- Run `20261110T001047Z`: **0/1,056 strict certifications**. Of these, 860 failed `pre_eval_input_binding_missing` and 196 failed `market_unavailable_or_unverified`. Exactly 860 pass the current *weaker* metadata-only test, but none have proof of pre-evaluation input isolation.
- No retrospective timestamp or source reconstruction was used, and no original forecast was modified. Both remain `publication_eligible:false`.

Independent Deepnote detached read-only run `df9be8c6-3006-402f-999a-3d5805dfe5cc` reproduced these results, with 3.35 and 38.87 seconds of replay work respectively. See the `new_strict_validator_replay` section of [the JSON evidence](phase0r_historical_slate_replay_20261109.json).

## Corrections now in the repository

- [PR #86](https://github.com/royalexx/pickem-auditor/pull/86): mandatory input-freeze chronology
- [PR #87](https://github.com/royalexx/pickem-auditor/pull/87): one shared deterministic posterior integration seed for both sides of NHL goalie saves
- [PR #88](https://github.com/royalexx/pickem-auditor/pull/88): freeze timestamp only after source capture completed
- [PR #91](https://github.com/royalexx/pickem-auditor/pull/91): **actual pre-evaluation** collector input archival and isolated frozen model execution, with strict certification checking, model cutoff receipts and fail-closed fallback
- [PR #92](https://github.com/royalexx/pickem-auditor/pull/92): explicitly unavailable, non-promotable NFL research sidecars when GitHub pinned artifact downloads return HTTP 415

PR #91 passed GitHub offline CI and two independent Deepnote six-suite regression runs. The final targeted run `f6fa6f26-844c-4ac9-b6b1-2ccc2f51103d` passed **60 tests** (5 pre-evaluation, 13 release, 7 capture, 13 job, 9 point-in-time, 13 model report). PR #92 passed the full GitHub CI suite and its independent nine-test Deepnote shadow suite `49019a93-6746-4387-b8a1-de971d44a4a0`.

These tests certify software behavior on frozen fixtures, **not** independent provider-publication truth or fully prospective forecast performance.

## Mandatory operational acceptance — next genuinely pregame slate

1. Pin the exact current `main` SHA and training-pause guard before the slate starts; do not launch Dell NUTS retraining. Obtain original two-sided markets from the existing free collection path; do not invent or later replace quotes.
2. Before computing a candidate, archive its canonical bytes, collector usage, original sportsbook quote data, applicable policy and any numeric lineup/season inputs. Compute the numerical result against the isolated frozen data root, not the mutable original. Explicitly mark a missing or oversized source **uncertified**.
3. Freeze the original forecast once, with source file digest manifest, market clocks, event/player identity, kickoff time, model data cutoff, evaluation-start and input-freeze timestamps. Protect idempotent reruns from mutating it.
4. Run `scripts/phase0_preflight.py` (strict certification by default) on the original forecast ledger, with the corresponding archived byte root. The output distinguishes `metadata_verified_rows` from genuinely `certified_rows`.
5. Independently audit every claimed certified row by re-reading the saved archive bytes, validating its `model_input_binding`, receipt IDs, actual evaluated candidate digest, cutoff times, event start and bookmaker timestamps. Reject missing or future sources. Preserve explicit abstentions for absent markets; no arbitrary minimum quote coverage is implied.
6. Verify no invalid same-contract Over/Under NUTS probabilities survive the existing 1e-8 integrity gate. Require a **new** pregame NHL saves shadow batch to establish PR #87's operational correction; do not rewrite the six archived failures.
7. Record unexpected failures and unavailable research sidecars in the receipt; HTTP 415 is quarantined without fallback model, ranking or training. A separate optional shadow failure cannot imply production model availability.
8. Produce the genuine live batch's `source_coverage.csv`, `forecast_receipt_manifest.json`, `phase0r_live_certification.md`, reproducible logs and independent signed audit evidence. **Only then** update `docs/phase0r_state.json` to `CLOSED` if all strict data-integrity gates pass.

**Additional limits:** a SHA-256 source receipt proves the archived bytes but cannot independently validate an upstream provider's publication clock or prove that an unarchived hidden transformation did not leak future data. Any component with such an unresolved dependency must remain research-only. Shadow Bayesian/NUTS models require their own artifact cutoffs and promotion controls; an Engine A/B input certificate is not a blanket certification of those separate models.

Phase 0R closure unblocks Phase 1 development; it **does not** authorize Tier 1/2 publication, production-model promotion, or claims of betting profitability.
