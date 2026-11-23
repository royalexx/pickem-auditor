# NBA S0 original pregame short-run trigger — November 22, 2026

**Research only; not a production deployment, model training claim, or original outcome score.**

## Incident and root cause
- The isolated Nov 22 long-wait Deepnote canary (notebook `da3378b589ca4909b992d2e0b2fcb2ae`, run `25c5e82b-4f9e-47df-a5b4-5163a88a9bbd`) was preempted with `DETACHED_TIMEOUT_PREEMPTIBLE` before its event-relative capture window.
- The run output stopped after `ARMED_FIRST_EVENT_ONLY`; no later `attempt_summary` or original frozen-player receipt was verified. An armed window is **not** an original forecast.
- Sleeping inside a detached notebook across an event wait is not a reliable scheduler. The P1 canonical collector already supports `wait=False` with exact real-time original source gates.

## Replacement; single active NBA collector owner
- Reused **existing disabled NBA capture task** `6afa51eeb1488191956f2d672edf6d33`; did not create a new conflicting NBA source owner.
- Updated it to `NBA S0 pregame capture — short research-only runs`, enabled on `2026-11-22`.
- iCal: `DTSTART;TZID=America/Toronto:20261122T182500`, `RRULE:FREQ=HOURLY;BYHOUR=11,12,13,14,15,16,17,18,19,20,21,22,23` (one run per eligible hour, at minute 25, current Toronto time).
- One unattended invocation executes **one detached Deepnote job immediately**, without waiting for later capture windows. Notebook ID `232c139125204558bc17ac43d2767e62`, project ID `9cc31536-93be-44db-bdeb-06fba3f61410`.
- The notebook first checks out **exact historical model code commit** `99d4331887dcdf3bda1584c4f02dde80a9985225`, not the evolving draft branch HEAD. This matches the already-predeclared immutable unfitted S0 method artifact (`ModelArtifact` SHA256 `5e178f8fae59d9e3d8c83760d822dc4bebac8426e2e7efc85eef1974d280cd16`; raw artifact SHA256 `5387397fc601c8fda2e0a026df10e64260bcdea2a3c4816750d93cc0ab73511a`).
- All source data continue through the original P1 `run_daily(wait=False)` `WindowPolicy`: early T−70 to T−50 minutes, final T−35 to T−20 minutes. Real NBA tipoff and possession clocks determine admission, not automation scheduled time. Late and missing data abstain.
- Every created P3 `S_ONLY` conditional-on-played prediction must pass P0 hash-backed immutable source, feature, model and forecast admission. Forecast receipt journal: `/work/research/v25_remediation_20261122/nba_s0_short_runs/<sha256>.json`. A claim, dry run, schedule or read-only model method is **not** counted as a frozen original player forecast.
- Every output remains research-only, not price/line linked and not eligible as an unconditional betting pick, model promotion, training or P6 production release. Any uncertain actual playing status is never assumed certain.

## Operational constraints
- Scheduler has a one-run-per-hour minimum interval; the chosen minute-25 sweep favors the established :00/:30 tipoff rhythm. It **does not guarantee** all future events or two windows per game. Events outside admitted windows can legitimately return zero. Exact automated start and Deepnote availability are still operational risks.
- An ongoing same-notebook run must cause the next invocation to abstain; do not run the old sleeping notebook.
- A Deepnote Team Trial concurrent-project limit can block a scheduled run; report `BLOCKED_BY_RUNTIME`. No fallback local or GitHub Actions source collector is authorized.
- Preserve all existing NFL automations, NHL shadow task and morning settlement task. Morning settlement remains at `06:00 America/Toronto` and independently consumes only valid original pregame forecasts and verified NBA FINAL outcomes. A zero-forecast day yields no valid nightly S0 settlement.
- Prior NBA task prompt and schedule remain in the privately persisted Deepnote rollback snapshot `research/v25_remediation_20261122/private_automation_rollback_snapshot.json`, SHA256 `2d3ec761af2d19179688c2c10eb3ca71702400f162f2b510cf03811b9d0cd36f`. **Never commit the private full prompts to GitHub.**

## Acceptance conditions
1. One `short_runs/<sha256>.json` receipt with a verified `COMPLETED_SHORT_WINDOW_RUN` for actual current Toronto date, including genuine event IDs, source claim outcomes, duration and observed run SHA.
2. At least one genuine pregame player/market-free P0 `ForecastSnapshot` admitted strictly before the event's original scheduled start, exact bytes retrievable by independent reader, source available before freeze. Pure `NOT_DUE` cannot satisfy this condition.
3. Independent next-morning official FINAL `SourceReceipt`, `OutcomeRecord` and `SettlementRecord` matching the frozen original identities and scored conditional-on-played law, without DNP=zero or fabricated market outcome.
4. Each condition passes independently and remains BLOCKED otherwise; no retroactive original prediction or purported completed lifecycle.

Current task activation is not itself proof of conditions 1–3.
