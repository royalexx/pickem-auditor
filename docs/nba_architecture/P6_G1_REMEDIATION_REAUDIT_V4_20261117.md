# Independent P6 G1 remediation review v4 — NO-GO

Authority: **PA-V25-MASTER-2026-11-09 / v1.1**. Accepted G0 remains
`59d28dc23be97de2a6a82d22be8338151e31f5b6` only. Reviewer:
`/root/p6_independent`, a separate ChatGPT agent that authored no P1–P5 or
P0 implementation repair. This is an independent finite engineering/source
review, not historical predictive validation or release authorization.

The final ledger has **36 criteria: 28 finite PASS, zero FAIL, eight BLOCKED**.
The P2 conditional cutoff and P5 recursive outcome defects are repaired and
independently verified. The review found one additional publication defect,
returned it to the responsible owner, preserved a separate NO-GO, and verified
the new exact repair. Missing authentic evidence and unaccepted material
distribution/physical-model contracts still prohibit G1 acceptance.

The complete per-criterion source SHA, command, observed result, classification,
owner, controls, dependencies, minimum prerequisite and independent disposition
are in [the 36-row ledger](p6_independent_v4_20261117/final_v2/criterion_ledger.json).

## Exact submissions and independent execution

All PR heads were freshly fetched through GitHub and Git before testing and
checked again after execution. No P1–P5/P0 head drift was observed.

