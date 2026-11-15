# WS1 weather handoff — Sunday November 15, 2026

Research-only Phase 0R source integration under PA-V25-MASTER-2026-11-09 / v1.1. WS1 is the sole weather collector; WS3, WS4 and WS6 consume this pin. No forecast, sportsbook contract, original handoff or historical feature pin was changed.

## Immutable delivery

- Final pin: `reports/nfl_20261115_prospective/weather_v2/revision_2/WEATHER_FEATURE_PIN.json`
- Final pin SHA-256: `a80bc6ad4d5059e8db283516fe6c97587803b17fea2247c33af228d39554ef86`
- Parent pin SHA-256: `273da5a6f5456e99e9b5bd4f2172abce1bf77c7bfbe82d38199886fcad612807`
- Canonical WS1 manifest SHA-256: `5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71`
- Event table SHA-256: `b08383c9d3225159f203377c4c37ddb296881c474e42c2214e8c469fad271bb4`
- Schema: `ws1-nfl-pregame-weather-v2`; migration and offline adapter documented in `docs/NFL_SUNDAY_WEATHER_V2.md`.
- Deepnote source capture run: `7dfe59cf-01cb-42b9-9eae-51515ba59051` (success, free CPU Basic).
- Deepnote final tests, source replay and roof revision run: `ac19bed0-0907-47e5-b257-ee41bcd1f8bf` (success, free CPU Basic).
- Earlier QA attempt `e2a2e455-b176-4c58-a728-f01f480ea83c` failed because the subprocess Python lacked pytest; the successful run installed pytest in ephemeral `/tmp`.

## Coverage

{"already_started": 1, "complete_native_fields": 2, "exposure_unverified": 4, "partial_weather": 0, "retractable_roof_status_unknown": 2, "roof_uncertainty": 4, "total_events": 12, "verified_weather": 11}

Exposure counts for eligible games: {"EXPOSED_OUTDOOR": 5, "EXPOSURE_UNVERIFIED": 4, "RETRACTABLE_ROOF_STATUS_UNKNOWN": 2}.

Verified weather means source issuance and receipt are pregame, validity covers kickoff, and core wind/temperature/precipitation probability are present. It does not imply complete hazards or verified exposure. All 11 games supply wind, gusts, wind direction, temperature, apparent temperature, precipitation probability/amount, snow and ice. Nine native hazard values are missing; two games have all eleven native fields. All missingness remains explicit. Four proposed retractable-roof venues lack original game-specific closure evidence; never apply a fabricated closed-roof adjustment.

NE–DET (`401873053`) had already reached its 14:30 UTC kickoff. It has only an exclusion receipt, no newly constructed pregame weather.

## Source hashes and per-event freezes

All times are UTC, on 2026-11-15 unless stated otherwise. Each source hash below identifies the full original NWS grid response; every coordinate, venue and roof source also has its own hash in the pin.

