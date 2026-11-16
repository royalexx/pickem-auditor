# Engineering candidate for independent G0 review

This continuation supersedes the **verification status**, not the preserved evidence, of the partial packet in `hardening_20261116`. Governing authority: PA-V25-MASTER-2026-11-09 / v1.1. The engineering sweep defined below is complete and has no known unresolved critical/high G0 defect. Independent technical acceptance remains pending. Synthetic tests are not proof that the system is defect-free, fitted, authentic, predictive or production-ready.

Use the exact final PR head and its fresh execution receipt, not a moving branch name. The implementation freeze commit is recorded in receipt.json; the evidence-only final head is identified in PR #156. No substantive code may change after freeze without repeating affected checks and issuing a new receipt.

## What the continuation changed

The first new discovery log records 11 accepted contradictions and two valid-state errors among 14 tests. Subsequent red logs preserve source data-cutoff, open O player payload, superseded revision, invalid threshold mass, minute-law support, blocks and steals failures. The failure ledger records test-level input construction and closure. All earlier seven repairs, five independent repairs and three participation failures remain executable regressions.

Repairs add consecutive source revision chains and current-feature revision binding, prior-date/source-scope matching, a local-date/UTC-freeze plausibility bound (without inventing a timezone), precise RFC3339 UTC timestamps (up to six fractional digits; finer precision is rejected rather than truncated), source-bound roster evidence, team-total type/identity checks, closed witnesses/O player fields, conditional-target DNP rejection, numerically stable mixture sums and a global 1e-12 marginal L1 tolerance, real discrete minute-law normalization/support, defensive opportunity bounds, full correction context and complete forecast/settlement validation. Unknown eligibility cannot carry undeclared evidence.

Only two preexisting positive fixtures in test_v2_contracts.py needed context migration: the valid correction now supplies the predecessor object, and the valid source correction selects its new receipt for the feature. Assertions remain intact; neither rejection expectation was weakened. All three original golden JSON files, prior FAIL/BLOCKED receipts and previous documentation remain byte-identical. A new complete-pipeline golden is added separately.

## Mandatory complete-pipeline boundary

`families_v2.validate_forecast(d,p,g=...,o=...,scenarios=...)` is the G0 full-forecast entry point. It validates the actual upstream objects and binds their original output hashes/model lineage/allocation to the distribution. S_ONLY requires no offer and no O/J. S_O and S_O_J require actual G/O context; a shared G dependency must be declared in lineage. J additionally requires the actual joint bundle. Component-only `validate_distribution`, `validate_scenarios`, and `validate_evaluation` are local interface checks and must never be represented as integrated acceptance.

`families_v2.validate_settlement(e,d,p,view=...,quote=...,g=...,o=...,scenarios=...,history=...)` is the C entry point. It revalidates the complete frozen forecast, actual original quote and offer view, and every prior correction beginning at revision 1. Missing originals, duplicate settlements, missing/reordered history, identity drift and backdating fail closed. `validate_evaluation(...,previous=...)` also requires the immediate predecessor for corrections; local validation does not replace full-history C validation.

`parse_contract(raw)` is the strict external JSON ingestion entry point; ordinary json.loads cannot detect duplicate keys. Nonfinite JSON and duplicate keys fail before a contract is consumed. Native Python payloads still require the semantic validators.

The inherited `synthetic_point_mass` descriptor is retained solely to read preserved diagnostic fixtures; it is **not a complete normalized exposure law** and the full forecast boundary rejects it. `discrete_minutes` specifies a normalized conditional law over minutes, including genuine played-zero when applicable. Every positive-weight played draw must be in support. The law is bounded by the supplied G scenario envelope; finite sample frequencies need not equal law masses. Additional continuous/parametric law families need registered support/normalization semantics and executable positive/negative cases before full acceptance. No actual fitted opportunity family is claimed by this G0 candidate.

## Participation transition matrix and source policy

| Eligibility / availability / evidence | Probability | Positive-weight permitted states |
|---|---:|---|
| Verified ineligible or source-bound authoritative OUT | null or 0 | DNP only |
| Eligible/unknown, uncertain availability | null | DNP, played-zero, played-positive |
| Independently estimated | 0 | DNP only |
| Independently estimated | strictly between 0 and 1 | DNP, played-zero, played-positive; no exact sample frequency requirement |
| Independently estimated | 1 | played-zero or played-positive |
| O verified_out evidence | 0 and exclusion bound in snapshot | DNP only |

DNP/played-zero have zero minutes and zero count stats; PLAYED has positive minutes. Zero-weight rows remain physically and legally valid but do not impose probability endpoint events. A rounded official 0:00 is not automatically genuine zero exposure; real adapters must resolve rounding explicitly. Reported statuses other than unknown require source-bound player/game/field/value evidence. `out` is authoritative for this snapshot; uncertain reports use questionable/unknown. This policy does not authenticate the underlying source. Early exit is legal positive exposure. OT raises team minutes to 240+25*OT and player capacity to 48+5*OT.

