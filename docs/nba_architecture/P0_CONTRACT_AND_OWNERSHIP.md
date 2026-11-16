# NBA V2.5 P0 — canonical S/O/J/C integration contract

Version: nba-sojc-contract/1.0.0. Research-only; no model or publishing promotion.
Code base: main 912bc7010058092ea735dcda0aa941429194474b.
Scope: NBA, full-game original pregame player-stat markets including all overtime.
The S/O/J/C names are dependency families, not four equally weighted probability votes.

## Only approved dependency graph

1. Original receipt bytes and identity/eligibility evidence -> WS1 pregame snapshot.
2. Pregame snapshot -> G shared latent game state, and S independent statistical distributions.
3. Pregame snapshot + G shared state -> O participation, played-conditional minutes, rotation and opportunity allocation.
4. G + O + compatible S conditional outcome laws -> J same-draw joint player statistics.
5. S marginal law or J empirical marginal law -> exact Over/Under/Push at one unchanged contract.
6. C independent chronological calibration, official settlement, side-by-side model evaluation and diagnostics.
7. Selection/reporting may consume approved C outputs later; P0 does not implement ranking, publish tiers, train or fit weights.

G is a shared internal game-state input, not a fourth voting model. An S distribution that is conditional on O cannot be counted as independent from O or J. C may compare alternative forecasts but never votes as an outcome law. Model selection requires future precommitted testing. The historical Engine A/B, Bayesian A/B, original NUTS and 60/40 outputs are frozen, read-only comparators only.

## Versioned envelopes (Python + JSON Schema)

- pregame: original receipts, available/freeze/forecast/training clocks, game/team/player IDs, uncertainty and full attempted-source coverage. Source hash is raw bytes, not interpreted data. Hashes are not signatures or trustworthy timestamps.
- S: full nonnegative integer PMF for one statistic, explicit unconditional versus played-conditional status, provenance, parameters/version. Derived stat combos must not be added as independent component votes.
- O: explicit legal roster eligibility (nullable), P(participation) (nullable), played-conditional minutes law moments, scenario participation and conserved team opportunities. Unknown cannot silently become 0 or 1.
- G: game-wide scenario IDs, duration/overtime, pace, team possessions, score-state and shared weights; draw once per game/scenario.
- J: player and team scenario outcomes referencing exact G/O IDs, constrained physical accounting. Same draw supplies points, assists, rebounds, threes, PR/PA/RA/PRA.
- forecast: original contract ID, stat, period, line, quote timestamp and raw quote hash, one distribution pointer, one coherent Over/Under/Push triplet, explicit unverified status.
- evaluation: exact frozen forecast hash, original contract/settlement link, correction version, actual official source receipt, valid pending/settled/push/void semantics and matched/unmatched cohort retention.

The v1 pure-Python validators enforce times, source hashes, mass normalization, seed determinism, roster/member joins, player/team exposure, count support, points/rebound/assists/combo invariants and freeze immutability. JSON Schema provides machine-readable shape. These are minimum boundaries, not a claim that upstream data are authenticated or that all basketball physics are represented. A production-grade J implementation still needs lineup witnesses, missed-shot/rebound ledgers, shot/FT opportunities and detailed substitution/clock consistency.

## Ownership — exclusive write boundaries

| Owner | Owns | Does not own |
|---|---|---|
| P0 integrator | v2/nba_architecture, versioned schemas, common fixtures, ADR/gate manifest | Source ingestion, model weights, fitting, scoring claims |
| WS1 source/provenance | source receipts, strict as-of player/team/quote identities, source coverage, official lineup evidence | statistical minutes or outcome model |
| S statistical | standalone and conditional PMF/likelihood adapters; baseline/challenger implementations | roster eligibility and game-wide minute conservation |
| O opportunity | participation P1/P2, DNP separation, conditional minutes M0/M1/M2, rotations, shares, team minute ledger | source authenticity and final stat conversion |
| G/J simulation | game-state scenario and shared seed, finite pools, same-draw primitive stats and physical invariants | reinterpreting source clocks; official settlement; training selection |
| C evaluator | independent receipts, frozen contract/forecast matching, scoring, model comparison, calibration research and blocked/promotion reporting | modifying upstream frozen probabilities or simulator draws |
| Release custodian | release gate and rollback; independent acceptance of G0 and later promotions | authorizing trusted pick claims from synthetic test fixtures |

Each owning team adds an explicit adapter from its own existing schema to this v1 boundary; no team silently rewrites another team's on-disk artifacts. Breaking fields/units/semantics requires a new major schema with ADR and dual-read migration. Adding genuinely optional fields requires a minor version and new fixture. Patch releases may fix a validator bug without changing accepted record meaning.

## Deterministic fixtures and failure handling

Run: python -m unittest discover -s tests/nba_architecture -v

Each draw is keyed by SHA256(VERSION|master_seed|event|scenario|component). Freeze is create-only; duplicate identical writes are idempotent and conflicting writes fail. All source/quote/event/player IDs and clocks must be reconciled independently. Retain eligible, ineligible, missing, rejected, abstained and unmatched records in denominators. Non-original historical reconstruction stays shadow and cannot be used to assert real pregame validation. The synthetic ten-player fixture tests only contract invariants.

## G0 gate

G0 may PASS only after exact branch/tree/tests are verified, every owner has acknowledged compatible adapters or signed blockers, independent integrity review has accepted the contract, and a valid SHA-bound signed-off receipt identifies outstanding provenance and research-only scope. A local successful unit suite is necessary but not sufficient. Until then G0 is FAIL (research interface staged only). No heavyweight experiments are authorized by P0.
