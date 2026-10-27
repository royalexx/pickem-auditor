# Evidence-first afternoon verification queue

At each 4 p.m. Toronto pregame run, \`scripts/research_triage.py\` reads the new shadow forecasts and creates \`reports/research_triage.json\`. The report is included in the daily GitHub Actions artifact and execution receipt. A separate offline audit can rebuild it from persisted forecasts without requesting PropLine odds.

This is **research prioritization, not a prediction or published pick**. It never changes archived forecasts, the 70/30 diagnostic, validated weights, model probabilities, rankings, or any \`researched\` flag. A preliminary model/market discrepancy is not demonstrated betting value.

The queue first identifies forecasts blocked by game-specific status or venue evidence that already have a numerical grade, reliable Engine A and two independent approved sportsbook quotes. A provisional grade at least 0.57 and a grade/market discrepancy at least 0.03 prioritize source checks; they are *not tier criteria*. Reliable Engine B goes ahead of A-only cases. Duplicate sides/stats for a player are consolidated, with six subjects per fixture and 30 subjects per afternoon as the initial capacity limit. Games that have already started are not treated as eligible.

The report preserves the full counts of \`SAMPLE_BLOCK\`, \`INVALID_MARKET\`, \`CONTEXT_UNRESOLVED\`, \`NORMAL_LEFT_TAIL\` and other reasons. These are separate engineering problems; researching an injury list cannot solve missing dated observations or insufficient two-sided market prices.

## Closing verification tasks

For each subject, the queue identifies missing source-backed facts through the existing research-packet validator, with a current explicit game-specific player-active status being first priority. The subject identity must match the actual team, fixture, and stable ID where available. An injury-list omission, generic roster membership, projected NHL line, or an empty report **does not** establish active status. Doubtful/out designations and conflicting reports stay explicitly unresolved or vetoed.

Read source pages or official structured evidence, record URLs, timestamps, short supporting quotes, and an actual reviewer identifier using \`scripts/verified_scouting.py\`. That tool only accepts correctly identified, reviewer-read facts; it cannot be invoked with invented confirmations. Audit the same-date packet using \`scripts/research_packet.py audit\` with the corresponding saved pregame candidate rows. No postgame evidence may be backdated to create a pregame pick. When a lineup or starting goalie is not officially confirmed by 4 p.m., recheck before that specific event starts.

The source queue is a planning artifact. It does not replace human/agent examination of matchup scheme, opportunities, opponent context, injury consequences, opposing arguments, and evidence-gated probabilistic validation.

## Source-specific, identity-checked research plan

The source checklist deduplicates official ESPN fixture and injury lookups across selected subjects. Each proposed URL has `verified=false` and `source_state=not_checked`; a proposed lookup is **not** evidence that its contents were fetched or reviewed. An ESPN injury-list omission cannot prove an athlete is active. Explicit game-specific roster flags, fresh timestamps, cross-source counterevidence, and the complete stat-specific scouting checklist remain required for a publication decision.

Per-candidate `source_tasks` list exact missing packet paths. Game, weather and environment paths are included only when the packet player/team/sport and both fixture teams reconcile, using the packet's canonical no-space game key (e.g. `BOS@NSH`). A mismatch is labeled `packet_fixture_identity_not_verified`; it is not silently repaired.

The queue is deliberately **not** executed as an automatic grade or tier approval. The reviewed evidence must still pass the same-date packet validator and existing model ranking vetoes. A replay after games begin cannot backdate verification.

The per-fixture cap groups opponents as an unordered team pair; subject-first matchup labels can be reversed for athletes on opposing teams. The queue reports `qualified_by_sport` and `selected_by_sport` so the daily report makes sport imbalance explicit rather than pretending it is a representative sample.
