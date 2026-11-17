# Independent scoped P6 repair review

Reviewed candidate: `bafbcf2a09add125247c91c1cc8fc8d98987b5e9`.
Immutable prior audit source/publication: `b7ca2899ab8d902cda62bfb802ab74dcb5598a30`.
Accepted G0 remains `59d28dc23be97de2a6a82d22be8338151e31f5b6`.
Reviewer authored no implementation changes.

Create clean separate Git worktrees at the candidate and audit commits. With
Python, NumPy, SciPy, jsonschema and mpmath installed, run from this packet:

```bash
python reproduce.py --candidate /absolute/candidate --audit /absolute/audit --output /new/output --include-suites
```

The output path must not exist. This portable runner was itself exercised
without `--include-suites` under `portable-check/`; the same suite commands were
executed separately in `exact/` (513 architecture,68S,76C; all pass).
`run_review.py` and `run_sections.py` preserve actual original orchestration
source including execution workspace paths; they are not portable wrappers.

The independent expanded matrix adds15rawcredit keys to the prior matrix's
8exactclocks×14displays×2retainedsubsets:3360synthetic cases. It compares actual
P1 adjudication, actual P2 inspection, P5 prior attachment and public outcome
validation. `exact/expanded.json` has zero disagreements. Its identical source
against exact baseline6dee produces150P2,45P5prior,15P5outcome disagreements in
`expanded-red.json` (expected exit2). Run `expanded_matrix.py --assembly
/absolute/baseline --output /new/red.json` for that negative control.
Matrices overlap public cases and are not additional observed games.

The ten independent sections are unchanged programs from the audit source:

```bash
python /absolute/audit/scripts/nba_p6_independent_checks_v4_20261117.py --assembly /absolute/candidate --expected-assembly bafbcf2a09add125247c91c1cc8fc8d98987b5e9 --section joint --output /new/joint.json
```

Repeat for physical,scores,quarantine,cutoff,optimizer,native,replay,
incompatibility,discovery; expected exit0 for each. `joint` reports n32 BLOCKED
as an expected preserved boundary. `incompatibility` proves the existing
marginal law cannot have an exact coherent coupling; its PASS is correct
failure exposure, not physical-law acceptance.

`authentic.stdout` is the fresh exact-candidate strict-builder BLOCKED result:
26attempted entries, no output snapshot. The original command is the same as
the prior audit ledger, with a fresh output path. It exits2.

No source admission or new physical-law/coupling proof was supplied. The
36-criterion decision is28PASS/0FAIL/8BLOCKED, overallG1NO-GO. This is a scoped
repair review with regression evidence and unchanged prior criteria, not a
fresh comprehensive rerun of the old24/32/256seed/99archive campaign. The full
requested remediation remains incomplete. All input fixtures here are synthetic.
