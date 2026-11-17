# P1 native owner handoff v1

Authority: PA-V25-MASTER-2026-11-09 / v1.1. Status: implemented engineering transport; **independent admission pending; P1 G1 BLOCKED**. This additive contract does not amend accepted G0 at `59d28dc23be97de2a6a82d22be8338151e31f5b6`. It preserves the earlier P1 interfaces and receipts.

`v2.nba_architecture.p1_handoff.VERSION` is `nba-p1-native-handoff/1.0.0`. The exact outputs are closed, distinct shapes. Consumers must validate the kind and schema, bind their actual code/artifact bytes, and independently recompute all source-derived fields. No string, hash, label or caller assertion authenticates an original source. Every v1 export deliberately has `admission_status=BLOCKED`. There is no real-admission registry or route in this contract. An independently accepted future admission protocol requires a separately versioned extension.

## Prior-game exposure for P2/P3/P4

`export_prior_game(data, bundle, *, ingested_at, source_profile='unadmitted_source_reconstruction')` consumes the existing P1 normalized player row and actual `p1_evidence` bundle. It rechecks the complete raw source/ancestor chain, game/player/team/stat identity and actual duration before export. `evidence_bundle` transports `{capture,raw_base64,prior}` recursively. `decode_evidence_bundle` decodes and rechecks every raw digest and ancestor; internal consistency is its entire claim. Raw-byte SHA-256 refers to exact supplied bytes; it is never a canonical parsed-JSON SHA or an independent collector attestation.

`exposure` is the exact existing `nba-p1-prior-game-evidence/1.0.0` result, including separate displayed/exact minutes, participation, counts, duration, OT, raw/receipt hashes and unresolved source status. `game_start_at` comes from those same source bytes. `clocks` keeps provider publication, first defensible availability, collector observation, retrieval, ingestion and outcome availability distinct. The currently unavailable publication/availability/observation/release clocks are null. Retrieval is the actual supplied capture clock. Ingestion must be at or after retrieval. Modern retrieval never becomes original pregame availability.

Role and role evidence remain null because no admitted dated role evidence exists. Attempted/admitted/quarantined denominators are 1/0/1. The only source profiles are `unadmitted_source_reconstruction` and explicitly labeled `synthetic_engineering`; both remain blocked. P2 independently binds this row to its pregame snapshot, declared model cutoff, target-game exclusion, role mapping and source admission. A valid structural transport is never permission for historical fitting.

## Pregame candidate context for P3/P4

`export_pregame_context(*,game_id,team_ids,event_start_at,input_freeze_at,bundles,ingested_at)` consumes the existing source-bound reviewed assertion export. It preserves supplied raw export bytes, hashes, provider URL, origin and source clocks. The hash domain explicitly says `EXACT_SUPPLIED_EXPORT_BYTES_NOT_ORIGINAL_PROVIDER_HTTP`: a custom adapter assertion is not an NBA native HTTP response. Its claimed availability clock is unadmitted. Sources require external independent review.

The output preserves legal eligibility separately from observed availability. Participation probability/authentication, dated membership, role/role evidence and source-bound home identity stay null; role uncertainty is unknown. A subset of candidates has `roster_completeness.status=UNPROVEN`, no completeness proof, the observed candidate count and null complete-population denominator. No export certifies that an empty or partial roster is complete. Consumers must abstain before sampling whenever required authentic context, complete roster, home identity or fitted priors are missing.

## Isolated outcome versions for P5

`export_outcome(vault,game_id,player_id)` requires an explicitly injected isolated vault object. Pregame entrypoints neither import the vault nor open its files. The outcome entrypoint calls the existing full-chain validator, then reads exact immutable outcome JSON/raw source bytes. It exports every revision, exact raw SHA/base64, parent link and complete accounting-source ancestry. No existing record is changed. Missing results are `UNRESOLVED`, with null minutes/count/version and empty statistics/revisions.

Observed time is not official end or release time. `event_start_at` is source-derived only when accounting evidence exists; `event_end_at` and `outcome_released_at` stay null. Displayed and exact minutes remain separate. Participation preserves PLAYED, PLAYED_ZERO_MINUTES, DNP, UNRESOLVED and VOID. `official_count` remains null because the consumer must select its explicit statistic. `scoring_authorized=False`; P5 must preserve missing clocks/source admission and return no-score rather than creating a G0 evaluation object. Forecast ingestion and this outcome access stay physically separate.

## Acceptance and boundaries

Synthetic compatibility must be run separately from the authentic blocked case. Positive tests preserve a legal two-OT exposure, rounded-subminute credits/display, uncertain roster candidates and all outcome correction versions. Negative tests corrupt raw and ancestor bytes, orphan/backdate revisions, change game identities, and place ingestion before retrieval. Complete source admission, original pregame roster/context, dated trade membership, original availability, official schedule/result/DNP/played-zero populations and full official corrections remain external P1 prerequisites. Genuine minute-display exception admission also remains blocked. The official preholdout `0021800001` retrieval attempt returned HTTP 403; exact failed response bytes and current clocks are retained in the versioned evidence directory.

Rollback: revert only the new handoff implementation/tests/documents, preserving all existing owner and G0 source files, old failed receipts and source bytes. No automatic merge, G2, historical fitting/evaluation, deployment, schedule change or Tier promotion is authorized.
