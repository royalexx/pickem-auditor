# NBA points and NHL SOG metric shadow comparison

The approved work is a two-slate prospective, research-only count comparison conditional on played appearances. The real pregame freeze was 2026-11-24 15:06:23.012981 UTC, before the Nov 25 NHL and Nov 27 NBA slate. It uses prior regular-season spines through Nov 23, and only historical player-team proxy eligibility. Existing production controls and forecast schedules are preserved.

- NHL SOG compares the fixed baseline with 5v5 individual unblocked attempts per 60. Fourteen scheduled games, 556 frozen play-conditional forecasts, and 57 exclusions for insufficient baseline or advanced history.
- NBA points compares the same kind of baseline separately with actual eFG% and with TS%. Eleven scheduled games, 307 frozen play-conditional forecasts, and 27 exclusions for insufficient baseline or advanced history.
- The freeze seals one Poisson mean per model per exact league event and player. Count CRPS is primary and negative log score is secondary. Score every matched positive-participation official row. Preserve unavailable source, absent player, and identity-mismatch rows. Single-slate game-cluster intervals are descriptive.
- This checkout retains the early frozen artifact and the model coefficients and historical receipt. All 11 source byte objects were also read back locally in the user's shared workspace against the publisher listing digests. The official finals are acquired separately after the games and checked against exact identities and original pregame chronology. Never overwrite the pregame artifact.

Pregame SHA-256 `0113325f00f9c4597a6ffcd13750fc54cdff3fcc15ffe57082aa115ebbc32c21`. Coefficient and historical recheck SHA-256 `3bc0766354cef373c01cdfa5f866af363586d2ac4763470963afc3c8d950a211`.

Run at the verified repository root after the official finals are available. Use a distinct output directory for each read and retry.

```sh
python scripts/score_metric_shadow.py --sport NHL \
  --pregame docs/evidence/metric-shadow-20261124/pregame-shadow-20261125-27.json \
  --sha256 0113325f00f9c4597a6ffcd13750fc54cdff3fcc15ffe57082aa115ebbc32c21 \
  --out /work/reports/v25_metric_shadow_20261124/nhl-nov25-final
```

For NBA use `--sport NBA` and a distinct `nba-nov27-final` destination. The shell runtime verified 16 numerical Poisson CRPS cases, one original final-box integration with a missing-player denominator, and rejection of a false forecast digest. A negative or inconclusive one-slate outcome remains part of the research record.
