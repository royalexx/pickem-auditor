# CI-only independent verification

Exact reviewed implementation: `eb3e51fcc300293228273652a43e11b2090f9b79`, compared with publication `cb87fdcd66e2c3603de53d1a53c19907112bc989`.

```sh
git diff cb87fdcd eb3e51fc --stat
git diff cb87fdcd eb3e51fc -- v2 scripts config tests research
gh run view 44637780773 --repo royalexx/pickem-auditor --json databaseId,headSha,status,conclusion,jobs
gh run view 44637772523 --repo royalexx/pickem-auditor --json databaseId,headSha,status,conclusion,jobs
gh run view 44637780773 --repo royalexx/pickem-auditor --log
```

For a fresh Python3.12 environment, reproduce the workflow's PyYAML6.0.2 install, requirements-nfl-inference.txt and requirements-nba-research-tests.txt installs, then ensure the OS-provided pdftotext is present (`apt-get install --no-install-recommends poppler-utils`). Run `python -m unittest discover -s tests -q`. Full dependency installation and fresh-environment evidence is retained separately under the owner ci_dependency_repair directory. Network access for package installation is separate from the offline test suite. Pinned top-level packages are numpy2.3.5/scipy1.17.0/jsonschema4.26.0/pytest9.2.0; transitive and OS package versions are recorded in installation logs, not claimed as a full lockfile.

The previous failed hosted runs remain preserved under ci_dependency_repair; successful repaired runs do not replace their receipts. No replay of native real-model forecasts is needed for this dependency-only diff because their code/config/model/input bytes are unchanged.

Final accepted full-history implementation checks:

```sh
gh run view 44638398365 --repo royalexx/pickem-auditor --json databaseId,headSha,status,conclusion,jobs
gh run view 44638386925 --repo royalexx/pickem-auditor --json databaseId,headSha,status,conclusion,jobs
sha256sum -c docs/nba_architecture/p1_p5_handoffs_20261119/independent/ci/SHA256SUMS
```

`hosted-*` files preserve the rejected dependency-only candidate and its in-progress observations; `final-*` files record the accepted full-history candidate. Full terminal returned logs are byte domains GH_CLI_RENDERED_ACTION_LOG_UTF8 and metadata files are GH_CLI_RENDERED_JSON. Their hashes describe these rendered outputs, not unavailable original runner log transport bytes.
