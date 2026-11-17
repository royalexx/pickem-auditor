# Latest-owner root-discovery extension

Pre-P6 QC applied the first P0 repair to disposable exact owner snapshots. P1/P2/P5 then imported cleanly, but P3 exposed three references to `test_p3_o_family` and P4 exposed two references to `test_p4_joint`. Those canonical owner helper modules were outside root discovery's import path. The exact source heads and every before/after loader error are retained in `latest_owner_extension/`.

Commit `31a2886` adds two helper-only compatibility exports. When the relevant owner module exists it is imported normally and errors propagate. On an isolated branch without that owner's implementation, no helper is needed and no test case is introduced or suppressed. Canonical assertions and all inherited G0 bytes remain unchanged.

The existing permanent regression now passes on all five exact owner snapshots with the full P0 support: zero root errors, identical canonical NBA test IDs between root and dedicated entrypoints, and no duplicate IDs. No unrelated root test body executes in these loader checks.

Reproduction remains the same `test_nba_root_discovery_v4.py` command documented in REPRODUCE.md. Independent P6 acceptance remains pending; these are implementation quality-control results only.
