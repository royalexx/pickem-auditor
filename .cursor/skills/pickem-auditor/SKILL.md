---
name: pickem-auditor
description: Fresh NBA/NHL/NFL full-slate player-prop scouting, public-market cross-checking, rigorous research packets, model diagnostics, and tiered candidate ranking. Invoke for pick'em targets, prop board requests, or slate audits.
---

# Pick'em Auditor — Cursor project skill

Read `references/research_blueprint.md` before starting: it defines the required
research work product, completion checklist, sample report and morning handoff.

Prioritize research quality and completeness over elapsed time. The operator accepts
runs of an hour or longer. Do not shorten collection, skip mandatory checks, reduce
the researched shortlist, or stop after convenient examples to finish faster.
Investigate every serious candidate and explicit contextual trigger, seek independent
and opposing evidence, resolve source conflicts, and pursue alternate authoritative
sources when a feed fails. Use bounded request timeouts and sensible retries so one
dead endpoint cannot stall all other work. Refresh prices and time-sensitive facts
before final grading; exclude games that have started. Checkpoint authorized internal
histories and actual pregame forecasts during long runs. If access or runtime limits
prevent completion, preserve completed work, identify the exact remaining gaps, and
label the run incomplete. Never fill a gap or force a tier to make a run look finished.

Run commands from **repository root**, not from this directory. Do fresh source and odds checks every run: never reuse a prior slate, line, or yesterday's injury status. Do not research Underdog, import Underdog lines, build slips, or suggest stakes. Numerical probabilities are *uncalibrated model estimates* until enough settled out-of-sample forecasts establish calibration.

Load odds credentials automatically from the operator's `config/credentials.local.json`
or `PROPLINE_API_KEY` environment override. Never print or quote credential values, put
them in research packets, or commit the local configuration. A personal ZIP may
contain that file; remove it before redistributing the project.

1. Read `references/shared_context.md`, `references/season_opportunities.md`, `references/advanced_scouting.md`, `references/workflow_stages.md`, `references/slate_fetch.md`, `references/research_packet.md`, `references/math_helper.md`, `references/veto_rules.md`, and `references/funnel_checks.md` as applicable.
2. Run `python3 scripts/collect_workflow.py --date YYYY-MM-DD` (Toronto slate date). This runs collection, common-input preparation and scanning with existing free NFL/NHL/NBA sources. Read its manifest and stage logs. Each run has its own directory under `data/collection_runs`; use that run’s research packet, prep and scan paths in subsequent commands. Exit zero means ready for research, never approved picks. See `references/collection_workflow.md`. For feed diagnostics only, use `python3 scripts/fetch_slate.py --preflight`. Inspect `coverage.by_sport` for priced rows and usable histories. `usable` means raw rows were collected; it does not prove usable prices or complete coverage. A false `coverage.has_priced_history_rows`, a zero-priced slate or absent quotes is a **blocked run**, never "no targets". Report missing-history coverage and verify quote freshness separately.
3. Use the workflow’s `scan.json` and `prep.jsonl`. For a manual re-preparation, run `python3 scripts/fetch_slate.py prep --stdout | python3 scripts/pickem_math.py scan --stdin` with `set -o pipefail` and explicit input paths when using a run directory. Save the scan JSON to a temporary location only when needed to identify its real shortlist. Perform Stage D context research even for strong value-free triggers.
4. Read the workflow’s `research_queue.json` and `scan.research_candidates` even when the publication shortlist is empty. Read `references/research_tasks.md`. The workflow attempts structured-source resolution and regrades automatically. Inspect its source-attempt records and audit status. Pursue remaining web research yourself: resolve every task through fresh sources or document a concrete blocker, then regrade. A source retry or pending task list is not a completed research run. For NHL goalie starters, the resolver checks ESPN scoreboard `probables` for explicit confirmed status; if absent, search dated Daily Faceoff reports and their cited sources. If feeds leave availability empty, read `references/verified_reports.md` and use its verified-report importer after reading explicit game-day sources. Fill verified, time-stamped research facts. `python3 scripts/research_packet.py gaps --packet data/research_<date>.json --scan <scan_json>` restricts gap searches to the actual shortlist, not all prep candidates. Verify URLs and quotes against retrieved pages. Null if unavailable.
5. Run `python3 scripts/research_packet.py audit --packet data/research_<date>.json --prep <prep.jsonl>` to validate, merge and evaluate in one step. Add `--collect-lineups` only when a live collection pass is intended. Use collector-owned usage histories for Engine B. Route upcoming injuries and joint lineup effects only through shared context per `references/shared_context.md`. Researcher scalar and typed scenario estimates remain diagnostics. Missing evidence means Engine B abstains. The separate `validate`, `to-pipeline`, and `pipeline --batch --stdin` commands remain diagnostic alternatives. The pipeline refuses missing availability and required confirmation, unverifiable weather, inconsistent role windows and partial NFL reads cross-checks. Investigate any machine downgrade before reporting. Read the audit dispositions and give every researched candidate its exact final rank or blocking evidence; a numerical band is not a published tier. Distinguish supporting-research gaps from numerical prerequisites.
6. For NFL receiving and tackle props, inspect the attached current-season profiles per the season guide. Their older `season_projection` scenarios are diagnostics. Use source-owned usage for the eligible baseline. Use the computed effects ledger; do not hide context adjustments in baseline scalars. Inspect repeated causes and embedded baseline effects. Verify actual venue/roof from a public source; local venue hints are insufficient. Never apply both manual and computed opportunities. Perform the Stage I adversarial checklist and report exact machine `final_rank`, public reference line, assumptions, and data gaps. No forced Tier 1. Never describe a provisional 60% as calibrated 60%.
7. Conversation output is the report; do not persist user-facing picks/research unless asked. `scripts/jobs.py` is a separate, explicitly configured shadow-calibration workflow, not part of a user-facing invocation.

**Hard gates:** independent event mechanisms instead of URL counts; unknown status is not active; Out is rejected; unknown required goalie/QB confirmation cannot become a published grade; incomplete outdoor forecast is unresolved; Engine A uses history only; Engine B uses source-derived historical usage; upcoming context is applied once to the mixture. Partial read buckets are diagnostics. Tier 1 requires reliable results from both engines and a validated sport/stat blend. Always grade uncertainty-aware probabilities; point estimates are diagnostics. On failures give a coverage/failure explanation, not an empty successful board.
