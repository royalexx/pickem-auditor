# Immutable live-pool archive: oversized-bundle recovery

The Deepnote pregame run on 2026-11-08 successfully completed 2,436 full-slate
prop forecasts, generated all 60/40 post-shadow comparisons and passed the
full-forecast audit, but the GitHub archive step failed before publication:
`LIVE_POOL_BUNDLE_TOO_LARGE`. The previous archive writer permitted a single
compressed bundle of at most 8,000,000 bytes. This was a storage failure, **not**
an indication that the predictions were not generated.

## Protocol v1: shard when needed

- Small archives retain the original digest-named `.json.gz` file and old
  readers remain supported.
- When the full deterministic gzip bytes exceed 8 MB, split **those bytes**
  into bounded, immutable, 5,000,000-byte content-addressed blobs under
  `data/live_pool/YYYY-MM-DD/PHASE/parts/`.
- Commit the content-addressed `.manifest.json` only after all parts succeed.
  A partial upload without a manifest cannot appear as a settled archive.
- `iter_remote_docs` recognizes both legacy `.json.gz` and new manifest
  files, reconstructing the original byte stream only after checking
  every shard path, size and SHA-256 and the full payload checksum. Dates,
  phases and source identity remain tied to the manifest.
- Once reconstructed, `restore_forecasts` and `canonical_afternoon_docs`
  see the exact same document and retain the first archived pregame
  cohort by actual capture timestamp. No result-based regeneration is allowed.
- GitHub writes are append-only: retries re-use identical content-addressed
  parts; conflicts that do not match byte-for-byte must fail.

## Recovery on network/archive failure

The live notebook exports `PICKEM_LIVE_ARCHIVE_RECOVERY_DIR` pointing inside
the persistent, per-run `pickem_runs/YYYY-MM-DD/RUN_STAMP/` directory.
Before upload, the exporter stores
`live_pool_YYYY-MM-DD_PHASE_SHA256.json.gz`, containing the ORIGINAL
unmodified full compressed bundle. The writer verifies it on repeated runs.

To retry a failed publication from that retained original file:

```bash
python scripts/live_pool_exchange.py publish-frozen \
  --frozen pickem_runs/YYYY-MM-DD/RUN_STAMP/live_pool_YYYY-MM-DD_afternoon_SHA256.json.gz
```

This command validates the frozen bytes, sha256, date/phase and original
pregame forecast timestamps. It never collects outcomes or re-runs models.

**November 8 limitation:** this protection did not exist in the failed run,
so the existing original pregame source bundle was not exported. Its detailed
model comparisons and sidecar evidence remain in the Deepnote run directory,
but should not be fabricated into full original forecasts.

The standard pipeline's `--phase afternoon` command must not be used as
a post-kickoff substitute for recovering an older source bundle.

## Tests

`tests/test_live_pool_exchange.py` covers manifest round-trip, unchanged
raw forecast/source data, retry/idempotency, interrupted writes with no
discoverable partial bundle, tamper rejection and frozen-file recovery.
The original all-sport forecasting, price comparison and Tier gates are
untouched by this archive-layer repair.
