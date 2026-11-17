# P3 native scalar validation repair v5

Pre-P6 implementation quality control found that Python dictionary equality
treats booleans, integers and equal-valued floats as equal. At exact P3 head
`2a666106a02595c70e2e372729aeae73d337b745`, the native consumer accepted a
one-candidate export with `observed_candidates=True` and `admitted=False`.
The accepted output remained source-BLOCKED, but its typed denominator was
incorrect. The original full input, output and implementation digest are
preserved in `p3_scalar_repair_v5_20261116/orchestrator_before.json`.

Additional same-class review found that an exported legal-eligibility summary
could use numeric `0`/`1` in place of the raw assertion's `False`/`True`.
Raw assertions themselves already required exact bool or null. Full versioned
before probes preserve both defects, plus equal-valued float counts and valid
integer controls. The permanent new regression ran six test methods and
retained eight red subcases before implementation. Old v4 reports, receipt,
tests, output and published owner comments remain unchanged.

`nba-p3-p1-native-consumer/1.0.1` now validates the denominator's closed object
shape, requires exact nonnegative integer types for observed/admitted counts,
and requires unknown complete population to remain null. It independently
requires exact bool/null legal eligibility in the summary before comparing it
with reconstructed raw assertions. No numeric equality can supply a boolean
state. Valid integer counts and true/false/null eligibility remain accepted
as transport, with the original explicit source-admission BLOCKED disposition.

The relevant thirteen controls pass after repair. Exact committed-head full
G0/P3, pinned P6, prior v3 adversarial and actual latest-P1 native results are
recorded separately in the adjacent execution receipt. All fixtures remain
synthetic; no historical source is authenticated by these tests. Neither old
P3 producer nor accepted G0 source changed. B-P3-01 still requires authentic
complete original roster/context, dated membership, source-bound home/role
and independently admissible participation/minute priors. B-P4-03's coupling
proof proposal remains unaccepted and its n=32 failure remains preserved.

Reproduce the scalar probe and permanent regressions:

```bash
PYTHONPATH=.:tests/nba_architecture python scripts/nba_p3_native_scalar_probe_v5_20261116.py
PYTHONPATH=.:tests/nba_architecture python -m unittest test_p3_native_scalar_v5 -v
```

Owner verification supports separate independent P6 review; it is not gate
acceptance. No G2, historical fitting/validation/weight fitting, holdout access,
merge, schedule change, deployment or Tier promotion is performed or authorized.
