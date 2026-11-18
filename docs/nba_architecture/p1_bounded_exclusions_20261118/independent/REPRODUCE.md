# Independent reproduction

Exact tested implementation a8696fccb1eba992f1249e94c45e84bab558a836.
From repository root with Python and pdftotext:

```bash
PYTHONPATH=. python docs/nba_architecture/p1_bounded_exclusions_20261118/independent/probe.py > /tmp/p1-demo-public.stdout 2> /tmp/p1-demo-public.stderr
python -m unittest discover -s tests/nba_architecture -p 'test_*.py' -v > /tmp/p1-demo-architecture.stdout 2> /tmp/p1-demo-architecture.stderr
sha256sum -c docs/nba_architecture/p1_bounded_exclusions_20261118/independent/SHA256SUMS
```

public.stdout is the complete actual result serialized sorted-key JSON with a
newline, not a source capture. Source inputs are original PDF bytes and native
ESPN JSON HTTP-body bytes pinned by the prior independently accepted root.
The PDF receipt adapter copies existing sha256 into raw_sha256; no source field
or original clock is manufactured. Synthetic policy mutations use only the
untrusted classify_rows helper; changed source bundles are rejected by actual
public demonstrate before any exclusion classification.

Public probe methods count3; subcases overlap and are not observed games.
All26 observed source rows remain present, including2DNP and0actual excluded.
This is one listed completed-game population, not a complete target roster or
forecast/scoring cohort. SHA256SUMS covers raw disk bytes relative to repo root.