| Owner | Draft PR | Exact tested head |
|---|---:|---|
| P1 | [167](https://github.com/royalexx/pickem-auditor/pull/167) | `50d2b3874c7c14c9b73bdf13e441957986b88acd` |
| P2 | [165](https://github.com/royalexx/pickem-auditor/pull/165) | `fe46965394ea0f48ef5e9da501ec8ca9e441ce47` |
| P3 | [166](https://github.com/royalexx/pickem-auditor/pull/166) | `eb0882b5011f2004c5eaf27cccfdc6297704f261` |
| P4 | [164](https://github.com/royalexx/pickem-auditor/pull/164) | `865bdb8f4770ac28262e49c3b4901cf1d72a22fb` |
| P5 | [163](https://github.com/royalexx/pickem-auditor/pull/163) | `cb3ff8279bc7f4cc7b86a519a1e386ddbe37ae93` |
| P0 discovery | [171](https://github.com/royalexx/pickem-auditor/pull/171) | `c14b5584c30f8fbca3eb2e51acfaea24c40eff29` |

The recorded original audit pins differ from these submitted heads. The old
audit at `ddc60a83f6c9a2b863f5e7a44823bffa3b01e048`, its original reports,
fixtures, before/after evidence, criterion ledger and checksums remain intact.
Its complete 32-command expected execution was independently reproduced,
including the historical P2/P5 red exits and their exact counterexample names.

The frozen pre-P6 packet is `70d37e9b2a6bbf26def4bee79161a7bd3a49d343`.
Its manifest raw SHA256
`f29ac4a6e39162bd55d5acc0fbf536579da98b3510023e1a0b06c156eb7a0b71`
was verified against that historical source population. The owner repair
packet is `4d4d594fd7c88cdb3149cafd35515d5a65412b87`; all 27 entries in
its separate manifest were independently checked, raw SHA256
`cff5ad5d2df55f6e38aa88fcad1aba58b0f220a9d26d7956819e4c331438fafd`.

The final assembly is **`6dee6e09fa786479dc2e163a33e14257f207b35e`**.
Independent fresh Git checkout checks bind all **653 mapped owner files** to
their actual committed blobs, raw SHA256 and Git modes, compare the complete
changed-tree population, and preserve all **24 inherited accepted-G0 files**.
The source map raw SHA256 is
`f631042403a81bd9e987e72b1ab07e64f0d7eccb0f51c0ab9bc821215e22d94a`.
No replacement owner model was used. Production consensus, pause markers and
workflow paths have zero owner diff against accepted G0.

Final independent executable QA source is
**`c51c6f08f9009274258062cc5f3425e1f1567893`**. New test-source hashes and
execution provenance are retained separately from documentation successors.
The inherited runner's `qa_code_commit` records the `--repo` object database
HEAD, so it is not used to identify the independent review checkout; its raw
runner hash and the explicit QA-source receipt identify the executable bytes.

## Independent results

Fresh exact-owner execution passes all **24 commands**: P1/P2/P3/P4/P5
architecture suites **377/267/319/351/267**, five separate 83-control P6 runs,
P1 preflight 9, S-family 61, C-family 76, original immutable negative probes,
separate green repairs and the original v3 adversarial programs. Dedicated
tests overlap; these are execution counts, not independent observations.
The original upstream WS1/WS2/WS4/WS5 suites pass **25/25/33/63** at their
original exact pins, totaling 146 controls.

The original root discovery defect independently reproduces **1,652 test
objects and ten import errors** at original P2 `7ca4269...`, with `PYTHONPATH`
unset. At final assembly 6dee the clean root ID/import/duplicate regression
passes, as do **513 architecture, 61 S and 76 C tests**, ten inspected offline
suites with **56 methods**, compilation and two Bash syntax checks: all 17
affected commands pass. Unrelated root test bodies were not executed. This
is not a claim that repository-wide CI is green. The offline history bootstrap
test restores only its newly generated synthetic temporary archive; no
historical/holdout warehouse shard was decompressed.

The reviewer added and executed eleven new QA sections. They independently
check:

- 1,200 bounded primitive-event feasibility cases against complete independent
  enumeration: 660 feasible and 540 infeasible cases agree across P1, P2 and
  C. Huge integers preserve P1/C exactness; P2's numerical range remains
  explicitly unresolved rather than falsely accepted or physically rejected.
- 350 sparse full-count CRPS/NLPD/PIT/zero/tail/predictive-mean references;
  90 independent multivariate Energy/Variogram Score references; maximum CRPS
  error `2.8422e-14`, maximum Variogram error `1.4211e-14`.
- Twelve synthetic W2/W3 optimization problems against independent active-face
  KKT solutions built directly from full CDFs. Shared player/stat rows count
  as one game, and W3 sparse fallback uses game counts.
- 32 paired cutoff controls over all four primitive stats and S1/S2. Equality
  is legal; one microsecond late and after-declared/before-freeze models reject
  consistently through both public and conditional interfaces.
- 92 new nested outcome/clock/identity attacks and 88 valid pregame controls
  through mixed dictionaries, lists and tuples to depth ten. Source/identity
  aliases, post-freeze clocks and forbidden outcome namespaces reject while
  legitimate projected numerical inputs remain usable.
- False participation authentication, sampled-frequency certificates,
  wrong team/raw hashes, typed-denominator attacks and post-freeze source
  assertions. Unknown participation remains null; source-blocked P3 does
  not begin sampling.
- Actual latest P2/P3/P4 integration, all 96 normalized primitive/combo PMFs,
  same-draw PR/PA/RA/PRA, weighted ESS including a new nonuniform G/O/J case,
  preserved real-mode quarantine, positive O2 n=4/n=8 and the n=32 budget stop.
- Fresh-process replay with `PYTHONHASHSEED=1` and `777773`, reversing artifact,
  source and role dictionary order. Exact bundle/scenario hashes agree.
- Complete owner source-tree, raw/source/artifact inventories, correction and
  immutability controls, P1 available/missing population and 403 response bytes,
  and the append-only P3 documentation receipt.

The retained original and current suites additionally attack corrupt source and
ancestor bytes, orphan/backdated corrections, wrong identities, post-cutoff
training rows, impossible minute laws, missing/insufficient five-on-floor
witnesses, resealed replay tampering, mismatched G/O/S/J weights and IDs,
shooting/rebound/assist violations, incorrect same-draw combinations,
nonnormalized laws, tail claims and fabricated date labels. These were rerun
against the exact submitted owner heads. No historical predictive scoring or
fitting was used for any numerical test.

## A new independent red was repaired and separately re-reviewed

First submission `d46f5322b47367ba601b05197cef8404758da23d` claimed four P2
report files in its source map but omitted them from the committed tree.
Ignored `reports/` paths were copied into a worktree and omitted by `git add -A`.
The independent permanent check, exact failed input/output and NO-GO were
published at QA `b477df63f1e996c8a6ef7c7fd2083ac493909abd` and remain in
[red_v1](p6_independent_v4_20261117/red_v1/INDEPENDENT_REVIEW_V1_RED.md).

Root/P0 repaired the assembler at
`7145c9dd734d00b5b4a451cfc1f730cd4967762d`: force-stage only the explicit
mapped owner population and verify every actual committed blob/mode afterward.
The owner then published r3 and completed affected pre-P6 checks before final
independent review. Independent r3 verification is green; the only differences
from d46 are those four report additions and source-map metadata. Criterion
**F-P0-ASSEMBLY-01 PASS**. The failed d46 report is not rewritten as a pass.

QA setup failures are also retained separately, with the defective QA source,
failed outputs and explanations: a keyword-only call, an invalid output-freeze
input, an overstrong mathematical tolerance, a masking `PYTHONPATH`, and a
private draft ledger-schema assumption. Corrections changed QA only and have
valid green executions. None is attributed to a P1–P5 repair.

## The authentic case stops before G

The actual strict P1 builder returns `OFFICIAL_SOURCE_EVIDENCE_REQUIRED` for
**26 attempted entries**, writes no snapshot, and stops before shared G, P3,
P2, P4 or C. Synthetic compatibility cases were executed separately.

The independently rehashed **99 compressed shards / 39,916,715 bytes** prove
opaque archive integrity only. They do not establish original HTTP-byte
captures, first availability, complete rosters, DNP/played-zero/unknown
denominators or correction completeness. No shard was decompressed or scored.
The retained ESPN box/schedule retrievals and modern official rule document
are unadmitted later sources; original availability remains null. The retained
official prior-game NBA `0021800001` request is a 443-byte HTTP403 response.
Its exact response bytes and retrieval clocks are consistent; it supplies no
duration or minute-exception evidence.

P1 must obtain independently admissible original roster/availability evidence,
dated player/team/game/trade mappings, a complete official schedule/result and
participation population, official duration/OT/correction chains and authentic
minute-display exceptions. P2/P3 require admissible existing fitted priors and
lawful cutoffs bound to those sources. Missing fields remain unknown. Target
boxscores, final rosters, actual minutes, outcomes, asserted timestamps,
matching hashes and synthetic fixtures cannot supply these prerequisites.

## P4 proposals are not accepted for G1

Actual latest P2 Gamma mixing uncertainty now reaches the actual P3-bound
constrained J kernel. This is a verified engineering improvement. It does not
preserve the original P2 marginal distributions or authenticate participation.
All 48 actual public unconditional P2 calls abstain. The fixed-O played-
conditional reference agrees with public played-conditional PMFs to maximum
error `3.7402e-12`; sampled PLAYED states do not establish genuine q=1.

The reviewer independently reran all **256 predetermined J seeds × the same
four actual O2 scenarios**. All **1,024 weighted paths** were retained, no O
draw was resampled and no scenario discarded. The study includes **zero
observed games**, 12,288 rate-pair attempts, zero rate rejections, and 1,037
event attempts with 13 retained tied-draw rejections. Independent raw pooling
reconstructs all 96 complete normalized PMFs and reproduces semantic SHA256
`5de46126c5158d061d9f327f3e78c1faa123970ccf1a7fba80cb61cbed28b262`.
Raw compressed and uncompressed hashes are separately recorded because raw
outputs retain measured runtimes.

Independent analytical comparison reproduces maximum absolute mean distortion
**11.3679975911** and maximum empirical TV **0.4767262428**. Synthetic player
21 PTS has reference mean 28.00504928 and J mean 39.373046875, clustered
Monte Carlo SE 0.3032011. These are engineering discrepancies and Monte Carlo
uncertainty, not game-level validation or a certified approximation budget.

A new 70-digit reference proves exact physical marginal preservation is
infeasible for an actual source kernel: player 15, scenario 0 has
`Pr(3PM >= 20) = 4.7690783256717101e-10`, exceeding
`Pr(PTS >= 60) = 2.7588729050486701e-10` by `2.01020542062304e-10`.
Any coherent law with PTS ≥ 3×3PM requires the reverse inequality. The gap
also exceeds the combined finite-serialization tail bounds by about 48×.
This establishes a need for an explicit constrained-law contract; it does not
approve the proposed approximation or its much larger observed distortion.

**`NBA-J-CONSTRAINED-LATENT-RATE/0.1.0-PROPOSAL` is not accepted for G1.**
An independently reviewed material contract must establish admissible distortion
and tail limits and possession/FT/event-time/co-presence/scorer-linked assist,
rebound opportunity, possession-unit, OT path, early-exit clock and genuine
participation semantics. Aggregate accounting, normalized PMFs and honest
disclosure do not prove those requirements. Accepted G0 is not amended here.

The actual O2 n=32 case still fails `O_COUPLING_VERIFICATION_BUDGET` under
unchanged G0. The positive n=4/n=8 cases do not establish a generally valid
bounded operating range or scalable full-law coupling/max-q verifier. That
proposal is also not accepted as closing B-P4-03. No budget increase, scenario
discard or O0 substitution was used. These are material proof/contract
prerequisites, not an authorization to weaken the accepted validator.

## Final independent recommendations

| Family | Recommendation | Minimum remaining prerequisite |
|---|---|---|
| P1 | **BLOCKED** | Independently admissible source populations, clocks, membership, duration/OT/corrections and minute exceptions. |
| P2 | **BLOCKED** | Authentic P1 contract/evidence and admissible existing fitted artifacts; cutoff/software repairs pass. |
| P3 | **BLOCKED** | Original roster/context, dated membership and genuine participation/minute-prior authentication. |
| P4 | **BLOCKED** | Authentic admission plus independently accepted constrained physical-law and coupling/scaling proof contracts. |
| P5 | **BLOCKED** | Accepted native forecast/source/fit/J inputs and separate authentic outcome/end/release/correction evidence; recursive software repairs pass. |
| P6 | **PASS — finite independent QA** | This review and immutable evidence support the NO-GO decision; no predictive or release acceptance is granted. |

**Formal overall G1 decision: NO-GO.** No repairable implementation/publication
defect found in this review remains knowingly deferred. The eight substantive
criteria remain BLOCKED with exact responsible owners and prerequisites in
the ledger. G2, historical predictive training/validation, historical family
weight fitting, NUTS restart, merge, deployment, schedule changes and Tier
promotion remain closed and were not performed.

Reproduction commands and hash-domain notes are in
[REPRODUCE.md](p6_independent_v4_20261117/REPRODUCE.md). This independent draft
QA is [PR #172](https://github.com/royalexx/pickem-auditor/pull/172); the root
orchestrator owns the append-only coordinated issue #160 update.
