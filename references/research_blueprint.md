# Research blueprint and sample work product

## Contents

1. Quality standard and stopping rule
2. Collection and game context
3. Candidate investigation
4. Engine evaluation and adversarial review
5. Conversation report sample
6. Persistent handoff and morning work
7. Completion checklist

## 1. Quality standard and stopping rule

The operator prioritizes quality over speed and accepts an hour or longer. Never
skip mandatory work, reduce the researched shortlist, omit opposing evidence or
sample only convenient games because the run is lengthy. Progress updates do not
replace completed research. Elapsed time alone is never a stopping criterion.

Finish when required work is complete, or record a specific unresolved access/data
blocker after reasonable retries and alternate authoritative-source attempts.
Bound individual requests so a dead endpoint does not prevent independent work.
Never manufacture information to satisfy a checklist. If execution limits interrupt
the run, checkpoint completed work and label the run incomplete with a resumption
list. An empty or blocked run is not a successful finding of “no opportunities.”

This blueprint describes the work product. Use the canonical skill and
`shared_context.md` for current engine ownership and publication gates. Examples
below use placeholders and are not real picks, source evidence or probabilities.

## 2. Collection and game context

Verify the date and current Toronto time. Reconcile all scheduled NBA/NHL/NFL
games against actual starts. Build coverage before selecting players.

| Game | Start ET | Collection result | Missing markets/history | Context result |
|---|---|---|---|---|
| Away @ Home | [verified time] | [rows / priced sides] | [exact omissions or none] | [complete / unresolved fields] |

Retain collector observations, stable player/game IDs, current/prior separation,
workload units, source URLs and retrieval timestamps. Never convert a missing log
into zero production. Do not infer complete coverage merely from a successful exit.

For each game, investigate both teams: injuries, returning players, actual
replacement duties, likely starters/units, opponent scheme and deployment, rest,
spread/total, and venue/weather where applicable. Reuse verified team-level research
across players; do not count repeated citations as independent mechanisms.

Use an evidence register:

| Question | Observed fact | Source URL | Retrieved ET | Event/sample period | Confidence | Supports/against/neutral | Still missing |
|---|---|---|---|---|---|---|---|
| Is the player available? | [actual sourced status] | [retrieved source] | [time] | [tonight] | [verified/projected/unresolved] | [classification] | [confirmation needed] |
| Has usage changed? | [measured deployment with denominator] | [source] | [time] | [game IDs/date window] | [confidence] | [classification] | [limits] |

Distinguish when a source was retrieved from when its information was published.
Retrieve and inspect the underlying source; a search headline is not verification.
If unavailable, record primary and alternate-source attempts and the exact field
still missing. A source that does not mention an injury does not prove active status.

## 3. Candidate investigation

Run the actual market scanner on all prepared sides. Retain its exact counts and
shortlist. Add explicit sourced context triggers through the supported trigger
mechanism. Do not replace the shortlist with a few popular players.

For every shortlisted candidate, complete this dossier:

- Identity: sport, stable player ID, team, opponent, event, start and selected stat.
- Reference market: main line, approved books, both prices, timestamp, consensus
  quality and any verified movement. A one-sided price is insufficient.
- Historical deployment: current/recent/prior windows, zero exposure, workload
  units, role changes and whether the old role/team is comparable.
- Stat mechanism: what produces this stat and why this player receives those
  opportunities. Complete the sport/stat checklist in `advanced_scouting.md`.
- Supporting case: measured volume/deployment and the specific matchup channel.
- Opposing case: competition, role uncertainty, rotation, scheme, returners,
  weather, game script and plausible reasons the forecast fails.
- Event ledger: root cause IDs, absent teammates, effective times and whether the
  effect already appears in the historical baseline. Multiple absences are one
  supported joint allocation, not multiplied independent bonuses.
- Unresolved evidence and its consequence: abstention, flag, veto or Unranked.

For example, “teammate is out” is not a finished thesis. Establish who inherits
minutes/routes/snaps/ice time, compare complete observed lineup states, check
other personnel differences, and show whether the shared context operator has
enough support. Without that support, explain the uncertainty; do not enter an
uplift into both opportunity and conversion.

