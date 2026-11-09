# Phase 0 — Source provenance and research-only release guard (November 9, 2026)

## Scope and invariants

Phase 0 is a safety/data foundation, **not a replacement trained model**. The
preexisting production numerical baseline remains
`production-historical-ensemble-60-40-20261108-v1`, unchanged for measurement.
It has `empirically_calibrated=false`, and it may not certify Tier 1/2
realized hit rates. Do not overwrite old forecasts, rebuild old market quotes,
modify historical settlement, or restart paused NUTS work. The morning
settlement pathway and original per-model comparison chart stay intact.

## Implemented

- `scripts/phase0_policy.py` suspends Tier 1 and Tier 2 **publication**
  for the uncalibrated pre-V2 model family in real CLI/workflow release
  contexts. It does not overwrite legacy numerical ranks, historical
  probabilities, or Tier 3 research. `pick_verification.py` emits an
  explicit blocked receipt, and `verified_board.py` independently
  applies the same gate even to older attested decisions.
- `point_in_time_provenance.pregame_snapshot_status` validates contract
  identity, local game date, pre-event forecast clock, pre-forecast model
  training cutoff, correctly matched market line and book timestamps,
  declared source inventory, and on-disk SHA-256 source bytes. It does
  not use settlement or actual stats. Missing metadata or source bytes
  fail closed. It **does not prove independently** that a provider's
  self-reported publication timestamp is true.
- `scripts/phase0_preflight.py` audits exactly the latest frozen run on
  the requested slate date, counts all uncertified rows and reasons,
  identifies duplicated contract keys, records the source snapshot byte
  digest, and emits **publication_eligible=false** even when every source
  receipt is internally valid.
- `market_odds_archive.py` already archives the two-sided real-bookmaker
  quotes from existing provider collection with no new API requests. New
  records additionally preserve quote capture time, sanitized source host,
  source URL fingerprint, and an explicit warning that market
  `last_update` can fall back to collector time. Raw API URL query strings
  are not included in the normalized immutable archive. Source-less,
  unsafe URLs are excluded.
- `.github/workflows/pickem-daily.yml` runs the read-only preflight after
  afternoon snapshots and includes its report in the daily artifact.
- `live_pool_exchange.bundle` includes unmodified, SHA-validated
  normalized same-day market-quote archive snapshots and the matching
  Phase 0 preflight report in the immutable Deepnote afternoon source
  packet. This supplements the existing original source quotes/slate/meta.

## Current limitations and fail-closed conditions

Most older forecasts have no complete `source_receipts` manifest, no
independently saved bytes for each model feature, or no explicit
`model_training_cutoff_at`. They will read **uncertified**. A source
checksum is not independent proof of when the provider published it.
No retrospective data can create authentic old pregame source bytes.

A real-markets prospective validation set will accumulate only when
predictions, source receipts, market quotes, and subsequently settled
outcomes are all recorded at the proper times. Even complete pregame
receipt certification does not imply probability calibration or profit.

Only the two high-confidence tiers are suspended in the publication
pipeline; historical internal scores, research rankings, and settlement
remain available and retain their original model identities.

## Regression commands

```bash
python -m unittest discover -s tests -p 'test_phase0_provenance_release.py' -v
python -m unittest discover -s tests -p 'test_market_odds_archive.py' -v
python -m unittest discover -s tests -p 'test_live_pool_exchange.py' -v
python -m unittest discover -s tests -p 'test_point_in_time_provenance.py' -v
python -m unittest discover -s tests -q
```

The broad suite requires the external `zstd` executable for
`tests/test_history_bootstrap.py`; a machine without it must report
that dependency as unavailable, **not** claim those cases passed.

## Next requirements

- Produce and preserve original provider source bytes/receipts and
  training-cutoff evidence before future forecasts; do not fabricate.
- Run the actual afternoon Deepnote snapshot path with Phase 0 archival
  hooks enabled. Confirm the immutable source packet has the quote archive
  and preflight report before claiming operational adoption.
- Accumulate enough independent, matched real-bookmaker quote/date
  cohorts for walk-forward calibration and safe champion/challenger
  decisions. Keep the old model as a baseline until then.
