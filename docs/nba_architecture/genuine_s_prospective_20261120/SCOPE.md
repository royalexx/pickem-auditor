# New prospective genuine S1 baseline: pre-fit source/model contract

Authority PA-V25-MASTER-2026-11-09/v1.1 plus November19 source_listed_subset and
new explicit instruction to add what is missing for genuine S statistics.
This is a new cheap prospective S1 artifact, not historical replacement fitting.
No old forecasts/fits/readers are changed, no holdout scoring/decompression,
weight optimization, NUTS, schedule change, merge, deployment or Tier promotion.
Independent source/fit approval and later artifact admission are separate gates.

## Explicit additional cohort, frozen before implementation/fitting

PREFIT_POPULATION.json freezes exact identities and source bytes. Target
ESPN401910026 MEM@MIN, 2026-11-22T01:00UTC (November21 at8pmToronto),35current
source-listed candidates,27source-ready and8source abstentions. The previous
36-player GS@MEM cohort and its forecasts remain unchanged; no replacement or
backdated freeze. Planned forecast window2026-11-20T01:30..04:00UTC, horizon
47.5..45hours before event. Actual clock/horizon will be recorded, never filled
with a planned timestamp. Availability/roster changes before that future target
remain uncertain; legal eligibility and participation probabilities stay null.

Training source population: ten most recent completed games listed by each
fresh captured MEM/MIN ESPN schedule,20uniquegames. All20official NBA box pages
matched by source ETdate/home-awayteam names and captured Box Score link. Frozen
source data cutoff2026-11-20T01:07:00.131517UTC, after all captures completed.
The target and any uncompleted intervening games cannot enter training. Current
capture of old results is not original historical pregame availability. Future
intervening games remain unobserved, not imputed DNP or actual rest.

Raw official rows:532players plus166separatelylistedinactive identities.
Inspection found458printed exposures>=30seconds,68explicitDNP comments,
1sub30second exposure and5unknown exposures. Actual usable counts may decrease
only through declared validation/identity/role rejections, with every source row
retained. No outcome-based exclusion, tuning or source substitution is permitted.

## Source capabilities and exact measurements

Official www.nba.com/game/.../box-score HTTP200 raw HTML, exactly one
__NEXT_DATA__ payload: gameId/gameCode/gameStatus3/period/gameClock,
home/awaynativeIDs, full player records and integer count statistics. Require
final clock zero and complete matching source period arrays. Playing duration
is48+5*(period-4), consistent with NBA regulation/OT timing; never use wall-clock
'duration', player-minutes sums or faulty starters/bench aggregates to invent it.
Individual reported mm:ss is parsed to exact integer source seconds; native
minutes is seconds/60 using a documented float conversion, with original seconds
and rational retained. Source precision is reported seconds, not subsecond truth.
Printed zero,0<seconds<30,DNP,missing/unparsed exposure and unsupported accounting
are retained/excluded from fitting with distinct reasons. DNP requires explicit
comment; blank minute text alone remains unknown. Faulty bench/start aggregates
are quarantined, not substituted for individual exposure or complete roster.

Validate nonnegative integer statistics and PTS=2*FGM+3PM+FTM,
REB=OREB+DREB,3PM<=3PA<=FGA,FGM<=FGA,FTM<=FTA. Compare full official/ESPN count
vectors on an exact game/home-awayteam join and unique frozen NFKD/name_key name
normalization. No fuzzy matching or invented aliases. Inconsistent/unmatched/
ambiguous rows abstain and remain counted. Crosswalk applies only to the listed
completed-game rows; it does not establish later legal roster or universal ID
mapping. Preserve both provider IDs, source-declared clocks and any discrepancies.

Roles are ESPN_POSITION_BIN_OBSERVED_AT_CAPTURE, not authenticated historical
on-court/starter roles. Only frozen PG/SG/G->G,SF/PF/F->F,C->C provider enum bins
are supported; ambiguous/missing positions remain excluded/unresolved. The same
explicit reported-position-bin rule maps current roster metadata for dispatch.
Native S1 uses all target-player histories across roles/teams and only OTHER
players with the target role for its pooled prior; dated memberships are retained.

Every raw capture keeps body and receipt bytes, URL/status/actual retrieval and
ingestion clocks. Publication/original historical availability/correction-history
completeness stay unknown. The new capability is bounded to this frozen source
population. Neither the old PDF root nor a caller hash/approval flag grants new
admission. The CDN403 and initial collector schema failure are preserved reds;
source discovery matched names from captured summary boxes after the schedule's
missing name field, with no guessed identity.

## Predeclared model and actual time chain

Existing native S1 model, four primitive stats points/rebounds/assists/threes,
fixed prior_minutes180,prior_attempts40,dispersion12,min_player_games2,
seed20261120. No parameter search, score comparison, optimized weights, model
selection or quality acceptance. Reconstruct every fit row deterministically
from the independently admitted source reader; no caller-authored training rows.
Create one immutable artifact per statistic through native.fit only after the
independent pre-fit PASS. Model/data/source/reader bytes and actual fit receipt
must then receive separate independent real-artifact admission before registry
entry and genuine dispatch. The old empty registry stays unchanged.

Required clocks: max(source_ingested)<=data_cutoff<=fit_started<=fit_completed
<=artifact_observed<=new_input_freeze<=forecast<event_start. Record actual calls,
never infer observation from mtime or label. Forecast freeze is deliberately
assigned after fitting/admission in a new versioned cohort/receipt. Training
cutoff equals the frozen data cutoff; no new late source enters afterward.

## Forecast and archive contract

New versioned exact-source M0 reuse reads the same saved WS2 artifact/reader,
source last-ten ordinary played observations (at least5), strict missing/unknown
intervening completed-game controls and explicit-DNP-only return gap. All13
features are derived from observed history; rest/team-gap fields are labeled
observed-history/calendar proxies. Scheduled but uncompleted intervening games
are explicitly flagged unknown. No participation or team allocation is supplied.

S law is conditional on participation AND fixed M0 projected ordinary exposure.
No integration over minute uncertainty, full joint law, roster normalization,
scoring, predictive accuracy or full G1 acceptance. All35players x4statistics=
140attempts remain, including source/history/role/model/numerical abstentions.
The source parser/fit ledger retains all532player+166inactive source records
and every stat attempt. Bound raw inputs, extraction/fit code, artifacts,
clock receipts, role contract, native API output and append-only archive.

Publish exact implementation/testedSHAs, raw commands/stdout/stderr, input/output
byte-domain hashes, completeness ledgers, public positive/negative/mutation tests,
REPRODUCE/SHA256SUMS and separate reviewer decisions. Old20accepted readers,
models, forecasts, rejected receipts and correction ancestry remain unchanged.