| Original event ID | Fixture | Kickoff | NWS product issued | Retrieved | Weather freeze | NWS original SHA-256 |
|---|---|---|---|---|---|---|
| 401873053 | 2026-11-15 / NE / DET | 2026-11-15T14:30:00Z | — | — | excluded | — |
| 401873058 | 2026-11-15 / KC / ATL | 2026-11-15T18:00:00Z | 2026-11-15T13:41:44+00:00 | 2026-11-15T15:40:51.687700Z | 2026-11-15T15:40:52.576203Z | 2b5af6d7e0e89698f87abeb3abe56c17e9458db476c08892576608655ceafc4e |
| 401873056 | 2026-11-15 / HOU / CLE | 2026-11-15T18:00:00Z | 2026-11-15T14:46:49+00:00 | 2026-11-15T15:40:59.258975Z | 2026-11-15T15:41:00.189247Z | b8aa1f6efd3a8ba9da839bc5d5a0556a93d95227cd33a97f040b766e12b033e9 |
| 401873060 | 2026-11-15 / MIN / GB | 2026-11-15T18:00:00Z | 2026-11-15T13:36:28+00:00 | 2026-11-15T15:41:06.988904Z | 2026-11-15T15:41:07.819573Z | 208b8550e9e4eda7cd379a72600b9864109e0ba9e9835d8622e5d289204d1e6c |
| 401873059 | 2026-11-15 / MIA / IND | 2026-11-15T18:00:00Z | 2026-11-15T15:15:27+00:00 | 2026-11-15T15:41:16.661083Z | 2026-11-15T15:51:28.866933Z | 624495f58985ecdc4a0a9cbf57c211c6e815f300c7b70781251d9a76c6765204 |
| 401873055 | 2026-11-15 / CAR / NO | 2026-11-15T18:00:00Z | 2026-11-15T13:14:31+00:00 | 2026-11-15T15:41:24.565525Z | 2026-11-15T15:51:32.129857Z | 774d90123a665efb634672fca059886b399c2c28fc76e28cf1f965baa04ebfb9 |
| 401873054 | 2026-11-15 / BUF / NYJ | 2026-11-15T18:00:00Z | 2026-11-15T06:55:12+00:00 | 2026-11-15T15:41:32.721141Z | 2026-11-15T15:41:33.537260Z | a9ecf71638845234bd33ce4f05b693355573e74e80567b690e1a4592a19a4203 |
| 401873057 | 2026-11-15 / JAX / TEN | 2026-11-15T18:00:00Z | 2026-11-15T10:26:33+00:00 | 2026-11-15T15:41:41.467864Z | 2026-11-15T15:41:42.320565Z | a5a0dae28ab24e4e11c808942aa159e244d16026f4393fd50e63e48798f6b256 |
| 401873061 | 2026-11-15 / LAR / ARI | 2026-11-15T21:05:00Z | 2026-11-15T11:02:39+00:00 | 2026-11-15T15:41:49.604916Z | 2026-11-15T15:41:50.555996Z | 7445f90af33f202f40ed4be2ea3ab9e66fbde6dc293d230b6284b1f7ec9f4334 |
| 401873062 | 2026-11-15 / SEA / LV | 2026-11-15T21:05:00Z | 2026-11-15T06:33:06+00:00 | 2026-11-15T15:41:57.828320Z | 2026-11-15T15:51:35.318383Z | fbcfe4219079d0352115bf16d8d3cb70d95f2f15fc6f78d431bfdc7feffd23c1 |
| 401873063 | 2026-11-15 / SF / DAL | 2026-11-15T21:25:00Z | 2026-11-15T11:36:19+00:00 | 2026-11-15T15:42:05.518514Z | 2026-11-15T15:51:38.557329Z | 1e48fd2a3f56225fb00aa9b76ec1d1c2bb1d4d1e6b259b5315a795d99e09a486 |
| 401873064 | 2026-11-15 / PIT / CIN | 2026-11-16T01:20:00Z | 2026-11-15T11:06:24+00:00 | 2026-11-15T15:42:12.955243Z | 2026-11-15T15:42:13.749279Z | 35688705e43abd44f00aeaea99c668e48b1fcf36d6bbd7c33f8ea633b31296be |

## Consumption and limits

Use `load_weather_v2` with the exact final pin hash from the project root. Validate all original dependency and raw-source hashes before using any features. WS3 v1 cannot ingest this schema directly: do not force interval starts to kickoff or fill missing fields to satisfy v1. WS3/WS4 must adopt the separately versioned adapter for new forecasts; already frozen player forecasts remain unchanged. WS6 can audit all rows, including exclusions. Weather-neutral models may continue without this source. No weather-response coefficients are fitted.

The original native validity interval and its start-to-kickoff difference are recorded separately for every field. Precipitation intensity is a source interval average; structured weather type/intensity and hazards remain native. Roof evidence revisions retain prior freezes and set a new pregame freeze only for the added evidence. All forecast issuance/retrieval times are preserved.

No authorized authentic historical weather-vintage training archive was identified in the inspected project inventory. Authentic historical weather training rows: **0**. Observations and reconstructions are excluded. This does not block the prospective delivery.

PR #133 remains draft, open and unmerged. No production authority, schedules, NUTS state or model weights change. Rollback: stop consuming this new pin; retain every archived artifact.
