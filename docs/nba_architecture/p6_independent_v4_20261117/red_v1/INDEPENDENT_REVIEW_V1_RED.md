# Independent P6 v4 first review — NO-GO

Reviewer: separate `/root/p6_independent`, author of no P1–P5 or P0 repair.
Authority: PA-V25-MASTER-2026-11-09 / v1.1. Accepted G0 remains
`59d28dc23be97de2a6a82d22be8338151e31f5b6` only.

The submitted assembly `d46f5322b47367ba601b05197cef8404758da23d`
fails mandatory committed-source receipt verification. Its source map
`f72bfaa598e1386c2a6026d511e9f695a83b4c1a43088cec24edfb14e952808b`
claims four P2 report files that do not exist in the published assembly tree.
Their original bytes remain present at P2
`fe46965394ea0f48ef5e9da501ec8ca9e441ce47` and match the claimed hashes.
This is a repairable P0/orchestrator assembly publication defect,
**F-P0-ASSEMBLY-01**, rather than an unavailable source population.

The permanent independent regression was committed before execution at
`f79d621c3511a2dfbfcf2adcc145a852becd065c`. From that QA source:

```bash
python scripts/nba_p6_independent_checks_v4_20261117.py \
  --assembly /path/to/disposable/d46f532-assembly \
  --output /new/path/first-review.json --section evidence
```

Observed: FAIL, first absent path
`reports/P2_S_LOCAL_BENCHMARK_20261116.json`. Full population inspection
identified all four missing paths in `assembly_missing_mapped_files.json`.
The original failed execution and exact QA source digest are preserved in
`new_checks_first.json`; six other independent numerical/adversarial sections
passed during that execution. Their success does not cure the missing files.

Root cause and repair are assigned to the P0/orchestrator publication owner.
The implementation owner must publish a new exact assembly, preserving every
claimed owner blob and Git mode in the committed tree, and add a committed-tree
regression. The independent reviewer will then reexecute the permanent check
against that new SHA and append a separate review. This report is immutable;
a later green result must not overwrite this NO-GO.

The eight substantive source/admission/engineering-law blockers in the prior
audit remain open during this review. No source authentication, predictive
validation, constrained-law acceptance, G2 permission or deployment follows
from finite synthetic results. Overall G1 decision at this failed submission:
**NO-GO**.
