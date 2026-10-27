# Pick'em Auditor — 2026-10-27 research integration repair

## Changes delivered

1. `scripts/research_recovery.py`: recover only identity-matched, sourced and fresh facts from same-day research packets. Deny stale, unsupported or ambiguous inputs; unresolved conflicting sources stay null and are reported. Offline reproduction supported via `--now` (never for new live rankings).
2. `scripts/research_tasks.py --recover-packet PATH`: import source packet(s) before task creation, source resolution and evaluation.
3. `scripts/context_feeds.py`: preserve newer-retrieved facts when re-running a collection; avoid losing sourced venue classification due to blank collector fields.
4. `scripts/research_resolver.py`: add a bounded ESPN NHL injury status query for *explicit negative statuses only*, in addition to ESPN pregame event, actual venue, goalie and active-roster lookups. A missing injury entry or name on a roster is not active-game verification. All lookups are source-logged.
5. `scripts/verified_scouting.py`: strict importer for reviewer-read, cited qualitative dimensions, supporting checks and independent mechanism events; cannot alter historical usage or numeric Engine B baseline and cannot mark a report publication-eligible.
6. `scripts/probability_blend.py` and `scripts/pickem_math.py`: show a 70% A / 30% B **diagnostic** when both engines are reliable and verified. Official deployment still requires chronological holdout validation; diagnostics never change official tiers.
7. `scripts/pickem_math.py`: explain large model-market gap review in `grade.gap_review` and preserve the 8 percentage point Watchlist cap pending validation. The cap was reviewed, not silently removed.
8. `scripts/collection_receipt.py`: inspect restored history archive timestamps and coverage to distinguish scheduled automation activity from evidence that results were collected and saved.

## Exact offline replay of earlier venue loss

The `Pickem_Auditor_history.zip` in Library includes `data/research_2026-10-26.json` with a sourced Rogers Place `indoor=True` fact and a resumed packet lacking this fact. Running:

```
python scripts/research_recovery.py \
  --current data/resumed-context/research_2026-10-26.json \
  --prior data/research_2026-10-26.json \
  --out data/research_recovered_2026-10-26.json \
  --now 2026-10-26T21:50:00Z
```

Restored 127 sourced, fresh, identity-matched facts, including `weather.DET@EDM.indoor=True`. This was a retrospective reproduction; it does **not** make October 26's stale quotes usable on October 27 or create an active-status report for Ryan Shea.

## Research completion and live pricing

To rank prospectively, collect current public sportsbook quotes and verified game statuses, use `research_tasks.py --resolve`, complete sourced scouting dimensions and mechanisms with `verified_scouting.py`, then audit all candidates. Machine numeric estimates alone never attest the scouting checklist. Research publication approval remains an explicit review step.

## Test scope and limitations

121 focused regression tests passed (packet merge, resolver, recovery, ranking and blending). The unconstrained full suite exceeded its runtime limit here; therefore a full-suite pass is **not** claimed. Public API connectivity or an updated sports-book quote was not tested end-to-end in this container, so future live runs require network access.

October 27 morning automation: the schedule reports a run attempt with `no_update`, while the latest saved Library history archive is dated October 26. **Successful October 27 morning collection and persistence cannot be confirmed.**
