# Preserved reviewer-harness failures

These failures belong to the independent reviewer script, not the implementation candidate. No implementation repair was requested or authored.

1. The initial harness stored a Path in the unittest class attribute `run`, masking unittest's callable `run` method. Its actual current-clock CLI completed, but the harness stopped before executing review methods with `TypeError: 'PosixPath' object is not callable`. Original stderr/stdout are `initial_probe.stderr` and `initial_probe.stdout`. The successful CLI artifact tree remains in `initial_probe_current_cli/`; the initial CLI's separately captured stdout was overwritten by the next reviewer invocation, so it is not claimed as retained raw stdout. The original receipt and original archive bytes remain present. The reviewer renamed the attribute to `run_dir`.

2. The next harness completed all source/model/native/replay checks, then two mutation setup cases attempted to overwrite temporary copies of archive files with mode 0444. The operating system raised `PermissionError` before the intended corruption could reach the archive reader. Original `pre_chmod_probe.stderr`, `pre_chmod_probe.stdout`, `pre_chmod_RESULTS.json`, `pre_chmod_actual_cli.stdout`, `pre_chmod_actual_cli.stderr` and `pre_chmod_current_cli/` are preserved. The reviewer changed only the probe to chmod its temporary copied objects to 0644 before simulating privileged tampering. The final raw corruption and immutable-collision controls then passed.

The corrected final review passed all nine methods with zero failures/errors. The final probe also supports a separate output directory for fresh, create-only reproduction; that final script was executed again with its complete evidence retained under `reproduction/`.
