# Reproduce exact tested changes

Use the published branch and its exact commit, with no changes to old source,
model or forecast bytes. The final tested SHA and complete runtime file hashes
are in `final_suite/COMMAND.json`; actual issuance/compiler/run SHAs are in
their individual immutable receipts. The publication SHA is distinct from
those computation SHAs. Global `SHA256SUMS` uses repository-root relative paths.

The owner's exact installed versions are in `ENVIRONMENT.json` and the bounded
runtime dependencies in `requirements.txt`. Independent high-precision probes
used their separate reference environment and record actual commands/streams;
the full-law rare reference additionally needs mpmath. Tests and verification require
no live data fetch, saved-model replacement, NUTS or historical scoring.

From repository root, using the research environment's Python:

```sh
python -m unittest tests.nba_joint.test_residual_events_v1 tests.test_complete_predictive_c_v1 -v
python -m unittest discover -s tests -q
sha256sum -c docs/nba_architecture/complete_predictive_20261120/SHA256SUMS
```

For raw commands, stdout/stderr and unchanged-code manifests, use
`owner_execution/`, `final_suite/` and each `independent_*/REPRODUCE.md`.
The final suite's launcher compares all tracked runtime/test Python files
before and after execution. An isolated observer can rerun it into a fresh
directory without changing the original test evidence:

```sh
python docs/nba_architecture/complete_predictive_20261120/owner_execution/run_full_suite.py /tmp/complete-predictive-suite-fresh
```

Exercise the real public transports in fresh create-only directories:

```sh
python scripts/nba_complete_predictive.py read-outcomes --output /tmp/native-C-fresh
python scripts/nba_complete_predictive.py replay --output /tmp/full-S-C-replay-fresh
python scripts/nba_complete_predictive.py read-j --output /tmp/new-J-C-fresh
```

These read the exact actual artifacts and source bodies. They issue no new
forecast or score. Source-native output has698 rows; full replay has140
attempts/56 forecasts/84 abstentions/all outcomes pending. J transport has280
requests/112 supported/168 abstentions, with unchanged primitive140/56/84 and
32 same-draw samples. Timing and current model/source acceptance remain
separate from structural transport. Original and repaired J-C read outputs
are both retained; `j_c_transport_repaired` is the reviewed current reader.

Independent probes can write their own result files. Reproduce them in a fresh
worktree containing the published raw evidence, preserving this packet. For
the two prefit reviews, restore only the exact closed writer before running
the probe; the published writers contain the separately authorized activation:

```sh
git worktree add --detach /tmp/pickem-closed-J-review HEAD
git show 50022b13dea208ec519d7fef146b5e151d6f19e1:v2/nba_joint/real_event_parameters_v1.py > /tmp/pickem-closed-J-review/v2/nba_joint/real_event_parameters_v1.py
cd /tmp/pickem-closed-J-review
python docs/nba_architecture/complete_predictive_20261120/independent_j_prefit/prefit_probe.py
```

Use another fresh worktree for S3, restoring
`v2/nba_s_family/prospective_s3_fit_v1.py` from
`8730362cce3a04eb8edeaa15388651f1cee240f7` before its prefit probe.
The complete raw bodies and review packets were published after some of the
reviewed implementation commits; checking out an earlier code commit alone
does not recover those later-published inputs. Their hashes, not a fictional
earlier Git publication, establish which bytes were actually tested.

The actual one-time execution commands were:

```sh
python docs/nba_architecture/complete_predictive_20261120/run_s3_fit.py
python docs/nba_architecture/complete_predictive_20261120/issue_full_forecast.py
python scripts/nba_complete_predictive.py compile-j --output docs/nba_architecture/complete_predictive_20261120/fitted_j
python scripts/nba_complete_predictive.py run-j --output docs/nba_architecture/complete_predictive_20261120/actual_j_candidate
```

These are recorded provenance, not instructions to replace the original
directories or run another fit. Writers are create-only. The prefit approval
authorized one new prospective compile, now consumed. Model reproduction for
independent review reconstructed bytes in memory without calling that writer.
No historical replay or accuracy test is hidden behind these commands.

Byte domains:

| Hash | Byte domain |
|---|---|
| Capture body SHA | Exact HTTP response body bytes, including original encoding/whitespace. |
| Capture receipt SHA | Exact saved UTF8 JSON bytes; observations/retrieval/ingestion separate from null source publication. |
| Model/forecast/run raw SHA | Exact saved UTF8 JSON file bytes; unchanged clocks are part of raw artifacts. |
| Payload SHA | The specific version's canonical semantic JSON, excluding only fields explicitly documented in its producer. Never substitute it for a raw hash. |
| Source code SHA | Exact Python file bytes. Reader/helper closure guards reject drift. |
| Test/process output SHA | Exact redirected stdout or stderr bytes, including empty stderr. |
| SHA256SUMS | Repository file bytes at the published commit; each older independent ledger remains pinned to its own reviewed versions. |

Original body and receipt hashes/clocks are in `PBP_POPULATION.json`, the
original `PREFIT_POPULATION.json`, and raw capture directories. Exact new
artifact hashes are collected in `ARTIFACT_LEDGER.json`. Every failed/rejected
population remains in its original record. Avoid reserializing canonical or
HTTP files before verification. No zip/holdout archive needs decompression.
