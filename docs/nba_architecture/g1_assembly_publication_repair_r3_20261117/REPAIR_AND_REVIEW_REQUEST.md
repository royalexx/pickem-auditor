# Independent P6 publication red — owner repair r3

Independent reviewer PR #172 at `b477df63f1e996c8a6ef7c7fd2083ac493909abd` correctly rejected the pre-QC assembly publication assertion. The orchestrator's assembler copied four tracked P2 reports but used `git add -A` from a base that ignores `reports/`. The local files existed; the published Git tree did not contain them. The independent red report, original d46 assembly and original source map remain immutable.

The exact repair is `7145c9dd734d00b5b4a451cfc1f730cd4967762d`: stage only explicitly mapped owner paths with force, then verify every committed owner path/blob/mode and the full changed-file population. No untracked scratch file is force-added. The permanent publication regression was committed first at `7e46f5fb06213e319f72942e1e38981fde54e9ae`; old d46 still returns exit2 for exactly the four missing paths.

Corrected published assembly: **`6dee6e09fa786479dc2e163a33e14257f207b35e`**, branch `qa/nba-g1-exact-owner-assembly-v4-r3-20261116`. The full committed-tree check passes all **653** promised files and **24** inherited G0 objects/modes. Compared with d46, its only changes are the four reports and generated map metadata. Every P1-P5 executable, fixture, fitted artifact and input is unchanged.

A separate fresh Git checkout of r3 passed all 17 affected checks: root discovery/canonical IDs, **513 architecture**, **61 S**, **76 C**, ten inspected offline suites (**56 methods**), compilation and two Bash syntax checks. Tracked source remained unchanged. Runnable commands, raw logs, before/after source-map results, Git comparison, source hashes and the 36-criterion pending-review ledger accompany this receipt.

This is owner QC, not independent acceptance. The new independent reviewer must re-fetch r3 and issue a separate rereview. The eight source/fitted-prior/material-law/coupling blockers remain unchanged; no family or overall G1 PASS is awarded here. No G2, historical fitting/validation, historical weights, NUTS, deployment, schedule/Tier changes or merge occurred.

The earlier pre-QC publication manifest belongs to exact snapshot `70d37e9b2a6bbf26def4bee79161a7bd3a49d343`. Its listed assembler script legitimately changes in this repair. Historical receipt verification must use the corresponding Git blob versions. The repair has a new separate checksum manifest; no old report or receipt was rewritten.
