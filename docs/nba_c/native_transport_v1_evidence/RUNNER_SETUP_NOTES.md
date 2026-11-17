# Preserved native runner setup attempts

The first shell invocation could not redirect stdout because the local `work/`
directory did not exist. Python was not started. After creating that directory,
attempts 2–5 failed while materializing the dependency subset: missing inherited
WS2 allocator, P1 fixture helper, P3 golden fixture and P3 bridge respectively.
Each original traceback is retained with its own raw bytes. These are QA runner
dependency defects; they did not establish an implementation pass or failure.
The runner was corrected to export every actual pinned dependency. Attempt 6
executed all eight then-defined actual P1/P2/P3 cases successfully; attempt 7
executed nineteen cases including the actual latest P4 consumer. These are
intermediate synthetic engineering results, not final-head or G1 acceptance.

P1/P2/P3/P4 source modules and fixture bytes were always extracted from explicit
Git commit objects. No historical outcome population was extracted. The C
implementation was still a working candidate at these intermediate attempts;
final exact-head execution is recorded separately. `missing_outcome()` in the
new transport unit test initially omitted P1's existing
`INDEPENDENT_SOURCE_ADMISSION` missing-prerequisite entry. The later stricter
consumer exposed that QA fixture omission; it was corrected to match actual
P1 output, with the earlier test source preserved in commit 3937a1d.
