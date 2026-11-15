# NFL Sunday 2026-11-15 — Workstream 1 Source-Control Handoff

**Research-only. No production changes, Tier certification, automatic model promotion or payout claims.**

## Status and source snapshot

- Source owner: WS1 only. Target timezone America/Toronto, date Sunday 2026-11-15 (NFL Week 10).
- Verified main at inspection: 912bc7010058092ea735dcda0aa941429194474b.
- Isolated branch: chatgpt/nfl-sunday-ws1-source-20261115.
- Successful source capture Deepnote notebook 6ea975e8b111442d8aca8e103c98e133, run cd6e5a7d-bf05-490a-beb2-d0c2c3a3876e, Basic CPU.
- Original code SHA at live capture: 9c8dcea17365575337b0ab063c34e3f30e51baee.
- Initial tests: 32/32 adversarial assertions passing (the preceding aborted 31/32 fixture-only run did not fetch a source).
- 12/12 original NFL Sunday fixtures verified via ESPN against published schedule.
- First original source observations: 1,845 authentic paired Over/Under book quote records, with raw provider HTTP bytes separately archived. Exact stat split: receiving yards 584; receptions 568; rushing yards 249; tackles + assists 114; rushing attempts 98; passing yards 96; passing attempts 69; completions 67.
- Initial source-certified count: 0/1,845 due blank per-player team fields in the PropLine quote normalization. The original provider team pair and event ID survived; original source and ESPN raw bytes survived. 24 separate ESPN injury endpoint fetches failed; do not reinterpret missing injuries as healthy/active.
- Original immutable manifest: reports/nfl_20261115_prospective/source_control/captures/20ed83fd40787cccc38a242a8698f0a4e09aaaa54f261b923c8a5f4aa232ed10.json
- Original full manifest file SHA-256: 9a7752e70db7c1d56226847df56f7985c1dd4fba79ae6c3b49acc9e7aad6c150.
- Original canonical-object SHA-256: 20ed83fd40787cccc38a242a8698f0a4e09aaaa54f261b923c8a5f4aa232ed10.
- Raw unmodified response body bytes are under source_control/raw/[content_sha256].bin, each linked by exact original receipt, observed retrieval timestamp and hash.
- Provider Last-Modified and quoted market time are not retro-certified upstream publication evidence. HTTP possession establishes only possession.
- Original capture must never be overwritten. Parser repairs must produce a new SHA-addressed artifact with a reference to the original and demonstrate zero new provider requests.

## Exact kickoff windows

Source: https://www.nfl.com/schedules/2026/by-week/week-10

- 09:30 ET: NE at DET, international game in Munich.
- 13:00 ET: KC at ATL; HOU at CLE; MIN at GB; MIA at IND; CAR at NO; BUF at NYJ; JAX at TEN.
- 16:05 ET: LAR at ARI; SEA at LV.
- 16:25 ET: SF at DAL.
- 20:20 ET: PIT at CIN.

Enforce source_received_at <= input_freeze_at <= forecast_at < event_start_at for each individual event. A late collection cannot forecast a game already started. Reschedules require new authenticated source evidence, not a silent fixture alteration.

## Repair and strict provenance

The initial quote records have a two-team event pair but no player team. The approved parser repair joins a player to a team **only when independently captured ESPN roster bytes identify a unique same-named, uniquely ID'd player on exactly one of the two original provider event teams**. It must reject no matches, both teams matching, duplicate player identities, event mismatches and conflicting source clocks. The original quote remains byte-identical and the resolved identity records an independent-source basis.

The ESPN depthcharts source uses the ordered qb position array; the first element is an **expected QB**, not a verified game-day participant. Conflicting QB1 evidence requires abstention. Never use actual game-day snaps or final outcomes. Missing injury reports and missing product-specific void rules must remain explicit evidence gaps.

Run a no-network repair from only the above archived sources using scripts/nfl_sunday_rebind.py with --archive-root, --original-manifest and --code-sha. It checks the exact bytes and SHA of all archived sources before rebuilding any identity. It preserves the original frozen input clock and all original quote observations. **No new source provider request is made in this repair.**

The NHL/NFL C03 v2 context cohort library is present on main, but in scripts/jobs.py the dedicated C03 source-cohort path requires explicit PICKEM_C03_V2_SHADOW=1 plus existing certified-mode gating. A merged module is not proof the real context collector is enabled; C03 cohort B requires signed TLS source capture and the independent strict validator. This WS1 capture is not a C03 integrated run. Fail closed, not “fixed by import”.

