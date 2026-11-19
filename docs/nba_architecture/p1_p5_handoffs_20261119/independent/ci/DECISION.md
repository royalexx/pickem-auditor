# Independent CI dependency and history decision

**ACCEPT_CI_REPLAY_ENVIRONMENT_REPAIR**, exact implementation `3863f115713a6cb7001086e0702197605812fcf4`, incorporating dependency repair `eb3e51fcc300293228273652a43e11b2090f9b79`. The reviewer authored no implementation repairs.

Only `.github/workflows/ci.yml` and `requirements-nba-research-tests.txt` differ from accepted publication `cb87fdcd66e2c3603de53d1a53c19907112bc989`. Native source, readers, configuration, models, tests and runtime scripts are byte-identical. The disabled NUTS job is byte-identical and remained SKIPPED on hosted runs. No schedule, inference, scoring, sampling or release behavior changes.

The repair installs explicit numpy2.3.5/scipy1.17.0/jsonschema4.26.0/pytest9.2.0 test dependencies and OS pdftotext before full offline discovery, and fetches all Git history for existing P4 regression fixtures that materialize exact pinned owner bytes. The pins satisfy the existing NFL inference dependency bounds. This is top-level dependency pinning, not a full transitive or OS-package lockfile.

The initial publication's clean hosted suite failed with 48 errors and one discovery failure because jsonschema/pdftotext were absent. Dependency-only `eb3e51fc` passed 2,284 tests in a fresh isolated local venv (136.117s, nine skips), but both hosted runs still failed with two legacy P4 setup errors: pinned source Git objects were unavailable in the checkout (2,220 tests, nine skips). Those raw failures remain preserved. The subsequent full-history repair changes only CI checkout setup; it does not bypass or weaken the old source-byte tests.

Final exact `3863f115` push run **44638386925 passed**: 2,284 tests in 89.185s, nine skips. Its actual pdftotext version was 26.01.0. Full raw hosted logs and returned head/job metadata are in this directory. Acceptance covers the clean CI environment and full offline suite, retaining optional skipped tests as skipped; it does not assert that unexercised samplers or numerical statistic/joint inference were tested. The separate genuine P1→P5 research execution and archive acceptance remain unchanged.

Final PR run **44638398365 also passed** at exact `3863f115`: 2,284 tests in 145.236s, nine skips (2,275 successful executions). Both runs report offline-tests SUCCESS and NUTS SKIPPED. The recorded readbacks and raw logs independently confirm these dispositions. Later evidence-only publication heads require their own ordinary CI readback; these receipts bind the exact implementation named above.
