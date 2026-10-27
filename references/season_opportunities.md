# Engine B: season history and causal opportunity mechanisms

Current versions: Engine A `history-v5`, Engine B `scouting-v7`, season store
`nfl-season-v1`. Earlier engine forecasts cannot validate the new blend contract.

## Stored history and refresh

The NFL fetch now stores the current regular season in
`data/season/nfl_SEASON.sqlite3`. It retains normalized play-by-play and FTN charting,
source URLs, retrieval/as-of time, dictionary version/mapping, completed-game coverage,
and duplicate diagnostics. The collector attaches the relevant offense, passer,
opponent defense and defender profiles to the candidate's research packet.

```bash
python3 scripts/nfl_season_store.py refresh --season 2026 --db data/season/nfl_2026.sqlite3
python3 scripts/nfl_season_store.py profiles --season 2026 --db data/season/nfl_2026.sqlite3
```

Refresh is transactional. Duplicate play IDs do not increase samples. Conflicting
rows in the same snapshot fail and roll back; later clean refreshes can replace
source corrections. Store partitions cannot mix seasons. Same-day/future games and
unfinished games are excluded, as are nullified plays and special-team/try attempts.
This intentionally delays today's completed games until the next Toronto-local day. Source lag
and unknown read classifications remain visible. Historical storage does not
permit reusing old injury reports, weather forecasts or starter confirmations.

FTN Data via nflverse is attributed in `THIRD_PARTY_DATA.md`. The current nflreadr
read dictionary distinguishes primary, second, later, checkdown, designed and
scramble-drill throws. Designed throws are **not** counted again as first reads.
The mapping is versioned, not inferred from observed frequency. Unknown codes and
unmatched plays stay unknown. These labels identify the read actually targeted;
they do not identify the intended first receiver on every play or every route run.

## Offensive priority and defensive pass tendencies

Profiles retain QB/team throw counts, targetable fraction, read-bucket distribution,
individual recipients' conditional target shares and bucket leaders (ties retained),
recent versus earlier target shares, and available screen/RPO/play-action/motion
observations. Player and passer IDs are joined exactly. Team targets are not routes.
No route or alignment statistic is fabricated from a throw log.

Defense profiles report read coverage and observed checkdown rate on known reads,
plus EPA per dropback as a separate contextual measure. Opponent adjustment compares
each QB against that defense with **the same QB's other opponents**, rather than
calling every defense facing checkdown-heavy QBs strong. QBs without comparison
history are excluded from both actual and expected counts and disclosed. The
comparison remains descriptive and observational; pressure, protection, coverage,
personnel, game state and schedule confounding still require scouting.

A high checkdown rate alone is not a passing-defense quality grade. First-read
suppression and checkdown tendency are overlapping parts of one read distribution;
they are not two independent multipliers.

For receiving scenarios, include:

```json
{
  "weight": 0.5,
  "scope": "full_game",
  "dist": "poisson",
  "conversion": 0.65,
  "rationale": "Explain sourced QB, role, read tendency, personnel and script assumptions",
  "drivers": ["passer_progression", "targets_routes", "coverage_matchup"],
  "season_projection": {
    "mode": "receiving",
    "passer_id": "VERIFIED_PASSER_ID",
    "expected_pass_attempts": 30,
    "use_defense_adjustment": true
  }
}
```

Those numbers are illustrative, not recommendations or factual projections. The
packet must contain `season_context` and a fresh `confirmed_passer` fact whose value
is that exact ID. Research still supplies scenario weights, expected pass volume,
conversion and dispersion. The store supplies the observed conditional structure.

The calculation is:

    expected targets = pass attempts × targetable fraction
                       × sum_over_all_buckets(matched bucket probability × receiver bucket share)

Pass-attempt input means throws excluding sacks. The raw nflverse pass_attempt flag
includes sacks, so the builder removes them from throw/read denominators while
retaining sacks in dropback and defensive-play context.

It covers the full target distribution, including an explicit unknown component.
All recipients' targets sum to the targetable volume; a partial read bucket is never
relabeled a full-game total. The upcoming defense is removed from the offense
baseline before its tendency is applied. The defense shifts the known read mixture
once, with normalization; unknown mass is preserved. The output reports offense-only
and matched targets and their signed difference. A dominant checkdown recipient
can rise while a primary-only recipient falls in the same matchup. There is no
flat bonus for being a main option and no guarantee a favorable stock move clears
a line. Missing comparison denominators stop that scenario instead of inventing
an uplift. No arbitrary data cutoff is used to declare a defense elite.

