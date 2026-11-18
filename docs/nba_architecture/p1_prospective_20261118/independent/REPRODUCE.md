# Independent reproduction

From repo root; exact code/cohort digests are in FINAL_DECISION/decision.json.

```bash
PYTHONPATH=. python docs/nba_architecture/p1_prospective_20261118/independent/profile_probe.py
PYTHONPATH=. python docs/nba_architecture/p1_prospective_20261118/independent/probe.py
python -m unittest discover -s tests/nba_architecture -p 'test_p1_prospective_capture.py' -v
python scripts/nba_p1_prospective_capture.py --stage initial --output /tmp/new-independent-p1-prospective
sha256sum -c docs/nba_architecture/p1_prospective_20261118/independent/SHA256SUMS
```

Actual original CLI command used --output docs/nba_architecture/p1_prospective_20261118/independent/captures;
native.stdout/stderr preserve that execution. Unique attempt dirs prevent overwrite.
A rerun after freeze records a missed horizon, and new HTTP bodies may differ.
All current sources remain UNADMITTED. Body digests cover exact HTTP response
body bytes; code/cohort/receipt/output hashes cover raw files. HTTP Date is merely
an unverified header; native generated/published clock claims are separate.

profile probe checks frozen original capture hashes/selection/uniqueIDs and clocks.
Independent probe uses those actual native arrays for readers; its hostile capture
adapter and fake-clock scenarios are explicitly synthetic. before.* is the first
4method execution after owner fixes; final.* is the6method expanded probe. Neither
is claimed as a pre-repair red. Method/subcase counts overlap and are not games.
SHA256SUMS paths are relative to repository root; nested attempt SHA256SUMS paths
are relative to their individual attempt dirs.
