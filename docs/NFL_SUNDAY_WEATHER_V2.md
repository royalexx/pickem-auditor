# WS1 Sunday weather interchange v2

Governing contract: PA-V25-MASTER-2026-11-09 / v1.1, Phase 0R source
capture; November 8 research baseline rules 3, 7 and 15. Research only.

WS1 owns all shared weather collection. WS2–WS6 consume the same immutable
`reports/nfl_20261115_prospective/weather_v2/revision_2/WEATHER_FEATURE_PIN.json`.
The first `weather_v2/WEATHER_FEATURE_PIN.json` remains archived unchanged.
Revision 2 supplements stadium evidence and corrects the possibility of
mistaking retractable doors for evidence of a retractable roof. It preserves
all meteorological bytes and source timestamps; changed events retain their
prior freeze and record a new pregame freeze for the additional evidence.
Canonical original source manifest remains
`5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71`.
The sportsbook handoff, original contracts, historical pin and forecasts are
unchanged. Never call this producer from a model adapter.

## Versioned migration from WS3 v1

Schema `ws1-nfl-pregame-weather-v2` deliberately does not masquerade as the
proposed WS3 v1. That adapter rejects unknown fields, missing numeric fields
and valid times other than exact kickoff. An NWS grid value represents a
valid interval, often several hours long. Relabeling its start to kickoff
would destroy provenance. V2 retains native intervals and separately records
`target_minus_kickoff_seconds` per field. Interval start is inclusive and end
exclusive. No interpolation or observations are used.

Use `scripts.nfl_sunday_weather.load_weather_v2(path, expected_sha256, now_at)`
from the project root. It verifies dependency/table/raw hashes, source timing
and native-field replay, then returns eligible records keyed by the exact
original ESPN game ID. Rows already underway are excluded from that return;
the full pin retains their exclusion denominator. WS3's v1 loader remains
unchanged. WS3, WS4 and WS6 must explicitly adopt this v2 adapter; until then
they retain their existing weather-neutral behavior. This source packet
does not estimate any weather-response coefficient or authorize a forecast
rewrite. Missing weather is never a model-wide failure.

## Fields and semantics

The pin binds its canonical WS1 manifest, original feature pin, event table
and schedule bytes through `dependencies`. `events.jsonl` contains identical
event records and is separately hashed. `SHA256SUMS.json` inventories the
weather archive. Each successful request has original response bytes, exact
URL, retrieval time, HTTP headers and SHA-256. Failures retain their reason
and, for HTTP errors, original error response bytes. Reruns reuse receipts;
all writes reject conflicting bytes. Existing artifacts are never overwritten.

Each event records kickoff, stadium evidence, coordinates and their original
geocoder result, proposed and verified stadium type, roof evidence excerpts,
game-specific status evidence, exposure classification, per-event freeze,
native values, normalized values, missingness and uncertainty. Original
venue comes from the already frozen schedule. OpenStreetMap supplies
coordinate lineage; NWS points binds that location to its forecast grid.
Venue evidence is distinct from meteorological evidence. A stadium's
`indoor` flag alone never proves a retractable roof closed.

NWS `properties.updateTime` is preserved as the product issuance/update time;
HTTP Date/Last-Modified is not used as publication proof. Certified weather
requires issuance <= retrieval <= event freeze < kickoff. Weather obtained
after kickoff cannot become a newly certified pregame feature. An event
already started at collection is an exclusion receipt, not a weather record.

`VERIFIED_FORECAST` means an original, chronologically valid forecast covers
kickoff and supplies wind, temperature and precipitation probability. It
does not mean every field or stadium exposure is verified. `PARTIAL_FORECAST`
retains other source-supported fields. Missing fields remain null and are
listed; an empty native hazards/weather array means the source explicitly
returned no listed hazards/weather, unlike a missing value.

Wind is normalized to m/s; temperature to Celsius. Accumulated precipitation,
snow and ice become an average mm/hour over the original interval, never an
instantaneous rate. Precipitation type, coverage and intensity remain in
NWS's structured native `weather` records rather than invented numeric
categories. `hazards` and original full responses preserve significant
hazards. `gust_window` retains all overlapping forecast gust intervals for
the first three hours and derives their maximum. Apparent temperature is
source-provided; no unrequested formula replaces missing apparent values.
Deterministic forecasts have no invented confidence intervals. Native
probability/uncertainty products are retained where supplied.

Exposure values follow the requested five-state vocabulary. Retractable
roofs need original game-specific evidence for confirmed closure; absent
evidence yields uncertainty and no fabricated adjustment. Unverified stadium
type yields `EXPOSURE_UNVERIFIED`. Fixed indoor and outdoor classifications
are evidence-based and independent of weather completeness.

## Historical dataset and rollback

No authorized authentic historical forecast-vintage archive has been
identified in the inspected project inventory. Authentic historical training
rows remain zero. NWS observations and retrospective reconstructed weather
are excluded. This does not block today's capture.

Rollback is to stop consuming the new v2 pin/adapter. Keep the archived bytes,
old sources and frozen forecasts. PR #133 remains open and unmerged; no
production schedules, training state, weights or release authority change.
