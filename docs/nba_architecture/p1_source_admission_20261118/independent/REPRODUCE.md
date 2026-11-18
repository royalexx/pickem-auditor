# Independent reproduction

From repository root with Python and pdftotext installed:

```bash
PYTHONPATH=. python docs/nba_architecture/p1_source_admission_20261118/independent/probe.py
python -m unittest discover -s tests/nba_architecture -p 'test_*.py' -v
PYTHONPATH=. python docs/nba_architecture/p1_source_admission_20261118/independent/capture_probe.py /tmp/new-independent-p1-capture
```

Capture destination must not exist; network content may change. The installed
reader admits only its fixed old source bytes. Newly fetched bytes stay UNADMITTED.
Publication is never inferred from HTTP Date. The capture stdout records actual
HTTP receipt; original raw bytes remain under native_capture. The earlier direct
independent HTTP refetch and its 26-row corroboration are in profile_probe.json
and espn-independent-refetch.raw; both differ from the fixed admitted bytes.

Preinstallation execution used the same public reader and original six probe
methods, with `PACKET` patched to an isolated temporary directory holding exact
proposed root bytes named installed_identity_root.json; no production install.
Installed probes add root/code mutation and denominator wrapper tests. All raw
stdout/stderr, including blank streams, are retained. Tests count methods, and
method subcases overlap; do not add their populations as observed games.

SHA256SUMS covers exact disk bytes, relative to repository root. Receipt binding
in the root uses sorted-key compact UTF-8 JSON without trailing newline; raw
HTTP/PDF digests cover unmodified response bodies; code digests cover raw files.