## Tackles + assists and interior-run funnels

A defender profile stores credited solo/assisted involvement by interior run,
off-tackle run, edge run, unknown run, short/deep/unknown pass, scramble, sack and
other play categories. The opponent's offensive play mix is stored separately.
Rates use all team scrimmage plays in each category, including incompletions and
zero-credit plays. A defender appearing in multiple credit fields on one play
receives one combined tackle involvement count, not duplicate credit.

These are credited involvement rates per team play, **not** on-field tackle ability
or proof that a player aligned at interior MLB. Historical bench/absence exposure
is included. Actual position/alignment, current snap role and teammate competition
must be sourced in the research pass. Team assists may create credits for multiple
defenders on one play; conservation across players differs from target conservation.

For tackle scenarios use `season_projection` with `mode: "tackles"` and
`expected_defensive_plays`. The engine computes:

    expected tackles+assists = expected defensive plays
                              × sum(opponent category share × personal credited rate by category)

It compares that result with the same-volume historical baseline. An interior-run
opponent can raise an MLB's expectation when the player's observed involvement
supports that mechanism. Never infer this solely from the letters MLB or ILB.
An unobserved matchup category is missing data, not a zero tackle probability.

Weather, game script and injuries on either team can change the scenario's
`play_mix`, expected volume, or role. Optional `play_mix` must be supported by a
fresh `mix_evidence` fact with matching value. Optional `role_factor` requires a
fresh matching `role_evidence` fact. Each numeric context change needs canonical
`event_id`/`event_ids`, or a structured `causal_event` identity. The engine does
not automatically equate rain with more rushing, a teammate absence with all
vacated tackles, or an offensive-line injury with extra MLB tackles. These are
sourced scenario judgments, with alternatives and uncertainty.

## No double counting

- Engine A excludes all upcoming context. Historical game IDs are checked within
  and across baseline, recent and prior windows when provided. Automatic prep emits
  IDs from source logs; repeated identical games count once, conflicts fail. Aggregate
  inputs lacking IDs cannot prove identity and are labeled accordingly.
- Engine B calculates opportunities from the season mechanism **or** accepts a manual
  opportunity total. Supplying both is rejected. Tackle mode also rejects a manual
  conversion rate alongside its computed rate.
- Each scenario's effect ledger applies each canonical causal event once. Repeated
  citations or different checklist categories do not create additional effects.
  Overlapping read-tendency labels are normalized to one adjustment identity.
- `embedded_event_ids` identifies effects already reflected in a baseline. Reapplying
  one is rejected. `applied_effects` records manual scenario assumptions, their
  sourced driver and jointly affected inputs. An event affecting multiple inputs
  must be evaluated jointly, not multiplied as independent bonuses.
- Applying the same injury separately through role and play mix is rejected. Two
  articles about that injury are not two events. Use stable player/event IDs and
  `causal_event.parent_event_id` to connect derivative descriptions to the root.
- Events may recur across mutually exclusive scenarios; scenario probabilities are
  averaged, not stacked. Engine probabilities are blended convexly, not multiplied.

The ledger detects declared/canonical identity conflicts. It cannot infer that
unrelated prose labels secretly refer to the same event, verify a citation's truth,
or discover an undisclosed adjustment hidden in a manually supplied total. The
researcher must identify root causes and annotate embedded/manual effects honestly.
The adversarial review must inspect this ledger before publication.

## Validation limits

These are mechanism-based opportunity estimates inside the existing scouting
engine, not a newly trained predictive model. Sampling uncertainty in rates,
missing charting and causal confounding must be reflected in scenarios and research
judgment. No validated weights or calibrated Tier 1 probabilities are shipped.


## Version 4 reliability changes

The examples above show the mechanism; free scalar examples are diagnostic until
accompanied by typed `numeric_inputs` and measured scenario frequencies. Follow
`math_helper.md` for the current schema and sample floors. Sparse raw ratios do not
qualify as reliable. Sampling uncertainty propagates into B probabilities; this is
a conservative first-order approximation, not validated accuracy. Unquantified
role/mix overrides remain diagnostic. The tackles mode is strictly for **tackles +
assists**; it cannot score a solo-tackle market. No additional prediction model was
introduced. All current-version probabilities still need prospective validation.

The latest `scouting-v7` ownership contract supersedes scenario eligibility here:
these season mechanisms remain diagnostics and source context. Upcoming event
adjustments run only through the shared layer. Read `shared_context.md`.