Three-component tackle accounting remains exactly: def_tackles_solo + def_tackles_with_assist + def_tackle_assists. Missing any is unavailable. The original sportsbook's precise settlement equivalence remains separate and must be verified before outcome certification.

## Supported original offers and explicit gaps

The existing PropLine provider requests eight NFL player-stat markets: receptions, receiving yards, rushing yards, passing yards, passing attempts, completions, rushing attempts, tackles + assists. Each exact original offer retains provider event ID, ESPN game/player IDs where independently resolved, book, line, BOTH prices, period, source timestamp and receipt SHA. Multiple books or different lines for one player/stat are different candidates, not a single averaged prop. A modeled distribution without an offered line must never be labeled an offered contract.

Targets, solo tackles, tackle assists, passing/rushing/receiving/offensive touchdowns and other binary markets are unsupported by the current live original-offer request. They remain UNAVAILABLE; they are not zero-quote “lines”, are not silently synthesized, and may only enter a future isolated research-only universe after authentic source/settlement receipts. Touchdown markets remain excluded from the trusted production board.

## Artifact ownership and model contract

Root: reports/nfl_20261115_prospective/

- source_control/ — owned solely by WS1. Immutable quote/raw response archives and content-hashed source-control manifests.
- simple_models/ — Workstream 2 only.
- opportunity_models/ — Workstream 3 only.
- joint_models/ — Workstream 4 only.
- independent_validation/ — independent reviewer only.

Workstreams 2, 3 and 4 must consume **the same explicitly pinned source manifest path and file SHA**. No glob/latest selection, competing original quote requests, duplicate Deepnote source captures or cross-workstream file writes. They must not rerun fetch_slate.py, jobs.py snapshot, PropLineProvider, or nfl_sunday_capture.py.

Every downstream row must preserve these exact source identities: candidate_id, event_id, player_id, quote_id, book, stat, period, line, source_sha256, event_start_at, input_freeze_at, and source_manifest_file_sha256. It must add model_id, model_version, model_training_cutoff_at, forecast_at, model artifact SHA, three-way probability masses (over/under/push), abstention reason and research-only status. Strict source/role/quote/time gates may exclude outputs; preserve those exclusions in denominators.

Independent validator: scripts/nfl_sunday_handoff.py. Run it against the exact pinned source-manifest and WS2/3/4 JSONL results using --source-manifest, --workstream, --output-jsonl, --audit-out. It emits a SHA-addressed/immutable adversarial audit receipt. It rejects mismatched contract fields, source fingerprint, duplicate outputs, unavailable model lineage, post-freeze trained models and forecasts after kickoff. Distinguish unconditional predictive masses from conditional-on-no-push selected-side probabilities.

## Frozen production control

Do **not** recompute any legacy forecasts: Engine A, Engine B, Bayesian A/B, independently eligible strict NUTS, the existing 60/40 control and market comparator. A missing originally frozen exact-quote probability remains NOT_ORIGINALLY_FROZEN/UNAVAILABLE (null), not copied from a past slate or another quote line. Only separately verifiable source-and-model-frozen outputs can be joined by exact identity. This WS1 branch does not train or reweight models and must not change production tier/ranking settings.

## Manual Basic CPU launch, no automation assumption

In the authenticated connected Deepnote Basic CPU checkout at the exact code commit:

    PICKEM_ODDS_QUOTA_GUARD=1 PICKEM_PRODUCTION_CONSENSUS=0 PICKEM_PHASE0_CERTIFIED_ONLY=0 python scripts/nfl_sunday_capture.py --date 2026-11-15 --out-root reports/nfl_20261115_prospective --code-sha <actual_commit_sha>

This uses one quota-guarded NFL bulk original-offer fetch; run **only through WS1**, never concurrently with the normal daily afternoon notebook or other Deepnote jobs. The source-control lock denies simultaneous capture in the same root. Do not use GitHub Actions training, paid services or the Dell.

One dedicated Sunday pregame capture may be scheduled ahead of 09:30 a.m. ET, with a pinned notebook/code SHA, provided it does not conflict with the enabled 06:00 morning settlement or afternoon NHL captures. The disabled standard afternoon-slate automation must remain disabled. If a safe one-shot cannot be established, label the future run UNARMED and use the above manual command. Research source preservation is not evidence of validated models, live executable prices, payout-compatible edges, or Tier authorization.
