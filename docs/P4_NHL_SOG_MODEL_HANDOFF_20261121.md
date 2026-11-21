# P4 NHL SOG V2.5 — modeling artifact handoff (2026-11-21)

**Scope:** P4 source-consuming, research-only Poisson / Gamma–Poisson / fixed-shape native NB2. No P2 acquisition code, P0 schemas, NBA/NFL, production selection, tier policy, automation or C10 registration changed.

## Reconciled source state

- Repository base: `main` `912bc7010058092ea735dcda0aa941429194474b` (checked 2026-11-21); branch `chatgpt/p4-nhl-sog-model-artifacts-20261121`.
- Original Gamma source model: `v2/nhl_sog_exposure_shadow.py`; experiment `EXP-V25-NHL-SOG-EXPOSURE-EB-001`; exact 60-minute equivalent rate prior, 3-game exposure shrinkage, 5 own played games, 20 distinct peers, 200 played peer games, 20/10 history windows. **Not modified.**
- Original prospective source verifier and model/snapshot generator: `v2/nhl_sog_prospective_runner.py`; original signed history verifier: `v2/nhl_sog_official_history_producer.py`; roster/quote validators reused unchanged.
- Locked native NB2: `v2/nhl_sog_nb2_source_native.py`; preregistration `config/experiment_specs/EXP_V25_NHL_SOG_NB2_NATIVE_PLUGIN_MEAN_20261114.json`; exact mean `model.plugin_rate * model.plugin_exposure`; exact shape `r=4`, existing 40-date protocol. **Not modified.**
- Existing source-generated original Gamma daily manifest format: `v25_daily_original_sog_gamma_poisson_research_generator_v1`; native verifier admits only properly pregame signed original attempts from that manifest.
- Deepnote November 20 native audit: `NO_ORIGINAL_GAMMA_GENERATOR_YET`, zero original source batches.
- Deepnote November 18 Gamma manifest: 167 original two-sided offer rows, zero new frozen forecasts, 166 insufficient signed history *failure occurrences* and 1 missing provider native-ID *occurrence*. Not unique players. No restored/backdated forecast.
- Earlier November 13 manifest demonstrated two original frozen Gamma attempts in one run, but **historical** original receipts are not new November 21 prospective evidence.

## Added files and contracts

1. `v2/nhl_sog_p4_forecasts.py`: source bundle adapter; exact existing Gamma fit; complete Poisson, fixed-TOI Gamma, exposure-mixture Poisson, exposure-mixture Gamma distributions; synthetic-only analytic NB2 mathematical fixture; immutable writer and reader; authenticated existing Gamma runner integration; exact locked native runner invocation; adaptive-only version update; P5 read-only scoring payload.
2. `scripts/p4_nhl_sog_generate.py`: manually invoked only. Modes `synthetic`, `distribution`, `original`, `native`. Never schedule without independent authorization.
3. `scripts/p4_nhl_sog_make_fixture.py`: explicit synthetic signed-like structured-byte *fixture*, never an original signed source.
4. `tests/test_nhl_sog_p4_forecasts.py`: 16 locally defined unit tests of mathematical, temporal, DNP, source SHA, quote/line, immutable, adaptive and cohort invariants. **Repository tests have not run successfully in Deepnote yet.**
5. This handoff.

**New P2 data shape** `v25_nhl_sog_p4_p2_source_bundle_v1` is a P4 adapter, **not** a change to P0's authoritative schema. Required fields:

```json
{
  "schema": "v25_nhl_sog_p4_p2_source_bundle_v1",
  "source_classification": "original_signed",
  "event_id": "real-original-event-id",
  "player_id": "original-nhl-player-id",
  "team_id": "verified-current-team",
  "opponent_id": "verified-opponent",
  "position_group": "F",
  "event_start_at": "original UTC scheduled start",
  "input_freeze_at": "original UTC freeze",
  "historical_availability_cutoff_at": "original historical source cutoff",
  "source_manifest_path": "P2 signed original manifest relative path",
  "source_manifest_sha256": "exact original bytes SHA-256",
  "official_roster_receipts": {},
  "own_official_history": [],
  "peer_official_history": [],
  "flags": {}
}
```

The object above documents field names, not a usable source packet. Identity, signed observations, roster, original manifest and chronology must all verify against existing P2 evidence. The exact original two-sided quote route instead uses the existing `v25_sog_prospective_input_v1` bundle, augmented only with `p4_source_manifest_path` and `p4_source_manifest_sha256`.

## Registered comparisons

`plugin_poisson` = historical own played-game SOG/TOI rate times median own historical TOI of five games. It is not a new mean fit.

`fixed_exposure_gamma_poisson` uses the registered Gamma shape/rate posterior at that historical point TOI.

`mixture_exposure_plugin_poisson` integrates plugin Poisson counts over the registered smoothed 0.5-minute exposure PMF.

`full_gamma_poisson_exposure` integrates the Gamma posterior predictive over the same exposure PMF.

`nb2_fixed_shape4` with the original plugin-Poisson mean is **not emitted as a registered original forecast** by the generic P4 writer. The only genuine native NB2 entrypoint is the existing `run_day` via `run_registered_native_nb2_if_original_manifest_exists`, which independently checks full original signed history, original Gamma model/snapshot, original offer, live clock and exact first-attempt cohort. Synthetic NB2 examples must stay `synthetic` with no registered experiment ID.