## Completed attack plan and invariant ownership

`invariants.json` contains 24 manually reviewed groups with producers/validators, requirements, positive/negative executable references, resealing policy and G0/G1/G2 ownership. `check_inventory.json` includes every extracted req expression in both v2 modules, mapped to those groups. `test_inventory.json` locates the old and new cases. Reproduction checks these references and rejects missing mappings.

The sweep includes deterministic resealed cross-object attacks, the 600-case participation transition enumeration, 32 seeded random weighted mixtures, deletion of every required top-level field for all eight contract kinds, additions to every closed object represented in their schemas, all physical count fields at negative/fractional/boolean boundaries, all prospective source clocks crossing freeze, duplicate raw JSON keys, unknown fields/conditioning, source/settlement revision mutations, conditional-law support/mass, all eight primitive/composite marginals against an exact correlated joint reference, independent Poisson and negative-binomial reference calculations, and positive row/scenario reorder, player renaming, unequal weights, played-zero, OUT/DNP and OT counterparts. The existing historical, shooting, shared rebound, self-assist, quote, push, void and immutability regressions remain included.

Four deliberate guard mutations are killed by targeted tests: hard-zero participation, certain-participation DNP, conditional-target DNP, and minute draw outside conditional support. Their logs contain expected negative-test failures, not accepted test failures or skips. This is a targeted mutation sensitivity check, not a claim of exhaustive code mutation coverage. `run_guard_mutants.py` reproduces it using temporary isolated source copies.

## Family conformance and residual boundaries

| Family | G0 evidence | Remaining G1/G2 ownership |
|---|---|---|
| WS1/P1 | Source clocks, exact revision chains, identity and source-bound claims | Raw-byte authenticity, truthful publication/capture, source crosswalks and real receipt adapters |
| S/P2 | Full market-independent eight-stat distributions and component/data-cutoff lineage | Real conditional S model, fit, calibrated numerical approximation and fitted artifact manifest |
| O/P3 | Legal/participation distinction; normalized discrete law; exact G-conditioned exposure | Real participation fitting, accepted parametric laws, source rounding and actual owner adapter |
| G/J/P4 | Exact G/O/J joins, minute/shot/point/composite accounting and shared aggregate opportunities | Chronological five-on-court and event-level possession/OT trajectory witnesses; complete fitted generative pipeline |
| C/P5 | Full forecast/quote/terms/correction-chain context and settlement state checks | Authentic product interpretation, official-result evidence and external globally unique append-only storage |
| Independent QA/P6 | Own new adversarial cases, registry and deterministic author-run receipts | A separate reviewer must challenge the exact frozen candidate and may reject it |

The 146 pinned upstream v1 tests from the preceding packet remain unchanged-source regression evidence, not accepted v2 adapters. No G1 or G2 completion is asserted. A SHA proves structural byte consistency, not external authenticity or truthful provenance. Historical reconstruction remains uncertified even if a current archive includes corrected statistics. Aggregate rebound maxima include all missed FTs conservatively and do not prove every missed FT was live. Assist bounds prove aggregate no-self matching feasibility, not chronological play-by-play. MC ESS/SE describe heuristic numerical precision, not epistemic certainty or independent NBA games. Model/code manifest claims need genuine producer execution evidence at G1. Store-wide duplicate indexing/access control requires the real immutable storage adapter.

## Reproduction, handoff and rollback

From the frozen checkout: `python -m pip install -r v2/nba_architecture/requirements.txt`, then `python docs/nba_architecture/completion_20261116/reproduce.py --out /tmp/g0-independent-run`. The script checks schema, legacy and full-pipeline goldens, every prior document byte against c53a725, registry links, exact source/fixture hashes and full unittest discovery. Optional targeted mutation sensitivity: `python docs/nba_architecture/completion_20261116/run_guard_mutants.py` (writes only this new campaign's mutant results; use a disposable checkout when preserving the freeze).

Reviewer prompt: Independently audit PR #156 at its exact frozen final head. Read both modules, schema, new complete-pipeline boundary and this versioned registry. Rerun reproduction; reproduce the saved red cases at their original pre-repair checkpoints if needed. Invent different attacks, especially strict JSON ingestion, source/correction chain identity, O law/zero-minute semantics, full G/O/J-to-C joins, conditioning and threshold numerical boundaries. Treat all author conclusions as untrusted. Accept technical G0 only if no material defect remains, all stated engineering criteria reproduce, and remaining source/fit/event/storage limitations are correctly allocated to G1/G2. If you repair substantive code, hand it to another reviewer. Do not merge, train, optimize, score historical skill or deploy.

Rollback: close the draft PR and inspect c53a725 (previous partial repair) or 18bd569 (pre-repair independent red branch) in a separate detached checkout. Keep all original and new receipts. Main, production collectors, original archives, notebooks and schedules were not modified. The synthetic candidate author does not issue independent G0 PASS.
