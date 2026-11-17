# Native P1/P2/P3/P4 → C engineering transport v1

Authority: PA-V25-MASTER-2026-11-09 / v1.1. Accepted G0 remains
`59d28dc23be97de2a6a82d22be8338151e31f5b6`; its source and tests are unchanged.
This is an owner implementation proposal awaiting independent P6 review. It
awards no source admission, family acceptance, G1 acceptance or G2 authority.

## Forecast-only input and byte domains

`v2.nba_c.native_adapters.NativeForecastArchive.put_s` invokes the actual loaded
P2 `predict`, taking immutable `FittedS.payload` bytes, the original G0 pregame
object, exact source manifest and optional original G/O objects. P2 decides
whether it can produce a complete S_ONLY or S_O law. C preserves its distribution,
abstention reason, parameters and uncertainty. C does not replace its model,
resample O, erase an unknown participation probability or weight stages as
separate forecasts. Each attempted intake records produced/abstained counts.

The archive binds the raw fitted-artifact SHA-256, every P2 package source file,
the exact training-source manifest, original G/O objects and the actual returned
prediction. A separate G0 ForecastWarehouse validates and freezes the emitted
complete distribution. `get_s` independently rechecks all byte references,
artifact/model-code/source joins, G/O lineage and stored forecast equality.

P1 native source exports use `nba-p1-native-handoff/1.0.0`. Original supplied
source bytes and every ancestor are retained as base64 with raw SHA-256. These
are exact supplied export/source bytes. Canonical envelope hashes and parsed
JSON hashes are different domains; neither establishes original HTTP identity
or pregame availability. Source/capture schemas are closed. Revision ancestry
and retrieval clocks must remain consistent. A caller's `verified` flag is not
accepted. Every export remains BLOCKED and unadmitted.

Prior-game source attachments bind the original raw game identity and start,
exclude the target game, and must precede both the declared pregame cutoff and
fitted-artifact cutoff. Their source-bound duration, exact/displayed minutes,
player/team/stat identities and typed denominators are checked. Modern retrieval
and ingestion clocks remain modern; missing original availability, outcome
release and role evidence remain null. No source authentication is inferred.
Pregame context exports retain UNPROVEN roster completeness, missing home/role/
membership/participation fits and the observed candidate denominator. They never
complete an authentic roster from a synthetic model fixture.

## Actual latest J intake

`NativeForecastArchive.put_j` accepts the loaded actual P4 producer and its
original pregame/G/O/sidecar, fitted artifacts, source manifest, roles and
upstream source root. It invokes P4 `simulate_latest` and P4 `scenario_pmfs`.
There is no API for submitting a caller-written J result. All eight statistics
are derived from the same original J draw bundle. No independent marginal
sampling or post-draw physical repair is performed by C.

The native manifest is joined to the S lineage artifact, consumer code files,
upstream registry, artifact bytes, source manifest, roles, G/O/sidecar identities,
scenario hashes and event-audit ledger hashes. The original G0 integration and
forecast validators check the same-draw laws. Every actual pinned upstream code
file, synthetic fixture source/context byte, fitted artifact and input object is
preserved. `get_j` rechecks these bytes and joins and retrieves every immutable
G0 forecast. P4's law proposal remains PENDING independent acceptance; its real
integration status remains BLOCKED. Empty manifests, arbitrary versions, PASS
claims and altered scenario/audit hashes reject. Retaining a manifest is not an
independent acceptance of P4's approximation or event-time semantics.

## Separate native outcome transport

`NativeOutcomeArchive.put_p1` takes only an actual P1 outcome export. It has a
physically separate `native_outcome_only` root. Forecast intake takes no vault,
no native outcome export and no outcome lookup. The native outcome reader stores
every original record/source/accounting byte and every correction, preserving
DNP, PLAYED_ZERO_MINUTES, PLAYED, UNRESOLVED and VOID distinctly.

The consumer checks closed record schemas, record seals and canonical raw bytes,
source hashes, monotonic correction clocks, stable player/game/team identities,
source-bound accounting descriptors and the latest-summary join. It derives the
start clock, exact minutes and player/team/stat relationships from retained raw
accounting evidence. Raw ISO minute comparisons use exact rational arithmetic
before float serialization. Legal multi-OT caps use the specific prior game's
period count. Positive subminute exposure remains separate from a zero display;
true-zero positive credits remain quarantined even if the caller omits them from
its normalized stats. Nonplayed raw positive minutes or credits reject rather
than being erased or reinterpreted as DNP. Unknown participation does not become
DNP through a numeric zero or an owner assertion.

Partial counts must admit an exact nonnegative integer basketball completion.
`physical_counts.py` uses an exact P/R/A linear projection and closed-form
shot/free-throw count supports. This is a feasibility check, not an imputation:
it returns no invented statistic. It rejects odd/impossible shooting totals,
half-integer combination solutions and rebound-component contradictions. It
uses no historical data, floating optimizer or arbitrary count cap.

P1 schema v1 supplies no source-bound event-end or official-release clock. Those
fields and `official_count` must remain null. Missing-outcome exports retain
null display/exact minutes, empty stats and UNRESOLVED status. Typed summary
checks reject Boolean/integer equivalence. `scoring_disposition` always returns
BLOCKED and `scored: false`; the adapter never manufactures a G0 evaluation.
Admission requires a separately reviewed source population and clock contract.

## Recursive forecast quarantine and retained experiment gates

The synthetic `CachedCohort` forecast-input walker visits all dictionaries,
lists and tuples, including alternating or repeated containers. Cycles reject;
shared valid substructures and legitimate pregame numeric arrays remain legal.
Source/model clocks and linked identities use the same complete traversal.

Reserved target-result keys are case- and separator-invariant. The `actual*`,
`realized*` and `targetgame*` namespaces reject; `target_game_id` is the sole
identity exception and must match the row's game. Official-release/end clocks,
final roster/score and target outcome/result keys also reject. Explicit
`prior_game_*` and `projected_*` numerical leaf fields remain legal. Renaming a
field to a case/spacing variant or placing it inside nested lists does not make
it pregame evidence. Valid PMF integer keys are unaffected.

All original F-P5-01 controls remain: event/date/season alignment, conservative
2023–24-and-later quarantine, source/forecast/training clocks, independent
freeze/start/end/release chronology, supported-clock validation, complete
pipeline membership, uniqueness, valid full-count PMFs and W3 validation before
sparse fallback. Historical fitting remains unavailable. W0/W1/W2/W3 operate on
complete pipelines only; W4 remains prohibited.

## Independent acceptance and remaining prerequisite

Only `evidence_mode='synthetic_engineering'` is implemented for native intake.
Every real-mode value fails closed before forecast/outcome access. A successful
synthetic call proves callable compatibility and byte/semantic preservation;
it does not admit a real source, fit, complete roster, historical forecast or
P4 constrained law. B-P5-01 remains BLOCKED until P1 supplies independently
admitted original source/event/end/release/correction evidence and the latest
P2/P3/P4 contracts receive independent acceptance. No historical fitting,
historical scoring, G2 execution, automatic merge, deployment, schedule change
or Tier promotion follows from this implementation.
