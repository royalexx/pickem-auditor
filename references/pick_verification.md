# Pick verification: evidence, decisions, and pregame rechecks

## Operational stages

1. At approximately 16:13 America/Toronto, GitHub collects the complete
   multi-sport slate and PropLine quotes, runs Engine A and Engine B, and
   appends original shadow forecasts. This stage never alters calibration
   weights.
2. The established research triage selects up to 30 subjects (six per
   fixture); up to ten receive an initial verification pass. Every candidate
   gets an unverified source-review template.
3. Official ESPN/league data is used to verify current game identity, venue,
   explicit game-active roster flags and reported starting goalies. Injury
   feed omission, generic roster membership and projected lines NEVER count
   as confirmation. Later contradictory injury designations create an
   unresolved blocker.
4. The autonomous investigator checks official history and news. A
   separately named **deterministic machine reviewer** can approve only after
   re-fetching the exact official game-log response, verifying its SHA-256
   and game-level observations, confirming at least 15 dated observations
   with both supporting and opposing results, matching at least three
   games to the collector's independent history, reproducing a directly
   observed workload mechanism, and verifying current explicit game-active
   status without unresolved conflicting evidence. It never impersonates a
   human or certifies speculative opponent tactics.
   Alternatively, a reviewer/actual source-reading agent submits genuine supporting AND
   opposing evidence. The reviewer must read sources, match player/team/
   fixture, record exact URLs/quotes/time, and document source conflicts.
   The system cannot truthfully invent qualitative matchup or opportunity
   claims. It accepts verified game-day and scouting fact imports through
   scripts/verified_reports.py and scripts/verified_scouting.py.
5. scripts/pick_verification.py validates the same-day packet and reviews,
   reruns the engines on the frozen forecast inputs and current quotes,
   checks source history and vetoes, and produces a new verification receipt
   referencing the original forecast SHA-256. The original forecast remains
   unchanged. Both engines must be reliable; Tier 1 still needs a validated
   A/B blend. The preliminary 70/30 preview never bypasses that condition.
6. GitHub Action .github/workflows/pregame-verification.yml runs every
   15 minutes and only checks games 25 to 55 minutes from kickoff. It
   refreshes official statuses and current prices when needed. It avoids
   using any additional PropLine credits when none of the due subjects
   have either an admissible live-rechecked machine case or a genuine
   human adversarial research attestation. API daily quota checks
   remain enabled when a pull is actually required.
7. scripts/verified_board.py publishes only currently verified decisions.
   It expires decisions at game start or after 60 minutes, retains the
   latest contradictory/vetoed decision, and never treats a historical
   verified result as a current pick.

## Where files are stored

All current research state is under data/verification/YYYY-MM-DD/ on the
data/shadow-calibration branch:

- packet.json: current source packet (not a claim of complete research)
- queue.json: selected priority queue
- decisions/RUN_ID-ATTEMPT-PHASE.json: append-only decision receipt

The original snapshots in data/prop_snapshots.jsonl can only gain separate
settlement information from the next-morning results process. Verification
does not change model inputs, forecast dates, original probabilities or model
weights. scripts/shadow_store.sh refuses conflicting writes to an existing
verification decision. The immutable data/history-archive branch is read-only.

GitHub Actions artifacts also include reports/research_triage.json,
reports/review_template.json, reports/autonomous_investigation.json,
reports/pick_verification.json, reports/verified_board.json and reports/daily_receipt.json.

## Actual source review is required

The deterministic source-review route is enabled with `--auto-review`.
Machine observations are a narrowly verifiable alternative to human narrative
review, **not** a claim that a human read a story or that every matchup
tactic is proven. The re-fetched official source must match a SHA-256 digest,
source values, confirmed player and canonical fixture identity, fresh explicit
active status and independently checked usage data. In addition, both
favorable and unfavorable actual games and a reproducible workload mechanism
are required. Engine A, Engine B, source conflicts, market validation and
all Tier thresholds remain authoritative. The machine route may still
correctly yield no ranked candidates, particularly early in a season or
for NFL props without equivalent signed independent history.

The generated reports/review_template.json is explicitly **unreviewed**.
It is not an AI-generated source confirmation. A person or an actual
source-reading agent may add a current-date review file at
data/review_submissions/YYYY-MM-DD.json.

A valid review object has:
- date: Toronto slate YYYY-MM-DD
- game_day_reports (optional): sourced positive/negative status entries
  supported by scripts/verified_reports.py. Every report includes date,
  named reviewer, player, player_id, team, canonical fixture, explicit
  basis, source_read=true, precise quote and source publication/retrieval
  time. Do not mark a player active because the injury report omits them.
- scouting_reports (optional): named reviewer and fact/mechanism entries
  supported by scripts/verified_scouting.py, including the supporting
  stat-specific checklist and valid source readings.
- attestations: per-candidate objects with exact candidate_id,
  forecast_sha256 from the review template, player_id, team,
  decision="approve", source_read=true, reviewed_at, named reviewer,
  and nonempty supporting and opposing evidence lists. Each item must
  contain fact, value, confidence="confirmed", source_url, retrieved_at
  and a short directly read quote.

Use evidence URLs with real publication/retrieval timestamps. An attestation
is a human/agent claim of having READ an actual source. Schema validation
cannot prove that the cited page contains the claimed text. No one should
file such an attestation without genuinely reading and cross-checking it.

Game-day claims that conflict must be reconciled using new source-backed
facts; an unresolved contradictory status blocks all tiers. Stale, missing,
incompletely sourced or post-kickoff reports remain unranked. The source
review can be completed only before the relevant event, never backdated.

## Reproduction

After the scheduled afternoon job has generated the required files:

    python scripts/pick_verification.py --date YYYY-MM-DD \
      --snapshots data/prop_snapshots.jsonl \
      --queue reports/research_triage.json \
      --packet data/research_YYYY-MM-DD.json --phase initial --limit 10 \
      --auto-review

Review the JSON receipt and the full list of blockers; a successful process
exit with verified=0 is **not** a successful pick approval. The scheduled
pregame action handles live rechecks. Use workflow_dispatch only when
candidate games are within the valid 25–55 minute pregame window.

The latest active board can be rebuilt without an external API request:

    python scripts/verified_board.py --date YYYY-MM-DD \
      --snapshots data/prop_snapshots.jsonl \
      --archive-root data/verification --out reports/verified_board.json

## Limits and guards

- GitHub cron execution may be delayed. Missed windows are skipped, not
  retrospectively backfilled with fictional pregame approvals.
- Without independently re-fetched machine evidence or a genuinely
  source-reviewed human case, new source queries may improve evidence gaps
  but cannot promote an old forecast.
- Any line change, missing paired sportsbook quotes, unauthorized/expired
  market, stale status, missing historical observation verification,
  unsuitable sample size or unsettled research conflict remains a blocker.
- The existing quantitative Tier thresholds and weekly calibration
  validation rules are unchanged.
