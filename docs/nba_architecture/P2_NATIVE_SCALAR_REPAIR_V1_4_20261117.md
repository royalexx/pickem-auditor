# P2 native scalar validation repair 1.4

Governing authority: PA-V25-MASTER-2026-11-09 / v1.1. The owner pre-P6 audit continues the authorized repair loop; no independent acceptance is granted.

At P2 `a3513bdb5e557afce2c720a47458327c668b04ec`, **F-P2-05** exposed Python boolean equality in the new native structural consumer. Three synthetic tampering cases passed structural checks: raw JSON statistic `true` paired with exported count `1`, exported `exact_minutes=true` paired with a raw one-minute exposure, and boolean attempted/admitted/quarantined values paired with integer denominators. Real source admission remained BLOCKED, but those transported types were invalid.

`p2_scalar_v1_4_20261117/before_native_scalars.json` preserves all exact inputs/outputs and code SHA. `before_regression.log` preserves the three red subcases. The consumer now requires source statistics to be nonnegative integer counts with `type(value) is int`, exact exposure to be a numeric integer/float excluding bool, and denominator values to be actual integers. Existing valid integer counts, float minutes, cap equality and subminute controls remain accepted structurally while source admission stays BLOCKED. The new regression pairs each mutation with the valid exported fixture.

The S statistical model and conditional integration modules remain byte-identical to the already tested cutoff repairs; only the native source inspector and its tests change. All earlier failed/green receipts and PR comments remain preserved. Reproduction is `python -m unittest tests.nba_s_family.test_p1_native_v1 -v`; full exact-head suite commands and raw hashes are in the adjacent versioned execution receipt.

B-P2-01 still requires independently admitted authentic sources, lawful release/availability clocks, dated roles and identities, and an admissible existing fitted prior. No authentic source or fitted prior is manufactured. No historical fitting/evaluation, holdout access, G2, NUTS, production, schedule or Tier action is authorized or performed.
