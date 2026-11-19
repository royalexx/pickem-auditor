# Clean runner dependency and pinned-history repair

The accepted source/model/handoff implementation remains
7643a100153b3dd3084e03887eb43f1f8a60be9e. This follow-up changes only
.github/workflows/ci.yml and requirements-nba-research-tests.txt. It does not
change any accepted reader, source/model bytes, test expectations, schedule,
training pause or scientific gate.

First hosted red: publicationcb87fdcd66e2c3603de53d1a53c19907112bc989,
GitHubpush44637265084 andPR44637295968. The full offline discovery encountered
48errors from missing jsonschema and pdftotext, plus the import-discovery guard
failure. The exact gh CLI failed-step log stdout is preserved in this directory.
Its byte domain is rendered GitHub Actions log text, not an original HTTP body.

Dependency repair eb3e51fcc300293228273652a43e11b2090f9b79 explicitly installs
the tested NumPy2.3.5, SciPy1.17.0, jsonschema4.26.0 and pytest9.2.0 plus the
Poppler pdftotext executable. These are test-only packages; no sampler is added.
The dependency bounds remain compatible with existing NFL inference tests.

Fresh local reproduction created a new isolated venv and installed:

```bash
python -m venv /workspace/scratch/p1-p5-ci-venv
/workspace/scratch/p1-p5-ci-venv/bin/python -m pip install \
  -r requirements-nfl-inference.txt \
  -r requirements-nba-research-tests.txt \
  PyYAML==6.0.2
/workspace/scratch/p1-p5-ci-venv/bin/python -m unittest discover -s tests -q
```

Result:2284tests run,2275passed and9optional tests skipped, with zero failures
or errors. Raw installation/test stdout,
stderr, exact commands and dependency freeze are retained. Local pdftotext was
already installed; hosted CI now installs it explicitly.

Second hosted red at eb3e51fc: push44637772523 andPR44637780773 ran2220tests but
could not materialize two pinned P4 owner source versions from the shallow
checkout. The original failed logs are retained here and under independent/ci.
The missing examples are exact owner commit
ae956315db9162315d16bdd0a6fe0b4c8afbfe1c:v2/nba_s_family/__init__.py and
96d210a6100085640e7e82928ab1c864839fc454:v2/nba_s_family/model.py. No main or
different owner version was substituted. The local complete repository contained
these objects, explaining its different result.

Checkout repair3863f115713a6cb7001086e0702197605812fcf4 adds fetch-depth:0
only to the offline-tests checkout, making exact history on isolated owner
branches available. Existing tests still materialize and hash-check the same
accepted pins. Final hostedpush44638386925 andPR44638398365 both succeeded at
exact3863f115:2284tests run,2275passed,9optional skips, zero failures/errors.
Raw logs/metadata and separate independent CI decision retain this result;
earlier reds remain unchanged. The archived bytes and native handoff readers
remain identical to the independently accepted7643a100 implementation.

The preexisting joint-bayes-nuts-smoke job stays explicitly disabled. There is no
trigger, cron, notebook or production dependency change. Git history retrieval
does not execute training, score held-out observations or open model holdout
archives. No P2/S or P4/J inference claim follows from this CI repair.
