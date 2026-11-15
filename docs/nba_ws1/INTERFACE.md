# NBA WS1 immutable consumer interface 1.0.0

`v2.nba_ws1` owns `NBAPregameFeatureSnapshot`. This is a source and descriptive-feature interface, not a prediction, minutes model, likelihood, evaluator or market-edge estimator. Consumers in WS2–WS4 import it or write adapters around its JSON. They must not change WS1 internals to impose a model family.

## Public API

```python
from v2.nba_ws1 import Receipt, Record, build_snapshot, NBAPregameFeatureSnapshot

# Retain exact bytes first; the clock must come from the trusted collector.
receipt = Receipt.capture(raw_bytes, source=source_url,
                          observed_at=collector_completed_at,
                          origin="original_capture")
# Use a source adapter to produce validated Record instances.
snapshot = build_snapshot(
    game_id=canonical_game_id,
    forecast_at=forecast_at,
    input_freeze_at=input_freeze_at,
    model_training_cutoff_at=actual_downstream_training_cutoff,
    records=source_adapter_records,
    receipts=source_receipts,
)
serialized = snapshot.to_json()
restored = NBAPregameFeatureSnapshot.from_json(serialized)
# Raises for blocked snapshots. A returned object still has shadow-only status.
inputs = restored.require_usable(required_player_features=["ELIGIBILITY_UNCERTAIN"])
```

Variable names above denote caller-supplied inputs, not fabricated example data. The fully populated, real-source sample is in `sample/`.

The classes are frozen dataclasses with JSON strings for nested data. `Record.data` and `snapshot.to_dict()` return fresh objects; mutating them cannot change the immutable instance. `save_snapshot` uses `<content_hash>.json`, exclusive creation, and exact-byte comparison on reruns. Conflicting existing content raises `IMMUTABLE_SNAPSHOT_CONFLICT`.

## Serialization and hashes

Schema identifier: `nba-pregame-feature-snapshot/1.0.0`. JSON is UTF-8, sorted-key, compact, Unicode-preserving, finite-number-only JSON. `content_hash` is SHA-256 of the canonical object **excluding** `content_hash`; `to_json()` adds the hash and a single terminal newline. Receipt and normalized-record hashes cover their complete metadata, excluding their own hash field. Raw-source SHA-256 covers original uncompressed response bytes. Warehouse v1 `source_sha256` instead hashes canonicalized parsed JSON: these are different hash domains and must not be interchanged.

`from_json` rejects duplicate keys, wrong schema, changed hashes, invalid receipt/record metadata, impossible clocks, removed blocking status, inconsistent ledger denominators and feature vectors that cannot be reconstructed from the accepted normalized records. A newly recomputed outer hash does not authorize editing a feature. Independent raw-source verification and transformations are exercised by the offline sample replay.

A hash is **not** a signature, independent timestamp attestation or proof that a source was truthful. An attacker who controls the collector, normalized data and all receipt clocks can fabricate a consistent hash chain. Trusted ingestion, preserved original bytes and independent source review remain required. `certification` therefore remains `not_independently_certified`; no object in this release claims full data certification.

## Identity and input record types

Every identity is namespaced: `espn:game:401909986`, `espn:player:<id>`, `espn:team:<id>`. Native league IDs would use their own provider namespace. Abbreviations use `espn_abbrev:team:<code>` and **are not** equal to numeric ESPN team IDs. No fuzzy names, jersey matches or silent abbreviation aliases create identity joins.

`resolve_crosswalk` requires one source-backed mapping valid at the requested instant and already observed by that instant; absent, expired, future or overlapping mappings fail. It does not invent mappings or independently authenticate caller-supplied mapping evidence. Effective intervals are `[valid_from, valid_to)`; `null` means no documented end, not perpetual team membership. Historical player-game rows carry their own team/opponent; current membership never overwrites them.

`Record.make` accepts these exact, closed field sets, in addition to a receipt reference, positive revision, optional `supersedes`, and immutable record hash:

| Kind | Data fields |
| --- | --- |
| `schedule` | game_id, home_team_id, away_team_id, event_start_at, venue, status |
| `player_game` | game_id, player_id, team_id, opponent_id, game_date, minutes, participation, starter, stats |
| `team_game` | game_id, team_id, opponent_id, game_date, possessions, pace_per_48, stats, opponent_stats |
| `roster` | game_id, player_id, team_id, status, uncertainty |
| `availability` | game_id, player_id, team_id, status, uncertainty, role, detail |
| `contract` | contract_id, quote_id, game_id, player_id, team_id, stat, period, line, quoted_at, book, prices, payout_terms |
| `game_market` | game_id, team_id, kind, line, quoted_at, book, period |

Unknown fields, including current-game realized possessions or final score attached to a schedule, fail validation. A record of historical outcomes must use a historical kind; the target game's historical records are rejected before any feature is built.

A correction requires an existing parent with the same natural key, a higher revision, an explicit supersession link, and a nondecreasing capture clock. Conflicting unlinked versions block the snapshot. Both accepted historical versions remain in `input_records`; only the latest **available at freeze** enters the vectors. Late corrections cannot rewrite an old snapshot. Historical archive files are never updated by this module.

## Top-level snapshot fields

