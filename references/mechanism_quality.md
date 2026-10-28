# Evidence-quality mechanism grading

The live verified Tier pipeline does NOT promote plays by counting named mechanisms or citations. Statistical and market probabilities remain unchanged; the research component supplies a source-audited maximum Tier. The lower of the existing numeric/risk rank and that maximum is used.

## Eligibility

- Legacy unverified events, bare article links, duplicated citations and incomplete causal narratives: Watchlist ceiling.
- Deterministic machine-reviewed NHL/NBA workload changes: Tier 3 ceiling. Official history is independently fetched and checked, but the same observed workload is already part of Engine B, so it is corroboration rather than an independent forecasting effect.
- Actually source-read, quantified, counterchecked, sport-relevant opponent-scheme effect not already included in model inputs: Tier 2 ceiling.
- Exceptionally corroborated measured scheme effect: Tier 1 ceiling, but a published Tier 1 still requires the original market, numerical and chronologically validated A/B blend criteria.

The human/agent scheme evidence requires a genuine named adversarial source-review attestation and a causal_validation record tied to the SAME mechanism event_id, target_stat and opponent. It must specify a causal metric (position_matchup_opportunity_rate or opponent_scheme_allowance_rate), units, numeric before/after values with >=5 observations in each window, >=10% side-supporting change, primary before_fact and after_fact matching those values, and sourced counterevidence. Two sport-relevant independent primary owners are required. The before/after source facts must also match the named reviewer's supporting evidence by exact URL, value and excerpt, and the counterexample must match that reviewer's opposing evidence; unrelated attestations cannot sponsor a mechanism. A third owner with >=10 observations per window and >=20% change can establish a Tier 1 evidence ceiling. This is a quality standard, not a guaranteed probability or profit.

The NHL official website and api-web.nhle.com are one source owner. An NBA league site cannot manufacture independent NHL corroboration. Workload, role, pace and weather signals are treated as overlapping with existing engine/context channels unless additional model-incrementality verification is implemented. Independently reviewed scheme claims are rejected when existing Engine A opponent/funnel or Engine B defensive factors already incorporate them. Quoted values in source records still require a real source-reading reviewer; schema validation alone cannot establish the content of an article.

## Enforcement

- scripts/mechanism_evidence.py produces a versioned quality report and Tier ceiling without adjusting q_model or A/B weights.
- scripts/research_packet.py still calculates the historical mechanism count for diagnostics, not for authorized verified ranking.
- scripts/pick_verification.py assesses current machine or human evidence linked to the immutable forecast, feeds the quality ceiling to the evaluator, reapplies that ceiling before publication, and retains blockers and the full quality diagnostic.
- scripts/pickem_math.py finalize/decide use quality ceilings when supplied. Calls omitting quality continue to support old standalone/scan diagnostic behavior but cannot themselves create a verified receipt.
- scripts/verified_board.py rejects approval receipts without mechanism-evidence-v1 and rejects ranks exceeding their evidence ceiling. Machine-only workload decisions cannot reach Tier 2/1 by citation inflation. This policy change applies to new receipts; it does not rewrite old forecasts.

Stage D scan uses optimistic legacy placeholders for DISCOVERY only. It is not a publishable rank. Low-confidence or unsupported candidates remain Watchlist/Unranked. Numerical boundaries, original probabilities, blend weights, settled outcomes and all other vetoes are unchanged.

## Validation

Offline regression tests cover contradictory outcomes, copied/mirrored owners, stale reports, missing counterevidence, wrong prop/fixture, model overlap, fabricated counts, machine-only Tier ceilings and verified board acceptance. A valid test fixture is NOT evidence that an actual live pick has qualified.
