# Hosted-review reproduction

From repository root:

```bash
PYTHONPATH=. python docs/nba_architecture/p1_prospective_20261118/independent/hosted_probe.py
sha256sum docs/nba_architecture/p1_prospective_20261118/HOSTED_WORKER.py docs/nba_architecture/p1_prospective_20261118/independent/hosted-block-readback.py
sha256sum -c docs/nba_architecture/p1_prospective_20261118/independent/HOSTED_SHA256SUMS
```

The worker test compiles exact raw worker bytes; replaces clock, network,
subprocess and storage only within isolated synthetic execution. It exercises
transport, duplicate claims and invalid windows/pins. It does not start a hosted
pregame/morning worker. Hosted actual probe evidence was fetched read-only using
Deepnote get_notebook/get_block and get_run(snapshotDelivery=blocks) for the two
published run IDs. Automation readbacks were obtained read-only via private peek
for each exact ID; current prompt/schedule fields were compared with owner receipt.
No implementation code, notebook block or automation was edited by this reviewer.
Existing independent SHA256SUMS is preserved; HOSTED_SHA256SUMS covers only new
hosted review files, with raw-byte paths relative to repository root.
