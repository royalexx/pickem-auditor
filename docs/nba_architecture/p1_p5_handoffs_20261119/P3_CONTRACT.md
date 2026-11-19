# Reviewed bounded native minutes reuse contract

This profile was independently reviewed before reader implementation. It extends
only the default subset research interface. Original full-roster, source-native
and synthetic-only adapters retain their contracts. Authority remains
PA-V25-MASTER-2026-11-09/v1.1 plus the November 19 user amendment.

The frozen target is PROSPECTIVE_COHORT.json: GS at MEM, ESPN 401910019,
November 19 at 8pm Toronto, all 36 preselected candidate IDs. Freeze is the actual
recorded November 19 22:47:40.810486 UTC, after all history captures. Forecast time
is recorded at actual inference, before the target. This additional research run
does not alter tonight's pinned source-only confirmation or retrospectively mint
November 18 forecasts.

The exact cohort canonical-JSON SHA256 is
0ecd8c98ea97bb8be852807c5935d8427adb2b9d9ca062d823da86279f57357f.
The adapter refuses another cohort or caller-amended scope; another target needs
a separate reviewed reuse decision. Hashes enforce the reviewed contract; a
caller-provided hash or flag cannot register a different profile.

Only the exact saved WS2 model raw SHA256
ea7eae3afc760eafda0fbf0dbdccd2cb77b31b0aca54fc3606b4b31ba90693de
and native reader raw SHA256
6dfb65b783f881de37e3779f3eb40433e1a1c99db103b0b3fef49e30092a5b30
are permitted. A caller-supplied hash, approval, reviewer name or model name
cannot register another artifact. These pins implement an independently reviewed
bounded exploratory reuse decision, not general fitted-model admission. Original
declared code commit, cutoff and training-manifest metadata stay separate from
the actual executing reader hash. Historical training-source authenticity and
the inferred-overtime calibration limitations remain unverified; no new fit,
holdout replay, performance acceptance or promotion is authorized.

Sources are the original P1 raw roster/scoreboard plus current captures of both
team schedules and every listed completed current-season game before the target.
Each HTTP body is joined to its original receipt and actual retrieval/ingestion
clocks, exact endpoint, game, teams, player and declared status. Receipt/HTTP Date
is not a source publication timestamp. Unsupported publication, complete
correction history and orphan correction claims reject. Rejected populations
remain in the denominator. This is research byte/identity/clock consistency, not
a new general source-authenticity root.

For each candidate, retain one observation classification per selected team game:
PLAYED with positive displayed integer minutes, explicit DNP, PLAYED_ZERO_DISPLAY
or UNKNOWN. Missing rows never become DNP. The model feature window consists of
at most ten positive played appearances on strictly earlier UTC calendar dates,
with at least five required. Every team game from the earliest selected positive
appearance through freeze must classify as explicit PLAYED or DNP; missing and
displayed-zero observations within that interval cause local abstention. Native
causal_features derives all 13 fields. Rest
and back-to-back are UTC calendar-date proxies, not hour-precise rest. Return gap
counts only explicit DNP observations after the latest positive appearance;
unknown, missing and displayed-zero observations in that interval cause local
abstention. Position comes from the bound current roster. Team change compares
current team to the last observed appearance within CURRENT_TEAM_OBSERVED_WINDOW;
other-team history and complete career membership remain unknown.

Invoke MinutesModel.forecast for M0, M1 and M2, with participation and legal
eligibility null. Genuine positive results are marginal minutes conditional on
participation, UNCERTIFIED/SHADOW. M0 remains the benchmark; M1/M2 are exploratory
comparators. No partial-roster team allocation, statistic probabilities, joint
law, unconditional forecast or predictive-accuracy claim follows. Each of 36
candidates has three retained attempts: 108 total, including every source/model/
history rejection. Preserve input/output hashes and original metadata unchanged.
