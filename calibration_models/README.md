# NFL Sunday Workstream 5 — calibration shadows

Governing plan: `PA-V25-MASTER-2026-11-09 / v1.1`. Ticket: the user's
bounded, low-computation November 15 calibration research workstream,
supporting Phase 1 baseline evaluation and Phase 1.5 reliability diagnosis.
Status: **implemented / tested / shadow-only / blocked-by-data**.
This is not independent verification, empirical calibration certification,
Phase 0R closure, an investment gate, a Tier promotion, or betting guidance.

All changes are confined to `calibration_models/` on
`research/nfl-20261115-calibration-shadow`. No production module,
60/40 configuration, posterior, collector, schedule, or settlement is changed.
Rollback consists of not consuming these separate outputs; no production
rollback is necessary. No live collector is called.

## Frozen experiment

Hypothesis: probability transformations might reduce the observed confidence
and directional errors without changing opportunity forecasts. Primary
comparisons are conditional nonpush Brier and log loss against **both** C1
and C2 on the identical original contract intersection. Coverage is reported
separately for every candidate. There is no winner selection, coefficient
tuning, or model promotion from Sunday's outcomes.

| Candidate | Exact configuration |
|---|---|
| C1 | Original frozen production 60/40 Over/Under/Push triple, copied without changing its values. Conditional probability is `p = over/(1-push)`. |
| C2 | Same-book, same-contract original American odds. Reuse `pickem_math.implied`; normalize `implied(over)/(implied(over)+implied(under))`. This is multiplicative two-way de-vig, without production's extra hold adjustment. |
| C3 | Reuse `reform_step8_market_shadow.equal_logit_over`: `sigmoid(0.5*logit(p)+0.5*logit(m))`, with its existing endpoint clipping at `1e-9`. |
| C4 | `0.50 + 0.75*(p-0.50)`. Fixed conservative sensitivity, **not empirically calibrated**. |
| C4_sensitivity_050 | Separately named frozen `alpha=0.50` in `0.50+alpha*(p-0.50)`. |
| C4_sensitivity_090 | Separately named frozen `alpha=0.90` in the same equation. No coefficient is selected using Sunday outcomes. |
| C5 | Reuse step 10 `fit_beta` and `beta_map`: `sigmoid(c+a*log(p)-b*log(1-p))`, nonnegative `a,b`; L2=20 toward `(a,b,c)=(1,1,0)`; mapping endpoint clipping `1e-8`. Negative or nonfinite fits abstain. |
| C6 | Reuse step 10 `fit_stack` and `stack_map`: intercept plus model and market logits; L2=20 toward `(intercept,model,market)=(0,0.5,0.5)`. |
| C7 | `d=abs(p-m)`; `s=0.25*clip((d-0.15)/0.35,0,1)`; `p7=0.50+(1-s)*(p-0.50)`. At most 25% confidence shrinkage; no effect when `d<=0.15`. This is a bounded disagreement sensitivity, not a learned correction. |

The production control policy is
`production-historical-ensemble-60-40-20261108-v1`.
The implementation version is `nfl-ws5-calibration/1.0.0`.
Model IDs hash the exact configuration, fitted parameters when present,
implementation and dependency source hashes, and historical input cohort for
learned models. The output registry records every ID and configuration.
Without training, C5/C6 IDs denote **blocked specifications**, not fitted
forecast artifacts.

### Push and eligibility semantics

Each record contains **both sides** of one exact contract. It is counted
once, never as two independent outcomes. C1 keeps the original three-way
triple exactly. C3–C7 operate on conditional probabilities and restore
unconditional masses with the **unchanged original** push probability.
That push mass is inherited from production, not fitted or market-derived.
C2 has `unconditional=null`: two-way odds do not identify a market push
probability. It can be scored on nonpush binary outcomes without inventing
one. The scorer excludes push, void, DNP, unknown, and missing settlements
from binary scores and reports exclusions; it never treats a push as Under.

