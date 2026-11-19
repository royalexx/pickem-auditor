# Independent reproduction

From repo root, Python/pdftotext installed:

```bash
PYTHONPATH=. python docs/nba_architecture/p1_workflow_repair_20261119/independent/prefix_red.py
PYTHONPATH=. python docs/nba_architecture/p1_workflow_repair_20261119/independent/selector_probe.py
PYTHONPATH=. python docs/nba_architecture/p1_workflow_repair_20261119/independent/source_scope_probe.py
python -m unittest discover -s tests/nba_architecture -p 'test_p1_injury_report_v2.py' -v
sha256sum -c docs/nba_architecture/p1_workflow_repair_20261119/independent/SHA256SUMS
```

prefix_red deliberately FAILS against immutable9352ae0b Git blob; finalselector
probe passes. selector-first.* preserves reviewer wrong75-total denominator
assumption; raw same-day75 versus completehref82 distinction is in final decision.
Current positive capture command is recorded exactly in actual-final-command.json;
its output paths are create-only, so reproduce with a new output path and future
explicit capture-test freeze. New HTTP bodies/clocks may differ. This current
public acquisition cannot backdate November18missing bytes or certify publication.

All bounded legitimate source search calls use URLs in source_search/*/receipt.json
and existing create-only p1_capture_v1.capture(URL,new_path). HTTP403 bodies are
preserved. source_scope_probe performs native JSON extraction from stored raw
__NEXT_DATA__ script, checks native identities/array counts/source receipt hashes,
and separately records provider-declared versus actual clocks. It is an audit
probe, not an implemented or admitted production reader. No review code mutates
sources, creates a forecast, installs a root or schedules a game.

SHA256SUMS hashes exact raw disk bytes relative to repository root; raw response
body/PDF hashes cover unmodified captured bytes. Native JSON interpretation never
substitutes for source body SHA. Final actual capture's nested manifest paths are
relative to that capture directory. Hostile denial/late/URL scenarios are clearly
synthetic controls; actual current capture and official source searches are not.
