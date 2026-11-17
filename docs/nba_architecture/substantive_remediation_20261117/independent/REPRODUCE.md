# Reproduce independent substantive review

Create clean worktrees at:

- final: `9e8145972077a598687eaabdbc559f3cbce5e4d7`
- coupling-only: `c296706d2c5e84b6140ac18141718300362ccf38`
- first gamebook candidate: `16f3eb732c476ea8683e7976f36c4d12f7680ed7`
- installed root: `b70d6b0af3ab6da26d7c56594158022755648b9d`

From this packet, with NumPy/SciPy/jsonschema/mpmath and Poppler'spdftotext and
pdftoppm installed:

```bash
OPENBLAS_NUM_THREADS=1 python probe_coupling.py --candidate /absolute/final --output /new/coupling.json
python final_confirmation.py --candidate /absolute/final --output /new/root.json
python probe_gamebook.py --candidate /absolute/first-gamebook-candidate --output /new/gamebook.json
```

The last command intentionally tests the uninstalled-root candidate and a
simulated trusted installation in an isolated temporary directory. It never
changes implementation files or the production registry. The finalconfirmation
command uses the actual installed fixed root at exactfinalhead.

From the respective worktree root:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=.:tests/nba_architecture python -m unittest discover -s tests/nba_architecture -v
OPENBLAS_NUM_THREADS=1 PYTHONPATH=.:tests/nba_architecture python -m unittest tests.nba_architecture.test_gamebook_v1 -v
```

Observed full suite521 atc296706d and527 atb70d6b0. The exactfinalhead adds only
two root-testmethods and no implementationchanges; its8methodgamebook suite
passes. A fresh full run atfinal is expected529 but is not claimed independently
executed here. Source hashes and actual root population are recorded in
`final-source-confirmation.json`.

`official-independent-refetch.receipt.json` records an actual200/applicationpdf
retrieval using Mozilla/5.0 at21:51:18UTC; the resulting rawbytes match the owner
capture at21:44:19.688624UTC. The approved exact earlier capture clock is not
replaced by the later independent clock. A plaincurl attempt initially returned
503; the independent urllib retrieval succeeded. The PNG is a rendered firstpage
for visualreview, not the raw source hash domain.

`gamebook_approval.json` is immutable: SHA256
64464f369f6696def13a58816b9a1a04c6c78de3bc6ecd7e782555b32a6e6ba6.
It authorizes only the exact three printed-content capabilities and no other
source/reader/capture population. `installed-root-confirmation.json` records
actualb70publicAPIexecution; `final-source-confirmation.json` repeats it atfinal.

All new coupling inputs are synthetic, zero observedgames, and fit no historical
models. OfficialPDFcontentreview does not certify historicaloriginalavailability,
completecorrections, future rosters, predictive forecasts or model quality.
