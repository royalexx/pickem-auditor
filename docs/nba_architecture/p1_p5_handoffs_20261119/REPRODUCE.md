# Exact tested public handoffs and replay

Authority: PA-V25-MASTER-2026-11-09/v1.1 plus the November 19
source_listed_subset amendment. This packet implements research transport and
bounded native conditional-minute reuse, not full G1 or predictive acceptance.

## Implementation sequence

| Stage | Exact implementation candidate | Actual capability |
|---|---|---|
| P1 accepted starting interface | 644f8f51ce08e0df1471a9e063dd03914582eb03 | Replayed source-listed request/abstention handoff |
| P2 final reader repair | 3ca43cddcae1a7aa0bbfa8ea9aea1a5139211ddf | All source-bound player/stat attempts and explicit missing-model abstentions; native S controls are synthetic only |
| P3 final accounting repair | 05b44764fd9fdb7be0a465131a88a9203e977210 | Genuine pinned native M0/M1/M2 conditional-minute execution for supported players |
| P4 final consumer | 36b09d0a4752352e2ffbed0af1e1101b844aaced | Genuine native minute-law consumption, with statistic/joint abstentions |
| P5 and final public runner | 7643a100153b3dd3084e03887eb43f1f8a60be9e | Replay-verified immutable research archive of original bytes and all attempts |

Full tested SHAs, exact argv, exit codes, stdout/stderr and per-run SHA256SUMS
are in each stage's COMMANDS.json and its sibling files. The final P5 packet
includes the complete targeted architecture/S/C regression command and actual
full pipeline execution. Independent decisions and raw probes are under
independent/p2, independent/p3 and independent/p4; P5's separate independent
decision is published with its evidence under independent/p5.

The final targeted run passed731tests and1579subtests. The subsequent clean-CI
setup repair3863f115713a6cb7001086e0702197605812fcf4 changes only test
dependencies and full-history checkout. All accepted reader bytes remain the
same. Fresh isolated and hosted full offline suites ran2284tests:2275passed,
9optional skips, zero failures/errors. Hostedpush44638386925 andPR44638398365
both succeeded. See ci_dependency_repair/REPRODUCE.md and independent/ci for
preserved original failures, exact installation/test commands and review.

The branch started from PR187 head33842b96093a453e5bdeb49dacc64986e27d5b37.
verification/ contains fresh main/PR161/173/175/176/187 heads and an empty source
handoff diff against its accepted implementation644f8f51. Accepted G0
59d28dc23be97de2a6a82d22be8338151e31f5b6 remains an ancestor; no main or
documentation publication was substituted for different accepted P1 code bytes.

## Offline deterministic replay

Use Python with numpy, scipy, jsonschema and pytest installed. Exact final test
environment versions are recorded in verification/environment.json. Check out
the implementation commit above to reproduce that version's exact CLI/code pins.
Use an absent output directory: the runner refuses overwrites.

```bash
python scripts/nba_subset_pipeline.py \
  --capture docs/nba_architecture/p1_subset_acceptance_20261119/initial_tonight_capture \
  --cohort docs/nba_architecture/p1_p5_handoffs_20261119/PROSPECTIVE_COHORT.json \
  --history docs/nba_architecture/p1_p5_handoffs_20261119/prospective_inputs \
  --forecast-at 2026-11-19T22:56:37.519571+00:00 \
  --through p5 \
  --output /tmp/nba-subset-handoff-replay-20261119
```

This is explicitly RECORDED_CLOCK_REPLAY, not a newly issued historical forecast.
The original committed native run at that actual clock remains in p3/actual_native.
The final full pipeline under p5/actual_full_pipeline instead records its own
actual pregame execution clock. Both preserve the same frozen source inputs.
Their native forecast IDs and P5 record IDs differ when the execution clock
differs. Receipt operation_completed_at/executed_at clocks are actual operations,
not fabricated provider publication or original historical pregame availability.

```bash
python -m pytest -v tests/nba_architecture tests/nba_s_family tests/nba_c
```

To exercise only the P1/P2 source/abstention boundary, supply the same capture,
cohort and an absent output directory with --through p2; no history is required.
Beyond P2 the runner requires --history and rejects another unreviewed cohort.

## Populations and expected records

The additional prospective cohort is GS at MEM, ESPN401910019, November19 at
8pm Toronto. PROSPECTIVE_COHORT.json freezes all36candidate identities and the
actual22:47:40.810486UTC input cutoff. Prior captures contain15completedgames
perteam/29uniquegames. Source-only tonight confirmation remains a separate
scheduled exercise with its original23:15UTC freeze; it is not replaced.

* P1:36candidates,25source-ready,11sourceabstentions; eligibility/q unknown.
* P2:144player/stat attempts,100missing-S-artifact and44sourceabstentions.
* P3:108player/model attempts,36native minute laws for12players,72abstentions.
  All540prior-game observations remain:368PLAYED,43explicitDNP,
  3PLAYED_ZERO_DISPLAY and126UNKNOWN. A displayedzero is not exactplayedzero.
* P4:432player/model/stat attempts,36native laws consumed and144statreferences;
  zero statistics forecasts. All432abstentions remain:132source,156history,
  144missingS-kernel. There is no joint-model execution.
* P5:684P2/P3/P4attempt records archived,36conditional-minute forecast records
  and648abstention records. All36P1candidates and540prior observations remain
  attached. Archive read reconstructs inputs from archived copies, checks reader
  bytes against the executing version and replays all source/model boundaries.

## Byte domains and trust limits

HTTP body.raw files preserve exact response body bytes; each original receipt
contains status, URL, byte count, SHA256 and actual retrieval/ingestion clocks.
Source publication and complete corrections remain unknown. Current capture of
a prior result is not original historical pregame availability. Native ESPN
identities are not a legal eligible-roster or NBA-identity crosswalk claim.

The native model raw file SHA is ea7eae3afc760eafda0fbf0dbdccd2cb77b31b0aca54fc3606b4b31ba90693de.
The native executing minutes reader SHA is6dfb65b783f881de37e3779f3eb40433e1a1c99db103b0b3fef49e30092a5b30.
Native forecast provenance also contains a canonical-JSON model hash and declared
historical training metadata; those are distinct domains, not new authentication
of the training archives. No training/holdout archives were decompressed/scored.

P1/P2/P3/P4 output wires use canonical compact JSON bytes. P5's manifest record ID
hashes canonical compact JSON plus a terminal LF. Each referenced byte object
has its exact raw hash, size and domain. The final CLI's recursive SHA256SUMS
covers outputs, receipt, P5 manifest and every archive object/record file.

P2 lacks a reviewed saved native S artifact and source-bound role/exposure
numerical dispatch. P4 additionally lacks a compatible admitted subset-joint law,
primitive attempt/conversion inputs and numerical dispatch. P5 archives these
missing mechanisms; it does not make the outputs scoring/settlement ready. No
full-roster prerequisite is reintroduced for supported per-player research.

Historical G0/PR173/175/176 reds, original n32 coupling-budget red, P2/P5
accounting repairs, original forecasts/models/posteriors and correction ancestry
remain unchanged. P2 duplicate-key and P3 DNP-credit reds, preliminary unaccepted
P3 output and failed initial command are retained. The old synthetic-only real
admission gates stay closed. There was no fit, NUTS restart, schedule change,
merge, deployment or Tier promotion.