Integer-valued statistics at fractional lines must have zero push mass.
Signed yardage is not truncated or forced into count support. Stat support,
period, product and settlement policy must be declared in the input.
These probability transformations do not claim a new full-stat distribution
or CRPS. Workstream 6 can separately score available three-way forecasts.

Common identity/source/time failures abstain all dependent candidates.
Missing or invalid model probabilities block model-dependent candidates;
valid C2 remains available. Missing/invalid original market quotes,
noncomplementary supplied market pairs, quote/source conflicts and reused
quote IDs block market-dependent candidates. C1/C4/C5 do not impute a
market probability. C3/C6/C7 require both inputs. Duplicate or conflicting
contract IDs/identities poison all copies, rather than choosing the first.
Started games abstain; the CLI checks the actual UTC clock again after
historical fitting and immediately before the immutable write. Every
original input row produces a status for every one of the nine named
configurations, including malformed rows.

### Historical training gate

Only historical records explicitly supplied by Workstream 1 are considered.
Every training record must have verified referenced source bytes, matching
original quote receipt content, valid original chronology, a certified
source attestation, and `out_of_fold=true`. These attestations are inherited
from WS1, not independently certified here. Only the frozen production
policy is pooled. November 15 and later events are rejected even if their
outcomes are provided. Settlements must be available before the target
input freeze. Push/void/unsettled labels cannot enter the binary fit.

Reuse step 10's first feasible chronological split: at least **300 training
contracts over 20 dates**, then **100 heldout contracts over 20 dates**.
Training labels must additionally be available before the earliest heldout
input freeze. Both classes must occur in training. Duplicate contracts or
the same game appearing on multiple dates block the cohort. Game/date folds
do not overlap. Fit once on that training prefix; never refit on historical
holdout or Sunday labels. Beta and stacking have independent fit failures.
There is no `force` option and no Sunday fitting fallback. Historical
holdout scores and paired date-block intervals reuse step 10 and remain
descriptive. The numerical gate does not establish scientific sufficiency.

## Workstream 1 handoff — identified, forecast-blocked

Workstream 1 was located on `chatgpt/nfl-sunday-ws1-source-20261115`, commit
`9c8dcea17365575337b0ab063c34e3f30e51baee`, during the final live inventory.
Its successful Deepnote run is `cd6e5a7d-bf05-490a-beb2-d0c2c3a3876e`,
notebook `6ea975e8b111442d8aca8e103c98e133`, project
`9cc31536-93be-44db-bdeb-06fba3f61410`. The run reports 1,845 original
paired contract rows, **zero source-certified and zero forecast-eligible**;
all rows failed `EVENT_IDENTITY_UNVERIFIABLE`. Twelve schedule games were
verified, but provider quote identities were not reconciled. Its frozen
legacy control columns were deliberately left null. This run is inspected
historical source evidence, not a WS5 test run or source re-collection.

Original manifest path in that project:
`reports/nfl_20261115_prospective/source_control/captures/20ed83fd40787cccc38a242a8698f0a4e09aaaa54f261b923c8a5f4aa232ed10.json`.
File SHA-256:
`9a7752e70db7c1d56226847df56f7985c1dd4fba79ae6c3b49acc9e7aad6c150`.
The filename hashes canonical JSON **without** its trailing newline; the
file hash includes the newline. These two different hashes are intentional.

`native_ws1.py` consumes that actual `nfl_20261115_source_control_v1`
manifest, verifies its canonical name/file hash and all archived source
bytes, and preserves every native source/eligibility failure for all nine
configurations. It cannot turn source rejection into a forecast or synthesize
missing frozen probabilities. Native rows marked eligible in a future packet
still abstain with `WS1_native_probability_and_settlement_adapter_incomplete`
until their precise probability/quote/settlement semantics are reviewed.
The current original packet therefore produces only immutable abstentions.

The separate `research/nfl-nov15-prospective-shadow-freeze` branch contains
an older comparison-file consumer. It is not substituted as a WS1 input.

