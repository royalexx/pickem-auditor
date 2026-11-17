# P3 native P1 handoff and additive remediation evidence v4

Authority: PA-V25-MASTER-2026-11-09 / v1.1. P3 remains shadow-only and G1 BLOCKED;
P6 must independently decide acceptance. Accepted G0 and all old P3 source,
tests, source artifacts, reports and receipts are unchanged.

`v2/nba_o_p1_native.py` consumes the actual P1
`nba-p1-native-handoff/1.0.0` pregame-context export. It independently decodes
the exact exported bytes, verifies their raw SHA, parses closed assertion
fields, and reconstructs the candidate identity/availability rows rather than
trusting P1's summary. It joins game/team/player/freeze/start identities,
checks asserted availability clocks, preserves every null membership, role,
home and participation field, and verifies incomplete-roster denominators.
Raw adapter-export bytes are explicitly distinguished from original provider
HTTP bytes. None are authenticated by matching hashes.

The available P1 transport has no accepted independent source-admission path,
complete original roster, dated membership, source-bound home/role or admissible
participation/minute prior. Therefore the native consumer returns a sealed
`p3_native_input_abstention` at `INDEPENDENT_SOURCE_ADMISSION`, retaining the
entire export and all missing requirements. It performs no O sampling. A caller
cannot enable certification with a status string, complete-roster label,
participation number or hash. A future admission path requires a separately
reviewed version. This implements the latest callable boundary; it does not
supply unavailable evidence or close B-P3-01.

The actual native P1 exporter is called by
`scripts/nba_p3_native_handoff_check_v4_20261116.py`; all fixture source bytes
are explicitly synthetic engineering examples. Its first run occurred while
new P1/P3 files were uncommitted; raw module digests are retained and it is not
an exact-commit acceptance receipt. Final committed-head execution is recorded
separately. Positive/negative tests preserve source uncertainty and reject raw
corruption, summary/identity changes, post-freeze clocks, false participation,
invented source admission and candidate-population changes.

The proposed O-model cutoff defect was disproved: the accepted G0 checked
validator already rejects `MODEL_AFTER_DATA_CUTOFF` when model cutoff is one
microsecond after P's declared cutoff but before freeze. The first probe's empty
stdout and raw traceback are retained. The corrected probe and permanent
paired before/equality/one-microsecond-after regressions preserve this existing
protection for both O model metadata and player priors. No cutoff repair or new
acceptance is claimed.

The P3 handoff documentation digest discrepancy is corrected by the additive
`p3_remediation_v4_20261116/documentation_receipt_v2.json`. It identifies both
the original pre-append digest and exact complete unchanged Markdown digest;
the old receipt is not rewritten. The separate coupling proposal documents the
retained actual O2 n=32 red boundary, finite n=4/n=8 results and the mathematical
requirements for any future scalable proof. Proposal disclosure alone does not
close B-P4-03.

Early exit still means a cap on total player-minutes, never an authenticated
clock exit. Five-on-floor witnesses demonstrate aggregate mathematical exposure
feasibility and remain distinct from genuine chronological rotations.

Reproduction (fresh output directory for every invocation):

```bash
python -m unittest discover -s tests/nba_architecture -p 'test_*.py' -v
PYTHONPATH=. python scripts/nba_p3_native_handoff_check_v4_20261116.py --p1-root /path/to/exact-p1-owner --output work/p3-native-fresh
```

P1 owns obtaining original captures and dated complete roster/context evidence;
P3/P1 must supply an independently admitted fitted-prior authentication contract
before participation certification. No genuine fit exists in the available
population. No historical fitting, holdout access, G2, schedule change, merge,
deployment or Tier promotion is authorized or performed. Rollback: close the
isolated owner PR or revert only these additive P3 files, preserving every old
and new failure receipt. Implementation testing is not independent acceptance.
