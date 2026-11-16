# Phase 8A manual operations

All times are America/Toronto (UTC−05:00). All ten slots remain NOT_DUE at this session’s observation time. No scheduler exists. Use an available Cloud checkout as the primary runtime; Deepnote live NBA access returned 403. Start the runtime and preflight before the window. Do not launch a capture before its own window.

```bash
OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase8a.preflight
```

| Slot | Date | ESPN ID | Capture window | Command |
|---|---|---|---|---|
| 1 | 2026-11-16 | 401909994 | 18:20–18:30 | `OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase7.pilot capture --slot 1 --output reports/nba_phase7_pilot` |
| 2 | 2026-11-16 | 401909995 | 18:20–18:30 | `OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase7.pilot capture --slot 2 --output reports/nba_phase7_pilot` |
| 3 | 2026-11-17 | 401910002 | 18:50–19:00 | `OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase7.pilot capture --slot 3 --output reports/nba_phase7_pilot` |
| 4 | 2026-11-17 | 401910003 | 19:20–19:30 | `OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase7.pilot capture --slot 4 --output reports/nba_phase7_pilot` |
| 5 | 2026-11-18 | 401910007 | 18:20–18:30 | `OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase7.pilot capture --slot 5 --output reports/nba_phase7_pilot` |
| 6 | 2026-11-18 | 401910008 | 18:20–18:30 | `OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase7.pilot capture --slot 6 --output reports/nba_phase7_pilot` |
| 7 | 2026-11-19 | 401910019 | 19:20–19:30 | `OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase7.pilot capture --slot 7 --output reports/nba_phase7_pilot` |
| 8 | 2026-11-19 | 401910020 | 19:20–19:30 | `OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase7.pilot capture --slot 8 --output reports/nba_phase7_pilot` |
| 9 | 2026-11-20 | 401909305 | 18:20–18:30 | `OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase7.pilot capture --slot 9 --output reports/nba_phase7_pilot` |
| 10 | 2026-11-20 | 401909306 | 18:50–19:00 | `OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase7.pilot capture --slot 10 --output reports/nba_phase7_pilot` |

Slots sharing windows require separate commands in separate terminals/processes, using the same authoritative output root. The claim is per slot. A duplicate attempt cannot become a second source universe. Do not remove acquisition claims to retry. Inspect any failure; recovery requires a separately versioned authorized protocol. Never backfill after a deadline.

Requests use 15 seconds for preflight/supplements, 25 seconds for WS1 and 20 seconds for settlement. These are socket/request timeouts, not a guaranteed whole-process duration. Every source receipt and final ledger completion is checked against the deadline; slow responses may finish late and must block. No automatic retries or latency guarantee exist. Start at the beginning of the window, with dependencies already installed.

Deepnote Debian Bookworm local dependency setup (only if that runtime later has verified source access):

```bash
python -B -m research.nba_phase8a.setup_poppler --prefix .runtime/nba_phase8a-poppler
export PATH="$PWD/.runtime/nba_phase8a-poppler/extracted/usr/bin:$PATH"
export LD_LIBRARY_PATH="$PWD/.runtime/nba_phase8a-poppler/extracted/usr/lib/x86_64-linux-gnu"
python -B -m research.nba_phase8a.preflight
```

The setup refuses an existing prefix; reuse the extracted binaries instead of reinstalling. It downloads signed-index Debian packages, extracts locally, and records package hashes. It changes neither the production image nor system package database. The tests used temporary prefixes and read-only project storage; no persistent Deepnote dependency installation is claimed.

After every attempt, retain the entire slot tree including failures, raw gzip bytes, source receipts, claim, first pointer and frozen candidate ledger. Record a SHA-256 manifest and copy the unchanged tree to durable versioned research storage before ending the runtime. Local exclusive writes prevent accidental replacement but are not WORM storage; no hosted retention guarantee is assumed. Keep one authoritative output root across sessions, copying it back and verifying hashes before invoking another slot.

After FINAL, use the existing settlement command with the exact slot root and a NEW output directory. Example:

```bash
python -B -m research.nba_phase7.settlement --slot-root reports/nba_phase7_pilot/slot_01_401909994 --output "reports/nba_phase7_settlement/slot_01_$(date -u +%Y%m%dT%H%M%SZ)"
```

Each remaining manual intervention: start/restore the runtime; verify checkout/dependencies/source connectivity/storage/claims; invoke each due slot; archive each attempt; later confirm FINAL and invoke each settlement; archive settlements and review unresolved outcomes. Do not join postgame outcomes into frozen feature rows. ESPN is the current canonical settlement adapter, not a league-native active-list certificate.

No supported scheduler with verified execution/retention guarantees was established. No cron, Actions workflow or Deepnote schedule was created or enabled. Scheduling, if later proposed, needs separate authorization.
