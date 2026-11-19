The independent review of b415e8bf found a contradictory native DNP row could
carry MIN=0 and positive points while being classified DNP. The original public
red is preserved in independent/p3/dnp-credit-red.*. Final implementation
05b44764 keeps any nonempty credited DNP array UNKNOWN with original credits and
a reason. Only the affected player's uncertain feature window abstains; other
supported players continue.

The same repair freezes the exact 15 prior game IDs/dates per team already
selected in the original captured schedules. A missing completed game rejects
coverage rather than reducing the population. Invalid or missing source evidence
retains all required candidate/game observations as UNKNOWN with the source
rejection attached. Candidate/model attempts remain 108 and observations remain
540 even on those negative paths. This does not claim complete career history,
eligible roster completeness or genuine DNP labels for missing rows.

Final clean-source results remain 36 native conditional-minute outputs for 12
players and 72 explicit abstentions. The exact final implementation's 26 tests
and 24 subtests passed in p3_accounting_repair, with raw commands, stdout/stderr,
recorded-clock source/model replay and SHA256SUMS. Earlier outputs and defects
remain unchanged; the new implementation hash identifies the repaired reader.