The full probability generator additionally implements the interchange contract below,
named `nfl-ws1-calibration-input-v1`. This is a **provisional WS5 interface**,
not a claim that Workstream 1 already emits this schema. The initially inspected WS6
audit branch instead expects `nfl_sunday_ws1_original_v1` with a quote JSONL
ledger. Integration with the actual WS1 schema requires a reviewed adapter
for probability-producing rows. The native rejection adapter above already
consumes the identified WS1 packet. Do not rename an
unknown manifest or fabricate attestations to bypass this blocker.

Manifest fields:

| Field | Required content |
|---|---|
| `schema` | `nfl-ws1-calibration-input-v1` |
| `producer` | `workstream_1` |
| `target_date` | `2026-11-15` |
| `input_freeze_at` | Precise timezone-aware timestamp; cannot be in the future |
| `files` | Array of objects with relative `path` and exact byte `sha256`; every file is verified before use; traversal/escaping symlinks rejected |
| `contracts_sha256` | Hash selecting the original contracts JSON array from `files` |
| `history_sha256` | Optional hash selecting the historical JSON array; omission blocks fitting |

Each contract has `contract_id`, `sport="NFL"`, `event_id`, `player_id`,
`stat_key`, `period`, finite numeric `line`, `book`, `product_type`,
`settlement_policy`, `stat_support` (`integer` or `continuous`), `game_date`,
`event_start_at`, `forecast_at`, `input_freeze_at`, `source_available_at`,
`source_conflict=false`, and nonempty `source_sha256` pointing to verified
files. All timestamps are precise and timezone-aware. The game date must
agree with the event start's UTC date. Model-dependent candidates require
`production_policy`, `model_training_cutoff_at`, and
`production={over,under,push}` with valid, complementary probabilities.

Market-dependent candidates require `quote`, containing every identity
field above through `settlement_policy`, the identical `event_start_at`,
`original=true`, nonempty `quote_id`, `over_odds`, `under_odds`,
`available_at`, `observed_at`, and `source_sha256`. The referenced original
receipt JSON must contain the identical quote in its `quotes` array; the
normalized row's added `source_sha256` field may be omitted from raw bytes
to avoid self-referential hashing. Quote times must precede input freeze
and kickoff; invalid prices are never repaired. An optional
`market_probability={over,under}` must already be complementary and agree
with the raw-price de-vig result. It is never renormalized to hide an error.

Historical records use the same contract plus `source_certified=true`,
`out_of_fold=true`, `settled_at`, and `outcome` (`over` or `under` for fitting).
Unknown fields, including Sunday outcomes, are never used as predictors.

Run after the real schema and source packet are reconciled:

```sh
python -m calibration_models.shadow --help
python -m unittest calibration_models.test_shadow -q
```

The generator requires `--manifest`, `--manifest-sha256`, and `--out`.
The destination must be inside `calibration_models/`; creation is exclusive
and reruns cannot replace any existing receipt. There is no CLI option to
backdate the clock. The output includes the manifest hash, all input-file
hashes, source hashes, code commit, configurations, fitted parameters or
block reasons, per-candidate denominators, and every forecast/abstention.
Hashes establish byte identity, not an external trusted timestamp.

## Independent scoring handoff

`calibration_models.score.compare(report, settlements)` is separate from
the forecast module and is never imported by the pregame generator. Each
settlement must carry `contract_id`, `event_id`, the exact emitted `identity`
object, and `outcome`. WS6 remains responsible for independently authenticating
settlement source bytes and official final status before calling it.
Conflicting identities and duplicate settlements fail closed.