## Full predictive distribution and P5 interface

`freeze_forecast(...)` writes exclusively created `p4_nhl_sog/forecasts/<forecast_id>.json` files; no overwrite and no duplicate-identity changes. `read_immutable(root, receipt)` checks exact byte SHA before returning a record. One record contains:

- source and model lineage (SHA, event, player, team/opponent, code commit, original freeze, forecast and training cutoff);
- model family/version and source-classification/cohort;
- `distribution.pmf_from_zero` over count 0..K and `unallocated_upper_tail_mass <= 1e-12` without renormalizing the tail; original mathematical parameters for analytic extrapolation; mean, variance, quantiles, zero probability, numerical diagnostics;
- `original_quote` with verified quote identity and exact three-way probabilities **only** when the original quote verifier succeeded;
- `participation_condition = conditional_on_played`, `dnp_probability = null`, external void settlement semantics, `research_only=true` and no Tier/production promotion.

P5 calls `p5_scoring_packet(root, forecast_receipt)` to obtain a verified read-only distribution and grouping fields. P5 must independently load official outcome/settlement proofs and score only verified played games; DNP/scratched/unverified/void are excluded from full-count scoring, *not* recoded to zero. A verified played zero is 0. Push and void are distinct; an integer line can push. Related same player/game contracts cannot count as independent games.

**Important storage integration limit:** P4's content-addressed files and scoring packet are a staging interface, not proof that the existing canonical P0/P5 daily ledger has been successfully ingested. Original quote-qualified Gamma also continues to emit the existing P0 `ForecastSnapshot` through `forecast_for_approved_quote`. The canonical consumer join must be verified by P5 before operational acceptance.

## Track A versus Track B

**Track A locked:** original Gamma exposure posterior, original plugin-Poisson and native NB2 shape 4, C10 preregistered horizon, quote cohort and all interim no-promotion rules. Not updated from interim results. Shape cannot be retuned. Old pooled-peer Phase 1.5 NB2 untouched.

**Track B adaptive challenger:** `propose_adaptive_update` adds finalized *played* SOG to posterior Gamma shape and valid TOI to rate, requires chronologically available observations, rejects DNP/duplicates, saves new version with parent state SHA and training-data SHA via `freeze_adaptive_update`. Earlier artifact remains recoverable on failure. This is research-only; P5 must separately authenticate underlying official finalized observation receipts before admitting a real adaptive update. **No claim that a bare SHA field proves original signed source authenticity.** The adaptive output must never carry a locked experiment ID.

## Manual execution examples

```sh
python -m scripts.p4_nhl_sog_make_fixture --root /tmp/p4_sog
python -m scripts.p4_nhl_sog_generate --mode synthetic \
    --input /tmp/p4_sog/synthetic_nhl_sog_p4_bundle.json \
    --source-root /tmp/p4_sog --artifact-root /tmp/p4_sog/out \
    --code-commit <actual-reviewed-40-character-commit-SHA>

python -m unittest -v tests.test_nhl_sog_p4_forecasts

# Requires original P2 signed quote/historical data, NOT the fixture:
python -m scripts.p4_nhl_sog_generate --mode original \
    --input <genuine_p2_original_bundle.json> \
    --source-root <p2_original_archive_root> \
    --artifact-root <dedicated_p4_root> \
    --code-commit <actual-reviewed-40-character-commit-SHA>

# Registered native NB2, no re-fitting and no date override:
python -m scripts.p4_nhl_sog_generate --mode native \
    --source-root <existing_project_root> \
    --code-commit <actual-reviewed-40-character-commit-SHA>
```

The sample commands contain path/SHA parameters to be filled with actual current receipts. Never use test fixtures for original certification.

## Verification and remaining gates

- Independent local SciPy analytical reference, 2026-11-21: Poisson, Gamma–Poisson and NB2 pmf values, means, variances, normalization, zero probability, integer push and half-line three-way complementarity agree to approx 4e-16 maximum absolute PMF error. This **does not execute the new GitHub pipeline**.
- Test suite authored and uploaded to Deepnote, but detached run launch received the concrete error `Team Trial limit of 5 parallel running projects`. Existing project machine was `stopped`; do not stop other parallel work to claim an artificial run.
- **No actual P4 code integration run, no code-level PASS, no new source-certified November 21 pregame canary, and no Deepnote P4 numerical receipt yet**. Runtime gates remain BLOCKED, not PASS.
- Original P2 signed history, genuine quote, original model generator and strict live timing remain explicit source gates. No postgame retro-certification.
- Follow-up: execute new tests on free Deepnote CPU or local machine; run real original-source forecast once P2 provides a complete genuinely pregame bundle; reverify native NB2 via its original daily manifest; compare exact matched controls before any C10 scoring, and independently validate P0 ledger ingest.

## Release and rollback

Draft PR only, no merge. Tests and separate mathematical/security review required before engineering acceptance. To roll back, stop invoking `scripts/p4_nhl_sog_generate.py` and revert only its branch commit(s) through a review. Existing collectors, historical frozen forecasts, settlements, P0/P2 schemas, C10 study, production rankings, NUTS pause and automations require no rollback because none was changed. Preserve all append-only research receipts and abstentions even if the P4 adapter is withdrawn.