## 4. Engine evaluation and adversarial review

Run code for every candidate; never calculate publication probabilities in prose.

| Component | Required record |
|---|---|
| A | Version, source identity verification, mean, dispersion, sample windows, predictive win/push probabilities, reliability reasons |
| B | Version, collector reference/digest, workload and conversion units, observation IDs, uncertainty, probabilities, reliability/abstention reasons |
| Blend | Actual weights, matching validation fingerprint, or explicit A-only fallback |
| Shared context | Subject availability, joint event ledger, source support, one allocation transformation, eligibility and validation |
| Final grade | Exact machine final_rank, reason, flags/vetoes, reference market and evaluation time |

Ask what would invalidate the thesis. Verify the player/line/event join, original
source sample, independent and opposing evidence, availability, workload and push
treatment. Check the same effect was applied only once. Inspect every machine
downgrade. Reliable B and validated weights/context cannot be replaced by narrative
confidence. Out is ineligible and cannot become an under win.

Before final publication, refresh time-sensitive facts and prices to the required
freshness window. If a game starts during research, do not publish a new pregame
recommendation for it. Preserve only forecasts that were actually made before start.

## 5. Conversation report sample

The following is a layout, with deliberately unfilled fields:

**Research as of [date, time ET].** Probabilities are uncalibrated estimates at
public reference lines. [Number] Tier 1 / Tier 2 / Tier 3 / Watchlist candidates.
State the actual A/B blend status and material coverage limits immediately.

| Exact machine rank | Player / game | Stat / side / public line | Predictive P(win), P(push) | A / B reliability | Main reason / limitation |
|---|---|---|---|---|---|
| [returned rank] | [verified identity] | [actual reference] | [code outputs only] | [actual results] | [specific mechanism or blocker] |

For each candidate, explain the stat mechanism, strongest supporting evidence,
strongest opposing evidence, shared event treatment and reason for the exact rank.
Cite retrieved sources beside the factual claims. Include the actual line ladder
only when requested and calculated; label diagnostic alternatives clearly.

**Example of an honest blocked result:** “Player P — Unranked. Both source baselines
ran, but the reported teammate absence has no verified effective time and the joint
lineup comparison is unavailable. No adjusted probability or ranked pick is published.”
This is a fictional format example, not a result from a real game.

Finish with actual scanned/unresearchable/shortlisted counts, per-sport history and
price coverage, games excluded after start, rejected candidates with reasons, source
conflicts and unresolved gaps. Never fill a tier to make the report look complete.

## 6. Persistent handoff and morning work

For authorized daily collection, maintain one durable history archive and give both
scheduled tasks its exact persistent reference. Restore it before updating it.
Preserve source observations and provenance, raw collection results and failures,
immutable forecast inputs, actual forecast/evaluation timestamps, event start times,
both engine outputs, shared context, market references and unsettled outcomes.
Keep a per-run manifest with coverage and the next unresolved actions.

Do not rely on an overnight temporary workspace. Confirm a successful durable save
before claiming that morning handoff is ready. Exclude credential values from the
history archive and reports. Preserve the archive's identity when adding a new run.

The morning run fetches verified final results, checks actual participation, settles
the original forecasts, and appends/deduplicates source histories. Leave unfinished,
DNP or unsupported results unresolved. Never backfill a “pregame” forecast after the
outcome. Do not automatically change model settings, fit weights or calibrate unless
the user explicitly requests it; the user currently reserves that work for manual use.

## 7. Completion checklist

- Every scheduled in-scope game has a coverage disposition.
- Both sides of available covered markets were scanned; missing prices are explicit.
- Every shortlisted candidate and explicit context trigger was investigated.
- Mandatory advanced checks and both-team availability were sourced or blocked.
- Supporting and opposing cases, source conflicts and sample limitations are recorded.
- Both engines and shared context ran or have exact abstention/failure reasons.
- Source histories, root events and baseline exposure were checked for duplication.
- Prices and time-sensitive facts were refreshed; started games were excluded.
- Final ranks match machine output; no unsupported probability or tier is asserted.
- Authorized histories and actual forecasts were durably saved for the morning job.
- Any interrupted or blocked work is explicitly incomplete with a resumption list.