For each candidate, the scorer joins the candidate/C1/C2 common contracts,
reports dates/games and both baseline metrics, ten fixed reliability bins
for **both** Over and Under, signed Over residual and directional ties.
Binary scores include tied forecasts; direction accuracy excludes ties.
Paired Brier/log-loss intervals resample entire dates (primary) and games
(sensitivity), using the reviewed step 10 bootstrap (600 draws, seed
20261109). Intervals are withheld below 100 contracts or 20 clusters.
Single-Sunday results therefore cannot establish calibrated reliability.
C1 error slices use frozen absolute model-market gaps `[0,.15)`,
`[.15,.30)`, and `[.30,1]`; these examine C7's premise without tuning it.
Missing-market C1 records remain in coverage but cannot enter gap slices or
the common market comparison. No multiple-comparison-adjusted significance,
economic edge, or opportunity-model repair is asserted.

## Verification and remaining gates

Tests exercise original implementation reuse, exact C1 preservation,
price-derived de-vig, Over/Under reversal symmetry, bounded shrinkage,
push conservation, invalid identities/prices/times/source receipts,
started games, duplicate poisoning, independent candidate coverage,
manifest hashes/path traversal/exclusive writes, end-to-end synthetic
manifest generation, Sunday-outcome invariance, historical holdout-label
invariance, delayed-label leakage, and uncertified/duplicate training gates.
Synthetic chronological fixtures exercise 800 contracts on 40 dates with
a 400/400 split; they are **engineering evidence**, not real historical
NFL validation or empirical calibration claims.

The existing `fit_blend.py`, step 8 and step 10 test suites are rerun
unchanged. Their results and source hashes are recorded in the session
receipt. An isolated full offline suite is not silently represented as run.
The new tests live in this owned directory and require the explicit
command above; the repository's default `unittest discover -s tests` does
not discover them.

Remaining gates: complete verified access to the native WS1 byte bundle,
certified event identity and usable frozen probability/settlement receipts;
valid historical chronological source/OOF evidence for C5/C6; actual pregame
forecast capture and immutable external time attestation; independent WS6
scoring and adversarial review; multiple prospective dates before any
reliability claim. No release gate is passed by synthetic tests.

### Session execution status

Local relevant tests: **59 passed** (22 WS5 tests, 18 `fit_blend`, 9 step 8,
10 step 10), plus Python compilation and whitespace checks. All input data
used for new statistical fit tests are labeled synthetic engineering fixtures.

The actual original WS1 manifest exceeds Deepnote's 64 KiB text-read limit.
A bounded notebook was saved as
`77121881a3af4351a996c921440bbaf0`, code block
`11e914d1145146c2a0b39a2907e10dc5`, pinned to implementation commit
`eacaa7c711164a0e823da9d76bce684492938575`. It runs the same four suites,
then reads the native manifest and archived sources and writes only to
the owned `calibration_models/` project directory. It never calls the WS1
collector, reads Sunday outcomes or fits on Sunday's data.

The attempted detached Basic CPU (`lake`, 2 vCPU, 5 GiB) run was rejected
with **“Rate limit exceeded. Please retry later.”** No run ID was returned;
there is **no completed WS5 Deepnote run and no native Sunday forecast or
abstention artifact** from that notebook. Its planned output is not treated
as an existing file. The WS1 counts above come from the inspected completed
WS1 run snapshot, not independent WS5 verification of the full raw bundle.
The saved local model registry is specification-only. C5/C6 have no fitted
parameters. Resume the saved notebook when the service permits execution;
current WS1 failures must remain abstentions.

## November 15 Sunday execution amendment

The preceding initial-capture blockage is historical. The corrected canonical
WS1 manifest is now consumed by `native_ws1.py`; its CLI requires file SHA-256
`5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71`.
It verifies all archived bytes, native quote/candidate identity hashes, paired
raw outcomes within the same book/market/period/player/line, schedule identity,
source receipt timestamps and each game's kickoff. Duplicate exact contracts
poison every copy. Original provider-reported times remain explicitly unverified;
actual archived receipt times establish source availability. Missing player
activity confirmation does not suppress a conditional nonpush sportsbook
reference. No sportsbook payout, DNP terms or push mass is invented.

