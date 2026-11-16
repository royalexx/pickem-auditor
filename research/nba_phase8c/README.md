# NBA Phase 8C — one Daily Deepnote pilot orchestrator

Research-only, strictly point-in-time continuation of PR #143. Frozen parent: `1c78600b612f8c6bb9c3eb3c5649123706f4a78a`. Never changes source/model cutoff, ten pilot game IDs, registration bytes/hash, eligibility gates, original market contracts, historical M0, joint simulator, production ensemble, or tier selection.

## Verified provider diagnosis

A **real detached Deepnote Basic CPU HTTP test**, November 15 at approximately 19:53 Toronto, returned:

| Exact endpoint | Deepnote HTTP |
|---|---|
| `https://www.nba.com/players` | **403** |
| `https://www.nba.com/team/1610612738/celtics` | **200** |
| `https://official.nba.com/nba-injury-report-2026-27-season/` | **200** |
| ESPN scoreboard | **200** |
| ESPN team roster | **200** |

Thus NBA.com is not globally unavailable; the **directory page specifically fails**. Deepnote also passed official PDF parsing with locally extracted Poppler in Phase 8A. Do not identify the cause as an IP ban or API-wide shutdown without server evidence.

Source handling: the collector now retrieves fresh NBA team roster pages by **source-bound prior NBA team page URLs** from immutable Phase 8A identity evidence (route/navigation evidence only). It no longer depends on the blocked `nba.com/players` directory. A failed NBA roster or injury source creates explicit supplemental rejection receipts and **does not prevent ESPN WS1** from capturing original player candidates, scheduled games, historical player stats and game box scores. The existing ESPN FINAL summary remains the canonical settlement source. No name-only crosswalk or invented legal eligibility/appearance probability is authorized.


If Poppler provisioning fails, the daily worker permits a **hash-verified ESPN-only** candidate capture rather than discarding the entire original slot. The official injury parser then remains unavailable and its failure is retained; the worker does not infer verified inactivity, game-active eligibility, or positive appearance probabilities from ESPN membership.

A source-fallback capture means **ESPN candidate records only**, not league-certified legal game-active eligibility. J2 F, P1/P2 and original market-edge claims stay BLOCKED-BY-DATA.

## Daily execution design

**Exactly one ChatGPT automation runs daily at 18:05 America/Toronto**, November 16–21 inclusive. It launches ONE Deepnote notebook as detached `read_write` on free Basic CPU. The notebook downloads the SHA-pinned research repository into a temporary extracted directory, provisions local Poppler if needed, then executes:

```bash
OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase8c.daily --root /work
```

The script remains running until every day's frozen original window has been attempted; it starts concurrent same-window games via separate threads/slot locks. The original boundaries are derived only from the original SHA-verified ten-slot registry:

| Toronto date | Original capture opens | Original slot(s) |
|---|---|---|
| 2026-11-16 | 18:20 | 1, 2 |
| 2026-11-17 | 18:50, 19:20 | 3, 4 |
| 2026-11-18 | 18:20 | 5, 6 |
| 2026-11-19 | 19:20 | 7, 8 |
| 2026-11-20 | 18:20, 18:50 | 9, 10 |
| 2026-11-21 | no capture | settle previously captured FINAL games |

All source and completed ledger receipt clocks must be **no later than the 10-minute window's hard deadline**. Late start is recorded MISSED; source failures block, never backfill. Every run uses project-persistent `/work/reports/nba_phase7_pilot` and never clears existing slot claims or first original capture pointers. Independent FINAL settlement uses the existing ESPN Phase 7 adapter and separate append-only `/work/reports/nba_phase8c_settlement`. The day-wide run creates `/work/reports/nba_phase8c/YYYY-MM-DD/start.json`, `preflight.json`, per-window files, `settlement_attempts.json`, `capture_tree_manifest.json` and `finish.json`. A persistent storage test successfully wrote to `/work/research/nba_phase8c/probes`, then retrieved the same bytes through Deepnote project storage.

**Operational limitation:** One ChatGPT trigger does not guarantee a long-lived Deepnote job. The single Deepnote detached run must actually remain running to reach later windows; verify detached run status and receipts. If a detached run terminates early, the remaining original windows must be declared missed or handled by the documented manual Cloud fallback. This design intentionally does not add GitHub Actions, a second Deepnote scheduler or a duplicate collector.

## Reproduction and checks

```bash
OPENBLAS_NUM_THREADS=1 python -B -m unittest discover -s tests/nba_phase8c -v
OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase8c.daily --day 2026-11-17 --dry-run
```

Dry run never invokes capture, writes first claims, settles or modifies pilot storage. Source fallback tests mock the 403 endpoint and verify the independent official source and ESPN handoff; tests verify exact registered windows and stable source-bound routes, concurrent same-window dispatch, and late-run fail closure.

No original pilot capture or settlement has yet been executed. No prospective superiority or official participation claim is created by this infrastructure. All parent evidence remains immutable.

**Rollback:** pause the new daily automation and reinstate the two previous exact-window tasks if needed, and close the Phase 8C research draft. If merged, revert only Phase 8C files and the isolated Phase 7 `sources.py` patch. Never delete original source evidence or first-capture claims.