| Field | Meaning and consumer rule |
| --- | --- |
| schema_version, content_hash | Version and immutable content identity; fail on unsupported version |
| game | Scheduled game identity, venue, teams, start and source-observed schedule status |
| forecast_at, input_freeze_at | UTC instants; equality between freeze and forecast is allowed |
| model_training_cutoff_at | Caller-supplied actual downstream training cutoff; WS1 does not inspect or train a model |
| source_available_at | Maximum defensible availability of selected input sources; never inferred from game start |
| receipts | Source URL/identifier, raw hash, observed clock, availability clock, origin and receipt hash |
| input_records | Accepted normalized inputs, including superseded accepted versions; rejected outcome values are absent |
| players | Stable identities, current source roster evidence, original historical membership, descriptive vectors, availability evidence and missing codes |
| teams | Separate team and opponent identities, home flag, prior team-game vectors, rest, possessions/pace and offensive/defensive profiles |
| market_context | Original contracts, separately stored game markets and explicit quote-age policy |
| future_uncertainty | `overtime: unknown_future_outcome`; never a known target-game period count |
| ledger | Attempted, accepted, rejected, duplicates, superseded and per-rejection record IDs/codes |
| abstention_codes, status, certification | Blocking conditions and source limits; no publication or release authority |

Receipts may include unused discovery-source hashes, but no unused raw future outcomes are serialized. Rejected inputs are represented by immutable record hash, kind and reason. Consumers must never fetch a rejected record and treat it as a model input.

## Units, horizons and null semantics

* All clock fields are timezone-aware UTC, normalized to microseconds. Provider timestamps and ingestion timestamps are separate. `source_available_at` is conservatively at least `observed_at`, even if a source claims an earlier publication time.
* Historical `game_date` is a calendar date. ESPN adapters use America/Toronto. Date-only history on the same UTC date as freeze or capture is conservatively excluded because this interface cannot prove intraday ordering. No guessed final whistle or midnight publication time is created.
* Minutes are actual **historical** decimal minutes. The ESPN adapter preserves zero-minute appearances and long overtime workloads, including values over the old collector's 65-minute limit. DNP/unknown participation requires null minutes and an empty stat map. Missing players never acquire a fabricated zero.
* Supported original market statistics are points, rebounds, assists, threes, steals, blocks, turnovers, PRA, PR, PA and RA. Their historical count values are nonnegative integers. Additional historical fields are FGM, FGA, three-point attempts, FTM, FTA, offensive rebounds, defensive rebounds and personal fouls. Missing fields are absent or null, never zero-filled.
* Recent distributions use the latest five **played appearances**; longer distributions use the latest twenty. DNPs are retained in history and previous-participation indicators but excluded from played-minute distributions. Each distribution exposes ordered raw values, n, mean, median, population standard deviation, minimum and maximum. These are descriptive summaries, not predictive distributions, uncertainty intervals or calibrated minutes forecasts. An empty distribution has n=0, values=[], and null summary numbers.
* Starting-role fields count only explicitly observed starter flags; `starts_observed` is the denominator. Unknown starts are not bench appearances. Previous participation and historical team changes are evidence, not forecasts of tonight's role. Membership changes are not automatically verified trades.
* Team profiles summarize the last twenty available team-games. Defensive values are the same team's prior opponent totals. Possessions are historical possessions per game; pace is historical possessions per 48 minutes. Neither is inferred from incomplete player tables. The supplied ESPN adapter leaves both null. A future source adapter must document whether possessions are official or estimated and preserve its formula/provenance; do not silently mix definitions.
* Rest is the number of intervening Toronto calendar dates after the most recent available team-game, floored at zero. Back-to-back is rest==0. Missing team history gives null rest and null back-to-back, not a rested team assumption. These are calendar measures, not recovery hours.
* FGA/FTA/turnover histories expose usage-related inputs. True usage percentage, touches, lineup stint denominators and rebound/assist opportunities are unavailable in the legacy warehouse; no usage percentage is synthesized.
* Availability uncertainty is one of confirmed, reported, uncertain or unknown. ESPN season rosters yield `membership_only / reported`, never `eligible / confirmed`. Reported injury detail is preserved without a numerical minutes adjustment. Absence from an injury list is not proof of health.
* Market lines retain their original statistic and period. Contract/book/quote IDs are opaque original identities. Prices, when present, are compatible paired **decimal** odds strictly greater than 1. Missing paired prices and payout terms remain null; no default -110, de-vig value, multiplier or executable pick'em return is invented. Period/OT/void semantics belong to the original terms and the consumer's separate settlement policy.
* Quotation time must be no later than source capture and freeze. The default maximum quote age is 900 seconds, recorded in every snapshot and configurable explicitly. Distinct books/lines/quote times remain separate. Duplicate book/contract/time references are rejected even if quote IDs differ.

## Temporal and certification policy

The builder enforces `source_available_at <= input_freeze_at <= forecast_at < event_start_at` and `model_training_cutoff_at <= input_freeze_at`. Same-game outcomes, future dates, post-freeze roster/news, and late prices remain in rejection denominators but cannot enter vectors. Training cutoff validation checks the supplied bound, not the truth of an external model's training manifest; downstream consumers must verify that manifest.

Retrospective retrievals retain `retrospective_retrieval` origin and `RECONSTRUCTED_PROXY_HISTORY`. They are usable as currently retrieved history before a future event, but cannot be relabeled authentic original pregame captures for a past replay. In particular, a retrieval today cannot serve a November 10 freeze. Valid chronology alone does not establish an authenticated prospective forecast.

Snapshot status is blocked if any global blocking code exists; otherwise it is shadow_only. Missing player/team fields remain separately enumerated. Consumers must call `require_usable`, enforce their additional required-feature codes and review uncertainty. This version never grants trusted publication, Tier status, forecast skill or economic-edge certification.
