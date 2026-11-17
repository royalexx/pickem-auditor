# P2 independent sparse-source integer accounting 1.6

Authority: PA-V25-MASTER-2026-11-09 / v1.1. Native source admission remains BLOCKED; engineering feasibility never authenticates a source or supplies an observed missing statistic.

**F-P2-08**: P2's native raw-byte/derived-field comparison could accept self-consistent but physically impossible raw statistics. At `ac51a6263fd7993c467527e421dbf7c720082baf`, separately resealed raw sources with (1) points 1, FGA 1, 3PA 0, FTM 0; (2) inferred 2PM greater than 2PA; and (3) offensive rebounds greater than total rebounds passed structural checking. Exact accepted inputs/outputs and red regression subcases are preserved in `p2_integer_v1_6_20261117`.

The new `source_accounting.validate_count_feasibility` independently checks existence of a nonnegative **integer** completion for the supplied sparse statistics. Its 13 internal variables satisfy scoring, FGM/3PM/2PM, FGA/3PA/2PA, made-versus-attempted, total/offensive/defensive rebound and PR/PA/RA/PRA equations. SciPy's small MILP supplies a candidate witness; every candidate is rounded and rechecked against all constraints with exact Python integer arithmetic before structural acceptance. Missing fields remain unknown and no internal witness is exported as source observations. A parity-incompatible P/R/A completion cannot pass as fractional 1.5 values.

A numerical representation boundary of `2**48` for supplied counts causes explicit `ACCOUNTING_NUMERICAL_RANGE_UNRESOLVED`, never a claim that a larger count is physically impossible. Timeout, numerical failure or a failed exact witness also quarantine explicitly. This is separate from the physical source-specific overtime cap and does not reintroduce the removed 100-minute restriction. An unavailable authenticator cannot be replaced by feasibility or by a matching digest.

P1 uses a separate exact analytic method. Positive/negative references here independently enumerate 972 bounded shot-count cases across every optional shooting field subset and 216 combination cases across every PR/PA/RA subset. A further seeded 5,000-case sparse valid/mutated comparison against the exact P1 analytic module found zero disagreements at its recorded code pin; all inputs and outputs are retained. These are synthetic engineering comparisons, not statistical fitting or historical predictive evaluation, and they are supporting implementation QC rather than independent gate acceptance.

Run the native tests and the numerical references:

```bash
python -m unittest tests.nba_s_family.test_p1_native_v1 tests.nba_s_family.test_source_accounting_v1 -v
python scripts/nba_p2_source_integer_reference_20261117.py --repo /workspace/work/repo --p1-sha 542d91a7d6c134441ce8cb9bb54312095b186833 --output work/source-integer-reference-new
```

The reference command refuses to overwrite an existing directory. The submitted exact-head receipt supplies final P1/P2/P3 pins and output hashes. All previous repaired cutoff, exact raw-minute, scalar, high-OT and nonparticipation controls remain active. P2 S model/integration bytes are unchanged from `ac51a62`; no G0 semantics, source history, production policy or later gate changes. Only separate P6 review may issue independent family or overall recommendations.