The first real C2 freeze succeeded in Deepnote run
`11d1d944-1fcc-4192-925a-aeed8c89802e`, notebook
`266c60b16cc944e48eccf33bb30eb8a0`, from code commit
`81049c04359f609986c6e76813daee81a0295954`. Actual emission was
`2026-11-15T14:18:48.776849+00:00`, before the earliest 14:30 UTC game.
Of 1,845 original rows, 1,767 C2 references were frozen across 12 games;
54 roster-identity failures and 24 duplicate/conflicting exact identities
abstained. All original controls were null. Every C3/C4/C7 configuration
therefore produced zero forecasts. C5/C6 each abstained on all 1,845 rows,
including 1,767 training-gate abstentions and the 78 source/identity failures.
No training rows were admitted; original 300/20-date training and
100/20-date validation gates remain unchanged. The pinned run passed 64 tests.

The immutable project ledger is
`calibration_models/sunday_20261115T141848783858Z.json`, 14,976,415 bytes,
SHA-256 `4bde5ffe88aabfbfe563b57835889dce88e1df56fff703faa6c3b56a132a927e`.
Its accompanying `_receipt.json` contains all model IDs, source/code hashes,
source inventory, coverage, registry, dependency graph and test outputs.
The C2 model ID is
`C2:32f05d479a99021680f7d9467910c34af4ced553c76a065b42944a5e1df8eedc`.
The original quote-source SHA-256 is
`6993a07ebce5001a55729ff556765bff388bc91cb5235416af9cd26401ede14a`.
The source freeze was `2026-11-15T04:33:16.852853Z` and quote bytes were
received at `2026-11-15T04:32:39.016077Z`. This establishes archived availability,
not independent proof of the bookmaker's publication time or executable price.

At freeze, WS2 supplied no actual forecast file. WS3 supplied delivery/review
and execution-blocker receipts, not actual frozen probability rows. No WS1
forecast-feature handoff or authentic historical calibration packet was found.
No separately registered WS2/market research forecasts were manufactured.
The ledger remains in Deepnote; automated approval review blocked exporting
its compressed bytes and companion artifacts to the research branch pending
specific user authorization. This export failure does not undo the pregame freeze.

`score.py` now reports standalone and candidate/baseline pairwise conditional
scores without requiring C1. The original three-way common-cohort comparisons
remain separately available. Push, void and DNP remain exclusions.

### Late-arriving statistical forecasts

`frozen_research.py` accepts a hash-pinned **bound export**, schema
`ws5-bound-statistical-forecast-v1`, with `source_manifest_sha256` equal to
the corrected canonical hash, `feature_sha256`, and `forecasts`.
This is an explicit interchange interface, not a claim that existing WS2/WS3
reports already emit it. Each row must carry `contract_id`, every native
exact identity field (`event_id`, `book`, `player_id`, `stat`, `line`, `period`,
`quote_id`), `event_start_at`, `family` (`WS2_S2` or `WS3_OPPORTUNITY`),
`model_id`, `forecast_id`, `forecast_at`, `input_freeze_at`,
`model_training_cutoff_at`, `feature_available_at`, `feature_sha256`,
`conditional_no_push={over,under}`, and optional `unconditional={over,under,push}`
and `stat_support`. A bound export must preserve the upstream probabilities,
identities and timestamps, and disclose its conversion lineage; missing exact
identity binding is a blocker, never a fuzzy player-name join.

Supply the actual forecast file, actual feature manifest and prior C2 ledger
with their exact SHA-256 hashes to `python -m calibration_models.frozen_research`.
The five unfitted transformations are separately registered by upstream model,
family, artifact and feature hashes. They preserve genuine push mass and leave
unconditional probabilities unavailable for binary-only inputs. The CLI checks
the real clock before saving a new exclusive ledger; it cannot update the first
freeze or create a candidate after its kickoff. No live upstream model was
available to exercise this interface today; its tests are synthetic engineering
checks only. Original C1/C3 retain their existing production-only input contract
in `shadow.py`; new research outputs are never relabeled as production controls.
