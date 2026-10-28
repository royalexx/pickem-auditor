# Morning settlement: missed-cron recovery and persistence

The authoritative morning and afternoon workflow is
`.github/workflows/pickem-daily.yml` on the default branch. GitHub Actions
scheduled runs are best effort; late events and dropped events are documented
by GitHub. A green GitHub job can still have every substantive pipeline step
marked `skipped`; never treat green as proof of settlement.

## Morning times, America/Toronto

- Primary: 06:13 local, encoded as 10:13 UTC during DST and 11:13 UTC
  during standard time.
- Backup: 07:41 and 08:41 during DST, or 06:41 and 07:41 during standard
  time, encoded as 11:41 UTC and 12:41 UTC.
- The selector (`scripts/morning_schedule.py`) translates the scheduled
  UTC slot to Toronto local time and ignores inactive DST offsets and
  sufficiently late or previous-day events.
- `workflow_dispatch` supports `phase=morning` and an explicit
  `force_morning=true` flag for intentional same-day reruns. It does not
  silently override the settled-day marker.

Before any scheduled morning settlement, the job checks the authoritative
`data/shadow-calibration` branch for
`data/morning_runs/YYYY-MM-DD.json`. A valid completed-day marker causes
`phase=skip`, so backup cron events cannot duplicate completed work.
A missing/invalid/unreadable marker never fabricates success; the normal
settlement process will attempt to run and report failures.

A marker is written only after collection, forecast-history restoration,
league coverage validation, settlement, and forecast-identity verification
have *all* succeeded. The marker includes the Toronto date, GitHub run ID,
UTC timestamps, and a SHA-256 of the run receipt. The shadow persistence
script stores these markers on the same authoritative data branch as
settled forecasts and refuses conflicting replacement. Manual forced
reruns preserve the existing completed marker; they do not rewrite it.

## Confirming actual settlement

Check the GitHub run's steps, not only its green status. Require:
1. Gate prints `phase=morning`, not `skip`.
2. `reports/daily_receipt.json` has `phase=morning` and every required
   stage returns `ok: true`.
3. `reports/stages/settle_forecasts.log` reports `errors: 0` and
   `rows_written` for this execution.
4. `reports/forecast_invariants.json` reports `status: verified` and
   the original snapshot identity is unchanged.
5. The history persistence step succeeds, and a completed-day marker exists
   on the data branch.

The morning phase has `PICKEM_DISABLE_ODDS=1` deliberately: no PropLine
market calls or price refreshes are required to settle outcomes.

## Incident: 2026-10-28

No GitHub schedule-triggered run was created for the original 06:13 Toronto
morning slot on October 28. The previous scheduled success from October 27
was an inactive UTC-offset slot and logged `Running: skip`.
A one-time explicitly gated push triggered the normal morning workflow
on October 28 (run 40700885909), and that job completed successfully at
13:57 UTC. All seven stages succeeded, 426 forecast rows received settled
outcomes, original forecast identities were verified, and history
persistence completed. The receipt shows 2,382 total forecast rows,
1,804 with verified outcomes, and 578 still unresolved.

The one-time push trigger was removed. A completed marker for 2026-10-28
was recorded on `data/shadow-calibration` using the actual successful
run receipt and SHA-256.

The missing scheduled event's exact provider-side cause cannot be proven
from repository logs, because no event/job was created. GitHub documents
that some scheduled events may be delayed or dropped. The backup windows
and durable marker mitigate this failure mode; they do not guarantee
GitHub's scheduling service will create any particular event.
