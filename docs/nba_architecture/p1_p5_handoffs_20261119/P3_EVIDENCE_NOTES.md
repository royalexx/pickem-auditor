Implementation and tested commit: 67094fbf57dcb4e483f1a55a3a9031e08608b2dd.
Actual new forecast clock: 2026-11-19T22:56:37.519571 UTC, before the 01:00 UTC
target, after the separately frozen 22:47:40.810486 UTC inputs.

Actual source population: 36 frozen candidates, 25 source-ready and 11 source
abstentions. All 540 candidate/prior-team-game observations remain classified.
There are 108 candidate/model attempts: 36 played-conditional minute laws for
12 players across M0/M1/M2; 33 source abstentions, 33 unknown-history-window
abstentions, and six unknown-return-gap abstentions. All 36 laws retain unknown
participation and eligibility, with no team allocation or statistic forecasts.

p3_initial_native_probe.json is preserved, UNACCEPTED preliminary execution.
It produced 69 laws under uncommitted code before the independent reviewer found
that unknown intervening appearances could be skipped. Its raw implementation
hash is retained in that output; no exact committed SHA exists for that initial
probe. Do not use it as accepted forecast evidence. The committed implementation
rejects those uncertain windows locally and the actual committed run emits 36.

The first test command incorrectly named a nonexistent original test file. Its
exit code 4, stdout and stderr remain in p3/0.*. The corrected command is in
p3_verified_tests: 25 tests and 22 subtests passed at the exact implementation
commit. There was no source or model fitting, holdout scoring or decompression.

Raw source byte domains and clocks are original HTTP body/receipt files. The
model raw bytes hash and runtime reader code hash are pinned in P3_CONTRACT.md.
Native output provenance additionally contains the model's own canonical-JSON
artifact hash and declared historical training metadata; those are different
domains and do not replace the raw model hash or establish training-source
authenticity. Output files are canonical JSON; per-directory SHA256SUMS cover
their exact bytes. Retain the earlier red and failed command receipts unchanged.
