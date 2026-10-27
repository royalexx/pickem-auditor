# Evidence-first afternoon verification queue

At each 4 p.m. Toronto pregame run, \`scripts/research_triage.py\` reads the new shadow forecasts and creates \`reports/research_triage.json\`. The report is included in the daily GitHub Actions artifact and execution receipt. A separate offline audit can rebuild it from persisted forecasts without requesting PropLine odds.

This is **research prioritization, not a prediction or published pick**. It never changes archived forecasts, the 70/30 diagnostic, validated weights, model probabilities, rankings, or any \`researched\` flag. A preliminary model/market discrepancy is not demonstrated betting value.

The queue first identifies forecasts blocked by game-specific status or venue evidence that already have a numerical grade, reliable Engine A and two independent approved sportsbook quotes. A provisional grade at least 0.57 and a grade/market discrepancy at least 0.03 prioritize source checks; they are *not tier criteria*. Reliable Engine B goes ahead of A-only cases. Duplicate sides/stats for a player are consolidated, with six subjects per fixture and 30 subjects per afternoon as the initial capacity limit. Games that have already started are not treated as eligible.

The report preserves the full counts of \`SAMPLE_BLOCK\`, \`INVALID_MARKET\`, \`CONTEXT_UNRESOLVED\`, \`NORMAL_LEFT_TAIL\` and other reasons. These are separate engineering problems; researching an injury list cannot solve missing dated observations or insufficient two-sided market prices.

## Closing verification tasks

For each subject, the queue identifies missing source-backed facts through the existing research-packet validator, with a current explicit game-specific player-active status being first priority. The subject identity must match the actual team, fixture, and stable ID where available. An injury-list omission, generic roster membership, projected NHL line, or an empty report **does not** establish active status. Doubtful/out designations and conflicting reports stay explicitly unresolved or vetoed.

Read source pages or official structured evidence, record URLs, timestamps, short supporting quotes, and an actual reviewer identifier using \`scripts/verified_scouting.py\`. That tool only accepts correctly identified, reviewer-read facts; it cannot be invoked with invented confirmations. Audit the same-date packet using \`scripts/research_packet.py audit\` with the corresponding saved pregame candidate rows. No postgame evidence may be backdated to create a pregame pick. When a lineup or starting goalie is not officially confirmed by 4 p.m., recheck before that specific event starts.

The source queue is a planning artifact. It does not replace human/agent examination of matchup scheme, opportunities, opponent context, injury consequences, opposing arguments, and evidence-gated probabilistic validation.
