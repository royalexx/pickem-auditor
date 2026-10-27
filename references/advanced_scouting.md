# Engine B advanced research contract

Engine B is qualitative scouting translated into explicit scenarios. It does not
have fitted causal coefficients for every advanced statistic. The researcher must
explain how sourced evidence changes opportunities, conversion, or the range of
plausible full-game outcomes. Recent production alone is not a second statistical
engine: Engine A already models historical production. In B, trends matter through
changed deployment, opportunities, personnel, or matchup mechanisms.

`scouting_checklist.py` defines mandatory coverage categories by sport and stat.
Each `supporting_stats` category needs a fresh, confirmed fact object. A fact's value
can be a structured set of sourced observations with sample windows, denominators,
and limitations. Confirmed means the source observation was checked, not that the
future outcome is certain. A scenario must list `drivers` naming its sourced
supporting-stat categories. Missing categories remain visible in `engine_b.coverage`.
Incomplete coverage cannot make B reliable or enable Tier 1/validated blending.

| Sport / prop | Research B must consider |
|---|---|
| NFL, all | Deployment trends, team play/pass volume, opponent scheme, defensive funnels, game environment. |
| NFL receptions / receiving yards | Targets, routes, route participation, target share and targets per route; QB first/secondary/checkdown progression; coverage shells/man/zone and assignments; target depth and alignment. |
| NFL passing | QB progression, pressure/protection, coverage matchup, receiver availability, expected pass volume and script. |
| NFL rushing | Carry/snap share, front/box structure, blocking personnel and script. |
| NFL tackles | Defensive alignment/snaps, opponent play distribution, teammate competition and tackle-opportunity funnels. |
| NBA, all | Deployment trends, minutes/usage/touches, pace/possessions, opponent scheme, rotation injuries and script/rest. |
| NBA points / threes | Shot-location and attempt profile, defender assignment, switching/drop/help, creation role; three-point location and attempt type for threes. |
| NBA assists | Potential assists, passing/time-of-possession role, teammate availability and conversion. |
| NBA rebounds | Rebound chances, available misses, lineup sizes/box-outs and opponent shot profile. |
| NBA combinations | Union of the underlying stat-specific requirements. |
| NHL, all | Deployment trends, time on ice, lines/pairs, special teams, opponent style, game environment. |
| NHL shots | Attempts and SOG/60, conversion to on-target shots, line matching and suppression. |
| NHL blocks | Opponent attempt volume/location, defensive-zone and penalty-kill exposure, shot lanes and pairing. |
| NHL saves | Opponent SOG volume, confirmed starter, defensive suppression/shot quality and game-script workload. |

Do not invent data for a required category. A source reporting that a relevant
condition is neutral is evidence; an unavailable coverage/route/line statistic is
not equivalent to a neutral condition. Unknown observations are null and reported.
A category can document the relevant sourced mechanism without pretending a precise
unavailable metric exists. For example, a sourced scheme description may inform a
coverage matchup while explicitly stating the lack of a numerical coverage split.

## What is actually fetched versus researched

The repository can fetch NFL historical production, snaps, target/route-related
columns when present, and partial FTN progression/defensive diagnostics when charting
loads and joins. Existing charting can be unavailable or incomplete. It is not a
complete live coverage-shell/route-assignment database. The collector forwards
available primitive diagnostic values as **unverified feed diagnostics** in the
scouting seed, with their source hint. These never directly become verified facts.

NBA fetches counting production, historical logs, team pace/possessions and available
structured context. Potential assists, touches, rebound chances, shot-location
splits and defender assignments are research requirements; dedicated automatic
collectors for all of them are not implemented.

NHL fetches counting production, game logs, team shot rates and available deployment
fields. Detailed attempts/xG/line-matching/zone-start/special-teams evidence may need
additional sourced research. Complete advanced-data automation is not implemented.

The automatic seed makes omissions explicit and routes available diagnostics to the
research pass. It does not mark an advanced statistic available simply because a
checkbox or source URL exists. Source inspection and scenario justification remain
necessary. Do not equate pass attempts with targets, partial reads with total
production, potential assists with assists, team attempts with player blocks, or xG
with SOG/saves. Avoid counting one injury, pace effect or route change twice.

## Current NFL season mechanism

The original unverified hints are now supplemented by an actual season store and
full-game opportunity calculations. Read `season_opportunities.md`. Source-derived
read profiles and tackle-category rates can drive scenarios directly; source gaps
and fresh starter/role evidence remain explicit. The store does not supply unseen
route assignments, on-field alignment, injury redistribution, or weather effects
without sourced scenario assumptions.


## Current baseline and context ownership

Read `shared_context.md`. Advanced observations explain the context; researchers
cannot change eligible B opportunities, conversion or scenario weights directly.
The older scenario mechanism remains diagnostic. Only collector-owned histories
can establish an eligible baseline. Source lineup comparisons can report extra
3PT attempts, drives, passer-to-recipient edges, defensive opportunity and ice-time
changes. Missing tracking data stays missing. These explanatory deltas never become
extra multipliers beside the joint lineup allocation.
